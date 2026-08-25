"""
ShinVPN Tunneling & System Layer
================================
"""

from .wintun_adapter import WintunAdapter
from .linux_tun import LinuxTunAdapter
from .proxy_tunnel import LocalSocks5Proxy, WindowsSystemProxy
from .routing import RouteManager
from .killswitch import KillSwitch
from .dns_shield import DNSShield

__all__ = [
    "WintunAdapter",
    "LinuxTunAdapter",
    "LocalSocks5Proxy",
    "WindowsSystemProxy",
    "RouteManager",
    "KillSwitch",
    "DNSShield",
]
