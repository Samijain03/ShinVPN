"""
ShinVPN Linux TUN Adapter
=========================
Delusional Club Industries Linux Kernel TUN Device Interface.
Creates and manages /dev/net/tun devices for raw L3 IP packet routing.
"""

from __future__ import annotations
import logging
import os
import platform
import struct
import subprocess
from typing import Optional

try:
    import fcntl
except ImportError:
    fcntl = None

logger = logging.getLogger("shinvpn.tunnel.linux")

# Linux TUN constants
TUNSETIFF = 0x400454CA
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000


class LinuxTunAdapter:
    """Creates and controls a Linux TUN virtual network interface."""

    def __init__(self, dev_name: str = "shin0", mtu: int = 1420):
        self.dev_name = dev_name
        self.mtu = mtu
        self.fd: Optional[int] = None
        self.is_open = False

    def is_available(self) -> bool:
        return platform.system() == "Linux" and os.path.exists("/dev/net/tun")

    def open(self) -> bool:
        if not self.is_available():
            logger.debug("Linux TUN interface is not supported on this platform")
            return False

        try:
            self.fd = os.open("/dev/net/tun", os.O_RDWR)
            # ifr struct: 16-byte name + 2-byte flags + padding
            ifr = struct.pack("16sH", self.dev_name.encode("utf-8"), IFF_TUN | IFF_NO_PI)
            fcntl.ioctl(self.fd, TUNSETIFF, ifr)
            self.is_open = True
            logger.info(f"Linux TUN interface {self.dev_name} opened (fd={self.fd})")
            return True
        except Exception as e:
            logger.error(f"Failed to open /dev/net/tun device {self.dev_name}: {e}")
            return False

    def configure_ip(self, virtual_ip: str, server_ip: str = "10.8.0.1") -> bool:
        """Sets interface UP, configures IP address and MTU."""
        if not self.is_open:
            return False
        try:
            subprocess.run(["ip", "link", "set", "dev", self.dev_name, "mtu", str(self.mtu)], check=True)
            subprocess.run(["ip", "addr", "add", f"{virtual_ip}/24", "peer", server_ip, "dev", self.dev_name], check=True)
            subprocess.run(["ip", "link", "set", "dev", self.dev_name, "up"], check=True)
            logger.info(f"Configured {self.dev_name}: {virtual_ip}/24 (MTU {self.mtu})")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to configure network parameters on {self.dev_name}: {e}")
            return False

    def read_packet(self) -> Optional[bytes]:
        if not self.is_open or self.fd is None:
            return None
        try:
            return os.read(self.fd, self.mtu + 100)
        except Exception as e:
            logger.debug(f"TUN read error: {e}")
            return None

    def write_packet(self, packet: bytes) -> bool:
        if not self.is_open or self.fd is None:
            return False
        try:
            os.write(self.fd, packet)
            return True
        except Exception as e:
            logger.debug(f"TUN write error: {e}")
            return False

    def close(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None
        self.is_open = False
