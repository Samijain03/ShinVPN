"""
ShinVPN Client Engine & State Machine
=====================================
Delusional Club Industries Next-Gen VPN Client.
Implements zero-knowledge handshake, dual tunnel routing, live telemetry, and auto-reconnect.
"""

from __future__ import annotations
import asyncio
import enum
import logging
import platform
import struct
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple

from ..crypto.keys import KeyPair, load_public_key
from ..crypto.handshake import HandshakeState, HandshakeRole
from ..crypto.cipher import ShinCipher
from ..protocol.constants import (
    MSG_HANDSHAKE_INIT,
    MSG_HANDSHAKE_RESP,
    MSG_DATA_PACKET,
    MSG_KEEPALIVE,
    MSG_DISCONNECT,
    MSG_PROXY_CONNECT,
    MSG_PROXY_DATA,
    MSG_PROXY_CLOSE,
    MSG_SPEEDTEST_REQ,
    MSG_SPEEDTEST_DATA,
    KEEPALIVE_INTERVAL,
)
from ..protocol.frames import (
    parse_frame,
    ShinFrame,
    HandshakeInitFrame,
    DataPacketFrame,
    KeepAliveFrame,
    DisconnectFrame,
    ProxyConnectFrame,
    ProxyDataFrame,
    ProxyCloseFrame,
    SpeedtestReqFrame,
    SpeedtestDataFrame,
)
from ..transport.udp_transport import create_udp_client, UDPClientProtocol
from ..transport.stealth_transport import StealthWSClient
from ..tunnel.proxy_tunnel import LocalSocks5Proxy, WindowsSystemProxy
from ..tunnel.killswitch import KillSwitch
from ..tunnel.dns_shield import DNSShield
from .config import ClientConfig

logger = logging.getLogger("shinvpn.client")


