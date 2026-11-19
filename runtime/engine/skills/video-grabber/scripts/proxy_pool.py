#!/usr/bin/env python3
"""proxy_pool.py - rotating egress proxy pool for video-grabber.

Sources (merged, de-duplicated):
  * user file   (default %USERPROFILE%\\.video-grabber\\proxies.txt), one proxy per line
  * env var     VG_PROXIES  (comma / whitespace / semicolon separated)
  * Tor         socks5://127.0.0.1:9050  (only if tor=True and the port is open;
                NEWNYM rotation through control port 9051 when reachable)
  * free lists  public proxy lists (only if free=True). These are UNTRUSTED:
                proxy.trusted == False, and callers must not send cookies/credentials
                through them (ProxyPool.next(trusted_only=True) skips them).

Accepted line formats:  scheme://user:pass@host:port | scheme://host:port | host:port
                        | host:port:user:pass   (scheme defaults to http)
Schemes: http, https, socks5, socks5h, socks4.

If the pool is empty (or every proxy failed) next() returns None, which means
DIRECT connection (no proxy). Every report states this explicitly.

Importable:
    from proxy_pool import ProxyPool, Proxy
    pool = ProxyPool.from_sources(tor=False, free=False, check=True)
    p = pool.next()            # Proxy or None (= direct)
    pool.mark_bad(p)
    pool.current_ip(p)         # exit IP through p (or direct if None)

CLI:
    python proxy_pool.py check [--free] [--tor] [--file F] [--no-cache] [--json]
    python proxy_pool.py ip [--proxy URL|none] [--json]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import random
import re
import socket
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote, unquote, urlsplit

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

HOME = Path(os.environ.get("USERPROFILE") or Path.home())
VG_DIR = HOME / ".video-grabber"
DEFAULT_FILE = VG_DIR / "proxies.txt"
CACHE_DIR = VG_DIR / "cache"
CACHE_FILE = CACHE_DIR / "healthy_proxies.json"
CACHE_TTL = 30 * 60  # seconds
IP_URL = "https://api.ipify.org?format=json"
IP_FALLBACKS = ("https://ifconfig.me/ip", "https://icanhazip.com")
TOR_SOCKS = ("127.0.0.1", 9050)
TOR_CONTROL = ("127.0.0.1", 9051)
FREE_LIST_URLS = (
    # Well-known, frequently updated public lists. Quality is poor; treat as untrusted.
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=yes&anonymity=all",
)
FREE_SAMPLE = 150  # how many free proxies to health-check per run
SCHEMES = {"http", "https", "socks5", "socks5h", "socks4"}
DIRECT_LABEL = "direct (no proxy)"


# --------------------------------------------------------------------------- model
@dataclass
class Proxy:
    scheme: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    source: str = "file"          # file | env | tor | free | cli
    trusted: bool = True          # False for free/public proxies
    ok: Optional[bool] = None     # None = unchecked
    latency_ms: Optional[int] = None
    exit_ip: Optional[str] = None
    error: Optional[str] = None
    checked_at: Optional[float] = None
    fails: int = 0

    # ---- parsing -----------------------------------------------------------
    @classmethod
    def parse(cls, text: str, source: str = "file", trusted: Optional[bool] = None) -> "Proxy":
        s = text.strip()
        if not s:
            raise ValueError("empty proxy string")
        if "://" not in s:
            parts = s.split(":")
            if len(parts) == 4 and parts[1].isdigit():  # host:port:user:pass
                host, port, user, pw = parts
                s = f"http://{quote(user, safe='')}:{quote(pw, safe='')}@{host}:{port}"
            else:
                s = "http://" + s
        u = urlsplit(s)
        scheme = (u.scheme or "http").lower()
        if scheme not in SCHEMES:
            raise ValueError(f"unsupported proxy scheme: {scheme}")
        if not u.hostname or not u.port:
            raise ValueError(f"proxy needs host and port: {text!r}")
        return cls(
            scheme=scheme, host=u.hostname, port=int(u.port),
            username=unquote(u.username) if u.username else None,
            password=unquote(u.password) if u.password else None,
            source=source, trusted=(source != "free") if trusted is None else trusted,
        )

    # ---- representations ---------------------------------------------------
    @property
    def key(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def url(self) -> str:
        """Full URL including credentials (do not print; use .safe_url)."""
        auth = ""
        if self.username:
            auth = quote(self.username, safe="")
            if self.password:
                auth += ":" + quote(self.password, safe="")
            auth += "@"
        return f"{self.scheme}://{auth}{self.host}:{self.port}"

    @property
    def safe_url(self) -> str:
        return f"{self.scheme}://{'***@' if self.username else ''}{self.host}:{self.port}"

    def requests_proxies(self) -> dict:
        u = self.url
        if self.scheme == "socks5":  # resolve DNS on the proxy side
            u = "socks5h" + u[len("socks5"):]
        return {"http": u, "https": u}

    def playwright(self) -> dict:
        """Proxy dict for playwright (browser.new_context(proxy=...)).
        Note: Chromium does not support authenticated SOCKS proxies."""
        scheme = "socks5" if self.scheme == "socks5h" else self.scheme
        d = {"server": f"{scheme}://{self.host}:{self.port}"}
        if self.username:
            d["username"] = self.username
            d["password"] = self.password or ""
        return d

    def yt_dlp_arg(self) -> str:
        """Value for yt-dlp --proxy."""
        return self.url

    def public_dict(self) -> dict:
        d = asdict(self)
        d.pop("password", None)
        d["username"] = "***" if self.username else None
        d["url"] = self.safe_url
        return d

    def __str__(self) -> str:  # never leak credentials in logs
        return self.safe_url


def describe(proxy: Optional[Proxy]) -> str:
    return DIRECT_LABEL if proxy is None else f"{proxy.safe_url} [{proxy.source}{'' if proxy.trusted else ', UNTRUSTED'}]"


# --------------------------------------------------------------------------- helpers
def parse_lines(lines: Iterable[str], source: str) -> list[Proxy]:
    out = []
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        for tok in re.split(r"[\s,;]+", line):
            if not tok:
                continue
            try:
                out.append(Proxy.parse(tok, source=source))
            except ValueError:
                pass
    return out


def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def tor_newnym(password: Optional[str] = None, host: str = TOR_CONTROL[0], port: int = TOR_CONTROL[1]) -> bool:
    """Ask Tor for a new circuit (new exit IP). Needs ControlPort 9051 enabled
    (CookieAuthentication or HashedControlPassword, or no auth). Returns True on 250 OK."""
    password = password if password is not None else os.environ.get("VG_TOR_PASSWORD", "")
    try:
        with socket.create_connection((host, port), timeout=3) as s:
            f = s.makefile("rwb")

            def cmd(c: str) -> str:
                f.write((c + "\r\n").encode())
                f.flush()
                return f.readline().decode(errors="replace").strip()

            auth = cmd(f'AUTHENTICATE "{password}"')
            if not auth.startswith("250"):
                # try cookie auth
                info = cmd("PROTOCOLINFO 1")
                cookie_path = None
                while info and not info.startswith("250 OK"):
                    m = re.search(r'COOKIEFILE="([^"]+)"', info)
                    if m:
                        cookie_path = m.group(1).replace("\\\\", "\\")
                    info = f.readline().decode(errors="replace").strip()
                if not cookie_path or not Path(cookie_path).exists():
                    return False
                auth = cmd("AUTHENTICATE " + Path(cookie_path).read_bytes().hex())
                if not auth.startswith("250"):
                    return False
            return cmd("SIGNAL NEWNYM").startswith("250")
    except OSError:
        return False


def _session():
    if requests is None:
        raise RuntimeError("python package 'requests' is required (pip install requests[socks])")
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 video-grabber/1.0"
    return s


def get_exit_ip(proxy: Optional[Proxy] = None, timeout: float = 10.0) -> str:
    """Return the public exit IP seen by the internet (through proxy, or direct)."""
    s = _session()
    kw = {"timeout": timeout}
    if proxy is not None:
        kw["proxies"] = proxy.requests_proxies()
    last = None
    for url in (IP_URL,) + IP_FALLBACKS:
        try:
            r = s.get(url, **kw)
            r.raise_for_status()
            if "json" in url:
                return r.json()["ip"]
            ip = r.text.strip()
            if re.fullmatch(r"[0-9a-fA-F:.]+", ip):
                return ip
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"could not determine exit IP: {last}")


def check_proxy(p: Proxy, timeout: float = 8.0) -> Proxy:
    t0 = time.perf_counter()
    try:
        p.exit_ip = get_exit_ip(p, timeout=timeout)
        p.latency_ms = int((time.perf_counter() - t0) * 1000)
        p.ok, p.error = True, None
    except Exception as e:  # noqa: BLE001
        p.ok, p.latency_ms = False, None
        p.error = str(e).splitlines()[0][:200]
    p.checked_at = time.time()
    return p


def fetch_free_proxies(limit: int = FREE_SAMPLE, timeout: float = 10.0) -> list[Proxy]:
    """Download public proxy lists. Returned proxies are untrusted."""
    found: dict[str, Proxy] = {}
    s = _session()
    for url in FREE_LIST_URLS:
        try:
            r = s.get(url, timeout=timeout)
            if r.ok:
                for p in parse_lines(r.text.splitlines(), source="free"):
                    p.trusted = False
                    found.setdefault(p.key, p)
        except Exception:  # noqa: BLE001
            continue
    items = list(found.values())
    random.shuffle(items)
    return items[:limit]


# --------------------------------------------------------------------------- pool
@dataclass
class ProxyPool:
    proxies: list[Proxy] = field(default_factory=list)
    strategy: str = "round_robin"  # or "random"
    notes: list[str] = field(default_factory=list)
    max_fails: int = 2

    def __post_init__(self):
        self._lock = threading.Lock()
        self._idx = 0
        self._bad: set[str] = set()

    # ---- construction ------------------------------------------------------
    @classmethod
    def from_sources(cls, file=None, env: bool = True, tor: bool = False, free: bool = False,
                     check: bool = True, use_cache: bool = True, strategy: str = "round_robin",
                     timeout: float = 8.0, workers: int = 32) -> "ProxyPool":
        pool = cls(strategy=strategy)
        seen: set[str] = set()

        def add(items: Iterable[Proxy]):
            for p in items:
                if p.key not in seen:
                    seen.add(p.key)
                    pool.proxies.append(p)

        path = Path(file) if file else DEFAULT_FILE
        if path.exists():
            add(parse_lines(path.read_text(encoding="utf-8", errors="replace").splitlines(), "file"))
            pool.notes.append(f"loaded proxies from {path}")
        elif file:
            pool.notes.append(f"proxy file not found: {path}")
        if env and os.environ.get("VG_PROXIES"):
            add(parse_lines([os.environ["VG_PROXIES"]], "env"))
            pool.notes.append("loaded proxies from env VG_PROXIES")
        if tor:
            if port_open(*TOR_SOCKS):
                add([Proxy("socks5", TOR_SOCKS[0], TOR_SOCKS[1], source="tor")])
                pool.notes.append("Tor SOCKS 127.0.0.1:9050 is up"
                                  + ("; control port 9051 available for NEWNYM" if port_open(*TOR_CONTROL) else
                                     "; control port 9051 closed (no NEWNYM rotation)"))
            else:
                pool.notes.append("Tor requested but 127.0.0.1:9050 is not listening (Tor not running/installed)")
        if free:
            fp = fetch_free_proxies()
            add(fp)
            pool.notes.append(f"fetched {len(fp)} free public proxies (UNTRUSTED: no cookies/logins through them)")

        if check and pool.proxies:
            cached = _load_cache() if use_cache else {}
            fresh = {k: v for k, v in cached.items() if k in seen}
            to_check = [p for p in pool.proxies if p.key not in fresh]
            for p in pool.proxies:
                if p.key in fresh:
                    c = fresh[p.key]
                    p.ok, p.latency_ms, p.exit_ip, p.checked_at = c["ok"], c.get("latency_ms"), c.get("exit_ip"), c.get("checked_at")
            if fresh:
                pool.notes.append(f"{len(fresh)} proxies taken from health cache (TTL {CACHE_TTL // 60} min)")
            pool.check(to_check, timeout=timeout, workers=workers)
            pool.proxies = [p for p in pool.proxies if p.ok]
            pool.proxies.sort(key=lambda p: (not p.trusted, p.latency_ms or 10**9))
        if not pool.proxies:
            pool.notes.append("pool is empty -> using DIRECT connection (no proxy)")
        return pool

    # ---- health ------------------------------------------------------------
    def check(self, items: Optional[list[Proxy]] = None, timeout: float = 8.0, workers: int = 32) -> list[Proxy]:
        items = self.proxies if items is None else items
        if not items:
            return []
        with cf.ThreadPoolExecutor(max_workers=min(workers, len(items))) as ex:
            list(ex.map(lambda p: check_proxy(p, timeout), items))
        _save_cache(items)
        return items

    # ---- selection ---------------------------------------------------------
    def healthy(self, trusted_only: bool = False) -> list[Proxy]:
        return [p for p in self.proxies if p.key not in self._bad and p.ok is not False
                and (p.trusted or not trusted_only)]

    def next(self, trusted_only: bool = False) -> Optional[Proxy]:
        """Next proxy (round-robin or random). None means DIRECT (pool empty/exhausted)."""
        with self._lock:
            cands = self.healthy(trusted_only)
            if not cands:
                return None
            if self.strategy == "random":
                return random.choice(cands)
            p = cands[self._idx % len(cands)]
            self._idx += 1
            return p

    def mark_bad(self, p: Optional[Proxy], reason: str = "") -> None:
        if p is None:
            return
        with self._lock:
            p.fails += 1
            p.error = reason or p.error
            if p.fails >= self.max_fails or reason:
                self._bad.add(p.key)
                p.ok = False
        _save_cache([p])

    def rotate_tor(self) -> bool:
        return any(p.source == "tor" for p in self.proxies) and tor_newnym()

    @staticmethod
    def current_ip(proxy: Optional[Proxy] = None, timeout: float = 10.0) -> str:
        return get_exit_ip(proxy, timeout)

    def __len__(self):
        return len(self.healthy())

    def summary(self) -> dict:
        return {
            "healthy": [p.public_dict() for p in self.healthy()],
            "bad": sorted(self._bad),
            "count": len(self.healthy()),
            "mode": "proxy pool" if self.healthy() else DIRECT_LABEL,
            "notes": self.notes,
        }


# --------------------------------------------------------------------------- cache
def _load_cache() -> dict:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        now = time.time()
        return {k: v for k, v in data.items() if now - (v.get("checked_at") or 0) < CACHE_TTL}
    except Exception:  # noqa: BLE001
        return {}


def _save_cache(items: Iterable[Proxy]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {}
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        for p in items:
            if p.checked_at:
                data[p.key] = {"ok": p.ok, "latency_ms": p.latency_ms, "exit_ip": p.exit_ip,
                               "checked_at": p.checked_at, "source": p.source}
        CACHE_FILE.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- CLI
def _print(obj, as_json: bool):
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
        return
    for k, v in obj.items():
        if isinstance(v, list):
            print(f"{k}:")
            for i in v:
                print("  -", i if not isinstance(i, dict) else
                      f"{i.get('url')} src={i.get('source')} trusted={i.get('trusted')} "
                      f"latency={i.get('latency_ms')}ms exit_ip={i.get('exit_ip')}")
        else:
            print(f"{k}: {v}")


def main(argv=None) -> int:
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="video-grabber proxy pool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="load + health-check proxies")
    c.add_argument("--file")
    c.add_argument("--free", action="store_true", help="include free public proxies (untrusted)")
    c.add_argument("--tor", action="store_true", help="include Tor at 127.0.0.1:9050")
    c.add_argument("--no-env", action="store_true")
    c.add_argument("--no-cache", action="store_true")
    c.add_argument("--timeout", type=float, default=8.0)
    c.add_argument("--json", action="store_true")
    i = sub.add_parser("ip", help="show exit IP (direct or through a proxy)")
    i.add_argument("--proxy", default=None, help="proxy URL, or 'none' for direct")
    i.add_argument("--json", action="store_true")
    n = sub.add_parser("newnym", help="ask Tor for a new circuit")
    n.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "check":
        direct_ip = None
        try:
            direct_ip = get_exit_ip(None, timeout=a.timeout)
        except Exception as e:  # noqa: BLE001
            direct_ip = f"error: {e}"
        t0 = time.time()
        pool = ProxyPool.from_sources(file=a.file, env=not a.no_env, tor=a.tor, free=a.free,
                                      check=True, use_cache=not a.no_cache, timeout=a.timeout)
        out = pool.summary()
        out["direct_ip"] = direct_ip
        out["elapsed_s"] = round(time.time() - t0, 1)
        nxt = pool.next()
        out["next"] = describe(nxt)
        _print(out, a.json)
        return 0
    if a.cmd == "ip":
        p = None if (not a.proxy or a.proxy.lower() == "none") else Proxy.parse(a.proxy, source="cli")
        t0 = time.perf_counter()
        try:
            ip = get_exit_ip(p)
            _print({"via": describe(p), "exit_ip": ip, "latency_ms": int((time.perf_counter() - t0) * 1000)}, a.json)
            return 0
        except Exception as e:  # noqa: BLE001
            _print({"via": describe(p), "error": str(e)}, a.json)
            return 1
    if a.cmd == "newnym":
        ok = tor_newnym()
        _print({"tor_newnym": ok}, a.json)
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
