"""
ShinVPN AEAD Cipher & Anti-Replay Protection
=============================================
Delusional Club Industries High-Throughput Authenticated Encryption.
Implements ChaCha20-Poly1305 (RFC 8439) with 64-bit monotonically incrementing
sequence numbers and a sliding-window replay filter.
"""

from __future__ import annotations
import struct
import threading
from typing import Tuple, Optional
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.exceptions import InvalidTag


class AntiReplayWindow:
    """
    Sliding window anti-replay protection.
    Maintains a 128-packet bitmask and the highest seen sequence number.
    Rejects duplicate packets and out-of-order packets falling behind the window.
    """

    def __init__(self, window_size: int = 128):
        self.window_size = window_size
        self.max_seq: int = 0
        self.bitmap: int = 0
        self._lock = threading.Lock()

    def check_and_update(self, seq: int) -> bool:
        """
        Validates if sequence number is fresh and updates the window.
        Returns True if packet is valid (not replayed), False if duplicate or too old.
        """
        with self._lock:
            if seq == 0:
                # Sequence 0 is reserved or initial
                return False

            if seq > self.max_seq:
                # Packet is ahead of current maximum
                diff = seq - self.max_seq
                if diff >= self.window_size:
                    self.bitmap = 1
                else:
                    self.bitmap = ((self.bitmap << diff) | 1) & ((1 << self.window_size) - 1)
                self.max_seq = seq
                return True

            diff = self.max_seq - seq
            if diff >= self.window_size:
                # Too old, outside replay window
                return False

            bit = 1 << diff
            if (self.bitmap & bit) != 0:
                # Already received (replay attack)
                return False

            # Valid in-window packet
            self.bitmap |= bit
            return True

    def reset(self) -> None:
        with self._lock:
            self.max_seq = 0
            self.bitmap = 0


class ShinCipher:
    """
    Session AEAD cipher engine.
    Handles encryption of outbound packets and decryption/verification of inbound packets
    using ChaCha20-Poly1305.
    """

    REKEY_BYTES_THRESHOLD: int = 1024 * 1024 * 1024  # 1 GB
    REKEY_PACKETS_THRESHOLD: int = 2**24             # 16.7M packets

    def __init__(self, key: bytes, session_id: int, is_initiator: bool = True):
        if len(key) != 32:
            raise ValueError(f"ChaCha20-Poly1305 key must be 32 bytes, got {len(key)}")
        self._aead = ChaCha20Poly1305(key)
        self.session_id = session_id
        self.is_initiator = is_initiator
        self._tx_seq: int = 0
        self._rx_replay = AntiReplayWindow(window_size=128)
        self._bytes_encrypted: int = 0
        self._bytes_decrypted: int = 0
        self._tx_lock = threading.Lock()

    @property
    def bytes_encrypted(self) -> int:
        return self._bytes_encrypted

    @property
    def bytes_decrypted(self) -> int:
        return self._bytes_decrypted

    @property
    def current_tx_seq(self) -> int:
        return self._tx_seq

    def should_rekey(self) -> bool:
        """Returns True if the session has reached safety rekey limits."""
        return (
            self._bytes_encrypted >= self.REKEY_BYTES_THRESHOLD
            or self._tx_seq >= self.REKEY_PACKETS_THRESHOLD
        )

    def _build_nonce(self, seq: int) -> bytes:
        """
        Builds a 12-byte nonce for ChaCha20-Poly1305:
        - 4 bytes: Session ID (little-endian)
        - 8 bytes: Sequence Number (little-endian)
        """
        return struct.pack("<IQ", self.session_id, seq)

    def encrypt(self, plaintext: bytes, associated_data: Optional[bytes] = None) -> Tuple[int, bytes]:
        """
        Encrypts a payload.
        Returns: (sequence_number, ciphertext_with_tag)
        """
        with self._tx_lock:
            self._tx_seq += 1
            seq = self._tx_seq
            nonce = self._build_nonce(seq)
            ciphertext = self._aead.encrypt(nonce, plaintext, associated_data)
            self._bytes_encrypted += len(ciphertext)
            return seq, ciphertext

    def decrypt(self, seq: int, ciphertext: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """
        Decrypts and authenticates a payload.
        Verifies anti-replay counter and ChaCha20-Poly1305 MAC tag.
        Raises InvalidTag or ValueError on failure.
        """
        if not self._rx_replay.check_and_update(seq):
            raise ValueError(f"Packet with seq {seq} rejected by anti-replay filter")

        nonce = self._build_nonce(seq)
        plaintext = self._aead.decrypt(nonce, ciphertext, associated_data)
        self._bytes_decrypted += len(ciphertext)
        return plaintext
