"""
ShinVPN Server Virtual IP Pool
==============================
Delusional Club Industries Virtual Subnet Allocator.
Manages dynamic IP assignment (10.8.0.2 - 10.8.0.254) for connected VPN clients.
"""

from __future__ import annotations
import ipaddress
import logging
from typing import Dict, Optional, Set

logger = logging.getLogger("shinvpn.server.ip_pool")


class IPPool:
    """Manages lease allocation of IPv4 addresses within a virtual subnet."""

    def __init__(self, subnet: str = "10.8.0.0/24", server_ip: str = "10.8.0.1"):
        self.network = ipaddress.IPv4Network(subnet, strict=False)
        self.server_ip = ipaddress.IPv4Address(server_ip)
        self._allocated: Dict[int, ipaddress.IPv4Address] = {}  # session_id -> ip
        self._reserved: Set[ipaddress.IPv4Address] = {
            self.network.network_address,
            self.network.broadcast_address,
            self.server_ip,
        }

    def allocate(self, session_id: int, preferred_ip: Optional[str] = None) -> str:
        """Allocates an available virtual IP for the given session ID."""
        if session_id in self._allocated:
            return str(self._allocated[session_id])

        if preferred_ip:
            try:
                cand = ipaddress.IPv4Address(preferred_ip)
                if cand in self.network and cand not in self._allocated.values() and cand not in self._reserved:
                    self._allocated[session_id] = cand
                    logger.info(f"Allocated preferred VIP {cand} to session {session_id}")
                    return str(cand)
            except ValueError:
                pass

        # Find first available host IP
        for host in self.network.hosts():
            if host not in self._reserved and host not in self._allocated.values():
                self._allocated[session_id] = host
                logger.info(f"Allocated VIP {host} to session {session_id}")
                return str(host)

        raise RuntimeError("No available Virtual IP addresses left in pool")

    def release(self, session_id: int) -> None:
        """Releases the virtual IP allocated to the session."""
        ip = self._allocated.pop(session_id, None)
        if ip:
            logger.info(f"Released VIP {ip} from session {session_id}")

    def get_session_by_ip(self, ip_str: str) -> Optional[int]:
        """Finds the session ID assigned to a given virtual IP."""
        try:
            target_ip = ipaddress.IPv4Address(ip_str)
            for sess_id, ip in self._allocated.items():
                if ip == target_ip:
                    return sess_id
        except ValueError:
            pass
        return None
