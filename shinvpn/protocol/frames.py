"""
ShinVPN Frame Encoder & Decoder
===============================
Delusional Club Industries Binary Packet Framing.
Provides binary serialization and deserialization for all protocol frames.
"""

from __future__ import annotations
import struct
import time
from dataclasses import dataclass
from typing import Optional, Tuple, Union

from .constants import (
    MAGIC_BYTES,
    PROTOCOL_VERSION,
    MSG_HANDSHAKE_INIT,
    MSG_HANDSHAKE_RESP,
    MSG_DATA_PACKET,
    MSG_KEEPALIVE,
    MSG_REKEY_INIT,
    MSG_REKEY_RESP,
    MSG_DISCONNECT,
    MSG_PROXY_CONNECT,
    MSG_PROXY_DATA,
    MSG_PROXY_CLOSE,
    MSG_SPEEDTEST_REQ,
    MSG_SPEEDTEST_DATA,
    MSG_MULTIHOP_FORWARD,
)

# Header format:
# !4s (Magic: "SHIN")
# B   (Version: 1)
# B   (Msg Type: 1-10)
# I   (Session ID: 4 bytes)
# Q   (Sequence Number: 8 bytes)
# H   (Payload Length: 2 bytes)
HEADER_FORMAT = "!4sBBIQH"
HEADER_LEN = struct.calcsize(HEADER_FORMAT)  # 20 bytes


@dataclass
class FrameHeader:
    version: int
    msg_type: int
    session_id: int
    seq_num: int
    payload_len: int

    def pack(self) -> bytes:
        return struct.pack(
            HEADER_FORMAT,
            MAGIC_BYTES,
            self.version,
            self.msg_type,
            self.session_id,
            self.seq_num,
            self.payload_len,
        )

    @classmethod
    def unpack(cls, data: bytes) -> FrameHeader:
        if len(data) < HEADER_LEN:
            raise ValueError(f"Data too short for ShinVPN header: {len(data)} < {HEADER_LEN}")
        magic, ver, msg_type, sess_id, seq, payload_len = struct.unpack(
            HEADER_FORMAT, data[:HEADER_LEN]
        )
        if magic != MAGIC_BYTES:
            raise ValueError(f"Invalid magic bytes: {magic!r}")
        if ver != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported protocol version: {ver}")
        return cls(
            version=ver,
            msg_type=msg_type,
            session_id=sess_id,
            seq_num=seq,
            payload_len=payload_len,
        )


class ShinFrame:
    """Base class for all ShinVPN protocol frames."""

    msg_type: int = 0

    def __init__(self, session_id: int = 0, seq_num: int = 0, payload: bytes = b""):
        self.session_id = session_id
        self.seq_num = seq_num
        self.payload = payload

    def to_bytes(self) -> bytes:
        header = FrameHeader(
            version=PROTOCOL_VERSION,
            msg_type=self.msg_type,
            session_id=self.session_id,
            seq_num=self.seq_num,
            payload_len=len(self.payload),
        )
        return header.pack() + self.payload

    @classmethod
    def from_header_and_payload(cls, header: FrameHeader, payload: bytes) -> ShinFrame:
        return cls(session_id=header.session_id, seq_num=header.seq_num, payload=payload)


class HandshakeInitFrame(ShinFrame):
    msg_type = MSG_HANDSHAKE_INIT


class HandshakeRespFrame(ShinFrame):
    msg_type = MSG_HANDSHAKE_RESP


class DataPacketFrame(ShinFrame):
    msg_type = MSG_DATA_PACKET


class KeepAliveFrame(ShinFrame):
    msg_type = MSG_KEEPALIVE

    def __init__(self, session_id: int = 0, seq_num: int = 0, timestamp: Optional[float] = None, payload: bytes = b""):
        if not payload:
            ts = timestamp if timestamp is not None else time.time()
            payload = struct.pack("!d", ts)
        super().__init__(session_id=session_id, seq_num=seq_num, payload=payload)

    @property
    def timestamp(self) -> float:
        if len(self.payload) >= 8:
            return struct.unpack("!d", self.payload[:8])[0]
        return 0.0


class RekeyInitFrame(ShinFrame):
    msg_type = MSG_REKEY_INIT


class RekeyRespFrame(ShinFrame):
    msg_type = MSG_REKEY_RESP


class DisconnectFrame(ShinFrame):
    msg_type = MSG_DISCONNECT


class ProxyConnectFrame(ShinFrame):
    msg_type = MSG_PROXY_CONNECT

    def __init__(self, session_id: int = 0, seq_num: int = 0, conn_id: int = 0, host: str = "", port: int = 0, payload: bytes = b""):
        if not payload:
            host_bytes = host.encode("utf-8")
            payload = struct.pack("!IH", conn_id, port) + struct.pack("!H", len(host_bytes)) + host_bytes
        super().__init__(session_id=session_id, seq_num=seq_num, payload=payload)

    @property
    def conn_id(self) -> int:
        return struct.unpack("!IH", self.payload[:6])[0]

    @property
    def port(self) -> int:
        return struct.unpack("!IH", self.payload[:6])[1]

    @property
    def host(self) -> str:
        h_len = struct.unpack("!H", self.payload[6:8])[0]
        return self.payload[8:8+h_len].decode("utf-8")


