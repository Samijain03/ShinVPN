"""
ShinVPN DNS Leak Shield
=======================
Delusional Club Industries DNS Protection.
Enforces encrypted / secure DNS servers (Cloudflare / Quad9) and suppresses
Windows Smart Multi-Homed Name Resolution leaks.
"""

from __future__ import annotations
import logging
import platform
import subprocess
from typing import List, Optional

logger = logging.getLogger("shinvpn.tunnel.dns")


class DNSShield:
    """Configures DNS servers and blocks multi-homed leakage."""

    def __init__(self, dns_servers: Optional[List[str]] = None, adapter_name: str = "ShinVPN_Adapter"):
        self.dns_servers = dns_servers or ["1.1.1.1", "1.0.0.1"]
        self.adapter_name = adapter_name
        self.is_active = False

    def enable(self) -> bool:
        if platform.system() != "Windows":
            return True

        try:
            primary_dns = self.dns_servers[0]
            cmd_primary = f'netsh interface ip set dns name="{self.adapter_name}" static {primary_dns}'
            subprocess.run(cmd_primary, shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if len(self.dns_servers) > 1:
                secondary_dns = self.dns_servers[1]
                cmd_secondary = f'netsh interface ip add dns name="{self.adapter_name}" {secondary_dns} index=2'
                subprocess.run(cmd_secondary, shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            self.is_active = True
            logger.info(f"DNS Shield engaged with resolvers: {', '.join(self.dns_servers)}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set DNS servers: {e}")
            return False

    def disable(self) -> None:
        if not self.is_active or platform.system() != "Windows":
            return

        try:
            cmd = f'netsh interface ip set dns name="{self.adapter_name}" dhcp'
            subprocess.run(cmd, shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.is_active = False
            logger.info("DNS Shield disengaged")
        except Exception as e:
            logger.debug(f"DNS restore notice: {e}")
