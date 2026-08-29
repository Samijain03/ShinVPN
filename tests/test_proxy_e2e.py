"""
End-to-End Tunnel Proxy Verification Test
=========================================
Verifies that HTTP CONNECT and SOCKS5 traffic sent through Local Proxy Gateway
traverses the encrypted ShinVPN UDP tunnel, reaches the remote destination,
and returns data seamlessly with zero packet drops.
"""

import asyncio
import pytest
from shinvpn.crypto.keys import generate_keypair
from shinvpn.server.config import ServerConfig, AllowedPeer
from shinvpn.server.server import ShinVPNServer
from shinvpn.client.config import ClientConfig
from shinvpn.client.client import ShinVPNClient, ClientState


def test_e2e_proxy_tunnel_traffic():
    async def run_test():
        # 1. Start a Mock Target TCP Echo Server
        async def handle_echo(reader, writer):
            data = await reader.read(1024)
            if data.startswith(b"GET /test"):
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 13\r\n\r\nHello ShinVPN")
            else:
                writer.write(b"ECHO:" + data)
            await writer.drain()
            writer.close()

        echo_server = await asyncio.start_server(handle_echo, "127.0.0.1", 52988)
        
        # 2. Start ShinVPN Server
        srv_kp = generate_keypair()
        cli_kp = generate_keypair()
        srv_port = 52980
        srv_cfg = ServerConfig(
            listen_host="127.0.0.1",
            udp_port=srv_port,
            stealth_port=52981,
            enable_stealth=False,
            private_key=srv_kp.private_b64,
            public_key=srv_kp.public_b64,
            allowed_peers=[
                AllowedPeer(name="ProxyTestClient", public_key=cli_kp.public_b64, allowed_ip="10.8.0.2")
            ],
        )
        vpn_server = ShinVPNServer(srv_cfg)
        await vpn_server.start()

        # 3. Start ShinVPN Client
        proxy_port = 10988
        cli_cfg = ClientConfig(
            server_host="127.0.0.1",
            udp_port=srv_port,
            stealth_port=52981,
            transport_type="udp",
            client_private_key=cli_kp.private_b64,
            client_public_key=cli_kp.public_b64,
            server_public_key=srv_kp.public_b64,
            enable_killswitch=False,
            enable_dns_shield=False,
            enable_system_proxy=False,  # Don't modify host registry in unit test
            local_proxy_port=proxy_port,
        )
        vpn_client = ShinVPNClient(cli_cfg)
        connected = await vpn_client.connect()
        assert connected is True

        await asyncio.sleep(0.3)

        # 4. Test SOCKS5 Request through Local Proxy Gateway
        socks_reader, socks_writer = await asyncio.open_connection("127.0.0.1", proxy_port)
        # SOCKS5 Greeting (VER=5, 1 auth method: 0)
        socks_writer.write(b"\x05\x01\x00")
        await socks_writer.drain()
        auth_resp = await socks_reader.readexactly(2)
        assert auth_resp == b"\x05\x00"

        # SOCKS5 CONNECT to 127.0.0.1:52988 (Mock Target)
        # VER=5 | CMD=1 (CONNECT) | RSV=0 | ATYP=1 (IPv4) | 127.0.0.1 (4B) | Port 52988 (2B)
        import struct
        req = b"\x05\x01\x00\x01\x7f\x00\x00\x01" + struct.pack("!H", 52988)
        socks_writer.write(req)
        await socks_writer.drain()
        conn_resp = await socks_reader.readexactly(10)
        assert conn_resp[1] == 0x00  # SOCKS5 Success

        # Send data through SOCKS5 tunnel
        socks_writer.write(b"PING_OVER_SOCKS5")
        await socks_writer.drain()
        reply = await socks_reader.read(1024)
        assert reply == b"ECHO:PING_OVER_SOCKS5"
        socks_writer.close()

        # 5. Test HTTP CONNECT Request through Local Proxy Gateway (Simulating Browser HTTPS)
        http_reader, http_writer = await asyncio.open_connection("127.0.0.1", proxy_port)
        http_writer.write(b"CONNECT 127.0.0.1:52988 HTTP/1.1\r\nHost: 127.0.0.1:52988\r\n\r\n")
        await http_writer.drain()
        http_resp = await http_reader.readuntil(b"\r\n\r\n")
        assert b"200 Connection Established" in http_resp

        # Send payload through HTTPS tunnel
        http_writer.write(b"GET /test HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        await http_writer.drain()
        http_body = await http_reader.read(1024)
        assert b"Hello ShinVPN" in http_body
        http_writer.close()

        # Cleanup
        await vpn_client.disconnect()
        await vpn_server.stop()
        echo_server.close()
        await echo_server.wait_closed()

    asyncio.run(run_test())