class ProxyDataFrame(ShinFrame):
    msg_type = MSG_PROXY_DATA

    def __init__(self, session_id: int = 0, seq_num: int = 0, conn_id: int = 0, raw_data: bytes = b"", payload: bytes = b""):
        if not payload:
            payload = struct.pack("!I", conn_id) + raw_data
        super().__init__(session_id=session_id, seq_num=seq_num, payload=payload)

    @property
    def conn_id(self) -> int:
        return struct.unpack("!I", self.payload[:4])[0]

    @property
    def raw_data(self) -> bytes:
        return self.payload[4:]


class ProxyCloseFrame(ShinFrame):
    msg_type = MSG_PROXY_CLOSE

    def __init__(self, session_id: int = 0, seq_num: int = 0, conn_id: int = 0, payload: bytes = b""):
        if not payload:
            payload = struct.pack("!I", conn_id)
        super().__init__(session_id=session_id, seq_num=seq_num, payload=payload)

    @property
    def conn_id(self) -> int:
        return struct.unpack("!I", self.payload[:4])[0]


class SpeedtestReqFrame(ShinFrame):
    msg_type = MSG_SPEEDTEST_REQ

    def __init__(self, session_id: int = 0, seq_num: int = 0, probe_id: int = 0, chunk_count: int = 10, chunk_size: int = 1024, payload: bytes = b""):
        if not payload:
            payload = struct.pack("!III", probe_id, chunk_count, chunk_size)
        super().__init__(session_id=session_id, seq_num=seq_num, payload=payload)

    @property
    def probe_id(self) -> int:
        return struct.unpack("!III", self.payload[:12])[0]

    @property
    def chunk_count(self) -> int:
        return struct.unpack("!III", self.payload[:12])[1]

    @property
    def chunk_size(self) -> int:
        return struct.unpack("!III", self.payload[:12])[2]


class SpeedtestDataFrame(ShinFrame):
    msg_type = MSG_SPEEDTEST_DATA

    def __init__(self, session_id: int = 0, seq_num: int = 0, probe_id: int = 0, chunk_idx: int = 0, data_block: bytes = b"", payload: bytes = b""):
        if not payload:
            payload = struct.pack("!II", probe_id, chunk_idx) + data_block
        super().__init__(session_id=session_id, seq_num=seq_num, payload=payload)

    @property
    def probe_id(self) -> int:
        return struct.unpack("!II", self.payload[:8])[0]

    @property
    def chunk_idx(self) -> int:
        return struct.unpack("!II", self.payload[:8])[1]

    @property
    def data_block(self) -> bytes:
        return self.payload[8:]


class MultiHopForwardFrame(ShinFrame):
    """
    Onion Encapsulated Multi-Hop Frame.
    Hop 1 peels outer layer and forwards inner_frame to target_endpoint (e.g. Hop 2).
    Format: [1B HostLen] [Host] [2B Port] [Inner Encrypted Frame]
    """
    msg_type = MSG_MULTIHOP_FORWARD

    def __init__(self, session_id: int = 0, seq_num: int = 0, next_host: str = "", next_port: int = 0, inner_frame_data: bytes = b"", payload: bytes = b""):
        if not payload:
            host_b = next_host.encode("utf-8")
            payload = struct.pack("!B", len(host_b)) + host_b + struct.pack("!H", next_port) + inner_frame_data
        super().__init__(session_id=session_id, seq_num=seq_num, payload=payload)

    @property
    def next_host(self) -> str:
        hlen = self.payload[0]
        return self.payload[1 : 1 + hlen].decode("utf-8", errors="replace")

    @property
    def next_port(self) -> int:
        hlen = self.payload[0]
        return struct.unpack("!H", self.payload[1 + hlen : 3 + hlen])[0]

    @property
    def inner_frame_data(self) -> bytes:
        hlen = self.payload[0]
        return self.payload[3 + hlen :]


FRAME_TYPE_MAP = {
    MSG_HANDSHAKE_INIT: HandshakeInitFrame,
    MSG_HANDSHAKE_RESP: HandshakeRespFrame,
    MSG_DATA_PACKET: DataPacketFrame,
    MSG_KEEPALIVE: KeepAliveFrame,
    MSG_REKEY_INIT: RekeyInitFrame,
    MSG_REKEY_RESP: RekeyRespFrame,
    MSG_DISCONNECT: DisconnectFrame,
    MSG_PROXY_CONNECT: ProxyConnectFrame,
    MSG_PROXY_DATA: ProxyDataFrame,
    MSG_PROXY_CLOSE: ProxyCloseFrame,
    MSG_SPEEDTEST_REQ: SpeedtestReqFrame,
    MSG_SPEEDTEST_DATA: SpeedtestDataFrame,
    MSG_MULTIHOP_FORWARD: MultiHopForwardFrame,
}


def parse_frame(data: bytes) -> ShinFrame:
    """Parses raw binary data into a typed ShinFrame instance."""
    if len(data) < HEADER_LEN:
        raise ValueError(f"Packet too short for ShinVPN header ({len(data)} bytes)")
    
    header = FrameHeader.unpack(data)
    expected_len = HEADER_LEN + header.payload_len
    if len(data) < expected_len:
        raise ValueError(
            f"Truncated packet: expected {expected_len} bytes, got {len(data)}"
        )

    payload = data[HEADER_LEN:expected_len]
    frame_cls = FRAME_TYPE_MAP.get(header.msg_type, ShinFrame)
    return frame_cls.from_header_and_payload(header, payload)
