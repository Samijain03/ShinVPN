"""
ShinVPN Universal Transparent Proxy & Gateway Tunnel
=====================================================
Delusional Club Industries High-Speed Multiplexed Gateway.
Provides multi-protocol support:
- HTTP / HTTPS Connect Proxy (RFC 7231 / RFC 2817)
- SOCKS5 Proxy (RFC 1928) with IPv4, IPv6, and Domain Name resolution
- SOCKS4 / SOCKS4a Proxy
- Stream multiplexing over ShinVPN encrypted frames
- Automated Windows WinINet System Proxy integration with instant refresh.
"""

from __future__ import annotations
import asyncio
import logging
import platform
import re
import socket
import struct
from typing import Callable, Dict, Optional, Tuple

try:
    import winreg
except ImportError:
    winreg = None

logger = logging.getLogger("shinvpn.tunnel.proxy")


class UniversalProxyGateway:
    """
    Universal proxy server that automatically detects and handles
    HTTP CONNECT, plain HTTP, SOCKS5, and SOCKS4 on a single port.
    Multiplexes streams through the ShinVPN encrypted tunnel.
    """

    def __init__(
        self,
        listen_host: str = "127.0.0.1",
        listen_port: int = 10808,
        send_frame_callback: Optional[Callable[[int, int, str, int, bytes], None]] = None,
    ):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.send_frame_callback = send_frame_callback
        self.server: Optional[asyncio.Server] = None
        self._active_connections: Dict[int, asyncio.StreamWriter] = {}
        self._next_conn_id: int = 1
        self._running = False

    async def start(self) -> None:
        self._running = True
        self.server = await asyncio.start_server(
            self._handle_client_connection,
            self.listen_host,
            self.listen_port,
        )
        logger.info(f"ShinVPN Universal Proxy Gateway active on {self.listen_host}:{self.listen_port}")

    async def _handle_client_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        conn_id = self._next_conn_id
        self._next_conn_id += 1
        self._active_connections[conn_id] = writer

        try:
            # Peek or read first byte to determine protocol
            initial_data = await reader.read(1)
            if not initial_data:
                writer.close()
                return

            first_byte = initial_data[0]

            # -------------------------------------------------------------
            # Case 1: SOCKS5 (0x05)
            # -------------------------------------------------------------
            if first_byte == 5:
                await self._handle_socks5(conn_id, reader, writer)

            # -------------------------------------------------------------
            # Case 2: SOCKS4 / SOCKS4a (0x04)
            # -------------------------------------------------------------
            elif first_byte == 4:
                await self._handle_socks4(conn_id, reader, writer)

            # -------------------------------------------------------------
            # Case 3: HTTP / HTTPS Proxy (CONNECT, GET, POST, etc.)
            # -------------------------------------------------------------
            else:
                # Read rest of initial HTTP request line/headers
                rest_of_header = await reader.readuntil(b"\r\n\r\n")
                raw_http_header = initial_data + rest_of_header
                await self._handle_http_proxy(conn_id, raw_http_header, reader, writer)

        except (asyncio.IncompleteReadError, ConnectionResetError, asyncio.CancelledError):
            pass
        except Exception as e:
            logger.debug(f"[Conn #{conn_id}] Proxy error: {e}")
        finally:
            if self.send_frame_callback:
                self.send_frame_callback(conn_id, 3, "", 0, b"")
            self._active_connections.pop(conn_id, None)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    # =========================================================================
    # SOCKS5 Handler
    # =========================================================================
    async def _handle_socks5(
        self, conn_id: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        # Read NMETHODS and METHODS
        nmethods_byte = await reader.readexactly(1)
        nmethods = nmethods_byte[0]
        methods = await reader.readexactly(nmethods)

        # Reply NO AUTH REQUIRED (0x00)
        writer.write(b"\x05\x00")
        await writer.drain()

        # Read SOCKS5 Request: VER (1) | CMD (1) | RSV (1) | ATYP (1)
        req = await reader.readexactly(4)
        cmd, atyp = req[1], req[3]
        if cmd != 1:  # Only CONNECT supported
            writer.write(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")  # Command not supported
            await writer.drain()
            return

        if atyp == 1:  # IPv4
            addr_bytes = await reader.readexactly(4)
            target_host = socket.inet_ntoa(addr_bytes)
        elif atyp == 3:  # Domain Name
            domain_len = (await reader.readexactly(1))[0]
            target_host = (await reader.readexactly(domain_len)).decode("utf-8", errors="replace")
        elif atyp == 4:  # IPv6
            addr_bytes = await reader.readexactly(16)
            target_host = socket.inet_ntop(socket.AF_INET6, addr_bytes)
        else:
            return

        port_bytes = await reader.readexactly(2)
        target_port = struct.unpack("!H", port_bytes)[0]

        # 🛡️ CyberShield Ad & Tracker Interception
        from .adblock import shield_instance
        if shield_instance.should_block(target_host):
            logger.info(f"🚫 [CyberShield] Dropped ad/tracker connection to {target_host}:{target_port}")
            writer.write(b"\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00")  # Connection Refused
            await writer.drain()
            return

        logger.debug(f"[SOCKS5 #{conn_id}] Connecting to {target_host}:{target_port}")

        # Send Connect Frame to ShinVPN Server
        if self.send_frame_callback:
            self.send_frame_callback(conn_id, 1, target_host, target_port, b"")

        # Reply SOCKS5 Success
        writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        await writer.drain()

        # Pipe Client -> ShinVPN Tunnel
        await self._pipe_client_to_tunnel(conn_id, reader)

    # =========================================================================
    # SOCKS4 / SOCKS4a Handler
    # =========================================================================
    async def _handle_socks4(
        self, conn_id: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        cmd_byte = await reader.readexactly(1)
        cmd = cmd_byte[0]
        port_bytes = await reader.readexactly(2)
        target_port = struct.unpack("!H", port_bytes)[0]
        ip_bytes = await reader.readexactly(4)

        # Read USERID until null terminator
        user_id = b""
        while True:
            b = await reader.readexactly(1)
            if b == b"\x00":
                break
            user_id += b

        # SOCKS4a domain support (if IP starts with 0.0.0.x)
        if ip_bytes[:3] == b"\x00\x00\x00" and ip_bytes[3] != 0:
            target_host = b""
            while True:
                b = await reader.readexactly(1)
                if b == b"\x00":
                    break
                target_host += b
            target_host = target_host.decode("utf-8", errors="replace")
        else:
            target_host = socket.inet_ntoa(ip_bytes)

        if cmd != 1:  # Only CONNECT
            writer.write(b"\x00\x5b\x00\x00\x00\x00\x00\x00")  # Request rejected
            await writer.drain()
            return

        # 🛡️ CyberShield AdBlocker Check
        from .adblock import shield_instance
        if shield_instance.should_block(target_host):
            writer.write(b"\x00\x5b\x00\x00\x00\x00\x00\x00")
            await writer.drain()
            return

        if self.send_frame_callback:
            self.send_frame_callback(conn_id, 1, target_host, target_port, b"")

        # Reply SOCKS4 Granted (0x5A)
        writer.write(b"\x00\x5a\x00\x00\x00\x00\x00\x00")
        await writer.drain()

        await self._pipe_client_to_tunnel(conn_id, reader)

    # =========================================================================
    # HTTP / HTTPS CONNECT Proxy Handler
    # =========================================================================
    async def _handle_http_proxy(
        self, conn_id: int, header_bytes: bytes, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        header_text = header_bytes.decode("utf-8", errors="replace")
        lines = header_text.split("\r\n")
        request_line = lines[0] if lines else ""
        parts = request_line.split(" ")
        if len(parts) < 2:
            return

        method = parts[0].upper()
        target_uri = parts[1]

        # 1. HTTPS CONNECT (e.g. CONNECT www.google.com:443 HTTP/1.1)
        if method == "CONNECT":
            if ":" in target_uri:
                target_host, port_str = target_uri.split(":", 1)
                target_port = int(port_str)
            else:
                target_host = target_uri
                target_port = 443

            # 🛡️ CyberShield Check
            from .adblock import shield_instance
            if shield_instance.should_block(target_host):
                logger.info(f"🚫 [CyberShield] Blocked HTTPS request to {target_host}")
                writer.write(b"HTTP/1.1 403 Forbidden (Blocked by Delusional CyberShield)\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()
                return

            logger.debug(f"[HTTPS Proxy #{conn_id}] CONNECT to {target_host}:{target_port}")

            # Notify ShinVPN Server to connect
            if self.send_frame_callback:
                self.send_frame_callback(conn_id, 1, target_host, target_port, b"")

            # Reply 200 Connection Established to Browser
            writer.write(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: ShinVPN-Delusional/1.0\r\n\r\n")
            await writer.drain()

            # Now stream encrypted TLS data directly
            await self._pipe_client_to_tunnel(conn_id, reader)

        # 2. Plain HTTP (e.g. GET http://example.com/index.html HTTP/1.1)
        else:
            # Extract host from URI or Host header
            match = re.search(r"https?://([^/]+)(/.*)?", target_uri)
            if match:
                host_part = match.group(1)
                path_part = match.group(2) or "/"
            else:
                host_part = target_uri
                path_part = "/"

            if ":" in host_part:
                target_host, port_str = host_part.split(":", 1)
                target_port = int(port_str)
            else:
                target_host = host_part
                target_port = 80

            from .adblock import shield_instance
            if shield_instance.should_block(target_host):
                writer.write(b"HTTP/1.1 403 Forbidden (Blocked by Delusional CyberShield)\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()
                return

            logger.debug(f"[HTTP Proxy #{conn_id}] {method} http://{target_host}:{target_port}{path_part}")

            # Notify tunnel to connect
            if self.send_frame_callback:
                self.send_frame_callback(conn_id, 1, target_host, target_port, b"")

            # Reconstruct clean HTTP request with relative path
            new_req_line = f"{method} {path_part} {parts[2] if len(parts) > 2 else 'HTTP/1.1'}"
            lines[0] = new_req_line
            # Filter Proxy-Connection headers
            filtered_lines = [l for l in lines if not l.lower().startswith("proxy-connection:")]
            reconstructed_header = "\r\n".join(filtered_lines).encode("utf-8") + b"\r\n\r\n"

            # Send initial HTTP request payload to ShinVPN server
            if self.send_frame_callback:
                self.send_frame_callback(conn_id, 2, "", 0, reconstructed_header)

            # Continue streaming remaining body / requests
            await self._pipe_client_to_tunnel(conn_id, reader)

    async def _pipe_client_to_tunnel(self, conn_id: int, reader: asyncio.StreamReader) -> None:
        """Pipes data from local client application into the ShinVPN tunnel."""
        while self._running:
            data = await reader.read(2048)
            if not data:
                break
            if self.send_frame_callback:
                self.send_frame_callback(conn_id, 2, "", 0, data)

    def feed_remote_data(self, conn_id: int, data: bytes) -> None:
        """Called when data arrives from the ShinVPN server for a given connection."""
        writer = self._active_connections.get(conn_id)
        if writer and not writer.is_closing():
            try:
                writer.write(data)
            except Exception:
                pass

    def close_connection(self, conn_id: int) -> None:
        writer = self._active_connections.pop(conn_id, None)
        if writer and not writer.is_closing():
            try:
                writer.close()
            except Exception:
                pass

    async def stop(self) -> None:
        self._running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for writer in list(self._active_connections.values()):
            try:
                writer.close()
            except Exception:
                pass
        self._active_connections.clear()


# Alias for backward compatibility
LocalSocks5Proxy = UniversalProxyGateway


class WindowsSystemProxy:
    """Manages Windows Internet Settings System Proxy via registry."""

    INTERNET_SETTINGS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

    @classmethod
    def enable(cls, proxy_server: str = "http=127.0.0.1:10808;https=127.0.0.1:10808;socks=127.0.0.1:10808") -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, cls.INTERNET_SETTINGS_KEY, 0, winreg.KEY_WRITE
            ) as key:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_server)
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "localhost;127.*;10.*;192.168.*;<local>")
            cls._refresh_wininet()
            logger.info(f"Windows System Proxy enabled: {proxy_server}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable Windows System Proxy: {e}")
            return False

    @classmethod
    def disable(cls) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, cls.INTERNET_SETTINGS_KEY, 0, winreg.KEY_WRITE
            ) as key:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            cls._refresh_wininet()
            logger.info("Windows System Proxy disabled")
            return True
        except Exception as e:
            logger.error(f"Failed to disable Windows System Proxy: {e}")
            return False

    @classmethod
    def _refresh_wininet(cls) -> None:
        """Signals Windows WinINet to immediately apply proxy settings without reboot."""
        if platform.system() != "Windows":
            return
        try:
            import ctypes
            INTERNET_OPTION_SETTINGS_CHANGED = 39
            INTERNET_OPTION_REFRESH = 37
            wininet = ctypes.windll.wininet
            wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
            wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)
        except Exception as e:
            logger.debug(f"WinINet refresh notice: {e}")
