"""
Unit Tests for ShinVPN Cryptography Core
"""

import pytest
from shinvpn.crypto.keys import KeyPair, generate_keypair, load_private_key, load_public_key
from shinvpn.crypto.cipher import ShinCipher, AntiReplayWindow
from shinvpn.crypto.handshake import HandshakeState, HandshakeRole


def test_keypair_generation_and_export():
    kp = generate_keypair()
    assert len(kp.private_bytes) == 32
    assert len(kp.public_bytes) == 32
    assert len(kp.private_b64) > 40
    assert len(kp.public_b64) > 40

    # Test reconstruction
    loaded_priv = load_private_key(kp.private_b64)
    loaded_pub = load_public_key(kp.public_b64)
    kp_reloaded = KeyPair.from_private_b64(kp.private_b64)
    assert kp_reloaded.public_bytes == kp.public_bytes
    assert kp_reloaded.private_bytes == kp.private_bytes


def test_anti_replay_window():
    window = AntiReplayWindow(window_size=128)

    # Sequence 0 is invalid
    assert not window.check_and_update(0)

    # In-order sequence numbers
    assert window.check_and_update(1)
    assert window.check_and_update(2)
    assert window.check_and_update(3)

    # Duplicate rejection
    assert not window.check_and_update(2)
    assert not window.check_and_update(3)

    # Advance window
    assert window.check_and_update(100)
    # Still in window (100 - 95 < 128)
    assert window.check_and_update(95)
    # Duplicate
    assert not window.check_and_update(95)

    # Giant leap
    assert window.check_and_update(500)
    # Out of window (500 - 100 > 128)
    assert not window.check_and_update(100)
    assert not window.check_and_update(300)
    # Inside new window
    assert window.check_and_update(490)


def test_chacha20_poly1305_cipher():
    key = b"01234567890123456789012345678901"  # 32 bytes
    session_id = 0x12345678
    tx_cipher = ShinCipher(key, session_id, is_initiator=True)
    rx_cipher = ShinCipher(key, session_id, is_initiator=False)

    plaintext = b"DELUSIONAL_CLUB_SECRET_PACKET_PAYLOAD_1337"
    ad = b"ASSOCIATED_HEADER_DATA"

    seq, ciphertext = tx_cipher.encrypt(plaintext, associated_data=ad)
    assert seq == 1
    assert ciphertext != plaintext

    decrypted = rx_cipher.decrypt(seq, ciphertext, associated_data=ad)
    assert decrypted == plaintext

    # Tampered ciphertext must fail
    tampered = bytearray(ciphertext)
    tampered[-1] ^= 0x01
    with pytest.raises(Exception):
        rx_cipher.decrypt(2, bytes(tampered), associated_data=ad)


def test_handshake_state_machine():
    client_kp = generate_keypair()
    server_kp = generate_keypair()

    client_hs = HandshakeState(
        role=HandshakeRole.INITIATOR,
        static_keypair=client_kp,
        peer_static_pub=server_kp.public_key,
    )
    server_hs = HandshakeState(
        role=HandshakeRole.RESPONDER,
        static_keypair=server_kp,
    )

    # 1. Client creates initiation
    init_bytes, sess_id = client_hs.create_initiation()
    assert len(init_bytes) > 0
    assert sess_id != 0

    # 2. Server processes initiation
    c_static_bytes, c_eph_bytes = server_hs.process_initiation(
        init_bytes, allowed_client_pub_keys=[client_kp.public_bytes]
    )
    assert c_static_bytes == client_kp.public_bytes

    # 3. Server creates response
    target_vip = "10.8.0.42"
    resp_bytes = server_hs.create_response(target_vip)
    assert server_hs.is_completed

    # 4. Client processes response
    assigned_vip = client_hs.process_response(resp_bytes)
    assert assigned_vip == target_vip
    assert client_hs.is_completed

    # 5. Verify bidirectional encrypted communication
    msg_to_server = b"Hello ShinVPN Server!"
    seq_c, ct_c = client_hs.tx_cipher.encrypt(msg_to_server)
    dec_s = server_hs.rx_cipher.decrypt(seq_c, ct_c)
    assert dec_s == msg_to_server

    msg_to_client = b"Welcome to Delusional Club Tunnel."
    seq_s, ct_s = server_hs.tx_cipher.encrypt(msg_to_client)
    dec_c = client_hs.rx_cipher.decrypt(seq_s, ct_s)
    assert dec_c == msg_to_client
