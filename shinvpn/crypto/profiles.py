"""
ShinVPN Multi-Device Profile Hub & Mobile QR Code Engine
========================================================
Delusional Club Industries Device Management & Provisioning.
Features:
- Multi-device client provisioning with dedicated VIP allocations
- Wi-Fi ZeroConf / mDNS UDP beacon for local network auto-discovery
- Authentic ISO/IEC 18004 SVG and ASCII QR code matrix generation
- Per-device data consumption telemetry tracking.
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass, asdict, field
import json
import logging
from pathlib import Path
import socket
import time
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
    bytes_consumed: int = 0
    last_connected: float = 0.0


class WifiZeroConfBeacon:
    """Announces ShinVPN server endpoint on local Wi-Fi / LAN via UDP broadcast."""

    def __init__(self, port: int = 51820, broadcast_port: int = 51822):
        self.port = port
        self.broadcast_port = broadcast_port
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._beacon_loop())
        logger.info(f"ShinVPN Wi-Fi ZeroConf Beacon active on port {self.broadcast_port}")

    async def _beacon_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)

        while self._running:
            try:
                msg = json.dumps({
                    "service": "shinvpn-core",
                    "version": "2.0",
                    "port": self.port,
                    "timestamp": time.time(),
                }).encode("utf-8")
                
                loop = asyncio.get_running_loop()
                await loop.sock_sendto(sock, msg, ("255.255.255.255", self.broadcast_port))
            except Exception:
                pass
            await asyncio.sleep(5.0)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()


class MultiDeviceProfileManager:
    """Manages multi-device client provisioning and QR code export."""

    def __init__(self, profiles_file: str = "profiles.json"):
        self.profiles_file = Path(profiles_file)
        self.profiles: Dict[str, DeviceProfile] = {}
        self.beacon = WifiZeroConfBeacon()
        self.load_profiles()

    def create_profile(
        self,
        name: str,
        device_type: str = "phone",
        server_config_path: str = "server.json",
    ) -> DeviceProfile:
        """Provisions a new device profile with a dedicated keypair and VIP."""
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
            bytes_consumed=0,
            last_connected=0.0,
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

    def update_usage(self, profile_id: str, bytes_delta: int) -> None:
        """Updates traffic consumed by a device profile."""
        if profile_id in self.profiles:
            p = self.profiles[profile_id]
            p.bytes_consumed += bytes_delta
            p.last_connected = time.time()
            self.save_profiles()

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

        # Auto-fetch server public key if not supplied
        if not server_pubkey:
            srv_path = Path("server.json")
            if srv_path.exists():
                try:
                    srv_cfg = ServerConfig.load_from_file(srv_path)
                    server_pubkey = srv_cfg.public_key
                except Exception:
                    pass

        return f"""[Interface]
PrivateKey = {p.private_key}
Address = {p.allocated_vip}/32
DNS = 1.1.1.1, 1.0.0.1

[Peer]
PublicKey = {server_pubkey}
Endpoint = {server_endpoint}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
"""

    def generate_svg_qr(self, data_str: str, dark_color: str = "#000000", light_color: str = "#ffffff") -> str:
        """
        Renders an authentic, 100% scannable ISO/IEC 18004 SVG QR Code.
        Fully compatible with iOS Camera, Android Google Lens, and WireGuard mobile apps.
        """
        try:
            import qrcode
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=4,
            )
            qr.add_data(data_str)
            qr.make(fit=True)
            matrix = qr.get_matrix()
            num_rows = len(matrix)
            box_size = 8
            svg_size = num_rows * box_size

            rects = []
            for r, row in enumerate(matrix):
                for c, val in enumerate(row):
                    if val:
                        rects.append(f'<rect x="{c * box_size}" y="{r * box_size}" width="{box_size}" height="{box_size}" fill="{dark_color}"/>')

            rects_str = "\n  ".join(rects)
            svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_size} {svg_size}" width="240" height="240" class="delusional-qr-svg">
  <rect width="100%" height="100%" fill="{light_color}" rx="6"/>
  {rects_str}
</svg>"""
            return svg
        except Exception as e:
            logger.error(f"QR code generation error: {e}")
            return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60"><text x="10" y="30" fill="red">QR Error: {e}</text></svg>'

    def generate_ascii_qr(self, data_str: str) -> str:
        """Renders an ASCII QR code for direct terminal rendering."""
        try:
            import qrcode
            import io
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=1,
                border=1,
            )
            qr.add_data(data_str)
            qr.make(fit=True)
            f = io.StringIO()
            qr.print_ascii(out=f, invert=True)
            return f.getvalue()
        except Exception as e:
            return f"QR Error: {e}"

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
