"""
ShinVPN Desktop Cyberpunk Application
=====================================
Delusional Club Industries Desktop Application Backend & Window Manager.
Hosts local FastAPI backend and embeds the UI via PyWebView / Browser.
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import threading
import webbrowser
from dataclasses import asdict
from pathlib import Path
from typing import Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..client.client import ShinVPNClient, ClientTelemetry, ClientState
from ..client.config import ClientConfig
from ..server.config import ServerConfig, AllowedPeer
from ..server.server import ShinVPNServer
from ..crypto.keys import generate_keypair

logger = logging.getLogger("shinvpn.gui")

app = FastAPI(title="ShinVPN Delusional GUI Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WEB_DIR = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

# Shared Client & Server Instances
_active_client: ShinVPNClient | None = None
_active_server: ShinVPNServer | None = None
_connected_websockets: Set[WebSocket] = set()

# Load persistent client profile if available, otherwise generate and save
_client_cfg_path = Path("client.json")
if _client_cfg_path.exists():
    try:
        _client_config = ClientConfig.load_from_file(_client_cfg_path)
    except Exception:
        _client_config = ClientConfig.generate_default()
else:
    _client_config = ClientConfig.generate_default()
    _client_config.save_to_file(_client_cfg_path)

_current_telemetry: ClientTelemetry = ClientTelemetry()


class ConnectRequest(BaseModel):
    server_host: str = "127.0.0.1"
    server_port: int = 51820
    transport_type: str = "udp"
    enable_killswitch: bool = False
    enable_dns_shield: bool = True
    enable_system_proxy: bool = True
    server_public_key: str = ""


def _telemetry_callback(telemetry: ClientTelemetry) -> None:
    global _current_telemetry
    _current_telemetry = telemetry
    # Broadcast to active WebSockets
    data = asdict(telemetry)
    data["state"] = telemetry.state.value
    msg = json.dumps(data)
    
    # Non-blocking async broadcast
    for ws in list(_connected_websockets):
        try:
            asyncio.create_task(ws.send_text(msg))
        except Exception:
            pass


@app.get("/")
async def get_index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/style.css")
async def get_css():
    return FileResponse(WEB_DIR / "style.css")


@app.get("/app.js")
async def get_js():
    return FileResponse(WEB_DIR / "app.js")


@app.get("/api/status")
async def get_status():
    global _current_telemetry, _client_config
    data = asdict(_current_telemetry)
    data["state"] = _current_telemetry.state.value
    data["client_key"] = _client_config.client_public_key
    return data


@app.post("/api/connect")
async def post_connect(req: ConnectRequest):
    global _active_client, _active_server, _client_config
    try:
        if _active_client and _active_client.telemetry.state == ClientState.CONNECTED:
            return {"success": True, "message": "Already connected"}

        _client_config.server_host = req.server_host
        if req.transport_type == "udp":
            _client_config.udp_port = req.server_port
        else:
            _client_config.stealth_port = req.server_port
        _client_config.transport_type = req.transport_type
        _client_config.enable_killswitch = req.enable_killswitch
        _client_config.enable_dns_shield = req.enable_dns_shield
        _client_config.enable_system_proxy = req.enable_system_proxy

        # Load or generate Server Configuration for Local Node / Standalone testing
        srv_cfg_path = Path("server.json")
        if not srv_cfg_path.exists():
            srv_cfg = ServerConfig.generate_default()
            srv_cfg.save_to_file(srv_cfg_path)
        else:
            srv_cfg = ServerConfig.load_from_file(srv_cfg_path)

        # Auto-authorize current client's public key in server config
        if not any(p.public_key == _client_config.client_public_key for p in srv_cfg.allowed_peers):
            srv_cfg.add_peer(name="GUI Local Client", public_key=_client_config.client_public_key, allowed_ip="10.8.0.2")
            srv_cfg.save_to_file(srv_cfg_path)

        # If targeting localhost or 127.0.0.1, ensure embedded server daemon is running
        if req.server_host in ("127.0.0.1", "localhost"):
            _client_config.server_public_key = srv_cfg.public_key
            if _active_server is None or not _active_server.is_running:
                srv_cfg.udp_port = req.server_port
                _active_server = ShinVPNServer(srv_cfg)
                try:
                    await _active_server.start()
                    logger.info(f"Embedded ShinVPN Server Daemon active on {srv_cfg.udp_port}")
                except OSError as err:
                    logger.info(f"Port already in use ({err}); connecting to existing daemon.")
            else:
                _active_server.authorize_peer(_client_config.client_public_key, "GUI Local Client")
        else:
            if req.server_public_key:
                _client_config.server_public_key = req.server_public_key
            else:
                _client_config.server_public_key = srv_cfg.public_key

        if _active_client:
            await _active_client.disconnect()
            _active_client = None

        _active_client = ShinVPNClient(_client_config, state_callback=_telemetry_callback)
        asyncio.create_task(_active_client.connect())
        return {"success": True}
    except Exception as e:
        logger.error(f"Connect API error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@app.post("/api/disconnect")
async def post_disconnect():
    global _active_client
    if _active_client:
        await _active_client.disconnect()
        _active_client = None
    return {"success": True}


@app.post("/api/speedtest")
async def post_speedtest():
    global _active_client
    if not _active_client or _active_client.telemetry.state != ClientState.CONNECTED:
        return {"success": False, "error": "VPN tunnel is not connected"}
    
    try:
        dl, ul, rtt = await _active_client.run_speedtest()
        return {
            "success": True,
            "download_mbps": dl,
            "upload_mbps": ul,
            "latency_ms": rtt,
        }
    except Exception as e:
        logger.error(f"Speedtest failed: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/genkeys")
async def api_genkeys():
    kp = generate_keypair()
    return {
        "private_key": kp.private_b64,
        "public_key": kp.public_b64,
    }


@app.get("/api/nodes")
async def api_nodes():
    return {
        "nodes": [
            {"id": "local", "name": "Local Core Node", "endpoint": "127.0.0.1:51820", "location": "Localhost", "country": "⚡", "ping_ms": 1.2},
            {"id": "tokyo", "name": "Tokyo Alpha-1", "endpoint": "tokyo.delusional.club:51820", "location": "Tokyo, Japan", "country": "🇯🇵", "ping_ms": 18.5},
            {"id": "frankfurt", "name": "Frankfurt Vault-7", "endpoint": "frankfurt.delusional.club:51820", "location": "Frankfurt, Germany", "country": "🇩🇪", "ping_ms": 42.1},
            {"id": "singapore", "name": "Singapore Nexus-9", "endpoint": "singapore.delusional.club:51820", "location": "Singapore", "country": "🇸🇬", "ping_ms": 28.4},
        ]
    }


# 1. CyberShield Ad & Tracker DNS Sinkhole Endpoints
@app.get("/api/adblock/stats")
async def api_adblock_stats():
    from ..tunnel.adblock import shield_instance
    return shield_instance.get_stats()


@app.post("/api/adblock/toggle")
async def api_adblock_toggle():
    from ..tunnel.adblock import shield_instance
    shield_instance.enabled = not shield_instance.enabled
    return shield_instance.get_stats()


# 2. Process-Level Split Tunneling Endpoints
@app.get("/api/processes")
async def api_get_processes():
    from ..tunnel.process_router import process_matrix
    apps = process_matrix.scan_active_applications()
    return {
        "enabled": process_matrix.enabled,
        "mode": process_matrix.mode,
        "applications": apps,
    }


class SplitTunnelRequest(BaseModel):
    enabled: bool
    mode: str = "INCLUSIVE"
    selected_apps: List[str] = []


@app.post("/api/processes/rules")
async def api_set_process_rules(req: SplitTunnelRequest):
    from ..tunnel.process_router import process_matrix
    process_matrix.set_rules(req.enabled, req.mode, req.selected_apps)
    return {"success": True, "mode": process_matrix.mode, "selected_count": len(process_matrix.selected_apps)}


# 3. Multi-Device Profile Hub & Mobile QR Codes
@app.get("/api/profiles")
async def api_get_profiles():
    from ..crypto.profiles import profile_manager
    return {"profiles": list(profile_manager.profiles.values())}


class CreateProfileRequest(BaseModel):
    name: str = "New Mobile Device"
    device_type: str = "phone"


@app.post("/api/profiles/generate")
async def api_generate_profile(req: CreateProfileRequest):
    from ..crypto.profiles import profile_manager
    prof = profile_manager.create_profile(req.name, req.device_type)
    return {"success": True, "profile": prof}


@app.get("/api/profiles/{profile_id}/qr")
async def api_get_profile_qr(profile_id: str, host: Optional[str] = None):
    from ..crypto.profiles import profile_manager
    import socket
    
    # Auto-detect local LAN IP so mobile device on Wi-Fi can connect
    if not host:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            detected_ip = s.getsockname()[0]
            s.close()
        except Exception:
            detected_ip = "127.0.0.1"
        endpoint = f"{detected_ip}:51820"
    else:
        endpoint = host if ":" in host else f"{host}:51820"

    conf = profile_manager.generate_wireguard_conf(profile_id, server_endpoint=endpoint)
    svg_qr = profile_manager.generate_svg_qr(conf)
    return {"success": True, "svg": svg_qr, "config": conf, "endpoint": endpoint}


# 4. Multi-Hop / Double VPN Config
class MultiHopConfigRequest(BaseModel):
    enabled: bool = False
    entry_node_id: str = "tokyo"
    exit_node_id: str = "frankfurt"


@app.post("/api/multihop/config")
async def api_set_multihop(req: MultiHopConfigRequest):
    return {"success": True, "multihop_enabled": req.enabled, "entry": req.entry_node_id, "exit": req.exit_node_id}


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    _connected_websockets.add(websocket)
    try:
        # Send initial state
        data = asdict(_current_telemetry)
        data["state"] = _current_telemetry.state.value
        await websocket.send_text(json.dumps(data))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _connected_websockets.discard(websocket)


def run_server(port: int = 58999):
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def main():
    port = 58999
    # Start web server thread
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    url = f"http://127.0.0.1:{port}"
    logger.info(f"ShinVPN GUI backend listening on {url}")

    # Try PyWebView, fallback to system browser
    try:
        import webview
        webview.create_window(
            "ShinVPN — Delusional Club Industries",
            url=url,
            width=1080,
            height=780,
            resizable=True,
            background_color="#08090e",
        )
        webview.start()
    except Exception as e:
        logger.info(f"PyWebView initialization note ({e}). Launching default browser...")
        webbrowser.open(url)
        try:
            while True:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
