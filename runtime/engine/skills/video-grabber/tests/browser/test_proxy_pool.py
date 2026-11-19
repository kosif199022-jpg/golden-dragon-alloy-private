"""Offline unit tests for proxy_pool.py  (python -m pytest tests/browser -q)"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import proxy_pool as pp  # noqa: E402
from proxy_pool import Proxy, ProxyPool  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(pp, "CACHE_FILE", tmp_path / "cache" / "healthy.json")
    monkeypatch.setattr(pp, "DEFAULT_FILE", tmp_path / "none.txt")
    monkeypatch.delenv("VG_PROXIES", raising=False)


@pytest.mark.parametrize("text,scheme,host,port,user", [
    ("1.2.3.4:8080", "http", "1.2.3.4", 8080, None),
    ("socks5://u:p%40ss@10.0.0.1:1080", "socks5", "10.0.0.1", 1080, "u"),
    ("https://proxy.example.com:443", "https", "proxy.example.com", 443, None),
    ("5.6.7.8:3128:bob:secret", "http", "5.6.7.8", 3128, "bob"),
])
def test_parse(text, scheme, host, port, user):
    p = Proxy.parse(text)
    assert (p.scheme, p.host, p.port, p.username) == (scheme, host, port, user)


def test_parse_password_decoding_and_no_leak():
    p = Proxy.parse("socks5://u:p%40ss@10.0.0.1:1080")
    assert p.password == "p@ss"
    assert "p@ss" not in str(p) and "p%40ss" not in str(p) and "***" in p.safe_url
    assert p.requests_proxies()["https"].startswith("socks5h://")
    assert p.playwright() == {"server": "socks5://10.0.0.1:1080", "username": "u", "password": "p@ss"}


@pytest.mark.parametrize("bad", ["ftp://1.2.3.4:21", "justahost", ""])
def test_parse_rejects(bad):
    with pytest.raises(ValueError):
        Proxy.parse(bad)


def test_parse_lines_comments_and_separators():
    items = pp.parse_lines(["# comment", "1.1.1.1:80, 2.2.2.2:81", "socks5://3.3.3.3:1080  # tor-ish", "garbage"], "file")
    assert [p.key for p in items] == ["http://1.1.1.1:80", "http://2.2.2.2:81", "socks5://3.3.3.3:1080"]


def test_free_is_untrusted():
    assert Proxy.parse("1.1.1.1:80", source="free").trusted is False
    assert Proxy.parse("1.1.1.1:80", source="env").trusted is True


def test_empty_pool_means_direct():
    pool = ProxyPool.from_sources(env=False, check=False)
    assert pool.next() is None
    assert pp.describe(None) == pp.DIRECT_LABEL
    assert any("DIRECT" in n for n in pool.notes)
    assert pool.summary()["mode"] == pp.DIRECT_LABEL


def test_round_robin_mark_bad_and_trusted_only():
    pool = ProxyPool(proxies=[Proxy.parse("1.1.1.1:80"), Proxy.parse("2.2.2.2:80"),
                              Proxy.parse("3.3.3.3:80", source="free")])
    seq = [pool.next().host for _ in range(4)]
    assert seq == ["1.1.1.1", "2.2.2.2", "3.3.3.3", "1.1.1.1"]
    assert all(pool.next(trusted_only=True).trusted for _ in range(5))
    pool.mark_bad(pool.proxies[0], "403")
    assert "1.1.1.1" not in {pool.next().host for _ in range(6)}
    pool.mark_bad(pool.proxies[1], "x")
    pool.mark_bad(pool.proxies[2], "x")
    assert pool.next() is None  # exhausted -> direct


def test_env_and_file_loading(tmp_path, monkeypatch):
    f = tmp_path / "p.txt"
    f.write_text("1.1.1.1:80\nsocks5://2.2.2.2:1080\n", encoding="utf-8")
    monkeypatch.setenv("VG_PROXIES", "3.3.3.3:8080;1.1.1.1:80")
    pool = ProxyPool.from_sources(file=str(f), env=True, check=False)
    assert sorted(p.key for p in pool.proxies) == ["http://1.1.1.1:80", "http://3.3.3.3:8080", "socks5://2.2.2.2:1080"]


def test_check_uses_cache_and_filters(monkeypatch, tmp_path):
    calls = []

    def fake_ip(proxy=None, timeout=10):
        calls.append(proxy.host)
        if proxy.host == "9.9.9.9":
            raise RuntimeError("dead")
        return "203.0.113.7"

    monkeypatch.setattr(pp, "get_exit_ip", fake_ip)
    monkeypatch.setenv("VG_PROXIES", "1.1.1.1:80 9.9.9.9:80")
    pool = ProxyPool.from_sources(check=True)
    assert [p.host for p in pool.proxies] == ["1.1.1.1"]
    assert pool.proxies[0].exit_ip == "203.0.113.7" and pool.proxies[0].latency_ms is not None
    assert sorted(calls) == ["1.1.1.1", "9.9.9.9"]
    calls.clear()
    pool2 = ProxyPool.from_sources(check=True)  # second run within TTL -> from cache
    assert calls == [] and [p.host for p in pool2.proxies] == ["1.1.1.1"]


def test_tor_not_running_is_reported(monkeypatch):
    monkeypatch.setattr(pp, "port_open", lambda *a, **k: False)
    pool = ProxyPool.from_sources(env=False, tor=True, check=False)
    assert pool.next() is None
    assert any("Tor requested" in n for n in pool.notes)
