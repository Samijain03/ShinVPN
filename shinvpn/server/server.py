"""
ShinVPN High-Performance Server Daemon
======================================
Delusional Club Industries Asynchronous Multi-Client VPN Server.
Supports both UDP datagram tunneling and Stealth WebSocket transport.
"""

from __future__ import annotations
import asyncio
import base64
import logging
import platform
import socket
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable

from ..crypto.keys import KeyPair, load_public_key
from ..crypto.handshake import HandshakeState, HandshakeRole
from ..crypto.cipher import ShinCipher
from ..protocol.constants import (
    MSG_HANDSHAKE_INIT,
    MSG_HANDSHAKE_RESP,
    MSG_DATA_PACKET,
    MSG_KEEPALIVE,
    MSG_REKEY_INIT,
    MSG_REKEY_RESP,
    MSG_DISCONNECT,
    MSG_PROXY_CONNECT,
    MSG_PROXY_DATA,
    MSG_PROXY_CLOSE,
    MSG_SPEEDTEST_REQ,
    MSG_SPEEDTEST_DATA,
)
from ..protocol.frames import (
    parse_frame,
    ShinFrame,
    HandshakeRespFrame,
    DataPacketFrame,
    KeepAliveFrame,
    ProxyDataFrame,
    ProxyCloseFrame,
    SpeedtestReqFrame,
    SpeedtestDataFrame,
)
from ..transport.udp_transport import create_udp_server, UDPServerProtocol
from ..transport.stealth_transport import StealthWSServer
from ..tunnel.linux_tun import LinuxTunAdapter
from .config import ServerConfig
from .ip_pool import IPPool

logger = logging.getLogger("shinvpn.server")


@dataclass
class ClientSession:
    session_id: int
    client_pub_b64: str
    client_addr: Tuple[str, int]
    virtual_ip: str
    tx_cipher: ShinCipher
    rx_cipher: ShinCipher
    transport_type: str  # "udp" or "stealth"
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    bytes_tx: int = 0
    bytes_rx: int = 0
    send_cb: Optional[Callable[[bytes], asyncio.Future]] = None
    # For user-space proxy routing: conn_id -> (reader, writer)
    proxy_streams: Dict[int, Tuple[asyncio.StreamReader, asyncio.StreamWriter]] = field(default_factory=dict)
    proxy_pending_buffers: Dict[int, bytearray] = field(default_factory=dict)
    proxy_connecting: Set[int] = field(default_factory=set)


