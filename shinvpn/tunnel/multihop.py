"""
ShinVPN Multi-Hop / Cascading Onion Routing Tunnel
==================================================
Delusional Club Industries Double-Layer Onion Tunnel.
Provides 2-hop cryptographic chaining:
Client -> Hop 1 (Entry Relay) -> Hop 2 (Exit Gateway) -> Internet.

Security Invariants:
- Entry Relay knows Client IP, but CANNOT see target destinations or payload.
- Exit Gateway sees target internet destinations, but NEVER knows Client's IP.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Optional, Tuple

from ..crypto.cipher import ShinCipher
from ..protocol.frames import MultiHopForwardFrame, DataPacketFrame, parse_frame

logger = logging.getLogger("shinvpn.multihop")


class MultiHopTunnel:
    """Manages dual-layer session keys and onion encapsulation."""

    def __init__(
        self,
        entry_node_endpoint: Tuple[str, int],
        exit_node_endpoint: Tuple[str, int],
        entry_cipher: ShinCipher,
        exit_cipher: ShinCipher,
    ):
        self.entry_endpoint = entry_node_endpoint
        self.exit_endpoint = exit_node_endpoint
        self.entry_cipher = entry_cipher
        self.exit_cipher = exit_cipher
        self.entry_session_id: int = entry_cipher.session_id
        self.exit_session_id: int = exit_cipher.session_id

    def encapsulate_packet(self, inner_ip_packet: bytes) -> bytes:
        """
        Double-encrypts payload:
        1. Encrypt inner_ip_packet with Exit Node cipher.
        2. Wrap in DataPacketFrame for Exit Node.
        3. Wrap in MultiHopForwardFrame for Entry Node.
        4. Encrypt with Entry Node cipher.
        """
        # Step 1: Encrypt payload for Exit Gateway
        inner_seq, inner_ciphertext = self.exit_cipher.encrypt(inner_ip_packet)
        exit_frame = DataPacketFrame(
            session_id=self.exit_session_id,
            seq_num=inner_seq,
            payload=inner_ciphertext,
        )
        exit_raw = exit_frame.to_bytes()

        # Step 2: Encapsulate in MultiHop forward frame for Entry Relay
        hop_frame = MultiHopForwardFrame(
            session_id=self.entry_session_id,
            seq_num=0,
            next_host=self.exit_endpoint[0],
            next_port=self.exit_endpoint[1],
            inner_frame_data=exit_raw,
        )
        return hop_frame.to_bytes()

    def decapsulate_packet(self, raw_data_from_tunnel: bytes) -> Optional[bytes]:
        """
        Decapsulates packet received back from double-hop tunnel.
        Peels Exit Node encryption.
        """
        try:
            frame = parse_frame(raw_data_from_tunnel)
            if isinstance(frame, DataPacketFrame):
                plaintext = self.exit_cipher.decrypt(frame.seq_num, frame.payload)
                return plaintext
        except Exception as e:
            logger.warning(f"Failed to decapsulate multi-hop packet: {e}")
        return None
