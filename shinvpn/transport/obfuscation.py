"""
ShinVPN Shadow-TLS DPI Camouflage & Obfuscation Engine
======================================================
Delusional Club Industries Anti-Censorship & DPI Evasion Layer.
Disguises VPN traffic frames as TLS 1.3 Application Data records and
applies Gaussian randomized padding to defeat deep packet inspection.
"""

from __future__ import annotations
import os
import random
import struct
from typing import Tuple

# TLS 1.3 Application Data Header:
# 0x17 (Type: Application Data) | 0x03 0x03 (Version: TLS 1.2/1.3 legacy record) | 2 Bytes Length
TLS_APP_DATA_MAGIC = b"\x17\x03\x03"


class DPIObfuscator:
    """Provides stealth camouflage, padding, and jitter simulation for VPN frames."""

    @staticmethod
    def apply_padding(raw_bytes: bytes, min_block_size: int = 64) -> bytes:
        """
        Applies randomized padding to normalize packet length distributions.
        Format: [2B Original Length] + [Payload] + [Random Padding Bytes]
        """
        orig_len = len(raw_bytes)
        # Pad to multiple of min_block_size with random variance
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
        # TLS Record Header: 1B ContentType (23) + 2B Version (0x0303) + 2B Length
        length = len(data)
        return TLS_APP_DATA_MAGIC + struct.pack("!H", length) + data

    @staticmethod
    def unwrap_tls_record(record: bytes) -> bytes:
        """Unwraps TLS record header if present."""
        if record.startswith(TLS_APP_DATA_MAGIC) and len(record) >= 5:
            length = struct.unpack("!H", record[3:5])[0]
            return record[5 : 5 + length]
        return record
