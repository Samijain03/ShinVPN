"""
ShinVPN Command Line Interface
==============================
Delusional Club Industries Unified Command Line Suite.
"""

from __future__ import annotations
import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Optional

import sys
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live

from ..crypto.keys import generate_keypair, KeyPair
from ..protocol.constants import DEFAULT_PORT_UDP, DEFAULT_PORT_STEALTH
from ..server.config import ServerConfig, AllowedPeer
from ..server.server import ShinVPNServer
from ..client.config import ClientConfig
from ..client.client import ShinVPNClient, ClientTelemetry, ClientState

app = typer.Typer(
    name="shinvpn",
    help="ShinVPN by Delusional Club Industries - High-Performance Encrypted Tunnel Suite",
    no_args_is_help=True,
)
console = Console(force_terminal=True, legacy_windows=False)


@app.command("genkeys")
def genkeys(
    save_prefix: Optional[str] = typer.Option(
        None, "--save", "-s", help="File prefix to save keys (e.g. 'client' creates client_priv.key & client_pub.key)"
    )
):
    """Generate a new Curve25519 (X25519) cryptographic keypair."""
    kp = generate_keypair()

    table = Table(title="✨ DELUSIONAL CLUB CRYPTOGRAPHIC KEYPAIR", border_style="purple")
    table.add_column("Key Type", style="cyan", no_wrap=True)
    table.add_column("Base64 Encoded Value", style="bold white")
    table.add_row("Private Key", kp.private_b64)
    table.add_row("Public Key", kp.public_b64)

    console.print(table)

    if save_prefix:
        priv_path = Path(f"{save_prefix}_priv.key")
        pub_path = Path(f"{save_prefix}_pub.key")
        kp.save_to_file(priv_path, pub_path)
        console.print(f"[green]✔ Saved keys to {priv_path} and {pub_path}[/green]")


@app.command("init-profiles")
def init_profiles():
    """Generates pre-linked server.json and client.json configuration files for instant testing."""
    srv_kp = generate_keypair()
    cli_kp = generate_keypair()

    srv_cfg = ServerConfig(
        private_key=srv_kp.private_b64,
        public_key=srv_kp.public_b64,
        allowed_peers=[
            AllowedPeer(name="Dev Client", public_key=cli_kp.public_b64, allowed_ip="10.8.0.2")
        ]
    )
    srv_cfg.save_to_file("server.json")

    cli_cfg = ClientConfig(
        server_host="127.0.0.1",
        udp_port=DEFAULT_PORT_UDP,
        stealth_port=DEFAULT_PORT_STEALTH,
        transport_type="udp",
        client_private_key=cli_kp.private_b64,
        client_public_key=cli_kp.public_b64,
        server_public_key=srv_kp.public_b64,
    )
    cli_cfg.save_to_file("client.json")

    console.print(Panel.fit(
        "[bold cyan]✔ Created pre-configured profiles:[/bold cyan]\n"
        "  - [purple]server.json[/purple] (with dev client authorized)\n"
        "  - [purple]client.json[/purple] (paired with server public key)\n\n"
        "[green]To run locally:[/green]\n"
        "  1. [bold]shinvpn server --config server.json[/bold]\n"
        "  2. [bold]shinvpn client --config client.json[/bold] or [bold]shinvpn gui[/bold]",
        title="✨ ShinVPN Config Generator",
        border_style="cyan"
    ))


@app.command("server")
def run_server(
    config_path: str = typer.Option("server.json", "--config", "-c", help="Path to server.json config"),
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Override UDP listen port"),
):
    """Start the ShinVPN server daemon."""
    p = Path(config_path)
    if not p.exists():
        console.print(f"[yellow]Config '{config_path}' not found. Generating default profile...[/yellow]")
        init_profiles()

    cfg = ServerConfig.load_from_file(config_path)
    if port:
        cfg.udp_port = port

    console.print(Panel(
        f"[bold cyan]ShinVPN Server Daemon[/bold cyan] [purple](Delusional Club Industries)[/purple]\n"
        f"Listening on: [bold]{cfg.listen_host}:{cfg.udp_port}[/bold] (UDP) | [bold]{cfg.stealth_port}[/bold] (Stealth WS)\n"
        f"Server PubKey: [bold white]{cfg.public_key}[/bold white]\n"
        f"Virtual Subnet: [bold]{cfg.virtual_subnet}[/bold]",
        border_style="purple"
    ))

    server = ShinVPNServer(cfg)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.start())
        loop.run_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping ShinVPN Server...[/yellow]")
        loop.run_until_complete(server.stop())
        console.print("[green]Server stopped cleanly.[/green]")


