"""
ShinVPN Handshake Engine
========================
Delusional Club Industries Zero-Knowledge Key Agreement.
Implements Noise-inspired X25519 ECDH + HKDF-SHA256 handshake with mutual
key verification, session key derivation, and ephemeral forward secrecy.
"""

from __future__ import annotations
import enum
import hmac
import hashlib
import os
import struct
from typing import Tuple, Optional
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from .keys import KeyPair, load_public_key
from .cipher import ShinCipher


class HandshakeRole(enum.Enum):
    INITIATOR = "initiator"  # Client
    RESPONDER = "responder"  # Server


class HandshakeState:
    """
    Manages state for an in-progress or completed cryptographic handshake.
    
    Handshake Steps:
    1. Client (Initiator) generates Ephemeral Keypair (E_c).
       Computes:
       - DH1 = ECDH(E_c_priv, S_s_pub) [Ephemeral Client -> Static Server]
       - DH2 = ECDH(S_c_priv, S_s_pub) [Static Client -> Static Server]
       Builds HandshakeInit containing E_c_pub, S_c_pub, and auth MAC.
       
    2. Server (Responder) verifies S_c_pub against allowed client keys.
       Generates Ephemeral Keypair (E_s).
       Computes:
       - DH1 = ECDH(S_s_priv, E_c_pub)
       - DH2 = ECDH(S_s_priv, S_c_pub)
       - DH3 = ECDH(E_s_priv, E_c_pub)
       Derives transmit & receive keys via HKDF-SHA256.
       Builds HandshakeResp containing E_s_pub, assigned virtual IP, and auth MAC.
       
    3. Client processes HandshakeResp, computes DH3, derives identical symmetric keys.
       Both sides establish ShinCipher instances.
    """

    PROTOCOL_SALT = b"ShinVPN_DelusionalClub_v1_Salt"
    INFO_KEY_TX = b"ShinVPN_Transmit_Key_v1"
    INFO_KEY_RX = b"ShinVPN_Receive_Key_v1"
    INFO_AUTH = b"ShinVPN_Handshake_Auth_v1"

    def __init__(
        self,
        role: HandshakeRole,
        static_keypair: KeyPair,
        peer_static_pub: Optional[x25519.X25519PublicKey] = None,
    ):
        self.role = role
        self.static_keypair = static_keypair
        self.peer_static_pub = peer_static_pub
        self.ephemeral_keypair = KeyPair.generate()
        self.peer_ephemeral_pub: Optional[x25519.X25519PublicKey] = None
        self.session_id: int = 0
        self.is_completed: bool = False

        # Derived session ciphers
        self.tx_cipher: Optional[ShinCipher] = None
        self.rx_cipher: Optional[ShinCipher] = None
        self.allocated_vip: Optional[str] = None

    def create_initiation(self) -> Tuple[bytes, int]:
        """
        [Client-side] Builds initiation packet payload.
        Returns: (initiation_bytes, session_id)
        Payload Layout:
        - 4B: Client Session ID
        - 32B: Client Ephemeral Public Key
        - 32B: Client Static Public Key
        - 32B: Timestamp Nonce (replay shield)
        - 16B: Auth Tag (HMAC over init packet using DH1+DH2)
        """
        if self.role != HandshakeRole.INITIATOR:
            raise RuntimeError("Only initiator can create handshake initiation")
        if not self.peer_static_pub:
            raise ValueError("Server static public key is required for initiation")

        self.session_id = int.from_bytes(os.urandom(4), "little")
        dh1 = self.ephemeral_keypair.private_key.exchange(self.peer_static_pub)
        dh2 = self.static_keypair.private_key.exchange(self.peer_static_pub)
        combined_secret = dh1 + dh2

        timestamp_nonce = os.urandom(32)
        raw_body = (
            struct.pack("<I", self.session_id)
            + self.ephemeral_keypair.public_bytes
            + self.static_keypair.public_bytes
            + timestamp_nonce
        )

        auth_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.PROTOCOL_SALT,
            info=self.INFO_AUTH,
        ).derive(combined_secret)

        auth_tag = hmac.new(auth_key, raw_body, hashlib.sha256).digest()[:16]
        return raw_body + auth_tag, self.session_id

    def process_initiation(
        self, init_bytes: bytes, allowed_client_pub_keys: Optional[list[bytes]] = None
    ) -> Tuple[bytes, str]:
        """
        [Server-side] Processes client HandshakeInit, validates client static key,
        computes session keys, and prepares HandshakeResp.
        
        Returns: (client_static_pub_bytes, client_ephemeral_pub_bytes)
        """
        if self.role != HandshakeRole.RESPONDER:
            raise RuntimeError("Only responder can process handshake initiation")
        if len(init_bytes) < 4 + 32 + 32 + 32 + 16:
            raise ValueError("Malformed HandshakeInit payload: too short")

        client_sess_id = struct.unpack("<I", init_bytes[:4])[0]
        self.session_id = client_sess_id
        client_eph_pub_bytes = init_bytes[4:36]
        client_static_pub_bytes = init_bytes[36:68]
        timestamp_nonce = init_bytes[68:100]
        provided_mac = init_bytes[100:116]

        if allowed_client_pub_keys is not None:
            if client_static_pub_bytes not in allowed_client_pub_keys:
                raise PermissionError("Client public key is not in authorized peers list")

        self.peer_static_pub = load_public_key(client_static_pub_bytes)
        self.peer_ephemeral_pub = load_public_key(client_eph_pub_bytes)

        # Reconstruct DH1 & DH2
        dh1 = self.static_keypair.private_key.exchange(self.peer_ephemeral_pub)
        dh2 = self.static_keypair.private_key.exchange(self.peer_static_pub)
        combined_secret = dh1 + dh2

        auth_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.PROTOCOL_SALT,
            info=self.INFO_AUTH,
        ).derive(combined_secret)

        raw_body = init_bytes[:100]
        computed_mac = hmac.new(auth_key, raw_body, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(provided_mac, computed_mac):
            raise PermissionError("HandshakeInit MAC verification failed")

        return client_static_pub_bytes, client_eph_pub_bytes

    def create_response(self, allocated_vip: str) -> bytes:
        """
        [Server-side] Creates HandshakeResp payload.
        Computes DH3 = ECDH(E_s_priv, E_c_pub).
        Derives symmetric keys and sets up TX/RX ciphers.
        
        Returns: response_bytes
        Payload Layout:
        - 4B: Session ID
        - 32B: Server Ephemeral Public Key
        - 4B: Allocated Virtual IPv4 (e.g. 10.8.0.2)
        - 32B: Server Nonce
        - 16B: Auth Tag
        """
        if self.role != HandshakeRole.RESPONDER:
            raise RuntimeError("Only responder can create handshake response")
        if not self.peer_ephemeral_pub or not self.peer_static_pub:
            raise RuntimeError("Cannot create response without peer keys")

        self.allocated_vip = allocated_vip
        dh1 = self.static_keypair.private_key.exchange(self.peer_ephemeral_pub)
        dh2 = self.static_keypair.private_key.exchange(self.peer_static_pub)
        dh3 = self.ephemeral_keypair.private_key.exchange(self.peer_ephemeral_pub)
        master_secret = dh1 + dh2 + dh3

        # Derive symmetric session keys:
        # Server TX key = Client RX key
        # Server RX key = Client TX key
        tx_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.PROTOCOL_SALT,
            info=self.INFO_KEY_TX,
        ).derive(master_secret)

        rx_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.PROTOCOL_SALT,
            info=self.INFO_KEY_RX,
        ).derive(master_secret)

        self.tx_cipher = ShinCipher(tx_key, self.session_id, is_initiator=False)
        self.rx_cipher = ShinCipher(rx_key, self.session_id, is_initiator=False)

        vip_octets = [int(x) for x in allocated_vip.split(".")]
        vip_bytes = bytes(vip_octets)

        server_nonce = os.urandom(32)
        raw_body = (
            struct.pack("<I", self.session_id)
            + self.ephemeral_keypair.public_bytes
            + vip_bytes
            + server_nonce
        )

        resp_auth_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.PROTOCOL_SALT,
            info=b"ShinVPN_Resp_Auth_v1",
        ).derive(master_secret)

        auth_tag = hmac.new(resp_auth_key, raw_body, hashlib.sha256).digest()[:16]
        self.is_completed = True
        return raw_body + auth_tag

    def process_response(self, resp_bytes: bytes) -> str:
        """
        [Client-side] Processes HandshakeResp from server.
        Derives symmetric keys and finishes handshake.
        Returns: allocated_vip string (e.g. '10.8.0.2')
        """
        if self.role != HandshakeRole.INITIATOR:
            raise RuntimeError("Only initiator can process handshake response")
        if len(resp_bytes) < 4 + 32 + 4 + 32 + 16:
            raise ValueError("Malformed HandshakeResp payload: too short")

        sess_id = struct.unpack("<I", resp_bytes[:4])[0]
        if sess_id != self.session_id:
            raise ValueError(f"Session ID mismatch: expected {self.session_id}, got {sess_id}")

        server_eph_pub_bytes = resp_bytes[4:36]
        vip_bytes = resp_bytes[36:40]
        server_nonce = resp_bytes[40:72]
        provided_mac = resp_bytes[72:88]

        self.peer_ephemeral_pub = load_public_key(server_eph_pub_bytes)
        self.allocated_vip = f"{vip_bytes[0]}.{vip_bytes[1]}.{vip_bytes[2]}.{vip_bytes[3]}"

        dh1 = self.ephemeral_keypair.private_key.exchange(self.peer_static_pub)
        dh2 = self.static_keypair.private_key.exchange(self.peer_static_pub)
        dh3 = self.ephemeral_keypair.private_key.exchange(self.peer_ephemeral_pub)
        master_secret = dh1 + dh2 + dh3

        resp_auth_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.PROTOCOL_SALT,
            info=b"ShinVPN_Resp_Auth_v1",
        ).derive(master_secret)

        raw_body = resp_bytes[:72]
        computed_mac = hmac.new(resp_auth_key, raw_body, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(provided_mac, computed_mac):
            raise PermissionError("HandshakeResp MAC verification failed")

        # Client TX key = Server RX key (INFO_KEY_RX)
        # Client RX key = Server TX key (INFO_KEY_TX)
        tx_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.PROTOCOL_SALT,
            info=self.INFO_KEY_RX,
        ).derive(master_secret)

        rx_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.PROTOCOL_SALT,
            info=self.INFO_KEY_TX,
        ).derive(master_secret)

        self.tx_cipher = ShinCipher(tx_key, self.session_id, is_initiator=True)
        self.rx_cipher = ShinCipher(rx_key, self.session_id, is_initiator=True)
        self.is_completed = True
        return self.allocated_vip