class ShinVPNServer:
    """The core ShinVPN multi-client server engine."""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.keypair = KeyPair.from_private_b64(config.private_key)
        self.ip_pool = IPPool(config.virtual_subnet, config.server_virtual_ip)
        
        # Sessions
        self.sessions_by_id: Dict[int, ClientSession] = {}
        self.sessions_by_addr: Dict[Tuple[str, int], ClientSession] = {}
        self.sessions_by_vip: Dict[str, ClientSession] = {}

        # Allowed peer public keys in raw bytes
        self.allowed_pub_keys: Dict[bytes, str] = {}
        for p in config.allowed_peers:
            try:
                raw_k = base64.b64decode(p.public_key.strip())
                self.allowed_pub_keys[raw_k] = p.name
            except Exception:
                pass

        # Transports
        self.udp_transport: Optional[asyncio.DatagramTransport] = None
        self.udp_protocol: Optional[UDPServerProtocol] = None
        self.stealth_server: Optional[StealthWSServer] = None
        self.tun_adapter: Optional[LinuxTunAdapter] = None

        self.start_time: float = 0.0
        self.is_running: bool = False
        self._janitor_task: Optional[asyncio.Task] = None

    def authorize_peer(self, public_key_b64: str, name: str = "Authorized Peer") -> None:
        """Dynamically authorizes a client public key in memory."""
        try:
            raw_k = base64.b64decode(public_key_b64.strip())
            self.allowed_pub_keys[raw_k] = name
            logger.info(f"Dynamically authorized peer '{name}' ({public_key_b64[:12]}...)")
        except Exception as e:
            logger.warning(f"Failed to authorize peer: {e}")

    async def start(self) -> None:
        """Starts the ShinVPN server daemon."""
        self.is_running = True
        self.start_time = time.time()
        logger.info("Initializing ShinVPN Server (Delusional Club Industries)...")
        logger.info(f"Server Public Key: {self.keypair.public_b64}")

        # 1. Initialize OS TUN if on Linux
        if platform.system() == "Linux":
            self.tun_adapter = LinuxTunAdapter(dev_name="shin0", mtu=self.config.mtu)
            if self.tun_adapter.open():
                self.tun_adapter.configure_ip(self.config.server_virtual_ip)

        # 2. Start UDP Transport
        self.udp_transport, self.udp_protocol = await create_udp_server(
            self.config.listen_host,
            self.config.udp_port,
            self._handle_udp_packet,
        )
        logger.info(f"UDP Transport active on {self.config.listen_host}:{self.config.udp_port}")

        # 3. Start Stealth Transport if enabled
        if self.config.enable_stealth:
            self.stealth_server = StealthWSServer(
                self.config.listen_host,
                self.config.stealth_port,
                self._handle_stealth_packet,
                self._handle_stealth_disconnect,
            )
            await self.stealth_server.start()

        # 4. Start cleanup janitor
        self._janitor_task = asyncio.create_task(self._session_janitor())
        logger.info("ShinVPN Server Daemon is fully ONLINE and awaiting peers.")

    def _handle_udp_packet(self, raw_data: bytes, addr: Tuple[str, int]) -> None:
        """Dispatches inbound UDP packet."""
        asyncio.create_task(self._process_inbound_packet(raw_data, addr, "udp", None))

    def _handle_stealth_packet(
        self, raw_data: bytes, addr: Tuple[str, int], send_cb: Callable[[bytes], asyncio.Future]
    ) -> None:
        """Dispatches inbound Stealth WebSocket packet."""
        asyncio.create_task(self._process_inbound_packet(raw_data, addr, "stealth", send_cb))

    def _handle_stealth_disconnect(self, addr: Tuple[str, int]) -> None:
        sess = self.sessions_by_addr.pop(addr, None)
        if sess:
            self._close_session(sess)

    async def _process_inbound_packet(
        self,
        raw_data: bytes,
        addr: Tuple[str, int],
        transport_type: str,
        send_cb: Optional[Callable[[bytes], asyncio.Future]],
    ) -> None:
        try:
            frame = parse_frame(raw_data)
        except Exception as e:
            logger.debug(f"Invalid frame from {addr}: {e}")
            return

        if frame.msg_type == MSG_HANDSHAKE_INIT:
            await self._handle_handshake_init(frame, addr, transport_type, send_cb)
            return

        # Lookup active session
        session = self.sessions_by_id.get(frame.session_id)
        if not session:
            logger.debug(f"Received frame for unknown session {frame.session_id} from {addr}")
            return

        session.last_seen = time.time()
        session.bytes_rx += len(raw_data)

        if frame.msg_type == MSG_KEEPALIVE:
            # Echo keepalive with sequence
            resp = KeepAliveFrame(session_id=session.session_id, seq_num=frame.seq_num)
            await self._send_to_client(session, resp.to_bytes())

        elif frame.msg_type == MSG_DATA_PACKET:
            await self._handle_data_packet(session, frame)

        elif frame.msg_type in (MSG_PROXY_CONNECT, MSG_PROXY_DATA, MSG_PROXY_CLOSE):
            await self._handle_proxy_frame(session, frame)

        elif frame.msg_type == MSG_SPEEDTEST_REQ:
            await self._handle_speedtest_req(session, frame)

        elif frame.msg_type == MSG_SPEEDTEST_DATA:
            # Client upload test packet received
            pass

        elif frame.msg_type == MSG_DISCONNECT:
            logger.info(f"Client session {session.session_id} sent graceful disconnect")
            self._close_session(session)

    async def _handle_speedtest_req(self, session: ClientSession, frame: ShinFrame) -> None:
        """Streams burst of dummy data chunks to client for downlink speed benchmarking."""
        try:
            plaintext = session.rx_cipher.decrypt(frame.seq_num, frame.payload)
            probe_id, chunk_count, chunk_size = struct.unpack("!III", plaintext[:12])
            chunk_size = min(chunk_size, 1300)  # Safe MTU boundary
            chunk_count = min(chunk_count, 500)
            dummy_block = b"X" * (chunk_size - 8)

            for i in range(chunk_count):
                payload_raw = struct.pack("!II", probe_id, i) + dummy_block
                seq, ciphertext = session.tx_cipher.encrypt(payload_raw)
                st_frame = ShinFrame(session_id=session.session_id, seq_num=seq, payload=ciphertext)
                st_frame.msg_type = MSG_SPEEDTEST_DATA
                await self._send_to_client(session, st_frame.to_bytes())
                if i % 20 == 0:
                    await asyncio.sleep(0.001)  # Micro-yield to prevent socket congestion
        except Exception as e:
            logger.debug(f"Speedtest req handling error: {e}")

    async def _handle_handshake_init(
        self,
        frame: ShinFrame,
        addr: Tuple[str, int],
        transport_type: str,
        send_cb: Optional[Callable[[bytes], asyncio.Future]],
    ) -> None:
        try:
            hs = HandshakeState(role=HandshakeRole.RESPONDER, static_keypair=self.keypair)
            
            allowed_list = list(self.allowed_pub_keys.keys()) if self.allowed_pub_keys else None
            client_static_pub, client_eph_pub = hs.process_initiation(frame.payload, allowed_list)
            
            client_pub_b64 = base64.b64encode(client_static_pub).decode('ascii')
            peer_name = self.allowed_pub_keys.get(client_static_pub, "Guest Client")
            logger.info(f"Authenticated peer '{peer_name}' ({client_pub_b64[:12]}...) from {addr}")

            # Allocate Virtual IP
            vip = self.ip_pool.allocate(hs.session_id)
            resp_payload = hs.create_response(vip)
            resp_frame = HandshakeRespFrame(session_id=hs.session_id, seq_num=1, payload=resp_payload)

            # Register session
            session = ClientSession(
                session_id=hs.session_id,
                client_pub_b64=client_pub_b64,
                client_addr=addr,
                virtual_ip=vip,
                tx_cipher=hs.tx_cipher,
                rx_cipher=hs.rx_cipher,
                transport_type=transport_type,
                send_cb=send_cb,
            )
            self.sessions_by_id[session.session_id] = session
            self.sessions_by_addr[addr] = session
            self.sessions_by_vip[vip] = session

            # Send response
            raw_resp = resp_frame.to_bytes()
            if transport_type == "udp":
                self.udp_protocol.send_to(raw_resp, addr)
            elif send_cb:
                await send_cb(raw_resp)

            logger.info(f"Handshake complete. Session {session.session_id} assigned VIP {vip}")
        except Exception as e:
            logger.warning(f"Handshake failed from {addr}: {e}")

    async def _handle_data_packet(self, session: ClientSession, frame: ShinFrame) -> None:
        """Decrypts payload from client and routes to TUN device or internet."""
        try:
            plaintext = session.rx_cipher.decrypt(frame.seq_num, frame.payload)
            if self.tun_adapter and self.tun_adapter.is_open:
                self.tun_adapter.write_packet(plaintext)
        except Exception as e:
            logger.debug(f"Data packet decryption failure for session {session.session_id}: {e}")

    async def _handle_proxy_frame(self, session: ClientSession, frame: ShinFrame) -> None:
        """Handles user-space multiplexed TCP connections from client."""
        try:
            decrypted_payload = session.rx_cipher.decrypt(frame.seq_num, frame.payload)
        except Exception as e:
            logger.debug(f"Proxy frame decrypt error: {e}")
            return

        if frame.msg_type == MSG_PROXY_CONNECT:
            # Format: conn_id (4B), port (2B), host_len (2B), host_bytes
            conn_id, port, host_len = struct.unpack("!IHH", decrypted_payload[:8])
            host = decrypted_payload[8:8+host_len].decode("utf-8", errors="replace")
            session.proxy_connecting.add(conn_id)
            session.proxy_pending_buffers[conn_id] = bytearray()
            asyncio.create_task(self._open_remote_proxy_connection(session, conn_id, host, port))

        elif frame.msg_type == MSG_PROXY_DATA:
            conn_id = struct.unpack("!I", decrypted_payload[:4])[0]
            data = decrypted_payload[4:]
            stream_pair = session.proxy_streams.get(conn_id)
            if stream_pair:
                writer = stream_pair[1]
                if not writer.is_closing():
                    writer.write(data)
                    try:
                        await writer.drain()
                    except Exception:
                        pass
            elif conn_id in session.proxy_connecting:
                # Buffer data while connection is still establishing!
                if conn_id in session.proxy_pending_buffers:
                    session.proxy_pending_buffers[conn_id].extend(data)

        elif frame.msg_type == MSG_PROXY_CLOSE:
            conn_id = struct.unpack("!I", decrypted_payload[:4])[0]
            session.proxy_connecting.discard(conn_id)
            session.proxy_pending_buffers.pop(conn_id, None)
            stream_pair = session.proxy_streams.pop(conn_id, None)
            if stream_pair:
                writer = stream_pair[1]
                try:
                    writer.close()
                except Exception:
                    pass

    async def _open_remote_proxy_connection(
        self, session: ClientSession, conn_id: int, host: str, port: int
    ) -> None:
        """Establishes a connection to the target server on the internet and pipes back to the client."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10.0
            )
            session.proxy_streams[conn_id] = (reader, writer)
            session.proxy_connecting.discard(conn_id)

            # Flush any data that arrived while connecting (e.g. TLS ClientHello)
            buffered = session.proxy_pending_buffers.pop(conn_id, None)
            if buffered:
                writer.write(buffered)
                await writer.drain()

            logger.debug(f"[Session {session.session_id} - Conn #{conn_id}] Connected to {host}:{port}")

            # Stream response back in MTU-safe chunks
            while self.is_running and conn_id in session.proxy_streams:
                data = await reader.read(1280)
                if not data:
                    break
                # Encrypt data frame to client
                seq, ciphertext = session.tx_cipher.encrypt(struct.pack("!I", conn_id) + data)
                p_frame = ShinFrame(session_id=session.session_id, seq_num=seq, payload=ciphertext)
                p_frame.msg_type = MSG_PROXY_DATA
                await self._send_to_client(session, p_frame.to_bytes())

        except Exception as e:
            logger.debug(f"[Conn #{conn_id}] Remote proxy connection closed: {e}")
        finally:
            session.proxy_connecting.discard(conn_id)
            session.proxy_pending_buffers.pop(conn_id, None)
            stream_pair = session.proxy_streams.pop(conn_id, None)
            if stream_pair:
                try:
                    stream_pair[1].close()
                except Exception:
                    pass

            # Notify client to close connection
            try:
                seq, ciphertext = session.tx_cipher.encrypt(struct.pack("!I", conn_id))
                c_frame = ShinFrame(session_id=session.session_id, seq_num=seq, payload=ciphertext)
                c_frame.msg_type = MSG_PROXY_CLOSE
                await self._send_to_client(session, c_frame.to_bytes())
            except Exception:
                pass

    async def _send_to_client(self, session: ClientSession, raw_data: bytes) -> None:
        session.bytes_tx += len(raw_data)
        if session.transport_type == "udp" and self.udp_protocol:
            self.udp_protocol.send_to(raw_data, session.client_addr)
        elif session.send_cb:
            await session.send_cb(raw_data)

    def _close_session(self, session: ClientSession) -> None:
        self.sessions_by_id.pop(session.session_id, None)
        self.sessions_by_addr.pop(session.client_addr, None)
        self.sessions_by_vip.pop(session.virtual_ip, None)
        self.ip_pool.release(session.session_id)
        for _, writer in session.proxy_streams.values():
            try:
                writer.close()
            except Exception:
                pass
        session.proxy_streams.clear()
        logger.info(f"Cleaned up session {session.session_id} ({session.virtual_ip})")

    async def _session_janitor(self) -> None:
        """Periodically purges inactive sessions exceeding timeout."""
        while self.is_running:
            await asyncio.sleep(15)
            now = time.time()
            stale = [s for s in self.sessions_by_id.values() if now - s.last_seen > 60.0]
            for s in stale:
                logger.info(f"Session {s.session_id} timed out; closing.")
                self._close_session(s)

    async def stop(self) -> None:
        """Gracefully stops server daemon."""
        self.is_running = False
        if self._janitor_task:
            self._janitor_task.cancel()
        if self.udp_transport:
            self.udp_transport.close()
        if self.stealth_server:
            await self.stealth_server.stop()
        if self.tun_adapter:
            self.tun_adapter.close()
        for s in list(self.sessions_by_id.values()):
            self._close_session(s)
        logger.info("ShinVPN Server stopped.")


def main_cli():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    cfg_path = Path("server.json")
    if len(sys.argv) > 1:
        cfg_path = Path(sys.argv[1])

    if not cfg_path.exists():
        cfg = ServerConfig.generate_default()
        cfg.save_to_file(cfg_path)
        print(f"Generated default server config at {cfg_path}")

    cfg = ServerConfig.load_from_file(cfg_path)
    server = ShinVPNServer(cfg)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.start())
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(server.stop())