@app.command("client")
def run_client(
    config_path: str = typer.Option("client.json", "--config", "-c", help="Path to client.json config"),
    transport: Optional[str] = typer.Option(None, "--transport", "-t", help="Transport mode: 'udp' or 'stealth'"),
):
    """Start the ShinVPN client in terminal mode with live telemetry."""
    p = Path(config_path)
    if not p.exists():
        console.print(f"[yellow]Config '{config_path}' not found. Generating default profile...[/yellow]")
        init_profiles()

    cfg = ClientConfig.load_from_file(config_path)
    if transport:
        cfg.transport_type = transport

    def render_telemetry_table(t: ClientTelemetry) -> Table:
        table = Table(title="⚡ SHINVPN LIVE TELEMETRY", border_style="cyan")
        table.add_column("Property", style="dim")
        table.add_column("Value", style="bold white")

        state_color = "green" if t.state == ClientState.CONNECTED else "yellow"
        table.add_row("Connection State", f"[{state_color}]{t.state.value}[/{state_color}]")
        table.add_row("Assigned VIP", f"[cyan]{t.allocated_vip}[/cyan]")
        table.add_row("Server Endpoint", t.server_address)
        table.add_row("Encapsulation", t.transport_mode.upper())
        table.add_row("Download Speed", f"[cyan]{(t.speed_rx_bps / 1_000_000):.2f} Mbps[/cyan]")
        table.add_row("Upload Speed", f"[purple]{(t.speed_tx_bps / 1_000_000):.2f} Mbps[/purple]")
        table.add_row("Tunnel Latency (RTT)", f"[blue]{t.rtt_ms:.1f} ms[/blue]")
        table.add_row("Total Data RX / TX", f"{t.bytes_rx / 1024:.1f} KB / {t.bytes_tx / 1024:.1f} KB")
        if t.last_error:
            table.add_row("Last Error", f"[red]{t.last_error}[/red]")
        return table

    client = ShinVPNClient(cfg)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def main_client_coro():
        console.print(f"[cyan]Connecting to ShinVPN Server {cfg.server_host}...[/cyan]")
        success = await client.connect()
        if not success:
            console.print(f"[red]Failed to establish tunnel: {client.telemetry.last_error}[/red]")
            return

        with Live(render_telemetry_table(client.telemetry), refresh_per_second=2) as live:
            while client.telemetry.state == ClientState.CONNECTED:
                live.update(render_telemetry_table(client.telemetry))
                await asyncio.sleep(0.5)

    try:
        loop.run_until_complete(main_client_coro())
    except KeyboardInterrupt:
        console.print("\n[yellow]Disconnecting ShinVPN Client...[/yellow]")
        loop.run_until_complete(client.disconnect())
        console.print("[green]Tunnel disconnected cleanly.[/green]")


@app.command("speedtest")
def run_cli_speedtest(
    config_path: str = typer.Option("client.json", "--config", "-c", help="Path to client.json config")
):
    """Run an end-to-end encrypted speed and latency benchmark test."""
    p = Path(config_path)
    if not p.exists():
        console.print(f"[yellow]Config '{config_path}' not found. Initializing...[/yellow]")
        init_profiles()

    cfg = ClientConfig.load_from_file(config_path)
    client = ShinVPNClient(cfg)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def do_test():
        console.print(f"[cyan]Connecting to ShinVPN Server {cfg.server_host}...[/cyan]")
        ok = await client.connect()
        if not ok:
            console.print(f"[red]Failed to connect: {client.telemetry.last_error}[/red]")
            return

        console.print("[purple]🚀 Running ShinVPN Encrypted Throughput & Latency Benchmark...[/purple]")
        dl, ul, rtt = await client.run_speedtest()
        await client.disconnect()

        table = Table(title="✨ SHINVPN BENCHMARK RESULTS", border_style="cyan")
        table.add_column("Metric", style="dim")
        table.add_column("Score", style="bold white")
        table.add_row("Download Throughput", f"[green]{dl:.2f} Mbps[/green]")
        table.add_row("Upload Throughput", f"[purple]{ul:.2f} Mbps[/purple]")
        table.add_row("Tunnel Latency (RTT)", f"[cyan]{rtt:.1f} ms[/cyan]")
        table.add_row("Encryption Cipher", "ChaCha20-Poly1305 (256-bit AEAD)")
        table.add_row("Key Exchange", "Curve25519 (X25519) Zero-Knowledge")
        console.print(table)

    try:
        loop.run_until_complete(do_test())
    except KeyboardInterrupt:
        pass


