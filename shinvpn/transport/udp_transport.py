"""
ShinVPN UDP Transport
=====================
Delusional Club Industries Low-Latency UDP Datagram Multiplexer.
"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import Callable, Optional, Tuple, Dict

from ..protocol.frames import parse_frame, ShinFrame, KeepAliveFrame
from ..protocol.constants import DEFAULT_PORT_UDP

logger = logging.getLogger("shinvpn.transport.udp")


class UDPClientProtocol(asyncio.DatagramProtocol):
    """Client-side UDP protocol for connecting to a ShinVPN server."""

    def __init__(
        self,
        on_packet_received: Callable[[bytes, Tuple[str, int]], None],
        on_connection_lost: Optional[Callable[[Optional[Exception]], None]] = None,
    ):
        self.on_packet_received = on_packet_received
        self.on_connection_lost_cb = on_connection_lost
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.last_rx_time: float = time.time()
        self.rtt_ms: float = 0.0

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        self.last_rx_time = time.time()
        try:
            self.on_packet_received(data, addr)
        except Exception as e:
            logger.error(f"Error handling UDP datagram: {e}", exc_info=True)

    def error_received(self, exc: Exception) -> None:
        logger.warning(f"UDP socket error received: {exc}")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if self.on_connection_lost_cb:
            self.on_connection_lost_cb(exc)

    def send(self, data: bytes, addr: Optional[Tuple[str, int]] = None) -> None:
        if self.transport and not self.transport.is_closing():
            if addr:
                self.transport.sendto(data, addr)
            else:
                self.transport.sendto(data)

    def close(self) -> None:
        if self.transport and not self.transport.is_closing():
            self.transport.close()


class UDPServerProtocol(asyncio.DatagramProtocol):
    """Server-side UDP protocol dispatching packets from multiple clients."""

    def __init__(
        self,
        on_packet_received: Callable[[bytes, Tuple[str, int]], None],
    ):
        self.on_packet_received = on_packet_received
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport
        logger.info("ShinVPN UDP Server listening on port")

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        try:
            self.on_packet_received(data, addr)
        except Exception as e:
            logger.error(f"Error processing datagram from {addr}: {e}", exc_info=True)

    def error_received(self, exc: Exception) -> None:
        logger.warning(f"UDP Server error received: {exc}")

    def send_to(self, data: bytes, addr: Tuple[str, int]) -> None:
        if self.transport and not self.transport.is_closing():
            self.transport.sendto(data, addr)

    def close(self) -> None:
        if self.transport and not self.transport.is_closing():
            self.transport.close()


async def create_udp_client(
    server_host: str,
    server_port: int,
    on_packet_received: Callable[[bytes, Tuple[str, int]], None],
    on_connection_lost: Optional[Callable[[Optional[Exception]], None]] = None,
) -> Tuple[asyncio.DatagramTransport, UDPClientProtocol]:
    """Factory creating an active UDP client transport connected to the server."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UDPClientProtocol(on_packet_received, on_connection_lost),
        remote_addr=(server_host, server_port),
    )
    # High-throughput 4MB socket buffer tuning
    sock = transport.get_extra_info("socket")
    if sock:
        try:
            import socket
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        except Exception as e:
            logger.debug(f"Socket buffer tuning notice: {e}")
    return transport, protocol


async def create_udp_server(
    listen_host: str,
    listen_port: int,
    on_packet_received: Callable[[bytes, Tuple[str, int]], None],
) -> Tuple[asyncio.DatagramTransport, UDPServerProtocol]:
    """Factory creating a listening UDP server endpoint."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UDPServerProtocol(on_packet_received),
        local_addr=(listen_host, listen_port),
    )
    # High-throughput 4MB socket buffer tuning
    sock = transport.get_extra_info("socket")
    if sock:
        try:
            import socket
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        except Exception as e:
            logger.debug(f"Socket buffer tuning notice: {e}")
    return transport, protocol
