"""
ShinVPN Server Configuration
============================
Delusional Club Industries Server Configuration Parser and Validator.
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
    DEFAULT_VIRTUAL_SUBNET,
    DEFAULT_SERVER_VIRTUAL_IP,
    DEFAULT_DNS_SERVERS,
    DEFAULT_MTU,
)


@dataclass
class AllowedPeer:
    name: str
    public_key: str
    allowed_ip: Optional[str] = None


@dataclass
class ServerConfig:
    listen_host: str = "0.0.0.0"
    udp_port: int = DEFAULT_PORT_UDP
    stealth_port: int = DEFAULT_PORT_STEALTH
    enable_stealth: bool = True
    private_key: str = ""
    public_key: str = ""
    virtual_subnet: str = DEFAULT_VIRTUAL_SUBNET
    server_virtual_ip: str = DEFAULT_SERVER_VIRTUAL_IP
    dns_servers: List[str] = field(default_factory=lambda: list(DEFAULT_DNS_SERVERS))
    mtu: int = DEFAULT_MTU
    allowed_peers: List[AllowedPeer] = field(default_factory=list)

    @classmethod
    def generate_default(cls) -> ServerConfig:
        kp = generate_keypair()
        cfg = cls(
            private_key=kp.private_b64,
            public_key=kp.public_b64,
        )
        return cfg

    @classmethod
    def load_from_file(cls, path: Union[str, Path]) -> ServerConfig:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Server config not found at {path}")
        data = json.loads(p.read_text(encoding="utf-8"))
        peers = [AllowedPeer(**p_data) for p_data in data.pop("allowed_peers", [])]
        return cls(allowed_peers=peers, **data)

    def save_to_file(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_peer(self, name: str, public_key: str, allowed_ip: Optional[str] = None) -> None:
        self.allowed_peers.append(AllowedPeer(name=name, public_key=public_key, allowed_ip=allowed_ip))
