# 🏛️ ShinVPN Architecture Deep-Dive
*Delusional Club Industries Engineering Whitepaper*

---

## 1. System Philosophy

ShinVPN is designed to deliver military-grade forward secrecy, low-latency datagram tunneling, and resilient censorship evasion while keeping the codebase modular and readable.

The system is partitioned into 5 core layers:
1. **Cryptographic Engine** (`shinvpn.crypto`)
2. **Binary Framing & Protocol** (`shinvpn.protocol`)
3. **Transport Layer** (`shinvpn.transport`)
4. **Tunnel & OS Routing Engine** (`shinvpn.tunnel`)
5. **Application & GUI Tier** (`shinvpn.gui`, `shinvpn.cli`)

---

## 2. Cryptographic Security Model

ShinVPN adheres to the **Noise Protocol Framework** principles:
- **Zero Inventions**: All algorithms are standard primitives from RFC 7748 (Curve25519), RFC 5869 (HKDF), and RFC 8439 (ChaCha20-Poly1305).
- **Ephemeral Forward Secrecy**: Every handshake generates fresh ephemeral keypairs $(E_c, E_s)$. Even if long-term static private keys are compromised in the future, past session traffic remains mathematically undecryptable.
- **Mutual Authenticity**: The server strictly checks the client's static public key before granting IP allocation or routing tunnel traffic.

### Handshake Key Derivation Graph:

$$\text{DH1} = \text{X25519}(E_{c\text{-priv}}, S_{s\text{-pub}})$$
$$\text{DH2} = \text{X25519}(S_{c\text{-priv}}, S_{s\text{-pub}})$$
$$\text{DH3} = \text{X25519}(E_{c\text{-priv}}, E_{s\text{-pub}})$$

$$\text{Master Secret} = \text{DH1} \parallel \text{DH2} \parallel \text{DH3}$$

$$\begin{aligned}
K_{\text{tx}}^{\text{client}} = K_{\text{rx}}^{\text{server}} &= \text{HKDF-SHA256}(\text{Master Secret}, \text{"ShinVPN\_Receive\_Key\_v1"}) \\
K_{\text{rx}}^{\text{client}} = K_{\text{tx}}^{\text{server}} &= \text{HKDF-SHA256}(\text{Master Secret}, \text{"ShinVPN\_Transmit\_Key\_v1"})
\end{aligned}$$

---

## 3. Dual-Engine Tunneling Architecture

```
                       ┌────────────────────────┐
                       │ User Application Traffic│
                       └───────────┬────────────┘
                                   │
                ┌──────────────────┴──────────────────┐
                ▼                                     ▼
     [Driver-Level Mode]                    [Zero-Driver Mode]
   Windows Wintun / Linux TUN             Local SOCKS5 / System Proxy
 (Raw L3 IPv4/IPv6 IP Packets)           (Multiplexed TCP/UDP Streams)
                │                                     │
                └──────────────────┬──────────────────┘
                                   │
                                   ▼
                       [ShinVPN Cryptographic AEAD]
                        ChaCha20-Poly1305 + Nonces
                                   │
                ┌──────────────────┴──────────────────┐
                ▼                                     ▼
      [Datagram Transport]                   [Stealth Camouflage]
      Direct Low-Latency UDP               Obfuscated WebSocket / TLS
      (Port 51820)                         (Port 8443 / DPI Bypass)
```

### Modes Breakdown:
1. **Wintun / Linux TUN**:
   - Opens a virtual network interface adapter.
   - Assigns a `/24` subnet Virtual IP (e.g. `10.8.0.2`).
   - Replaces system default route with split subnets `0.0.0.0/1` and `128.0.0.0/1`.
2. **Transparent SOCKS5 / System Proxy**:
   - Starts an internal high-speed SOCKS5 gateway on `127.0.0.1:10808`.
   - Modifies Windows WinINet internet settings automatically.
   - Encapsulates TCP connection requests into lightweight binary proxy multiplex frames (`MSG_PROXY_CONNECT`, `MSG_PROXY_DATA`, `MSG_PROXY_CLOSE`), enabling immediate VPN functionality without driver installation.

---

## 4. Kill Switch & Leak Prevention State Machine

To guarantee zero IP/DNS leaks:
1. **Firewall Rules Injection**: Upon connecting, the `KillSwitch` configures Windows Firewall (`netsh`) or Linux `iptables` with a default `DROP` / `Block_All` outbound rule.
2. **Explicit Whitelists**:
   - Local Loopback (`127.0.0.0/8`, `::1`)
   - Local LAN (`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`)
   - Direct ShinVPN Server IP & UDP port
   - Virtual TUN Network Adapter
3. **Emergency Disconnection Handling**: If the remote server socket dies, the client enters `RECONNECTING` state while maintaining active firewall blocks, preventing plain traffic leakage.
