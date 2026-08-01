"""Rate-limited HTTP with per-host token buckets, backoff and a circuit breaker.

Getting IP-banned by the SEC is the worst operational outcome available to this
project, so the bucket runs below the documented ceiling and is covered by a test
using a fake clock.
"""

import gzip
import json
import os
import threading
import time
import urllib.error
import urllib.request

# Per-host budgets. SEC documents 10 req/s; we sit at 8 for headroom.
# Companies House allows 600 requests per 5 minutes across ALL endpoints.
HOST_BUDGETS = {
    "data.sec.gov": (8.0, 1.0),
    "www.sec.gov": (8.0, 1.0),
    "efts.sec.gov": (5.0, 1.0),
    "api.company-information.service.gov.uk": (540.0, 300.0),
    "hn.algolia.com": (2.0, 1.0),
    "api.github.com": (20.0, 60.0),
    "stooq.com": (2.0, 1.0),
    "www.ecb.europa.eu": (2.0, 1.0),
}
DEFAULT_BUDGET = (2.0, 1.0)

RETRY_STATUS = {403, 429, 500, 502, 503, 504}
MAX_RETRIES = 5
BREAKER_THRESHOLD = 10


class SourceDegraded(Exception):
    """Raised when a host's circuit breaker has tripped."""


class _Bucket:
    """Token bucket: `capacity` tokens refilled over `window` seconds."""

    def __init__(self, capacity, window, clock=time.monotonic, sleep=time.sleep):
        self.capacity = float(capacity)
        self.window = float(window)
        self.tokens = float(capacity)
        self.updated = clock()
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()

    def take(self):
        while True:
            with self._lock:
                now = self._clock()
                elapsed = now - self.updated
                if elapsed > 0:
                    refill = elapsed * (self.capacity / self.window)
                    self.tokens = min(self.capacity, self.tokens + refill)
                    self.updated = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                deficit = 1.0 - self.tokens
                wait = deficit * (self.window / self.capacity)
            self._sleep(max(wait, 0.001))


class Session:
    """Shared HTTP session. One instance per run."""

    def __init__(self, user_agent=None, cache=None, clock=time.monotonic,
                 sleep=time.sleep, offline=False):
        self.user_agent = user_agent or os.environ.get(
            "SEC_USER_AGENT", "ciel-site sleeve scanner (contact@example.com)"
        )
        self.cache = cache
        self.offline = offline
        self._clock = clock
        self._sleep = sleep
        self._buckets = {}
        self._failures = {}
        self.degraded = set()
        self.stats = {"requests": 0, "cache_hits": 0, "retries": 0, "errors": 0}

    def _bucket(self, host):
        if host not in self._buckets:
            cap, win = HOST_BUDGETS.get(host, DEFAULT_BUDGET)
            self._buckets[host] = _Bucket(cap, win, self._clock, self._sleep)
        return self._buckets[host]

    def _host(self, url):
        return url.split("/")[2] if "://" in url else url.split("/")[0]

    def get(self, url, headers=None, ttl=None, binary=False):
        """Fetch a URL. Returns bytes (binary=True) or str.

        `ttl` of None means immutable: cached forever. Raises SourceDegraded if
        the host's breaker has tripped, so callers can skip a source and let the
        run finish rather than dying on one dead dependency.
        """
        host = self._host(url)
        if host in self.degraded:
            raise SourceDegraded(host)

        if self.cache is not None:
            hit = self.cache.get(url, ttl)
            if hit is not None:
                self.stats["cache_hits"] += 1
                return hit if binary else hit.decode("utf-8", "replace")

        if self.offline:
            raise SourceDegraded("%s (offline, no cache entry)" % host)

        req_headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json, text/html, */*",
        }
        if headers:
            req_headers.update(headers)

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            self._bucket(host).take()
            try:
                req = urllib.request.Request(url, headers=req_headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                self._failures[host] = 0
                self.stats["requests"] += 1
                if self.cache is not None:
                    self.cache.put(url, raw)
                return raw if binary else raw.decode("utf-8", "replace")
            except urllib.error.HTTPError as exc:
                last_err = exc
                if exc.code == 404:
                    self._failures[host] = 0
                    raise
                if exc.code not in RETRY_STATUS or attempt == MAX_RETRIES:
                    break
                delay = self._retry_after(exc) or (2 ** attempt)
                self.stats["retries"] += 1
                self._sleep(min(delay, 120))
            except Exception as exc:  # noqa: BLE001 - network layer is broad by nature
                last_err = exc
                if attempt == MAX_RETRIES:
                    break
                self.stats["retries"] += 1
                self._sleep(min(2 ** attempt, 120))

        self.stats["errors"] += 1
        self._failures[host] = self._failures.get(host, 0) + 1
        if self._failures[host] >= BREAKER_THRESHOLD:
            self.degraded.add(host)
        raise last_err if last_err else RuntimeError("request failed: %s" % url)

    @staticmethod
    def _retry_after(exc):
        value = exc.headers.get("Retry-After") if exc.headers else None
        if not value:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def get_json(self, url, headers=None, ttl=None, default=None):
        try:
            return json.loads(self.get(url, headers=headers, ttl=ttl))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return default
            raise
        except SourceDegraded:
            return default
        except json.JSONDecodeError:
            return default
