# ⚡ ShinVPN — Delusional Club Industries

<div align="center">

```
  ███████╗██╗  ██╗██╗███╗   ██╗██╗   ██╗██████╗ ███╗   ██╗
  ██╔════╝██║  ██║██║████╗  ██║██║   ██║██╔══██╗████╗  ██║
  ███████╗███████║██║██╔██╗ ██║██║   ██║██████╔╝██╔██╗ ██║
  ╚════██║██╔══██║██║██║╚██╗██║╚██╗ ██╔╝██╔═══╝ ██║╚██╗██║
  ███████║██║  ██║██║██║ ╚████║ ╚████╔╝ ██║     ██║ ╚████║
  ╚══════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝  ╚═══╝  ╚═╝     ╚═╝  ╚═══╝
```

**Next-Generation High-Throughput Encrypted VPN Suite**  
*Engineered by Delusional Club Industries*

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-9d4edd.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-00f5d4.svg)](LICENSE)
[![Crypto: X25519 + ChaCha20-Poly1305](https://img.shields.io/badge/Crypto-X25519%20%2B%20ChaCha20-ff0055.svg)]()
[![Build: Passing](https://img.shields.io/badge/Tests-Passing%20(11%2F11)-00f5d4.svg)]()

</div>

---

## 🌟 Overview

**ShinVPN** is a custom-engineered, educational, and high-performance VPN software suite developed for **Delusional Club Industries**. It bridges the gap between simple VPN configuration and deep networking engineering, incorporating modern cryptographic primitives, dual-engine tunneling, stealth traffic obfuscation, Windows firewall kill switch, DNS leak prevention, real-time telemetry, and a cyberpunk desktop GUI.

---

## 🚀 Key Features

* 🔐 **Modern Cryptography (Noise-Inspired)**:
  * **Key Agreement**: Ephemeral Curve25519 (X25519) Diffie-Hellman Key Exchange with zero-knowledge handshake.
  * **Key Derivation**: HKDF-SHA256 session key derivation with independent TX/RX keys.
  * **AEAD Transport**: Monotonically incrementing 64-bit sequence numbers authenticated via ChaCha20-Poly1305.
  * **Anti-Replay Filter**: 128-packet sliding bitmask rejecting duplicate and delayed packets.
* 🕳️ **Dual Tunneling Engine**:
  * **OS-Level L3 Interface**: Windows Wintun driver adapter and Linux `/dev/net/tun` for full raw IP routing.
  * **High-Speed Transparent Proxy Mode**: SOCKS5 + HTTP local gateway with automatic Windows System Proxy switching for instant execution without driver installation.
* 🛡️ **Stealth Camouflage Transport**:
  * Disguises VPN frames inside WebSocket/TLS streams with Delusional Club headers to bypass restrictive Deep Packet Inspection (DPI) and firewalls.
* 🛑 **Firewall Kill Switch & DNS Leak Shield**:
  * Windows Firewall (`netsh`) and Linux `iptables` rules enforcing zero-leak traffic policies upon connection drops.
  * Overrides DNS resolvers to Cloudflare (`1.1.1.1`) and disables Windows Multi-Homed DNS leakage.
* 📊 **Real-Time Telemetry & Cyberpunk Desktop GUI**:
  * Dark obsidian & neon violet/cyan aesthetics, interactive glowing connection ring, real-time Chart.js download/upload speedometers, ping latency gauge, session timers, server switcher, and live scrolling terminal console.
* 🖥️ **Unified CLI & Automation**:
  * Command-line suite (`shinvpn server`, `shinvpn client`, `shinvpn gui`, `shinvpn genkeys`, `shinvpn init-profiles`).
  * 1-click Linux VPS installer script (`scripts/deploy-vps.sh`) and Docker container support.

---

## 🏗️ Architecture

```
 ┌────────────────────────────────────────────────────────┐
 │      ShinVPN Client (Windows / Linux / macOS)          │
 │  ┌──────────────────────────────────────────────────┐  │
 │  │       Cyberpunk GUI / CLI (Delusional UI)        │  │
 │  └────────────────────────┬─────────────────────────┘  │
 │                           │ (IPC / WebSocket)          │
 │  ┌────────────────────────▼─────────────────────────┐  │
 │  │        ShinVPN Core Engine & State Machine       │  │
 │  │   - DNS Leak Shield    - Kill Switch (Firewall)  │  │
 │  │   - Reconnect Engine   - Telemetry Monitor       │  │
 │  └────────────────────────┬─────────────────────────┘  │
 │                           │                            │
 │  ┌────────────────────────▼─────────────────────────┐  │
 │  │     Tunnel Layer (Wintun / TUN / SOCKS Proxy)    │  │
 │  └────────────────────────┬─────────────────────────┘  │
 │                           │                            │
 │  ┌────────────────────────▼─────────────────────────┐  │
 │  │ Crypto & Framing (X25519 + ChaCha20-Poly1305)   │  │
 │  └────────────────────────┬─────────────────────────┘  │
 │                           │                            │
 │  ┌────────────────────────▼─────────────────────────┐  │
 │  │  Transport Layer: Encrypted UDP / Stealth HTTPS  │  │
 │  └────────────────────────┬─────────────────────────┘  │
 └───────────────────────────┼────────────────────────────┘
                             │ (Internet / VPS)
 ┌───────────────────────────▼────────────────────────────┐
 │       ShinVPN Server Daemon (Linux VPS / Docker)       │
 │  ┌──────────────────────────────────────────────────┐  │
 │  │ Crypto Unwrapping & Anti-Replay Verification     │  │
 │  └────────────────────────┬─────────────────────────┘  │
 │                           │                            │
 │  ┌────────────────────────▼─────────────────────────┐  │
 │  │   Virtual IP Pool (10.8.0.0/24) & Client Router  │  │
 │  └────────────────────────┬─────────────────────────┘  │
 │                           │                            │
 │  ┌────────────────────────▼─────────────────────────┐  │
 │  │   Linux TUN (/dev/net/tun) & NAT (iptables / IP) │  │
 │  └────────────────────────┬─────────────────────────┘  │
 │                           │                            │
 │                           ▼                            │
 │                    Target Internet                     │
 └────────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start

### 1. Installation

Clone and install dependencies:
```bash
git clone https://github.com/DelusionalClub/ShinVPN.git
cd ShinVPN
pip install -r requirements.txt
pip install -e .
```

### 2. Generate Pre-Linked Profiles
```bash
python -m shinvpn.cli.main init-profiles
```
This generates `server.json` and `client.json` pre-configured with keys and permissions.

### 3. Launch Server & Client

**Start Server:**
```bash
python -m shinvpn.cli.main server --config server.json
```

**Launch Cyberpunk Desktop GUI:**
```bash
python -m shinvpn.cli.main gui
# Or run scripts\run-gui.bat on Windows
```

**Or Run Terminal Client:**
```bash
python -m shinvpn.cli.main client --config client.json
```

---

## 🌐 Linux VPS Deployment

To deploy ShinVPN to a Linux VPS (Ubuntu/Debian) in 1 click:
```bash
sudo bash scripts/deploy-vps.sh
```
The script will:
1. Enable `net.ipv4.ip_forward=1`.
2. Configure `iptables` NAT masquerading.
3. Install ShinVPN daemon as a systemd service (`shinvpn-server.service`).
4. Generate `client.json` ready to transfer to your Windows PC.

---

## 🧪 Testing

Run the automated test suite covering crypto, protocol framing, and end-to-end loopback tunnels:
```bash
python -m pytest tests/ -v
```

---

## 📚 Technical Documentation

* [Architecture Deep Dive](docs/ARCHITECTURE.md)
* [Binary Protocol Specification](docs/PROTOCOL_SPEC.md)
* [VPS Deployment Guide](docs/DEPLOYMENT_GUIDE.md)

---

## 📄 License

MIT © [Delusional Club Industries](https://delusional.club)
