"""
ShinVPN Key Management
======================
Delusional Club Industries Cryptographic Key Utilities.
Utilizes Curve25519 (X25519) Diffie-Hellman keys for asymmetric exchange.
"""

from __future__ import annotations
import base64
import os
from pathlib import Path
from typing import Tuple, Union
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization


class KeyPair:
    """Represents an X25519 keypair used for ShinVPN identity and ephemeral exchanges."""

    def __init__(self, private_key: x25519.X25519PrivateKey, public_key: x25519.X25519PublicKey | None = None):
        self._private_key = private_key
        self._public_key = public_key or private_key.public_key()

    @property
    def private_key(self) -> x25519.X25519PrivateKey:
        return self._private_key

    @property
    def public_key(self) -> x25519.X25519PublicKey:
        return self._public_key

    @property
    def private_bytes(self) -> bytes:
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )

    @property
    def public_bytes(self) -> bytes:
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

    @property
    def private_b64(self) -> str:
        return base64.b64encode(self.private_bytes).decode('ascii')

    @property
    def public_b64(self) -> str:
        return base64.b64encode(self.public_bytes).decode('ascii')

    def save_to_file(self, private_path: Union[str, Path], public_path: Union[str, Path] | None = None) -> None:
        """Saves the keypair to disk with secure permissions."""
        p_priv = Path(private_path)
        p_priv.parent.mkdir(parents=True, exist_ok=True)
        p_priv.write_text(self.private_b64.strip(), encoding="utf-8")
        if os.name != "nt":
            os.chmod(p_priv, 0o600)

        if public_path:
            p_pub = Path(public_path)
            p_pub.parent.mkdir(parents=True, exist_ok=True)
            p_pub.write_text(self.public_b64.strip(), encoding="utf-8")

    @classmethod
    def generate(cls) -> KeyPair:
        """Generates a fresh X25519 keypair."""
        priv = x25519.X25519PrivateKey.generate()
        return cls(priv)

    @classmethod
    def from_private_bytes(cls, raw: bytes) -> KeyPair:
        """Reconstructs keypair from 32 raw bytes."""
        if len(raw) != 32:
            raise ValueError(f"X25519 private key must be 32 bytes, got {len(raw)}")
        priv = x25519.X25519PrivateKey.from_private_bytes(raw)
        return cls(priv)

    @classmethod
    def from_private_b64(cls, b64_str: str) -> KeyPair:
        """Reconstructs keypair from base64 string."""
        raw = base64.b64decode(b64_str.strip())
        return cls.from_private_bytes(raw)

    @classmethod
    def load_from_file(cls, private_path: Union[str, Path]) -> KeyPair:
        """Loads a keypair from a private key file."""
        content = Path(private_path).read_text(encoding="utf-8").strip()
        return cls.from_private_b64(content)


def generate_keypair() -> KeyPair:
    """Convenience factory for key generation."""
    return KeyPair.generate()


def load_private_key(raw_or_b64: Union[bytes, str]) -> x25519.X25519PrivateKey:
    """Loads an X25519 private key from bytes or base64."""
    if isinstance(raw_or_b64, str):
        raw = base64.b64decode(raw_or_b64.strip())
    else:
        raw = raw_or_b64
    if len(raw) != 32:
        raise ValueError(f"Invalid private key length: {len(raw)} bytes (expected 32)")
    return x25519.X25519PrivateKey.from_private_bytes(raw)


def load_public_key(raw_or_b64: Union[bytes, str]) -> x25519.X25519PublicKey:
    """Loads an X25519 public key from bytes or base64."""
    if isinstance(raw_or_b64, str):
        raw = base64.b64decode(raw_or_b64.strip())
    else:
        raw = raw_or_b64
    if len(raw) != 32:
        raise ValueError(f"Invalid public key length: {len(raw)} bytes (expected 32)")
    return x25519.X25519PublicKey.from_public_bytes(raw)
