"""
Benchmark pipeline verification test for ShinVPN
"""

import asyncio
from shinvpn.crypto.keys import generate_keypair
from shinvpn.server.config import ServerConfig, AllowedPeer
from shinvpn.server.server import ShinVPNServer
from shinvpn.client.config import ClientConfig
from shinvpn.client.client import ShinVPNClient, ClientState


def test_speedtest_pipeline():
    async def run_test():
        srv_kp = generate_keypair()
        cli_kp = generate_keypair()

        srv_port = 52931
        stealth_port = 52932
        srv_cfg = ServerConfig(
            listen_host="127.0.0.1",
            udp_port=srv_port,
            stealth_port=stealth_port,
            enable_stealth=False,
            private_key=srv_kp.private_b64,
            public_key=srv_kp.public_b64,
            allowed_peers=[
                AllowedPeer(name="BenchPeer", public_key=cli_kp.public_b64, allowed_ip="10.8.0.5")
            ],
        )
        server = ShinVPNServer(srv_cfg)
        await server.start()

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
            local_proxy_port=10897,
        )
        client = ShinVPNClient(cli_cfg)

        connected = await client.connect()
        assert connected is True

        # Run speedtest probe
        dl_mbps, ul_mbps, rtt_ms = await client.run_speedtest()
        assert dl_mbps > 0.0
        assert ul_mbps > 0.0

        await client.disconnect()
        await server.stop()

    asyncio.run(run_test())
