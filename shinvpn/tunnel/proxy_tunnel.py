"""
ShinVPN Transparent Proxy & Gateway Tunnel
===========================================
Delusional Club Industries High-Speed Multiplexed Gateway.
Provides local SOCKS5 proxying, stream multiplexing over ShinVPN encrypted frames,
and Windows System Proxy automation.
"""

from __future__ import annotations
import asyncio
import logging
import platform
import socket
try:
    import winreg
except ImportError:
    winreg = None
from typing import Callable, Dict, Optional, Tuple

logger = logging.getLogger("shinvpn.tunnel.proxy")


class LocalSocks5Proxy:
    """
    Local SOCKS5 proxy server that intercepts client applications,
    multiplexes their TCP streams into ShinVPN encrypted frames, and routes
    them through the ShinVPN tunnel.
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
            self._handle_socks_client,
            self.listen_host,
            self.listen_port,
        )
        logger.info(f"ShinVPN Local SOCKS5 Proxy active on {self.listen_host}:{self.listen_port}")

    async def _handle_socks_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        conn_id = self._next_conn_id
        self._next_conn_id += 1
        self._active_connections[conn_id] = writer

        try:
            # 1. SOCKS5 greeting: VER (1B) | NMETHODS (1B) | METHODS (NB)
            ver, nmethods = await reader.readexactly(2)
            if ver != 5:
                writer.close()
                return
            methods = await reader.readexactly(nmethods)
            # Reply NO AUTH (0x00)
            writer.write(b"\x05\x00")
            await writer.drain()

            # 2. SOCKS5 request: VER (1B) | CMD (1B) | RSV (1B) | ATYP (1B) | DST.ADDR | DST.PORT (2B)
            req = await reader.readexactly(4)
            cmd, atyp = req[1], req[3]
            if cmd != 1:  # Only CONNECT supported
                writer.write(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")  # Command not supported
                await writer.drain()
                writer.close()
                return

            if atyp == 1:  # IPv4
                addr_bytes = await reader.readexactly(4)
                target_host = socket.inet_ntoa(addr_bytes)
            elif atyp == 3:  # Domain name
                domain_len = (await reader.readexactly(1))[0]
                target_host = (await reader.readexactly(domain_len)).decode("utf-8")
            elif atyp == 4:  # IPv6
                addr_bytes = await reader.readexactly(16)
                target_host = socket.inet_ntop(socket.AF_INET6, addr_bytes)
            else:
                writer.close()
                return

            port_bytes = await reader.readexactly(2)
            target_port = struct.unpack("!H", port_bytes)[0]

            logger.debug(f"[Conn #{conn_id}] Proxying request to {target_host}:{target_port}")

            # Notify ShinVPN tunnel engine to open remote connection
            if self.send_frame_callback:
                self.send_frame_callback(conn_id, 1, target_host, target_port, b"")

            # Respond SOCKS Success
            writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()

            # Read client stream and send as proxy data frames
            while self._running:
                data = await reader.read(4096)
                if not data:
                    break
                if self.send_frame_callback:
                    self.send_frame_callback(conn_id, 2, "", 0, data)

        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        except Exception as e:
            logger.debug(f"[Conn #{conn_id}] SOCKS error: {e}")
        finally:
            if self.send_frame_callback:
                self.send_frame_callback(conn_id, 3, "", 0, b"")
            self._active_connections.pop(conn_id, None)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def feed_remote_data(self, conn_id: int, data: bytes) -> None:
        """Called when data arrives from the ShinVPN server for a given client connection."""
        writer = self._active_connections.get(conn_id)
        if writer and not writer.is_closing():
            writer.write(data)

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


class WindowsSystemProxy:
    """Manages Windows Internet Settings System Proxy via registry."""

    INTERNET_SETTINGS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

    @classmethod
    def enable(cls, proxy_server: str = "socks=127.0.0.1:10808") -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, cls.INTERNET_SETTINGS_KEY, 0, winreg.KEY_WRITE
            ) as key:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_server)
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>")
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
