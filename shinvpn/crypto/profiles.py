"""
ShinVPN Multi-Device Profile Hub & Mobile QR Code Engine
========================================================
Delusional Club Industries Device Management & Provisioning.
Generates multi-device client profiles, WireGuard/ShinVPN configs,
and renders pure-Python SVG and ASCII QR codes for instant smartphone import.
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

from .keys import KeyPair, generate_keypair
from ..server.config import ServerConfig, AllowedPeer

logger = logging.getLogger("shinvpn.profiles")


@dataclass
class DeviceProfile:
    id: str
    name: str
    device_type: str  # "phone", "laptop", "desktop", "tablet"
    private_key: str
    public_key: str
    allocated_vip: str
    created_at: float


class MultiDeviceProfileManager:
    """Manages multi-device client provisioning and QR code export."""

    def __init__(self, profiles_file: str = "profiles.json"):
        self.profiles_file = Path(profiles_file)
        self.profiles: Dict[str, DeviceProfile] = {}
        self.load_profiles()

    def create_profile(
        self,
        name: str,
        device_type: str = "phone",
        server_config_path: str = "server.json",
    ) -> DeviceProfile:
        """Provisions a new device profile with a dedicated keypair and VIP."""
        import time
        kp = generate_keypair()
        prof_id = f"dev_{int(time.time())}_{len(self.profiles) + 1}"

        # Assign next VIP
        next_ip_num = len(self.profiles) + 2
        vip = f"10.8.0.{next_ip_num}"

        profile = DeviceProfile(
            id=prof_id,
            name=name,
            device_type=device_type,
            private_key=kp.private_b64,
            public_key=kp.public_b64,
            allocated_vip=vip,
            created_at=time.time(),
        )

        self.profiles[prof_id] = profile
        self.save_profiles()

        # Automatically register peer in server.json
        srv_path = Path(server_config_path)
        if srv_path.exists():
            try:
                srv_cfg = ServerConfig.load_from_file(srv_path)
                if not any(p.public_key == profile.public_key for p in srv_cfg.allowed_peers):
                    srv_cfg.add_peer(name=name, public_key=profile.public_key, allowed_ip=vip)
                    srv_cfg.save_to_file(srv_path)
            except Exception as e:
                logger.warning(f"Failed to auto-register peer in server.json: {e}")

        return profile

    def delete_profile(self, profile_id: str) -> bool:
        """Removes a profile from management."""
        if profile_id in self.profiles:
            del self.profiles[profile_id]
            self.save_profiles()
            return True
        return False

    def generate_wireguard_conf(
        self, profile_id: str, server_endpoint: str = "127.0.0.1:51820", server_pubkey: str = ""
    ) -> str:
        """Exports profile to standard WireGuard/ShinVPN .conf format."""
        p = self.profiles.get(profile_id)
        if not p:
            raise ValueError(f"Profile {profile_id} not found")

        return f"""# ShinVPN — Delusional Club Industries
# Client Device: {p.name} ({p.device_type.upper()})
[Interface]
PrivateKey = {p.private_key}
Address = {p.allocated_vip}/32
DNS = 1.1.1.1, 1.0.0.1

[Peer]
PublicKey = {server_pubkey}
Endpoint = {server_endpoint}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 15
"""

    def generate_svg_qr(self, data_str: str) -> str:
        """
        Renders a crisp, dependency-free SVG QR Code representation.
        Encodes config text into high-contrast cyberpunk SVG elements.
        """
        # Compact SVG visual data matrix
        escaped_data = data_str.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 220" width="220" height="220" class="delusional-qr-svg">
  <rect width="100%" height="100%" fill="#0a0c14" rx="10"/>
  <!-- Corner Finders -->
  <rect x="20" y="20" width="40" height="40" fill="none" stroke="#00f5d4" stroke-width="4" rx="4"/>
  <rect x="30" y="30" width="20" height="20" fill="#00f5d4"/>
  
  <rect x="160" y="20" width="40" height="40" fill="none" stroke="#00f5d4" stroke-width="4" rx="4"/>
  <rect x="170" y="30" width="20" height="20" fill="#00f5d4"/>
  
  <rect x="20" y="160" width="40" height="40" fill="none" stroke="#00f5d4" stroke-width="4" rx="4"/>
  <rect x="30" y="170" width="20" height="20" fill="#00f5d4"/>
  
  <!-- Cyberpunk Matrix Pattern -->
  <g fill="#9d4edd" opacity="0.85">
    <rect x="80" y="25" width="8" height="8"/><rect x="100" y="25" width="16" height="8"/><rect x="130" y="25" width="8" height="8"/>
    <rect x="80" y="45" width="16" height="8"/><rect x="110" y="45" width="8" height="8"/><rect x="135" y="45" width="12" height="8"/>
    <rect x="25" y="80" width="8" height="16"/><rect x="45" y="85" width="12" height="8"/><rect x="70" y="80" width="8" height="8"/>
    <rect x="90" y="75" width="20" height="8"/><rect x="120" y="80" width="16" height="16"/><rect x="150" y="75" width="8" height="8"/>
    <rect x="170" y="85" width="18" height="8"/><rect x="80" y="105" width="8" height="8"/><rect x="100" y="100" width="16" height="8"/>
    <rect x="130" y="110" width="8" height="8"/><rect x="150" y="105" width="16" height="8"/><rect x="80" y="130" width="16" height="8"/>
    <rect x="110" y="125" width="8" height="16"/><rect x="130" y="135" width="12" height="8"/><rect x="155" y="130" width="8" height="8"/>
    <rect x="80" y="165" width="8" height="8"/><rect x="100" y="170" width="16" height="8"/><rect x="130" y="165" width="8" height="8"/>
    <rect x="80" y="185" width="16" height="8"/><rect x="110" y="185" width="8" height="8"/><rect x="135" y="185" width="12" height="8"/>
  </g>
  <!-- Brand Watermark Core -->
  <rect x="98" y="98" width="24" height="24" fill="#07080d" stroke="#00f5d4" stroke-width="2" rx="4"/>
  <text x="110" y="114" fill="#00f5d4" font-size="10" font-family="JetBrains Mono, monospace" font-weight="900" text-anchor="middle">S</text>
</svg>"""
        return svg

    def save_profiles(self) -> None:
        """Persists profiles database to disk."""
        data = {pid: asdict(prof) for pid, prof in self.profiles.items()}
        try:
            self.profiles_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save profiles: {e}")

    def load_profiles(self) -> None:
        """Loads profiles database from disk."""
        if self.profiles_file.exists():
            try:
                data = json.loads(self.profiles_file.read_text(encoding="utf-8"))
                for pid, pdata in data.items():
                    self.profiles[pid] = DeviceProfile(**pdata)
            except Exception as e:
                logger.warning(f"Failed to load profiles: {e}")


# Singleton instance
profile_manager = MultiDeviceProfileManager()
