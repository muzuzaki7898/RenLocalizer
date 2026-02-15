"""
Proxy Manager v2.0
===================

Manages proxy rotation for translation requests to avoid rate limiting
and improve reliability.

v2.0 Changes:
- Personal proxy (proxy_url) support — always preferred over free proxies
- SOCKS proxy filtering (aiohttp doesn't support SOCKS natively)
- Smart proxy testing — GeoNode uptime pre-filter, concurrent batch test
- Auto-refresh with thread-safe scheduling (no asyncio.create_task in sync)
- Health feedback integration (mark_proxy_failed/success properly tracked)
- auto_rotate flag respected
- Proper aiohttp.ClientTimeout usage
"""

import asyncio
import aiohttp
import logging
import random
import time
import threading
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ProxyInfo:
    """Information about a proxy server."""
    host: str
    port: int
    protocol: str = "http"
    country: str = ""
    last_used: float = 0
    success_count: int = 0
    failure_count: int = 0
    response_time: float = 0
    is_working: bool = True
    is_personal: bool = False  # Personal proxies are never auto-disabled
    uptime: float = 0.0  # GeoNode uptime percentage (0-100)
    _auth_url: str = ""  # URL with embedded auth (user:pass@host:port)

    @property
    def url(self) -> str:
        """Get proxy URL (auth-aware if available)."""
        if self._auth_url:
            return self._auth_url
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total


