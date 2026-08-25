"""
ShinVPN Firewall Kill Switch
============================
Delusional Club Industries Traffic Leak Prevention.
Enforces strict outbound firewall rules on Windows and Linux to ensure zero IP/DNS leaks
in case of unexpected tunnel drops.
"""

from __future__ import annotations
import logging
import platform
import subprocess
from typing import Optional

logger = logging.getLogger("shinvpn.tunnel.killswitch")

RULE_PREFIX = "ShinVPN_KillSwitch_"


class KillSwitch:
    """Firewall manager that drops all outbound non-tunnel traffic."""

    def __init__(self, server_ip: str, server_port: int, adapter_name: str = "ShinVPN_Adapter"):
        self.server_ip = server_ip
        self.server_port = server_port
        self.adapter_name = adapter_name
        self.is_active = False

    def enable(self) -> bool:
        """Applies firewall killswitch rules."""
        if self.is_active:
            return True

        logger.info("Engaging ShinVPN Firewall Kill Switch...")
        if platform.system() == "Windows":
            success = self._enable_windows()
        elif platform.system() == "Linux":
            success = self._enable_linux()
        else:
            logger.warning("Kill switch not supported on this OS")
            return False

        self.is_active = success
        return success

    def disable(self) -> None:
        """Removes all installed firewall killswitch rules."""
        if not self.is_active:
            return

        logger.info("Disengaging ShinVPN Firewall Kill Switch...")
        if platform.system() == "Windows":
            self._disable_windows()
        elif platform.system() == "Linux":
            self._disable_linux()

        self.is_active = False

    def _enable_windows(self) -> bool:
        try:
            # 1. Allow Loopback & Local LAN
            self._run_cmd(
                f'netsh advfirewall firewall add rule name="{RULE_PREFIX}Allow_LAN" dir=out action=allow remoteip=127.0.0.1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12'
            )
            # 2. Allow ShinVPN Server Traffic
            self._run_cmd(
                f'netsh advfirewall firewall add rule name="{RULE_PREFIX}Allow_Server" dir=out action=allow remoteip={self.server_ip} protocol=UDP remoteport={self.server_port}'
            )
            # 3. Allow ShinVPN Adapter Traffic
            self._run_cmd(
                f'netsh advfirewall firewall add rule name="{RULE_PREFIX}Allow_Adapter" dir=out action=allow interface="{self.adapter_name}"'
            )
            # 4. Block general outbound
            self._run_cmd(
                f'netsh advfirewall firewall add rule name="{RULE_PREFIX}Block_All" dir=out action=block'
            )
            return True
        except Exception as e:
            logger.error(f"Failed to enable Windows Kill Switch: {e}")
            self._disable_windows()
            return False

    def _disable_windows(self) -> None:
        rules = ["Allow_LAN", "Allow_Server", "Allow_Adapter", "Block_All"]
        for rule in rules:
            self._run_cmd(
                f'netsh advfirewall firewall delete rule name="{RULE_PREFIX}{rule}"'
            )

    def _enable_linux(self) -> bool:
        try:
            # Allow loopback
            self._run_cmd("iptables -A OUTPUT -o lo -j ACCEPT")
            # Allow local LAN
            self._run_cmd("iptables -A OUTPUT -d 192.168.0.0/16 -j ACCEPT")
            self._run_cmd("iptables -A OUTPUT -d 10.0.0.0/8 -j ACCEPT")
            # Allow server endpoint
            self._run_cmd(f"iptables -A OUTPUT -d {self.server_ip} -p udp --dport {self.server_port} -j ACCEPT")
            # Allow TUN adapter (shin0)
            self._run_cmd("iptables -A OUTPUT -o shin+ -j ACCEPT")
            # Drop rest
            self._run_cmd("iptables -A OUTPUT -j DROP")
            return True
        except Exception as e:
            logger.error(f"Failed to enable Linux Kill Switch: {e}")
            self._disable_linux()
            return False

    def _disable_linux(self) -> None:
        try:
            self._run_cmd("iptables -D OUTPUT -j DROP")
            self._run_cmd("iptables -D OUTPUT -o shin+ -j ACCEPT")
            self._run_cmd(f"iptables -D OUTPUT -d {self.server_ip} -p udp --dport {self.server_port} -j ACCEPT")
            self._run_cmd("iptables -D OUTPUT -d 10.0.0.0/8 -j ACCEPT")
            self._run_cmd("iptables -D OUTPUT -d 192.168.0.0/16 -j ACCEPT")
            self._run_cmd("iptables -D OUTPUT -o lo -j ACCEPT")
        except Exception:
            pass

    def _run_cmd(self, cmd: str) -> None:
        subprocess.run(
            cmd, shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
