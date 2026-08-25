"""
ShinVPN Routing Engine
======================
Delusional Club Industries Network Route Manager.
Configures default routes, split routes (0.0.0.0/1 & 128.0.0.0/1), and endpoint preservation.
"""

from __future__ import annotations
import logging
import os
import platform
import socket
import subprocess
from typing import List, Optional, Tuple

logger = logging.getLogger("shinvpn.tunnel.routing")


class RouteManager:
    """Manages system routing table entries for redirecting traffic through ShinVPN."""

    def __init__(self, server_ip: str, gateway_ip: str, adapter_name: str = "ShinVPN_Adapter"):
        self.server_ip = server_ip
        self.gateway_ip = gateway_ip
        self.adapter_name = adapter_name
        self.physical_gateway: Optional[str] = None
        self.routes_added: List[Tuple[str, str, str]] = []

    def get_default_gateway(self) -> Optional[str]:
        """Detects the current physical default gateway."""
        if platform.system() == "Windows":
            try:
                output = subprocess.check_output("route print 0.0.0.0", shell=True, text=True)
                for line in output.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 5 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                        return parts[2]
            except Exception as e:
                logger.warning(f"Could not parse Windows default gateway: {e}")
        elif platform.system() == "Linux":
            try:
                output = subprocess.check_output(["ip", "route", "show", "default"], text=True)
                parts = output.split()
                if "via" in parts:
                    return parts[parts.index("via") + 1]
            except Exception as e:
                logger.warning(f"Could not parse Linux default gateway: {e}")
        return None

    def setup_routes(self) -> bool:
        """
        Enables VPN routing:
        1. Adds static host route for server IP through physical gateway.
        2. Adds 0.0.0.0/1 and 128.0.0.0/1 through VPN gateway.
        """
        self.physical_gateway = self.get_default_gateway()
        if not self.physical_gateway:
            logger.warning("Could not determine physical gateway; routing setup skipped")
            return False

        logger.info(f"Physical Gateway: {self.physical_gateway}, VPN Gateway: {self.gateway_ip}")

        if platform.system() == "Windows":
            # 1. Server route
            self._exec(f"route add {self.server_ip} mask 255.255.255.255 {self.physical_gateway} metric 1")
            self.routes_added.append((self.server_ip, "255.255.255.255", self.physical_gateway))

            # 2. Split routes
            self._exec(f"route add 0.0.0.0 mask 128.0.0.0 {self.gateway_ip} metric 5")
            self.routes_added.append(("0.0.0.0", "128.0.0.0", self.gateway_ip))

            self._exec(f"route add 128.0.0.0 mask 128.0.0.0 {self.gateway_ip} metric 5")
            self.routes_added.append(("128.0.0.0", "128.0.0.0", self.gateway_ip))
            return True

        elif platform.system() == "Linux":
            self._exec(f"ip route add {self.server_ip} via {self.physical_gateway}")
            self.routes_added.append((self.server_ip, "32", self.physical_gateway))

            self._exec(f"ip route add 0.0.0.0/1 via {self.gateway_ip}")
            self.routes_added.append(("0.0.0.0/1", "", self.gateway_ip))

            self._exec(f"ip route add 128.0.0.0/1 via {self.gateway_ip}")
            self.routes_added.append(("128.0.0.0/1", "", self.gateway_ip))
            return True

        return False

    def restore_routes(self) -> None:
        """Removes all installed VPN routes and restores default behavior."""
        for dest, mask, gw in reversed(self.routes_added):
            try:
                if platform.system() == "Windows":
                    self._exec(f"route delete {dest} mask {mask} {gw}")
                elif platform.system() == "Linux":
                    if mask == "32":
                        self._exec(f"ip route del {dest} via {gw}")
                    else:
                        self._exec(f"ip route del {dest} via {gw}")
            except Exception as e:
                logger.debug(f"Error restoring route {dest}: {e}")
        self.routes_added.clear()

    def _exec(self, cmd: str) -> None:
        try:
            subprocess.run(cmd, shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.debug(f"Route command execution notice: {cmd} ({e})")
