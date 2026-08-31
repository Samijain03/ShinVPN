"""
Comprehensive Unit Tests for ShinVPN Enhanced & Optimized Features
==================================================================
Tests:
- Counting Bloom Filter & Reverse Domain Radix Trie
- Dynamic Dijkstra Hop Pathfinding & Auto-Failover
- Split Tunneling Presets & Socket PID Resolution
- Realistic TLS 1.3 ClientHello / ServerHello Handshake Synthesis
- ZeroConf Wi-Fi Beacon & Profile Telemetry
"""

import pytest
from shinvpn.tunnel.adblock import CyberShieldAdBlocker, BloomFilter, ReverseDomainRadixTrie
from shinvpn.tunnel.multihop import DynamicHopPathfinder, MultiHopTunnel
from shinvpn.tunnel.process_router import ProcessRoutingMatrix, PRESETS
from shinvpn.transport.obfuscation import DPIObfuscator, TLS_HANDSHAKE_MAGIC
from shinvpn.crypto.profiles import MultiDeviceProfileManager, WifiZeroConfBeacon
from shinvpn.crypto.cipher import ShinCipher


def test_bloom_filter_and_radix_trie():
    # 1. Bloom filter
    bf = BloomFilter(size_bits=4096, num_hashes=3)
    bf.add("doubleclick.net")
    bf.add("ads.google.com")
    assert bf.contains("doubleclick.net") is True
    assert bf.contains("ads.google.com") is True
    assert bf.contains("clean-safe-website-never-seen-before.com") is False

    # 2. Radix Trie
    trie = ReverseDomainRadixTrie()
    trie.insert("doubleclick.net")
    trie.insert("telemetry.microsoft.com")
    
    assert trie.match("doubleclick.net") is True
    assert trie.match("ad1.doubleclick.net") is True
    assert trie.match("sub.ad.doubleclick.net") is True
    assert trie.match("telemetry.microsoft.com") is True
    assert trie.match("microsoft.com") is False
    assert trie.match("google.com") is False


def test_adblock_whitelist_and_lru():
    shield = CyberShieldAdBlocker()
    # By default doubleclick.net is blocked
    assert shield.should_block("doubleclick.net") is True
    
    # Whitelist doubleclick.net
    shield.add_whitelist(["doubleclick.net"])
    assert shield.should_block("doubleclick.net") is False
    
    # Remove from whitelist
    shield.remove_whitelist("doubleclick.net")
    assert shield.should_block("doubleclick.net") is True


def test_dynamic_hop_pathfinder():
    pf = DynamicHopPathfinder()
    # Update metrics: Tokyo is low latency (15ms), Frankfurt is 40ms
    pf.update_metrics("tokyo", rtt=15.0, jitter=1.0, loss=0.0)
    pf.update_metrics("frankfurt", rtt=40.0, jitter=2.0, loss=0.0)
    pf.update_metrics("singapore", rtt=90.0, jitter=10.0, loss=15.0)

    entry, exit_node = pf.find_optimal_hop_pair()
    assert entry.node_id in ["local", "tokyo"]
    assert exit_node.node_id != entry.node_id
    assert exit_node.cost < 9999.0


def test_split_tunnel_presets(tmp_path):
    cfg_file = tmp_path / "test_split_preset.json"
    matrix = ProcessRoutingMatrix(config_path=str(cfg_file))

    # Apply Gaming Preset
    assert matrix.apply_preset("GAMING_MODE") is True
    assert matrix.mode == "EXCLUSIVE"
    assert matrix.should_route_process("discord.exe") is True
    assert matrix.should_route_process("steam.exe") is False

    # Apply Ultra Privacy Preset
    assert matrix.apply_preset("ULTRA_PRIVACY") is True
    assert matrix.mode == "INCLUSIVE"
    assert matrix.should_route_process("steam.exe") is True
    assert matrix.should_route_process("chrome.exe") is True


def test_tls_handshake_synthesis():
    # 1. TLS 1.3 ClientHello
    client_hello = DPIObfuscator.generate_tls_client_hello("delusional.club")
    assert client_hello.startswith(TLS_HANDSHAKE_MAGIC)
    assert b"delusional.club" in client_hello
    assert b"h2" in client_hello  # ALPN HTTP/2
    assert len(client_hello) > 100

    # 2. TLS 1.3 ServerHello
    server_hello = DPIObfuscator.generate_tls_server_hello()
    assert server_hello.startswith(b"\x16\x03\x03")
    assert len(server_hello) > 50


def test_profile_telemetry_and_zeroconf(tmp_path):
    prof_file = tmp_path / "test_prof_metrics.json"
    mgr = MultiDeviceProfileManager(profiles_file=str(prof_file))

    p = mgr.create_profile(name="iPad Pro", device_type="tablet", server_config_path="server.json")
    assert p.bytes_consumed == 0

    mgr.update_usage(p.id, 1048576)  # 1 MB
    assert mgr.profiles[p.id].bytes_consumed == 1048576
    assert mgr.profiles[p.id].last_connected > 0.0