class ClientState(enum.Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    AUTHENTICATING = "AUTHENTICATING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


@dataclass
class ClientTelemetry:
    state: ClientState = ClientState.DISCONNECTED
    allocated_vip: str = "0.0.0.0"
    server_address: str = ""
    transport_mode: str = "udp"
    bytes_tx: int = 0
    bytes_rx: int = 0
    packets_tx: int = 0
    packets_rx: int = 0
    speed_tx_bps: float = 0.0
    speed_rx_bps: float = 0.0
    rtt_ms: float = 0.0
    connected_time: float = 0.0
    handshake_epoch: float = 0.0
    is_speedtesting: bool = False
    speedtest_dl_mbps: float = 0.0
    speedtest_ul_mbps: float = 0.0
    rekey_remaining_bytes: int = 1024 * 1024 * 1024
    last_error: str = ""


class ShinVPNClient:
    """The central ShinVPN client daemon."""

    def __init__(self, config: ClientConfig, state_callback: Optional[Callable[[ClientTelemetry], None]] = None):
        self.config = config
        self.state_callback = state_callback
        self.keypair = KeyPair.from_private_b64(config.client_private_key)
        self.server_pub_key = load_public_key(config.server_public_key) if config.server_public_key else None
        
        self.telemetry = ClientTelemetry(
            server_address=f"{config.server_host}:{config.udp_port if config.transport_type == 'udp' else config.stealth_port}",
            transport_mode=config.transport_type,
        )

        # Handshake & Ciphers
        self.handshake: Optional[HandshakeState] = None
        self.session_id: int = 0
        self.tx_cipher: Optional[ShinCipher] = None
        self.rx_cipher: Optional[ShinCipher] = None

        # Transports
        self.udp_transport: Optional[asyncio.DatagramTransport] = None
        self.udp_protocol: Optional[UDPClientProtocol] = None
        self.stealth_client: Optional[StealthWSClient] = None

        # Tunnels & System
        self.proxy_tunnel: Optional[LocalSocks5Proxy] = None
        self.killswitch: Optional[KillSwitch] = None
        self.dns_shield: Optional[DNSShield] = None

        # Tasks
        self._loop_task: Optional[asyncio.Task] = None
        self._telemetry_task: Optional[asyncio.Task] = None
        self._handshake_future: Optional[asyncio.Future] = None
        self._running: bool = False
        self._last_calc_tx: int = 0
        self._last_calc_rx: int = 0
        self._last_calc_time: float = 0.0

    def _set_state(self, state: ClientState, err: str = "") -> None:
        self.telemetry.state = state
        if err:
            self.telemetry.last_error = err
            logger.error(f"ShinVPN State: {state.value} - Error: {err}")
        else:
            logger.info(f"ShinVPN State: {state.value}")
        if self.state_callback:
            self.state_callback(self.telemetry)

    async def connect(self) -> bool:
        """Initiates connection and handshakes with the VPN server."""
        if self.telemetry.state in (ClientState.CONNECTING, ClientState.AUTHENTICATING, ClientState.CONNECTED):
            return True

        if not self.server_pub_key:
            self._set_state(ClientState.ERROR, "Server public key is required")
            return False

        self._running = True
        self._set_state(ClientState.CONNECTING)

        try:
            # 1. Establish transport
            if self.config.transport_type == "udp":
                self.udp_transport, self.udp_protocol = await create_udp_client(
                    self.config.server_host,
                    self.config.udp_port,
                    self._on_packet_received,
                    self._on_connection_lost,
                )
            else:
                self.stealth_client = StealthWSClient(
                    self.config.server_host,
                    self.config.stealth_port,
                    on_packet_received=self._on_packet_received,
                )
                await self.stealth_client.connect()

            # 2. Perform Handshake
            self._set_state(ClientState.AUTHENTICATING)
            self.handshake = HandshakeState(
                role=HandshakeRole.INITIATOR,
                static_keypair=self.keypair,
                peer_static_pub=self.server_pub_key,
            )
            init_payload, self.session_id = self.handshake.create_initiation()
            init_frame = HandshakeInitFrame(session_id=self.session_id, seq_num=1, payload=init_payload)

            loop = asyncio.get_running_loop()
            self._handshake_future = loop.create_future()

            # Transmit HandshakeInit
            await self._send_raw(init_frame.to_bytes())

            # Wait for HandshakeResp
            await asyncio.wait_for(self._handshake_future, timeout=6.0)

            # Handshake successful
            self.tx_cipher = self.handshake.tx_cipher
            self.rx_cipher = self.handshake.rx_cipher
            self.telemetry.allocated_vip = self.handshake.allocated_vip or "10.8.0.2"
            self.telemetry.connected_time = time.time()
            self.telemetry.handshake_epoch = time.time()

            # 3. Setup Local Proxy & Routing
            self.proxy_tunnel = LocalSocks5Proxy(
                listen_host="127.0.0.1",
                listen_port=self.config.local_proxy_port,
                send_frame_callback=self._send_proxy_frame_from_local,
            )
            await self.proxy_tunnel.start()

            if self.config.enable_system_proxy:
                WindowsSystemProxy.enable(f"socks=127.0.0.1:{self.config.local_proxy_port}")

            # 4. Engage KillSwitch & DNS Shield if enabled
            if self.config.enable_killswitch:
                self.killswitch = KillSwitch(self.config.server_host, self.config.udp_port)
                self.killswitch.enable()

            if self.config.enable_dns_shield:
                self.dns_shield = DNSShield(self.config.dns_servers)
                self.dns_shield.enable()

            self._set_state(ClientState.CONNECTED)

            # 5. Start background telemetry & keepalive
            self._telemetry_task = asyncio.create_task(self._telemetry_and_keepalive_loop())
            return True

        except Exception as e:
            self._set_state(ClientState.ERROR, str(e))
            await self.disconnect()
            return False

    def _send_proxy_frame_from_local(
        self, conn_id: int, action: int, host: str, port: int, data: bytes
    ) -> None:
        """Callback from LocalSocks5Proxy to send encrypted multiplexed stream."""
        if not self.tx_cipher or self.telemetry.state != ClientState.CONNECTED:
            return

        asyncio.create_task(self._async_send_proxy(conn_id, action, host, port, data))

    async def _async_send_proxy(
        self, conn_id: int, action: int, host: str, port: int, data: bytes
    ) -> None:
        if action == 1:  # Connect
            host_bytes = host.encode("utf-8")
            raw_payload = struct.pack("!IHH", conn_id, port, len(host_bytes)) + host_bytes
            seq, ciphertext = self.tx_cipher.encrypt(raw_payload)
            frame = ShinFrame(session_id=self.session_id, seq_num=seq, payload=ciphertext)
            frame.msg_type = MSG_PROXY_CONNECT
            await self._send_raw(frame.to_bytes())

        elif action == 2:  # Data
            raw_payload = struct.pack("!I", conn_id) + data
            seq, ciphertext = self.tx_cipher.encrypt(raw_payload)
            frame = ShinFrame(session_id=self.session_id, seq_num=seq, payload=ciphertext)
            frame.msg_type = MSG_PROXY_DATA
            await self._send_raw(frame.to_bytes())

        elif action == 3:  # Close
            raw_payload = struct.pack("!I", conn_id)
            seq, ciphertext = self.tx_cipher.encrypt(raw_payload)
            frame = ShinFrame(session_id=self.session_id, seq_num=seq, payload=ciphertext)
            frame.msg_type = MSG_PROXY_CLOSE
            await self._send_raw(frame.to_bytes())

    def _on_packet_received(self, raw_data: bytes, addr: Optional[Tuple[str, int]] = None) -> None:
        self.telemetry.bytes_rx += len(raw_data)
        self.telemetry.packets_rx += 1
        try:
            frame = parse_frame(raw_data)
        except Exception as e:
            logger.debug(f"Client failed to parse frame: {e}")
            return

        if frame.msg_type == MSG_HANDSHAKE_RESP and self.telemetry.state == ClientState.AUTHENTICATING:
            try:
                vip = self.handshake.process_response(frame.payload)
                if self._handshake_future and not self._handshake_future.done():
                    self._handshake_future.set_result(vip)
            except Exception as e:
                if self._handshake_future and not self._handshake_future.done():
                    self._handshake_future.set_exception(e)

        elif frame.msg_type == MSG_KEEPALIVE:
            if isinstance(frame, KeepAliveFrame) and frame.timestamp > 0:
                current_rtt = round((time.time() - frame.timestamp) * 1000, 2)
                if self.telemetry.rtt_ms == 0.0:
                    self.telemetry.rtt_ms = current_rtt
                else:
                    self.telemetry.rtt_ms = round(0.7 * self.telemetry.rtt_ms + 0.3 * current_rtt, 1)

        elif frame.msg_type == MSG_SPEEDTEST_DATA:
            if self.rx_cipher:
                try:
                    self.rx_cipher.decrypt(frame.seq_num, frame.payload)
                except Exception:
                    pass

        elif frame.msg_type == MSG_PROXY_DATA:
            if self.rx_cipher and self.proxy_tunnel:
                try:
                    plaintext = self.rx_cipher.decrypt(frame.seq_num, frame.payload)
                    conn_id = struct.unpack("!I", plaintext[:4])[0]
                    data = plaintext[4:]
                    self.proxy_tunnel.feed_remote_data(conn_id, data)
                except Exception as e:
                    logger.debug(f"Proxy data decrypt error: {e}")

        elif frame.msg_type == MSG_PROXY_CLOSE:
            if self.rx_cipher and self.proxy_tunnel:
                try:
                    plaintext = self.rx_cipher.decrypt(frame.seq_num, frame.payload)
                    conn_id = struct.unpack("!I", plaintext[:4])[0]
                    self.proxy_tunnel.close_connection(conn_id)
                except Exception:
                    pass

    def _on_connection_lost(self, exc: Optional[Exception]) -> None:
        if self._running:
            logger.warning(f"Connection dropped: {exc}. Reconnecting...")
            self._set_state(ClientState.RECONNECTING)
            asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        await asyncio.sleep(2.0)
        if self._running:
            await self.connect()

    async def _send_raw(self, data: bytes) -> None:
        self.telemetry.bytes_tx += len(data)
        self.telemetry.packets_tx += 1
        if self.config.transport_type == "udp" and self.udp_protocol:
            self.udp_protocol.send(data)
        elif self.stealth_client:
            await self.stealth_client.send(data)

    async def run_speedtest(self, duration_secs: float = 3.0) -> Tuple[float, float, float]:
        """
        Runs a real-time bandwidth and latency benchmark through the encrypted tunnel.
        Returns: (download_mbps, upload_mbps, latency_ms)
        """
        if self.telemetry.state != ClientState.CONNECTED or not self.tx_cipher:
            return 0.0, 0.0, self.telemetry.rtt_ms

        self.telemetry.is_speedtesting = True
        logger.info("🚀 Initiating ShinVPN Tunnel Benchmark...")

        try:
            # 1. Download Test (Request server stream burst)
            probe_id = int(time.time()) & 0xFFFFFF
            probe_payload = struct.pack("!III", probe_id, 250, 1200)  # 250 chunks * 1.2KB ~ 300KB burst
            seq, ciphertext = self.tx_cipher.encrypt(probe_payload)
            req_frame = ShinFrame(session_id=self.session_id, seq_num=seq, payload=ciphertext)
            req_frame.msg_type = MSG_SPEEDTEST_REQ

            start_rx = self.telemetry.bytes_rx
            t0 = time.time()
            await self._send_raw(req_frame.to_bytes())
            
            # Wait for downlink burst
            await asyncio.sleep(1.5)
            rx_diff = self.telemetry.bytes_rx - start_rx
            dt_dl = time.time() - t0
            dl_mbps = max(0.1, (rx_diff * 8) / (dt_dl * 1_000_000))

            # 2. Upload Test (Stream burst to server)
            start_tx = self.telemetry.bytes_tx
            t1 = time.time()
            dummy_chunk = b"U" * 1150
            for i in range(150):
                up_payload = struct.pack("!II", probe_id, i) + dummy_chunk
                seq, ciphertext = self.tx_cipher.encrypt(up_payload)
                st_data = ShinFrame(session_id=self.session_id, seq_num=seq, payload=ciphertext)
                st_data.msg_type = MSG_SPEEDTEST_DATA
                await self._send_raw(st_data.to_bytes())
                if i % 15 == 0:
                    await asyncio.sleep(0.001)

            await asyncio.sleep(0.5)
            tx_diff = self.telemetry.bytes_tx - start_tx
            dt_ul = time.time() - t1
            ul_mbps = max(0.1, (tx_diff * 8) / (dt_ul * 1_000_000))

            self.telemetry.speedtest_dl_mbps = round(dl_mbps, 2)
            self.telemetry.speedtest_ul_mbps = round(ul_mbps, 2)
            logger.info(f"✨ Speedtest complete: Down: {dl_mbps:.2f} Mbps, Up: {ul_mbps:.2f} Mbps")
            return self.telemetry.speedtest_dl_mbps, self.telemetry.speedtest_ul_mbps, self.telemetry.rtt_ms

        finally:
            self.telemetry.is_speedtesting = False
            if self.state_callback:
                self.state_callback(self.telemetry)

    async def _telemetry_and_keepalive_loop(self) -> None:
        self._last_calc_time = time.time()
        self._last_calc_tx = self.telemetry.bytes_tx
        self._last_calc_rx = self.telemetry.bytes_rx
        last_ka_time = 0.0

        while self._running and self.telemetry.state == ClientState.CONNECTED:
            await asyncio.sleep(0.5)
            now = time.time()
            dt = now - self._last_calc_time
            if dt >= 0.4:
                tx_diff = self.telemetry.bytes_tx - self._last_calc_tx
                rx_diff = self.telemetry.bytes_rx - self._last_calc_rx
                
                instant_tx_bps = (tx_diff * 8) / dt
                instant_rx_bps = (rx_diff * 8) / dt

                # Exponential smoothing
                self.telemetry.speed_tx_bps = round(0.5 * self.telemetry.speed_tx_bps + 0.5 * instant_tx_bps, 2)
                self.telemetry.speed_rx_bps = round(0.5 * self.telemetry.speed_rx_bps + 0.5 * instant_rx_bps, 2)

                self._last_calc_tx = self.telemetry.bytes_tx
                self._last_calc_rx = self.telemetry.bytes_rx
                self._last_calc_time = now

                if self.tx_cipher:
                    self.telemetry.rekey_remaining_bytes = max(0, ShinCipher.REKEY_BYTES_THRESHOLD - self.tx_cipher.bytes_encrypted)

                if self.state_callback:
                    self.state_callback(self.telemetry)

            # Emit KeepAlive ping periodically
            if now - last_ka_time >= KEEPALIVE_INTERVAL:
                last_ka_time = now
                ka = KeepAliveFrame(session_id=self.session_id, seq_num=0, timestamp=now)
                await self._send_raw(ka.to_bytes())

    async def disconnect(self) -> None:
        """Disconnects tunnel and cleans up all system proxy / firewall modifications."""
        self._running = False
        if self._telemetry_task:
            self._telemetry_task.cancel()

        # Send Disconnect Frame
        if self.session_id and self.tx_cipher:
            try:
                d_frame = DisconnectFrame(session_id=self.session_id, seq_num=1)
                await self._send_raw(d_frame.to_bytes())
            except Exception:
                pass

        # Cleanup Transports
        if self.udp_transport:
            try:
                self.udp_transport.close()
            except Exception:
                pass
        if self.stealth_client:
            try:
                await self.stealth_client.close()
            except Exception:
                pass

        # Cleanup Proxy & System
        if self.config.enable_system_proxy:
            WindowsSystemProxy.disable()
        if self.proxy_tunnel:
            await self.proxy_tunnel.stop()
        if self.killswitch:
            self.killswitch.disable()
        if self.dns_shield:
            self.dns_shield.disable()

        self._set_state(ClientState.DISCONNECTED)
        logger.info("ShinVPN Client cleanly disconnected.")
