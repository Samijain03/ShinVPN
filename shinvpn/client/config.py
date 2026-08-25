"""
ShinVPN Client Configuration
============================
Delusional Club Industries Client Profile Management.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Union

from ..crypto.keys import KeyPair, generate_keypair
from ..protocol.constants import (
    DEFAULT_PORT_UDP,
    DEFAULT_PORT_STEALTH,
    DEFAULT_DNS_SERVERS,
    DEFAULT_MTU,
)


@dataclass
class ClientConfig:
    server_host: str = "127.0.0.1"
    udp_port: int = DEFAULT_PORT_UDP
    stealth_port: int = DEFAULT_PORT_STEALTH
    transport_type: str = "udp"  # "udp" or "stealth"
    client_private_key: str = ""
    client_public_key: str = ""
    server_public_key: str = ""
    enable_killswitch: bool = False
    enable_dns_shield: bool = True
    enable_system_proxy: bool = True
    local_proxy_port: int = 10808
    dns_servers: List[str] = field(default_factory=lambda: list(DEFAULT_DNS_SERVERS))
    mtu: int = DEFAULT_MTU

    @classmethod
    def generate_default(cls, server_pub_key: str = "") -> ClientConfig:
        kp = generate_keypair()
        return cls(
            client_private_key=kp.private_b64,
            client_public_key=kp.public_b64,
            server_public_key=server_pub_key,
        )

    @classmethod
    def load_from_file(cls, path: Union[str, Path]) -> ClientConfig:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Client config not found at {path}")
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(**data)

    def save_to_file(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