@app.command("adblock")
def run_adblock_stats(
    test_domain: str = typer.Option("", "--test", "-t", help="Test whether a specific domain is blocked")
):
    """View Delusional CyberShield AdBlocker & Malware Sinkhole status."""
    from ..tunnel.adblock import shield_instance
    stats = shield_instance.get_stats()
    table = Table(title="🛡️ DELUSIONAL CYBERSHIELD ADBLOCKER", border_style="cyan")
    table.add_column("Property", style="dim")
    table.add_column("Value", style="bold white")
    table.add_row("Status", "[green]ACTIVE (DNS SINKHOLE)[/green]" if stats["enabled"] else "[red]DISABLED[/red]")
    table.add_row("Loaded Rules", f"{stats['rules_loaded']:,} domains")
    table.add_row("Total Blocked Queries", f"[cyan]{stats['blocked_queries_count']}[/cyan]")
    table.add_row("Last Intercepted", stats['last_blocked_domain'] or "None")
    console.print(table)

    if test_domain:
        blocked = shield_instance.should_block(test_domain)
        if blocked:
            console.print(f"[red]🚫 Domain '{test_domain}' is BLOCKED (CyberShield Sinkhole)[/red]")
        else:
            console.print(f"[green]✔ Domain '{test_domain}' is PERMITTED[/green]")


@app.command("processes")
def run_list_processes():
    """Scan and list running desktop apps for split tunneling."""
    from ..tunnel.process_router import process_matrix
    apps = process_matrix.scan_active_applications()
    table = Table(title="🎯 RUNNING APPLICATION MATRIX", border_style="purple")
    table.add_column("Icon", style="dim")
    table.add_column("Application Name", style="bold white")
    table.add_column("Process Name", style="cyan")
    table.add_column("Category", style="dim")
    table.add_column("Routing Status", style="green")

    for app in apps:
        status = "[green]TUNNELED[/green]" if app["is_tunneled"] else "[dim]BYPASS[/dim]"
        table.add_row(app["icon"], app["display_name"], app["process_name"], app["category"], status)
    console.print(table)


@app.command("profile-add")
def run_add_profile(
    name: str = typer.Argument(..., help="Name of device (e.g. iPhone-15)"),
    device_type: str = typer.Option("phone", "--type", "-t", help="Device type: phone/laptop/desktop")
):
    """Provision a new multi-device profile."""
    from ..crypto.profiles import profile_manager
    prof = profile_manager.create_profile(name, device_type)
    console.print(f"[green]✔ Device Profile '{prof.name}' created![/green]")
    console.print(f"Allocated VIP: [cyan]{prof.allocated_vip}[/cyan]")
    console.print(f"Public Key: [purple]{prof.public_key}[/purple]")


@app.command("profile-qr")
def run_show_qr(
    profile_id: str = typer.Argument(..., help="Profile ID or Name to display QR for"),
    endpoint: str = typer.Option("", "--endpoint", "-e", help="Custom server endpoint host:port")
):
    """Render terminal ASCII QR Code for 1-click mobile WireGuard import."""
    from ..crypto.profiles import profile_manager
    # Find by ID or name
    p = profile_manager.profiles.get(profile_id)
    if not p:
        for prof in profile_manager.profiles.values():
            if prof.name.lower() == profile_id.lower():
                p = prof
                break

    if not p:
        console.print(f"[red]Error: Profile '{profile_id}' not found.[/red]")
        return

    ep = endpoint or "127.0.0.1:51820"
    conf = profile_manager.generate_wireguard_conf(p.id, server_endpoint=ep)
    ascii_qr = profile_manager.generate_ascii_qr(conf)
    console.print(f"[cyan]📱 ShinVPN WireGuard QR Code for '{p.name}' ({ep}):[/cyan]\n")
    print(ascii_qr)
    console.print("[dim]Scan this QR code using the WireGuard app on your phone.[/dim]\n")


@app.command("proxy-reset")
def run_proxy_reset():
    """Reset and disable Windows WinINet system proxy settings."""
    from ..tunnel.proxy_tunnel import WindowsSystemProxy
    WindowsSystemProxy.disable()
    console.print("[green]✔ Windows System Proxy reset and disabled successfully.[/green]")


@app.command("gui")
def run_gui():
    """Launch the Cyberpunk Desktop GUI."""
    from ..gui.gui_app import main as launch_gui
    console.print("[purple]Launching ShinVPN Cyberpunk Desktop UI...[/purple]")
    launch_gui()


if __name__ == "__main__":
    app()