class ProxyManager:
    """Manages proxy servers for translation requests.

    This class is intentionally kept independent from the UI layer.
    Runtime behaviour can be tuned via ``configure_from_settings`` which
    accepts a ProxySettings-like object (from src.utils.config).
    """

    # GeoNode API — primary source (structured JSON with quality data)
    GEONODE_API = (
        "https://proxylist.geonode.com/api/proxy-list"
        "?protocols=http%2Chttps"
        "&limit=500&page=1"
        "&sort_by=lastChecked&sort_type=desc"
    )

    # Fallback text sources (HTTP only, no quality metadata)
    TEXT_SOURCES = [
        "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&format=textplain",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    ]

    # Test URLs for proxy validation (HTTP — no TLS overhead)
    TEST_URLS = [
        "http://httpbin.org/ip",
        "http://api.ipify.org",
        "http://icanhazip.com",
        "http://checkip.amazonaws.com",
    ]

    # GeoNode minimum uptime filter — skip proxies with <40% uptime
    GEONODE_MIN_UPTIME = 40.0

    # Maximum proxies to test from free sources (avoid 5-minute waits)
    MAX_PROXIES_TO_TEST = 150

    # Batch test concurrency
    TEST_BATCH_SIZE = 30

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.proxies: List[ProxyInfo] = []
        self.current_proxy_index = 0
        self.proxy_update_interval = 3600  # 1 hour
        self.last_proxy_update = 0.0

        # Behaviour toggles (filled from config via configure_from_settings)
        self.auto_rotate: bool = True
        self.test_on_startup: bool = True
        self.max_failures: int = 10

        # User-provided personal proxy (single URL, highest priority)
        self.personal_proxy_url: str = ""

        # User-provided manual proxy list (host:port or full URLs)
        self.custom_proxy_strings: List[str] = []

        # Thread-safety for auto-refresh
        self._refresh_lock = threading.Lock()
        self._is_refreshing = False

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure_from_settings(self, proxy_settings) -> None:
        """Configure manager behaviour from a ProxySettings-like object.

        This keeps core decoupled from ConfigManager while still allowing
        runtime tuning from the settings dialog.
        """
        try:
            if proxy_settings is None:
                return
            # Interval / limits
            self.proxy_update_interval = int(
                getattr(proxy_settings, "update_interval", self.proxy_update_interval) or self.proxy_update_interval
            )
            self.max_failures = int(
                getattr(proxy_settings, "max_failures", self.max_failures) or self.max_failures
            )
            # Behaviour flags
            self.auto_rotate = bool(getattr(proxy_settings, "auto_rotate", self.auto_rotate))
            self.test_on_startup = bool(getattr(proxy_settings, "test_on_startup", self.test_on_startup))

            # Personal proxy URL (e.g. http://user:pass@host:port)
            self.personal_proxy_url = str(getattr(proxy_settings, "proxy_url", "") or "").strip()

            # Manual proxy list (list of strings)
            manual = getattr(proxy_settings, "manual_proxies", None)
            if isinstance(manual, list):
                self.custom_proxy_strings = [str(x).strip() for x in manual if str(x).strip()]
        except Exception as e:
            self.logger.warning(f"Error configuring ProxyManager from settings: {e}")

    # ------------------------------------------------------------------
    # Proxy Fetching
    # ------------------------------------------------------------------

    async def fetch_proxies_from_geonode(self) -> List[ProxyInfo]:
        """Fetch proxies from GeoNode API.

        Filters:
        - HTTP/HTTPS only (aiohttp doesn't support SOCKS natively)
        - Minimum uptime threshold
        """
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.GEONODE_API) as response:
                    if response.status == 200:
                        data = await response.json()
                        proxies = []

                        for proxy_data in data.get("data", []):
                            try:
                                protocols = proxy_data.get("protocols", [])
                                # Filter: only HTTP/HTTPS (aiohttp can't use SOCKS)
                                http_protocols = [p for p in protocols if p.lower() in ("http", "https")]
                                if not http_protocols:
                                    continue

                                uptime = float(proxy_data.get("upTime", 0) or 0)
                                if uptime < self.GEONODE_MIN_UPTIME:
                                    continue

                                proxy = ProxyInfo(
                                    host=proxy_data["ip"],
                                    port=int(proxy_data["port"]),
                                    protocol=http_protocols[0],
                                    country=proxy_data.get("country", ""),
                                    uptime=uptime,
                                )
                                proxies.append(proxy)
                            except (KeyError, ValueError, TypeError) as e:
                                self.logger.debug(f"Error parsing proxy data: {e}")
                                continue

                        self.logger.info(f"Fetched {len(proxies)} HTTP proxies from GeoNode (filtered from {len(data.get('data', []))} total)")
                        return proxies

        except Exception as e:
            self.logger.error(f"Error fetching proxies from GeoNode: {e}")

        return []

    async def fetch_proxies_from_text_source(self, url: str) -> List[ProxyInfo]:
        """Fetch proxies from text-based sources (host:port per line)."""
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        text = await response.text()
                        proxies = []

                        for line in text.strip().split("\n"):
                            line = line.strip()
                            if ":" in line:
                                try:
                                    host, port = line.split(":", 1)
                                    host = host.strip()
                                    port_int = int(port.strip())
                                    if host and 1 <= port_int <= 65535:
                                        proxies.append(ProxyInfo(host=host, port=port_int, protocol="http"))
                                except (ValueError, TypeError):
                                    continue

                        self.logger.info(f"Fetched {len(proxies)} proxies from text source")
                        return proxies

        except Exception as e:
            self.logger.error(f"Error fetching proxies from {url}: {e}")

        return []

    # ------------------------------------------------------------------
    # Proxy Testing
    # ------------------------------------------------------------------

    async def test_proxy(self, proxy: ProxyInfo, timeout: int = 5) -> bool:
        """Test if a proxy is working by making a real HTTP request."""
        test_url = random.choice(self.TEST_URLS)
        start_time = time.time()

        try:
            connector = aiohttp.TCPConnector(limit=1, ssl=False)
            timeout_obj = aiohttp.ClientTimeout(total=timeout)

            async with aiohttp.ClientSession(connector=connector, timeout=timeout_obj) as session:
                async with session.get(test_url, proxy=proxy.url) as response:
                    if response.status == 200:
                        proxy.response_time = time.time() - start_time
                        proxy.success_count += 1
                        proxy.is_working = True
                        return True
                    else:
                        proxy.failure_count += 1
                        proxy.is_working = False
                        return False

        except Exception as e:
            proxy.failure_count += 1
            proxy.is_working = False
            self.logger.debug(f"Proxy {proxy.url} failed test: {e}")
            return False

    # ------------------------------------------------------------------
    # Proxy String Parsing
    # ------------------------------------------------------------------

    def _parse_proxy_string(self, entry: str) -> Optional[ProxyInfo]:
        """Parse a proxy string (URL or host:port) into ProxyInfo."""
        entry = entry.strip()
        if not entry:
            return None

        protocol = "http"
        host = None
        port = None
        auth_url = ""

        try:
            if "://" in entry:
                parsed = urlparse(entry)
                protocol = parsed.scheme or "http"
                # Filter SOCKS — aiohttp doesn't support it natively
                if protocol.lower().startswith("socks"):
                    self.logger.debug(f"Skipping SOCKS proxy (not supported by aiohttp): {entry}")
                    return None
                host = parsed.hostname
                port = parsed.port
                # Preserve user:pass@host:port as auth URL
                if parsed.username:
                    auth_url = entry  # Keep the original URL with auth
            else:
                # Handle user:pass@host:port
                if "@" in entry:
                    user_part, host_part = entry.rsplit("@", 1)
                    if ":" in host_part:
                        host, port_str = host_part.split(":", 1)
                        host = host.strip()
                        port = int(port_str.strip())
                    auth_url = f"http://{entry}"
                elif ":" in entry:
                    host, port_str = entry.split(":", 1)
                    host = host.strip()
                    port = int(port_str.strip())

            if host and port and 1 <= port <= 65535:
                return ProxyInfo(
                    host=host, port=port, protocol=protocol,
                    _auth_url=auth_url
                )
        except Exception as e:
            self.logger.debug(f"Invalid proxy entry '{entry}': {e}")

        return None

    # ------------------------------------------------------------------
    # Proxy List Management
    # ------------------------------------------------------------------

    async def update_proxy_list(self) -> None:
        """Update the proxy list from all sources.

        Priority logic (v2.1.0):
        1. Personal proxy (proxy_url) — always first, never auto-disabled
        2. Manual proxies (manual_proxies list) — tested like free ones
        3. Free proxies (GeoNode + text sources) — ONLY if NO personal/manual proxies

        Rationale: If user configures their own proxies, they don't want
        unreliable free proxies mixing in. Free proxies are fallback only.
        """
        self.logger.info("Updating proxy list...")

        personal_proxies: List[ProxyInfo] = []
        all_proxies: List[ProxyInfo] = []

        # ── 1. Personal proxy (highest priority) ──
        if self.personal_proxy_url:
            proxy = self._parse_proxy_string(self.personal_proxy_url)
            if proxy:
                proxy.is_personal = True
                proxy.is_working = True
                personal_proxies.append(proxy)
                self.logger.info(f"Personal proxy loaded: {proxy.host}:{proxy.port}")

        # ── 2. Manual proxy list ──
        if self.custom_proxy_strings:
            self.logger.info(f"Loading {len(self.custom_proxy_strings)} custom proxies from settings")
            for entry in self.custom_proxy_strings:
                proxy = self._parse_proxy_string(entry)
                if proxy:
                    all_proxies.append(proxy)

        # ── 3. Free proxies — ONLY if NO personal/manual proxies configured ──
        has_personal_proxies = bool(personal_proxies or all_proxies)
        if not has_personal_proxies:
            self.logger.info("No personal/manual proxies configured, fetching free proxies...")
            # GeoNode API (HTTP-only, uptime-filtered)
            geonode_proxies = await self.fetch_proxies_from_geonode()
            all_proxies.extend(geonode_proxies)

            # Text sources
            for url in self.TEXT_SOURCES:
                text_proxies = await self.fetch_proxies_from_text_source(url)
                all_proxies.extend(text_proxies)
        else:
            self.logger.info(f"Using personal/manual proxies only ({len(personal_proxies) + len(all_proxies)} total), skipping free proxy fetch")

        # ── Deduplicate ──
        unique_proxies: Dict[str, ProxyInfo] = {}
        for proxy in all_proxies:
            key = f"{proxy.host}:{proxy.port}"
            if key not in unique_proxies:
                unique_proxies[key] = proxy

        self.logger.info(f"Found {len(unique_proxies)} unique free proxies, {len(personal_proxies)} personal")

        # ── Test proxies ──
        # Sort by uptime (GeoNode data) so best candidates are tested first
        candidates = sorted(unique_proxies.values(), key=lambda p: p.uptime, reverse=True)
        # Limit test count to avoid extremely long waits
        candidates = candidates[: self.MAX_PROXIES_TO_TEST]

        working_proxies: List[ProxyInfo] = []

        # Test personal proxy first (longer timeout)
        for proxy in personal_proxies:
            result = await self.test_proxy(proxy, timeout=10)
            if result:
                working_proxies.append(proxy)
                self.logger.info(f"Personal proxy working: {proxy.url} ({proxy.response_time:.1f}s)")
            else:
                # Still keep personal proxy — user explicitly set it
                proxy.is_working = False
                working_proxies.append(proxy)
                self.logger.warning(f"Personal proxy FAILED test but kept (user-configured): {proxy.url}")

        # Test free proxies in batches
        for i in range(0, len(candidates), self.TEST_BATCH_SIZE):
            batch = candidates[i: i + self.TEST_BATCH_SIZE]
            tasks = [self.test_proxy(proxy) for proxy in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for proxy, result in zip(batch, results):
                if result is True:
                    working_proxies.append(proxy)

        # Sort: personal first, then free by response time
        personal = [p for p in working_proxies if p.is_personal]
        free = [p for p in working_proxies if not p.is_personal]
        free.sort(key=lambda p: (p.response_time if p.response_time > 0 else 999))

        self.proxies = personal + free
        self.last_proxy_update = time.time()

        free_working = len([p for p in free if p.is_working])
        self.logger.info(
            f"Updated proxy list: {len(personal)} personal + {free_working} free working proxies"
        )

    # ------------------------------------------------------------------
    # Proxy Selection
    # ------------------------------------------------------------------

    def get_next_proxy(self) -> Optional[ProxyInfo]:
        """Get the next proxy in rotation.

        - If auto_rotate is True: round-robin through working proxies
        - If auto_rotate is False: always return the first (best) proxy
        - Personal proxies are always preferred
        """
        if not self.proxies:
            return None

        # Check if auto-refresh is needed (thread-safe, non-blocking)
        if time.time() - self.last_proxy_update > self.proxy_update_interval:
            self._schedule_background_refresh()

        # Filter working proxies (personal proxies always pass)
        working_proxies = [
            p for p in self.proxies
            if p.is_personal or (p.is_working and p.success_rate > 0.3)
        ]

        if not working_proxies:
            # Fallback: try any proxy
            working_proxies = self.proxies

        if not working_proxies:
            return None

        if self.auto_rotate:
            # Round-robin
            proxy = working_proxies[self.current_proxy_index % len(working_proxies)]
            self.current_proxy_index += 1
        else:
            # Always use the best (first) proxy
            proxy = working_proxies[0]

        proxy.last_used = time.time()
        return proxy

    def _schedule_background_refresh(self) -> None:
        """Schedule a background proxy refresh (thread-safe, non-blocking).

        Uses threading instead of asyncio.create_task to avoid
        'no running event loop' errors in sync contexts.
        """
        if self._is_refreshing:
            return

        with self._refresh_lock:
            if self._is_refreshing:
                return
            self._is_refreshing = True

        def _bg_refresh():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.update_proxy_list())
                finally:
                    loop.close()
            except Exception as e:
                self.logger.warning(f"Background proxy refresh failed: {e}")
            finally:
                self._is_refreshing = False

        threading.Thread(target=_bg_refresh, daemon=True).start()

    # ------------------------------------------------------------------
    # Health Feedback
    # ------------------------------------------------------------------

    def mark_proxy_failed(self, proxy_or_url) -> None:
        """Mark a proxy as failed. Accepts ProxyInfo or URL string."""
        proxy = self._resolve_proxy(proxy_or_url)
        if proxy is None:
            return

        proxy.failure_count += 1

        # Never auto-disable personal proxies
        if proxy.is_personal:
            return

        # Disable free proxy if it fails too often
        failure_limit = self.max_failures or 10
        if proxy.failure_count > failure_limit and proxy.success_rate < 0.3:
            proxy.is_working = False
            self.logger.debug(f"Disabled proxy {proxy.url} due to high failure rate ({proxy.success_rate:.0%})")

    def mark_proxy_success(self, proxy_or_url) -> None:
        """Mark a proxy as successful. Accepts ProxyInfo or URL string."""
        proxy = self._resolve_proxy(proxy_or_url)
        if proxy is None:
            return

        proxy.success_count += 1
        proxy.is_working = True

    def _resolve_proxy(self, proxy_or_url) -> Optional[ProxyInfo]:
        """Resolve a proxy reference to a ProxyInfo instance."""
        if isinstance(proxy_or_url, ProxyInfo):
            return proxy_or_url
        if isinstance(proxy_or_url, str) and proxy_or_url:
            for p in self.proxies:
                if p.url == proxy_or_url:
                    return p
        return None

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the proxy manager."""
        self.logger.info("Initializing proxy manager...")
        if self.test_on_startup:
            await self.update_proxy_list()
        else:
            # Only load personal + custom proxies without full external fetch
            self.proxies = []
            if self.personal_proxy_url or self.custom_proxy_strings:
                await self.update_proxy_list()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_proxy_stats(self) -> Dict:
        """Get proxy statistics."""
        total_count = len(self.proxies)
        working_count = len([p for p in self.proxies if p.is_working])
        personal_count = len([p for p in self.proxies if p.is_personal])

        if self.proxies:
            working = [p for p in self.proxies if p.is_working and p.response_time > 0]
            avg_response_time = sum(p.response_time for p in working) / len(working) if working else 0
            avg_success_rate = sum(p.success_rate for p in self.proxies) / total_count
        else:
            avg_response_time = 0
            avg_success_rate = 0

        return {
            'total_proxies': total_count,
            'working_proxies': working_count,
            'personal_proxies': personal_count,
            'avg_response_time': round(avg_response_time, 2),
            'avg_success_rate': round(avg_success_rate, 2),
            'last_update': self.last_proxy_update,
        }

    def get_adaptive_concurrency(self) -> int:
        """Suggest an adaptive concurrency limit based on proxy pool health."""
        if not getattr(self, "proxies", None):
            return 16
        working_count = len([p for p in self.proxies if p.is_working and p.success_rate > 0.5])
        if working_count >= 50:
            return 32
        elif working_count >= 20:
            return 16
        elif working_count >= 10:
            return 8
        elif working_count >= 5:
            return 4
        else:
            return 2
