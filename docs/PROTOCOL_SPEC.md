# 📡 ShinVPN Binary Protocol Specification
*Delusional Club Industries Network Standard v1.0*

---

## 1. Frame Header Format

Every datagram transmitted over ShinVPN begins with a 20-byte fixed header in Network Byte Order (Big-Endian):

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Magic Bytes ("SHIN")                    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|    Version    |   Msg Type    |          Reserved             |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                          Session ID                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                    Sequence Number (64-bit)                   +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|         Payload Length        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### Field Definitions:
* `Magic Bytes` (4 Bytes): ASCII `"SHIN"` (`0x53 0x48 0x49 0x4E`).
* `Version` (1 Byte): Current version `0x01`.
* `Msg Type` (1 Byte): Type of frame (1-10).
* `Session ID` (4 Bytes): Random 32-bit unsigned identifier negotiated during handshake.
* `Sequence Number` (8 Bytes): Monotonically increasing counter for ChaCha20-Poly1305 nonce and anti-replay verification.
* `Payload Length` (2 Bytes): Length in bytes of the following payload (excluding header).

---

## 2. Message Types

| Value | Identifier | Description |
|---|---|---|
| `0x01` | `MSG_HANDSHAKE_INIT` | Client initiation packet |
| `0x02` | `MSG_HANDSHAKE_RESP` | Server response & VIP allocation |
| `0x03` | `MSG_DATA_PACKET` | Encrypted L3 IP datagram |
| `0x04` | `MSG_KEEPALIVE` | Heartbeat & RTT ping |
| `0x05` | `MSG_REKEY_INIT` | Key rotation request |
| `0x06` | `MSG_REKEY_RESP` | Key rotation response |
| `0x07` | `MSG_DISCONNECT` | Graceful session termination |
| `0x08` | `MSG_PROXY_CONNECT` | Multiplexed remote TCP socket open |
| `0x09` | `MSG_PROXY_DATA` | Multiplexed remote stream chunk |
| `0x0A` | `MSG_PROXY_CLOSE` | Multiplexed socket close signal |

---

## 3. Cryptographic Nonce Construction

For all ChaCha20-Poly1305 cipher operations, the 12-byte IV is deterministically constructed:

```
[Session ID: 4 Bytes (Little-Endian)] + [Sequence Number: 8 Bytes (Little-Endian)]
```

Because sequence numbers are strictly incremented per transmitted packet, IVs never repeat within a session lifetime.

---

## 4. Anti-Replay Sliding Window Algorithm

ShinVPN protects against replay attacks by maintaining a 128-packet bitmask window:
1. If packet sequence $S > S_{\text{max}}$:
   - Calculate $\Delta = S - S_{\text{max}}$.
   - If $\Delta \ge 128$: reset bitmask to $1$.
   - Else: shift bitmask left by $\Delta$ and set lowest bit.
   - Update $S_{\text{max}} = S$.
2. If packet sequence $S \le S_{\text{max}}$:
   - Calculate $\Delta = S_{\text{max}} - S$.
   - If $\Delta \ge 128$: reject packet (too old).
   - If bit $\Delta$ is already set: reject packet (duplicate/replayed).
   - Else: set bit $\Delta$ and accept packet.
