"""
ShinVPN App-Level Split Tunneling Matrix
========================================
Delusional Club Industries Application Routing Engine.
Discovers active desktop applications and enforces process-specific
routing rules (VPN Only vs Bypass VPN).
"""

from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Set, Optional

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("shinvpn.split_tunnel")

# System processes to exclude from the user-facing app picker
EXCLUDED_SYSTEM_PROCS = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "svchost.exe", "fontdrvhost.exe",
    "dwm.exe", "conhost.exe", "sihost.exe", "taskhostw.exe", "explorer.exe",
    "ctfmon.exe", "searchhost.exe", "startmenuexperiencehost.exe", "runtimebroker.exe",
    "shellexperiencehost.exe", "securityhealthservice.exe", "spoolsv.exe",
    "audiodg.exe", "wlanext.exe", "smartscreen.exe", "compattelrunner.exe"
}

# Nice icon & display mappings
APP_METADATA_MAP = {
    "chrome.exe": {"name": "Google Chrome", "icon": "🌐", "cat": "Web Browser"},
    "msedge.exe": {"name": "Microsoft Edge", "icon": "🌐", "cat": "Web Browser"},
    "firefox.exe": {"name": "Mozilla Firefox", "icon": "🦊", "cat": "Web Browser"},
    "brave.exe": {"name": "Brave Browser", "icon": "🦁", "cat": "Web Browser"},
    "opera.exe": {"name": "Opera Browser", "icon": "⭕", "cat": "Web Browser"},
    "discord.exe": {"name": "Discord", "icon": "💬", "cat": "Communication"},
    "telegram.exe": {"name": "Telegram Desktop", "icon": "✈️", "cat": "Communication"},
    "slack.exe": {"name": "Slack", "icon": "💼", "cat": "Communication"},
    "spotify.exe": {"name": "Spotify Music", "icon": "🎵", "cat": "Media"},
    "steam.exe": {"name": "Steam Client", "icon": "🎮", "cat": "Gaming"},
    "epicgameslauncher.exe": {"name": "Epic Games", "icon": "🎮", "cat": "Gaming"},
    "qbittorrent.exe": {"name": "qBittorrent", "icon": "⚡", "cat": "P2P / Torrent"},
    "utorrent.exe": {"name": "uTorrent", "icon": "⚡", "cat": "P2P / Torrent"},
    "code.exe": {"name": "Visual Studio Code", "icon": "💻", "cat": "Development"},
    "git.exe": {"name": "Git SCM", "icon": "📦", "cat": "Development"},
    "curl.exe": {"name": "cURL CLI", "icon": "📡", "cat": "Network"},
}


class ProcessRoutingMatrix:
    """Manages application-level split tunneling policies."""

    def __init__(self, config_path: str = "split_tunnel.json"):
        self.config_path = Path(config_path)
        self.mode: str = "INCLUSIVE"  # "INCLUSIVE" (Bypass listed) or "EXCLUSIVE" (Tunnel listed)
        self.enabled: bool = False
        self.selected_apps: Set[str] = set()
        self.load_config()

    def scan_active_applications(self) -> List[Dict]:
        """Scans current OS processes and returns a deduplicated list of active user apps."""
        results: Dict[str, Dict] = {}

        if psutil is not None:
            try:
                for proc in psutil.process_iter(["name", "exe", "pid"]):
                    try:
                        pname = proc.info.get("name", "")
                        if not pname:
                            continue
                        pname_lower = pname.lower()
                        if pname_lower in EXCLUDED_SYSTEM_PROCS:
                            continue

                        if pname_lower not in results:
                            meta = APP_METADATA_MAP.get(pname_lower, {
                                "name": pname,
                                "icon": "📱",
                                "cat": "Application",
                            })
                            results[pname_lower] = {
                                "process_name": pname_lower,
                                "display_name": meta["name"],
                                "icon": meta["icon"],
                                "category": meta["cat"],
                                "pid": proc.info.get("pid"),
                                "is_tunneled": (
                                    pname_lower in self.selected_apps
                                    if self.mode == "EXCLUSIVE"
                                    else pname_lower not in self.selected_apps
                                ),
                            }
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception as e:
                logger.warning(f"Process scan error: {e}")

        # Ensure default common apps are presented even if not currently active
        for pname, meta in APP_METADATA_MAP.items():
            if pname not in results:
                results[pname] = {
                    "process_name": pname,
                    "display_name": meta["name"],
                    "icon": meta["icon"],
                    "category": meta["cat"],
                    "pid": None,
                    "is_tunneled": (
                        pname in self.selected_apps
                        if self.mode == "EXCLUSIVE"
                        else pname not in self.selected_apps
                    ),
                }

        return sorted(list(results.values()), key=lambda x: (x["pid"] is None, x["display_name"]))

    def set_rules(self, enabled: bool, mode: str, app_list: List[str]) -> None:
        """Configures split tunneling policy."""
        self.enabled = enabled
        self.mode = mode.upper()
        self.selected_apps = {a.strip().lower() for a in app_list if a.strip()}
        self.save_config()

    def should_route_process(self, process_name: str) -> bool:
        """Determines if a given process name should traverse the VPN tunnel."""
        if not self.enabled:
            return True  # All traffic tunneled by default

        pname = process_name.lower()
        if self.mode == "EXCLUSIVE":
            # Only explicitly selected apps route through VPN
            return pname in self.selected_apps
        else:
            # All apps route through VPN EXCEPT explicitly bypassed apps
            return pname not in self.selected_apps

    def save_config(self) -> None:
        """Persists split tunneling settings to disk."""
        data = {
            "enabled": self.enabled,
            "mode": self.mode,
            "selected_apps": list(self.selected_apps),
        }
        try:
            self.config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save split tunnel config: {e}")

    def load_config(self) -> None:
        """Loads split tunneling settings from disk."""
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.enabled = data.get("enabled", False)
                self.mode = data.get("mode", "INCLUSIVE")
                self.selected_apps = set(data.get("selected_apps", []))
            except Exception as e:
                logger.warning(f"Failed to load split tunnel config: {e}")


# Singleton instance
process_matrix = ProcessRoutingMatrix()
