"""
ShinVPN Stealth WebSocket / TLS Transport
==========================================
Delusional Club Industries Traffic Camouflage Engine.
Disguises VPN frames inside standard HTTPS / WebSocket streams with custom
Delusional Club headers to bypass restrictive firewalls and Deep Packet Inspection (DPI).
"""

from __future__ import annotations
import asyncio
import logging
import ssl
from typing import Callable, Optional, Tuple
import websockets
try:
    from websockets.asyncio.server import serve, ServerConnection as WebSocketServerProtocol
    from websockets.asyncio.client import connect, ClientConnection as WebSocketClientProtocol
except ImportError:
    from websockets.server import serve, WebSocketServerProtocol
    from websockets.client import connect, WebSocketClientProtocol

from ..protocol.constants import DEFAULT_PORT_STEALTH

logger = logging.getLogger("shinvpn.transport.stealth")

DELUSIONAL_SUBPROTOCOL = "delusional-shin-v1"
DELUSIONAL_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Delusional-Club-Engine/1.0"


class StealthWSClient:
    """Client for obfuscated WebSocket/TLS tunnel."""

    def __init__(
        self,
        server_host: str,
        server_port: int,
        use_tls: bool = False,
        ssl_context: Optional[ssl.SSLContext] = None,
        on_packet_received: Optional[Callable[[bytes], None]] = None,
    ):
        self.server_host = server_host
        self.server_port = server_port
        self.use_tls = use_tls
        self.ssl_context = ssl_context
        self.on_packet_received = on_packet_received
        self.ws: Optional[WebSocketClientProtocol] = None
        self._running = False
        self._rx_task: Optional[asyncio.Task] = None

    @property
    def is_connected(self) -> bool:
        if self.ws is None:
            return False
        if hasattr(self.ws, "closed"):
            return not self.ws.closed
        if hasattr(self.ws, "state"):
            return self.ws.state.name == "OPEN"
        return True

    async def connect(self) -> None:
        proto = "wss" if self.use_tls else "ws"
        uri = f"{proto}://{self.server_host}:{self.server_port}/delusional-tunnel"
        
        logger.info(f"Connecting Stealth Tunnel to {uri}...")
        headers = {
            "User-Agent": DELUSIONAL_USER_AGENT,
            "X-Delusional-Club": "True",
        }
        try:
            self.ws = await connect(
                uri,
                subprotocols=[DELUSIONAL_SUBPROTOCOL],
                ssl=self.ssl_context,
                additional_headers=headers,
                max_size=2**20,
                ping_interval=20,
                ping_timeout=20,
            )
        except TypeError:
            self.ws = await connect(
                uri,
                subprotocols=[DELUSIONAL_SUBPROTOCOL],
                ssl=self.ssl_context,
                extra_headers=headers,
                max_size=2**20,
                ping_interval=20,
                ping_timeout=20,
            )
        self._running = True
        self._rx_task = asyncio.create_task(self._rx_loop())
        logger.info("Stealth Tunnel established successfully")

    async def _rx_loop(self) -> None:
        try:
            while self._running and self.ws:
                msg = await self.ws.recv()
                if isinstance(msg, bytes):
                    if self.on_packet_received:
                        self.on_packet_received(msg)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Stealth client connection ended: {e}")
        finally:
            self._running = False

    async def send(self, data: bytes) -> None:
        if self.ws:
            try:
                await self.ws.send(data)
            except Exception:
                pass

    async def close(self) -> None:
        self._running = False
        if self._rx_task:
            self._rx_task.cancel()
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass


class StealthWSServer:
    """Server hosting obfuscated WebSocket/TLS tunnel."""

    def __init__(
        self,
        listen_host: str,
        listen_port: int,
        on_client_packet: Callable[[bytes, Tuple[str, int], Callable[[bytes], asyncio.Future]], None],
        on_client_disconnected: Optional[Callable[[Tuple[str, int]], None]] = None,
        ssl_context: Optional[ssl.SSLContext] = None,
    ):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.on_client_packet = on_client_packet
        self.on_client_disconnected = on_client_disconnected
        self.ssl_context = ssl_context
        self._server = None

    async def start(self) -> None:
        self._server = await serve(
            self._handle_client,
            self.listen_host,
            self.listen_port,
            subprotocols=[DELUSIONAL_SUBPROTOCOL],
            ssl=self.ssl_context,
            max_size=2**20,
            ping_interval=20,
            ping_timeout=20,
        )
        logger.info(f"Stealth WebSocket Server listening on {self.listen_host}:{self.listen_port}")

    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        peer_addr = (websocket.remote_address[0], websocket.remote_address[1])
        logger.info(f"New Stealth client connected from {peer_addr}")

        async def send_response(data: bytes):
            try:
                await websocket.send(data)
            except Exception:
                pass

        try:
            async for msg in websocket:
                if isinstance(msg, bytes):
                    self.on_client_packet(msg, peer_addr, send_response)
        except Exception as e:
            logger.warning(f"Stealth client {peer_addr} exception: {e}")
        finally:
            logger.info(f"Stealth client {peer_addr} disconnected")
            if self.on_client_disconnected:
                self.on_client_disconnected(peer_addr)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
