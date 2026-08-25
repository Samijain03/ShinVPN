"""
End-to-End Loopback Integration Tests for ShinVPN
"""

import asyncio
import pytest
from shinvpn.crypto.keys import generate_keypair
from shinvpn.server.config import ServerConfig, AllowedPeer
from shinvpn.server.server import ShinVPNServer
from shinvpn.client.config import ClientConfig
from shinvpn.client.client import ShinVPNClient, ClientState


def test_udp_tunnel_loopback():
    async def run_test():
        srv_kp = generate_keypair()
        cli_kp = generate_keypair()

        # 1. Setup Server
        srv_port = 52911
        stealth_port = 52912
        srv_cfg = ServerConfig(
            listen_host="127.0.0.1",
            udp_port=srv_port,
            stealth_port=stealth_port,
            enable_stealth=False,
            private_key=srv_kp.private_b64,
            public_key=srv_kp.public_b64,
            allowed_peers=[
                AllowedPeer(name="TestClient", public_key=cli_kp.public_b64, allowed_ip="10.8.0.2")
            ],
        )
        server = ShinVPNServer(srv_cfg)
        await server.start()

        # 2. Setup Client
        cli_cfg = ClientConfig(
            server_host="127.0.0.1",
            udp_port=srv_port,
            stealth_port=stealth_port,
            transport_type="udp",
            client_private_key=cli_kp.private_b64,
            client_public_key=cli_kp.public_b64,
            server_public_key=srv_kp.public_b64,
            enable_killswitch=False,
            enable_dns_shield=False,
            enable_system_proxy=False,
            local_proxy_port=10899,
        )
        client = ShinVPNClient(cli_cfg)

        # 3. Connect Client
        connected = await client.connect()
        assert connected is True
        assert client.telemetry.state == ClientState.CONNECTED
        assert client.telemetry.allocated_vip.startswith("10.8.0.")
        assert client.session_id in server.sessions_by_id

        # 4. Exchange & Verify Metrics
        await asyncio.sleep(0.5)
        assert client.telemetry.bytes_tx > 0
        assert client.telemetry.bytes_rx > 0

        # 5. Clean Disconnect
        await client.disconnect()
        assert client.telemetry.state == ClientState.DISCONNECTED

        await server.stop()

    asyncio.run(run_test())


def test_stealth_ws_tunnel_loopback():
    async def run_test():
        srv_kp = generate_keypair()
        cli_kp = generate_keypair()

        srv_port = 52921
        stealth_port = 52922
        srv_cfg = ServerConfig(
            listen_host="127.0.0.1",
            udp_port=srv_port,
            stealth_port=stealth_port,
            enable_stealth=True,
            private_key=srv_kp.private_b64,
            public_key=srv_kp.public_b64,
            allowed_peers=[
                AllowedPeer(name="StealthPeer", public_key=cli_kp.public_b64, allowed_ip="10.8.0.3")
            ],
        )
        server = ShinVPNServer(srv_cfg)
        await server.start()

        cli_cfg = ClientConfig(
            server_host="127.0.0.1",
            udp_port=srv_port,
            stealth_port=stealth_port,
            transport_type="stealth",
            client_private_key=cli_kp.private_b64,
            client_public_key=cli_kp.public_b64,
            server_public_key=srv_kp.public_b64,
            enable_killswitch=False,
            enable_dns_shield=False,
            enable_system_proxy=False,
            local_proxy_port=10898,
        )
        client = ShinVPNClient(cli_cfg)

        connected = await client.connect()
        assert connected is True
        assert client.telemetry.state == ClientState.CONNECTED
        assert client.telemetry.allocated_vip.startswith("10.8.0.")

        await asyncio.sleep(0.5)
        await client.disconnect()
        await server.stop()

    asyncio.run(run_test())
