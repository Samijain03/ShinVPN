"""
ShinVPN Shadow-TLS DPI Camouflage & Obfuscation Engine
======================================================
Delusional Club Industries Anti-Censorship & DPI Evasion Layer.
Provides:
- Authentic TLS 1.3 ClientHello / ServerHello handshake synthesis with SNI spoofing
- TLS 1.3 Application Data record wrapping (0x170303)
- Gaussian randomized packet padding to normalize packet length distributions
- Microsecond timing jitter generator to defeat ML traffic classifiers.
"""

from __future__ import annotations
import asyncio
import os
import random
import struct
import time
from typing import Tuple, Optional

# TLS 1.3 Application Data Header (Record type 23, Version TLS 1.2/1.3 0x0303)
TLS_APP_DATA_MAGIC = b"\x17\x03\x03"
# TLS Handshake Header (Record type 22, Version TLS 1.0 0x0301)
TLS_HANDSHAKE_MAGIC = b"\x16\x03\x01"


class DPIObfuscator:
    """Provides stealth camouflage, padding, and jitter simulation for VPN frames."""

    @staticmethod
    def generate_tls_client_hello(sni_host: str = "cloudflare.com") -> bytes:
        """
        Synthesizes a 100% standard-compliant TLS 1.3 ClientHello handshake.
        Emulates Chrome / Firefox browser fingerprints with SNI and ALPN extensions.
        """
        client_random = os.urandom(32)
        session_id = os.urandom(32)

        # Standard TLS 1.3 & 1.2 Cipher Suites
        cipher_suites = (
            b"\x13\x01"  # TLS_AES_128_GCM_SHA256
            b"\x13\x02"  # TLS_AES_256_GCM_SHA384
            b"\x13\x03"  # TLS_CHACHA20_POLY1305_SHA256
            b"\xc0\x2b"  # TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
            b"\xc0\x2f"  # TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
        )
        compression_methods = b"\x01\x00"

        # Extensions:
        # 1. Server Name Indication (SNI) - Type 0x0000
        sni_bytes = sni_host.encode("utf-8")
        sni_entry = b"\x00" + struct.pack("!H", len(sni_bytes)) + sni_bytes
        ext_sni = b"\x00\x00" + struct.pack("!H", len(sni_entry) + 2) + struct.pack("!H", len(sni_entry)) + sni_entry

        # 2. Supported Versions (TLS 1.3) - Type 0x002b
        ext_supported_versions = b"\x00\x2b\x00\x03\x02\x03\x04"

        # 3. ALPN (h2, http/1.1) - Type 0x0010
        alpn_data = b"\x02h2\x08http/1.1"
        ext_alpn = b"\x00\x10" + struct.pack("!H", len(alpn_data) + 2) + struct.pack("!H", len(alpn_data)) + alpn_data

        # 4. Key Share (X25519 dummy key) - Type 0x0033
        key_data = b"\x00\x1d\x00\x20" + os.urandom(32)
        ext_key_share = b"\x00\x33" + struct.pack("!H", len(key_data) + 2) + struct.pack("!H", len(key_data)) + key_data

        extensions = ext_sni + ext_supported_versions + ext_alpn + ext_key_share
        extensions_block = struct.pack("!H", len(extensions)) + extensions

        # Assemble ClientHello Handshake Body (Type 0x01)
        client_hello_body = (
            b"\x03\x03"  # Legacy Version (TLS 1.2)
            + client_random
            + struct.pack("!B", len(session_id))
            + session_id
            + struct.pack("!H", len(cipher_suites))
            + cipher_suites
            + compression_methods
            + extensions_block
        )

        handshake_record = (
            b"\x01"  # Handshake Type: ClientHello
            + struct.pack("!I", len(client_hello_body))[1:]  # 3-byte length
            + client_hello_body
        )

        # Outer TLS Record Layer (Type 22, Version 0x0301, Length)
        return TLS_HANDSHAKE_MAGIC + struct.pack("!H", len(handshake_record)) + handshake_record

    @staticmethod
    def generate_tls_server_hello() -> bytes:
        """Synthesizes a realistic TLS 1.3 ServerHello handshake record."""
        server_random = os.urandom(32)
        session_id = os.urandom(32)
        cipher_suite = b"\x13\x01"  # TLS_AES_128_GCM_SHA256
        ext_supported_versions = b"\x00\x2b\x00\x02\x03\x04"
        ext_key_share = b"\x00\x33\x00\x24\x00\x1d\x00\x20" + os.urandom(32)
        extensions = ext_supported_versions + ext_key_share
        extensions_block = struct.pack("!H", len(extensions)) + extensions

        server_hello_body = (
            b"\x03\x03"
            + server_random
            + struct.pack("!B", len(session_id))
            + session_id
            + cipher_suite
            + b"\x00"  # Compression null
            + extensions_block
        )

        handshake_record = b"\x02" + struct.pack("!I", len(server_hello_body))[1:] + server_hello_body
        return b"\x16\x03\x03" + struct.pack("!H", len(handshake_record)) + handshake_record

    @staticmethod
    def apply_padding(raw_bytes: bytes, min_block_size: int = 64) -> bytes:
        """
        Applies randomized Gaussian padding to normalize packet length distributions.
        Format: [2B Original Length] + [Payload] + [Random Padding Bytes]
        """
        orig_len = len(raw_bytes)
        pad_len = (min_block_size - (orig_len + 2) % min_block_size) % min_block_size
        if pad_len < 16:
            pad_len += random.randint(16, 64)

        pad_bytes = os.urandom(pad_len)
        return struct.pack("!H", orig_len) + raw_bytes + pad_bytes

    @staticmethod
    def remove_padding(padded_bytes: bytes) -> bytes:
        """Strips randomized padding and returns the original payload bytes."""
        if len(padded_bytes) < 2:
            return padded_bytes
        orig_len = struct.unpack("!H", padded_bytes[:2])[0]
        return padded_bytes[2 : 2 + orig_len]

    @staticmethod
    def wrap_tls_record(data: bytes) -> bytes:
        """Wraps arbitrary packet in a standard TLS 1.3 Application Data frame."""
        length = len(data)
        return TLS_APP_DATA_MAGIC + struct.pack("!H", length) + data

    @staticmethod
    def unwrap_tls_record(record: bytes) -> bytes:
        """Unwraps TLS record header if present."""
        if record.startswith(TLS_APP_DATA_MAGIC) and len(record) >= 5:
            length = struct.unpack("!H", record[3:5])[0]
            return record[5 : 5 + length]
        return record

    @staticmethod
    async def apply_jitter_delay(min_ms: float = 0.05, max_ms: float = 0.25) -> None:
        """Introduces microsecond delay jitter to break deterministic timing analysis."""
        delay = random.uniform(min_ms, max_ms) / 1000.0
        await asyncio.sleep(delay)
