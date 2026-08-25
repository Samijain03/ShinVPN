"""
Unit tests for ShinVPN GUI Backend Endpoints
"""

import asyncio
from fastapi.testclient import TestClient
from shinvpn.gui.gui_app import app


def test_gui_api_endpoints():
    client = TestClient(app)

    # 1. Test Static Files & Status
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "state" in data
    assert "client_key" in data

    # 2. Test Nodes API
    res = client.get("/api/nodes")
    assert res.status_code == 200
    nodes_data = res.json()
    assert len(nodes_data["nodes"]) >= 4

    # 3. Test Key Generation
    res = client.get("/api/genkeys")
    assert res.status_code == 200
    keys_data = res.json()
    assert "private_key" in keys_data
    assert "public_key" in keys_data

    # 4. Test Connect API (Localhost Auto-Server)
    res = client.post(
        "/api/connect",
        json={
            "server_host": "127.0.0.1",
            "server_port": 52941,
            "transport_type": "udp",
            "enable_killswitch": False,
            "enable_dns_shield": False,
            "enable_system_proxy": False,
        },
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

    # 5. Test Disconnect API
    res = client.post("/api/disconnect")
    assert res.status_code == 200
    assert res.json()["success"] is True
