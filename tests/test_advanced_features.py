"""
Comprehensive Unit Tests for ShinVPN Advanced Features
======================================================
Tests CyberShield AdBlocker, Shadow-TLS Obfuscation, Multi-Hop Double VPN,
Split Tunneling Matrix, and Mobile QR Profile Generation.
"""

import pytest
from shinvpn.tunnel.adblock import CyberShieldAdBlocker
from shinvpn.transport.obfuscation import DPIObfuscator
from shinvpn.tunnel.multihop import MultiHopTunnel
from shinvpn.tunnel.process_router import ProcessRoutingMatrix
from shinvpn.crypto.profiles import MultiDeviceProfileManager
from shinvpn.crypto.cipher import ShinCipher
from shinvpn.protocol.frames import MultiHopForwardFrame, parse_frame


def test_cybershield_adblocker():
    shield = CyberShieldAdBlocker(enable_adblock=True)
    
    # Known ad and telemetry domains must be blocked
    assert shield.should_block("doubleclick.net") is True
    assert shield.should_block("ad1.doubleclick.net") is True
    assert shield.should_block("google-analytics.com") is True
    assert shield.should_block("telemetry.microsoft.com") is True
    assert shield.should_block("coinhive.com") is True

    # Legitimate sites must NOT be blocked
    assert shield.should_block("google.com") is False
    assert shield.should_block("github.com") is False
    assert shield.should_block("delusional.club") is False

    # Stats counter
    stats = shield.get_stats()
    assert stats["blocked_queries_count"] >= 5
    assert stats["enabled"] is True

    # Custom rules
    shield.add_custom_rules(["custom-ad-tracker.xyz"])
    assert shield.should_block("custom-ad-tracker.xyz") is True
    assert shield.should_block("sub.custom-ad-tracker.xyz") is True


def test_shadow_tls_dpi_obfuscation():
    sample_payload = b"GET /vpn/stream HTTP/1.1\r\nHost: delusional.club\r\n\r\n"
    
    # 1. Padding
    padded = DPIObfuscator.apply_padding(sample_payload, min_block_size=64)
    assert len(padded) > len(sample_payload)
    
    unpadded = DPIObfuscator.remove_padding(padded)
    assert unpadded == sample_payload

    # 2. TLS 1.3 Record Wrapping
    tls_record = DPIObfuscator.wrap_tls_record(sample_payload)
    assert tls_record.startswith(b"\x17\x03\x03")
    
    unwrapped = DPIObfuscator.unwrap_tls_record(tls_record)
    assert unwrapped == sample_payload


def test_multihop_onion_tunnel():
    key_hop1 = b"\x01" * 32
    key_hop2 = b"\x02" * 32

    tunnel = MultiHopTunnel(
        entry_node_endpoint=("103.28.44.12", 51820),
        exit_node_endpoint=("45.142.112.5", 51820),
        entry_cipher=ShinCipher(key_hop1, session_id=101),
        exit_cipher=ShinCipher(key_hop2, session_id=202),
    )

    original_ip_packet = b"\x45\x00\x00\x3c\x1a\x2b\x00\x00\x40\x06\x00\x00" + b"A" * 40
    encapsulated = tunnel.encapsulate_packet(original_ip_packet)

    # Verify outer layer is a MultiHopForwardFrame
    outer_frame = parse_frame(encapsulated)
    assert isinstance(outer_frame, MultiHopForwardFrame)
    assert outer_frame.next_host == "45.142.112.5"
    assert outer_frame.next_port == 51820

    # Simulate exit node decapsulation
    exit_plaintext = tunnel.decapsulate_packet(outer_frame.inner_frame_data)
    assert exit_plaintext == original_ip_packet


def test_split_tunnel_process_matrix(tmp_path):
    cfg_file = tmp_path / "test_split.json"
    matrix = ProcessRoutingMatrix(config_path=str(cfg_file))

    # Test exclusive mode (only selected apps tunneled)
    matrix.set_rules(enabled=True, mode="EXCLUSIVE", app_list=["chrome.exe", "discord.exe"])
    assert matrix.should_route_process("chrome.exe") is True
    assert matrix.should_route_process("discord.exe") is True
    assert matrix.should_route_process("steam.exe") is False

    # Test inclusive mode (all apps tunneled except selected)
    matrix.set_rules(enabled=True, mode="INCLUSIVE", app_list=["steam.exe"])
    assert matrix.should_route_process("chrome.exe") is True
    assert matrix.should_route_process("steam.exe") is False


def test_mobile_profile_and_qr_generation(tmp_path):
    prof_file = tmp_path / "test_profiles.json"
    mgr = MultiDeviceProfileManager(profiles_file=str(prof_file))

    p = mgr.create_profile(name="Test Phone", device_type="phone", server_config_path="server.json")
    assert p.name == "Test Phone"
    assert p.allocated_vip.startswith("10.8.0.")
    assert len(p.public_key) > 20

    # WireGuard config generation
    wg_conf = mgr.generate_wireguard_conf(p.id, "127.0.0.1:51820", "SERVER_PUB_KEY")
    assert "[Interface]" in wg_conf
    assert "[Peer]" in wg_conf
    assert p.private_key in wg_conf

    # SVG QR code generation
    svg = mgr.generate_svg_qr(wg_conf)
    assert "<svg" in svg
    assert "viewBox" in svg
    assert "</svg>" in svg
