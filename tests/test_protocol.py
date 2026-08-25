"""
Unit Tests for ShinVPN Protocol Framing
"""

import struct
import pytest
from shinvpn.protocol.constants import (
    MAGIC_BYTES,
    PROTOCOL_VERSION,
    MSG_HANDSHAKE_INIT,
    MSG_HANDSHAKE_RESP,
    MSG_DATA_PACKET,
    MSG_KEEPALIVE,
    MSG_PROXY_CONNECT,
    MSG_PROXY_DATA,
    MSG_PROXY_CLOSE,
)
from shinvpn.protocol.frames import (
    FrameHeader,
    ShinFrame,
    HandshakeInitFrame,
    HandshakeRespFrame,
    DataPacketFrame,
    KeepAliveFrame,
    ProxyConnectFrame,
    ProxyDataFrame,
    ProxyCloseFrame,
    parse_frame,
)


def test_frame_header_pack_unpack():
    header = FrameHeader(
        version=PROTOCOL_VERSION,
        msg_type=MSG_DATA_PACKET,
        session_id=12345,
        seq_num=999,
        payload_len=64,
    )
    packed = header.pack()
    assert len(packed) == 20
    assert packed[:4] == MAGIC_BYTES

    unpacked = FrameHeader.unpack(packed)
    assert unpacked.version == PROTOCOL_VERSION
    assert unpacked.msg_type == MSG_DATA_PACKET
    assert unpacked.session_id == 12345
    assert unpacked.seq_num == 999
    assert unpacked.payload_len == 64


def test_data_packet_frame():
    payload = b"ENCRYPTED_IP_PAYLOAD_BYTES"
    frame = DataPacketFrame(session_id=42, seq_num=101, payload=payload)
    raw = frame.to_bytes()

    parsed = parse_frame(raw)
    assert isinstance(parsed, DataPacketFrame)
    assert parsed.session_id == 42
    assert parsed.seq_num == 101
    assert parsed.payload == payload


def test_keepalive_frame():
    frame = KeepAliveFrame(session_id=77, seq_num=5, timestamp=1700000000.5)
    raw = frame.to_bytes()

    parsed = parse_frame(raw)
    assert isinstance(parsed, KeepAliveFrame)
    assert parsed.session_id == 77
    assert abs(parsed.timestamp - 1700000000.5) < 0.001


def test_proxy_frames():
    # Connect
    conn_frame = ProxyConnectFrame(
        session_id=10, seq_num=1, conn_id=101, host="delusional.club", port=443
    )
    raw_conn = conn_frame.to_bytes()
    parsed_conn = parse_frame(raw_conn)
    assert isinstance(parsed_conn, ProxyConnectFrame)
    assert parsed_conn.conn_id == 101
    assert parsed_conn.host == "delusional.club"
    assert parsed_conn.port == 443

    # Data
    data_frame = ProxyDataFrame(
        session_id=10, seq_num=2, conn_id=101, raw_data=b"GET / HTTP/1.1\r\n\r\n"
    )
    raw_data = data_frame.to_bytes()
    parsed_data = parse_frame(raw_data)
    assert isinstance(parsed_data, ProxyDataFrame)
    assert parsed_data.conn_id == 101
    assert parsed_data.raw_data == b"GET / HTTP/1.1\r\n\r\n"

    # Close
    close_frame = ProxyCloseFrame(session_id=10, seq_num=3, conn_id=101)
    raw_close = close_frame.to_bytes()
    parsed_close = parse_frame(raw_close)
    assert isinstance(parsed_close, ProxyCloseFrame)
    assert parsed_close.conn_id == 101


def test_speedtest_frames():
    from shinvpn.protocol.frames import SpeedtestReqFrame, SpeedtestDataFrame
    # Speedtest Req
    req = SpeedtestReqFrame(session_id=1, seq_num=10, probe_id=999, chunk_count=100, chunk_size=1200)
    raw_req = req.to_bytes()
    parsed_req = parse_frame(raw_req)
    assert isinstance(parsed_req, SpeedtestReqFrame)
    assert parsed_req.probe_id == 999
    assert parsed_req.chunk_count == 100
    assert parsed_req.chunk_size == 1200

    # Speedtest Data
    data = SpeedtestDataFrame(session_id=1, seq_num=11, probe_id=999, chunk_idx=5, data_block=b"BURST_DATA")
    raw_data = data.to_bytes()
    parsed_data = parse_frame(raw_data)
    assert isinstance(parsed_data, SpeedtestDataFrame)
    assert parsed_data.probe_id == 999
    assert parsed_data.chunk_idx == 5
    assert parsed_data.data_block == b"BURST_DATA"


def test_invalid_packet_handling():
    # Corrupt magic
    corrupted = b"XXXX" + b"\x01\x03\x00\x00\x00\x01" + b"\x00" * 10
    with pytest.raises(ValueError):
        parse_frame(corrupted)

    # Truncated header
    with pytest.raises(ValueError):
        parse_frame(b"SHIN\x01")
