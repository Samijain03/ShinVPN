"""
ShinVPN Delusional CyberShield Ad & Malware DNS Sinkhole
========================================================
Delusional Club Industries DNS Sinkhole & Privacy Shield.
Provides high-performance in-memory filtering against ad trackers,
telemetry networks, cryptominers, and malicious phishing domains.
"""

from __future__ import annotations
import logging
import re
import threading
from typing import Set, Dict, List, Optional

logger = logging.getLogger("shinvpn.adblock")

# Built-in curated blocklist of notorious tracking, telemetry, ad, and malware domains
CORE_AD_AND_TRACKER_DOMAINS: List[str] = [
    # Google Ad & Analytics networks
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "google-analytics.com",
    "adservice.google.com",
    "pagead2.googlesyndication.com",
    "admob.com",
    # Facebook / Meta Telemetry
    "pixel.facebook.com",
    "an.facebook.com",
    "graph.facebook.com/tr",
    # Microsoft & Windows Telemetry
    "telemetry.microsoft.com",
    "v10.events.data.microsoft.com",
    "v20.events.data.microsoft.com",
    "watson.telemetry.microsoft.com",
    "v10.vortex-win.data.microsoft.com",
    # Major Ad Exchanges
    "adnxs.com",
    "criteo.com",
    "rubiconproject.com",
    "pubmatic.com",
    "openx.net",
    "taboola.com",
    "outbrain.com",
    "scorecardresearch.com",
    "quantserve.com",
    "moatads.com",
    "exponential.com",
    "advertising.com",
    "advertising.amazon.com",
    "amazon-adsystem.com",
    "casalemedia.com",
    "zedo.com",
    "chitika.net",
    "inmobi.com",
    "chartbeat.net",
    "segment.io",
    "hotjar.com",
    "mixpanel.com",
    "optimizely.com",
    "crazyegg.com",
    "mouseflow.com",
    "kissmetrics.com",
    # Malware, Phishing & Cryptojacking
    "coinhive.com",
    "coin-hive.com",
    "crypto-loot.com",
    "minr.pw",
    "webminepool.com",
    "jsecoin.com",
    "badsite-malware.com",
    "phishing-test-domain.club",
]


class CyberShieldAdBlocker:
    """High-throughput in-memory domain filter with sub-microsecond matching."""

    def __init__(self, enable_adblock: bool = True, enable_malware_block: bool = True):
        self.enabled = enable_adblock
        self.malware_enabled = enable_malware_block
        self._exact_blocked_domains: Set[str] = set()
        self._blocked_suffixes: List[str] = []
        self._lock = threading.Lock()

        # Telemetry
        self.blocked_queries_count: int = 0
        self.last_blocked_domain: Optional[str] = None
        self.recent_blocked_log: List[Dict[str, str]] = []

        self._load_core_blocklists()

    def _load_core_blocklists(self) -> None:
        """Populates internal lookup structures with high-efficiency sets."""
        with self._lock:
            for domain in CORE_AD_AND_TRACKER_DOMAINS:
                clean = domain.strip().lower()
                if clean:
                    self._exact_blocked_domains.add(clean)
                    self._blocked_suffixes.append("." + clean)
            logger.info(f"CyberShield loaded {len(self._exact_blocked_domains)} core filtering rules.")

    def add_custom_rules(self, domains: List[str]) -> None:
        """Adds user-defined custom domains to blocklist."""
        with self._lock:
            for d in domains:
                clean = d.strip().lower()
                if clean and clean not in self._exact_blocked_domains:
                    self._exact_blocked_domains.add(clean)
                    self._blocked_suffixes.append("." + clean)

    def should_block(self, domain: str) -> bool:
        """
        Determines whether a domain or any of its parent domains match blocklists.
        Returns True if blocked, False if permitted.
        """
        if not self.enabled:
            return False

        clean_d = domain.strip().lower().rstrip(".")
        if not clean_d:
            return False

        with self._lock:
            # 1. Exact match
            if clean_d in self._exact_blocked_domains:
                self._record_blocked(clean_d)
                return True

            # 2. Suffix match (e.g. ad1.doubleclick.net -> .doubleclick.net)
            for suffix in self._blocked_suffixes:
                if clean_d.endswith(suffix):
                    self._record_blocked(clean_d)
                    return True

        return False

    def _record_blocked(self, domain: str) -> None:
        """Updates internal telemetry counters."""
        self.blocked_queries_count += 1
        self.last_blocked_domain = domain
        entry = {"domain": domain, "category": "Ad / Tracker"}
        self.recent_blocked_log.append(entry)
        if len(self.recent_blocked_log) > 50:
            self.recent_blocked_log.pop(0)

    def get_stats(self) -> Dict:
        """Returns live statistics for GUI and telemetry."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "rules_loaded": len(self._exact_blocked_domains),
                "blocked_queries_count": self.blocked_queries_count,
                "last_blocked_domain": self.last_blocked_domain,
                "recent_blocked": list(reversed(self.recent_blocked_log[-10:])),
            }


# Singleton instance for system-wide access
shield_instance = CyberShieldAdBlocker()
