"""v10.16.0 links registry: schema, privacy scan, routing, find/list/stats, add (offline)."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[2]
DATA = SKILL / "app" / "data" / "links.json"
spec = importlib.util.spec_from_file_location("bd_links", SKILL / "tools" / "links" / "links.py")
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)

REG = json.loads(DATA.read_text(encoding="utf-8"))
CATS = {"video-source", "music", "stock-media", "github-repo", "docs", "ai-service", "claude-artifact", "font", "reference", "other"}


def test_schema_valid():
    assert REG["schema"] == "black-dragon.links.v1"
    assert REG["generated"] == "2026-11-10"
    assert isinstance(REG["counts"], dict) and REG["counts"]["kept"] == len(REG["links"])
    assert 0 < len(REG["links"]) <= 1500
    seen = set()
    for l in REG["links"]:
        assert {"url", "domain", "category", "handler", "first_seen", "mentions", "roles"} <= set(l)
        assert l["url"].startswith(("http://", "https://"))
        assert l["category"] in CATS
        assert l["mentions"] >= 1 and set(l["roles"]) <= {"user", "assistant", "tool_result"}
        assert l["url"] not in seen
        seen.add(l["url"])


def test_no_secrets_emails_local():
    bad = re.compile(r"(?i)(token|secret|password|passwd|api[_-]?key|access_token|signature|x-amz-|sessionid|session=|auth=|sig=)")
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
    local = re.compile(r"(?i)^https?://(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|0\.0\.0\.0)|^file:")
    cdn = re.compile(r"(?i)googlevideo|fbcdn|cdninstagram|tiktokcdn|amazonaws|blob\.core")
    raw = DATA.read_text(encoding="utf-8")
    assert not email.search(raw)
    for l in REG["links"]:
        u = l["url"]
        assert not bad.search(u), u
        assert not local.search(u), u
        assert not cdn.search(u), u
        assert "?" not in u or "youtube.com/watch?v=" in u, u
        assert L.secret_reason(u) is None, u


@pytest.mark.parametrize("url,cat,handler", [
    ("https://www.youtube.com/watch?v=abc123", "video-source", "fetch"),
    ("https://www.instagram.com/reel/DfEs8ddsRXH", "video-source", "fetch"),
    ("https://vt.tiktok.com/ZSpBg5fpp", "video-source", "fetch"),
    ("https://github.com/kosif199022-jpg/kosif-tool", "github-repo", "repo"),
    ("https://www.pexels.com/video/abc-123/", "stock-media", "hunter"),
    ("https://fonts.google.com/specimen/Cairo", "font", "fonts"),
    ("https://claude.ai/artifact/AbCdEf123", "claude-artifact", "artifact"),
    ("https://higgsfield.ai/", "ai-service", "hf"),
    ("https://soundcloud.com/a/b", "music", "fetch"),
])
def test_route_classification(url, cat, handler):
    c = L.classify(url)
    assert c["category"] == cat and c["handler"] == handler


def test_route_cli_and_json(capsys):
    assert L.main(["route", "https://www.instagram.com/reel/DfEs8ddsRXH", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["handler"] == "fetch" and "tool fetch" in out["cmd"] and out["covered"] is True
    assert L.main(["route", "https://example.org/x?token=abc"]) == 2


def test_stats_find_list(capsys):
    assert L.main(["stats", "--json"]) == 0
    s = json.loads(capsys.readouterr().out)
    assert s["total"] >= len(REG["links"]) and "github-repo" in s["categories"] and len(s["top_domains"]) <= 15
    assert L.main(["find", "github", "--json", "--limit", "3"]) == 0
    f = json.loads(capsys.readouterr().out)
    assert f["matches"] > 0 and len(f["links"]) <= 3
    assert L.main(["list", "--category", "stock-media", "--limit", "5", "--json"]) == 0
    li = json.loads(capsys.readouterr().out)
    assert li["links"] and all(x["category"] == "stock-media" for x in li["links"])


def test_help_exits_zero():
    with pytest.raises(SystemExit) as e:
        L.main(["--help"])
    assert e.value.code == 0


def test_add_writes_tmp_and_refuses_secret(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert L.main(["add", "https://www.pexels.com/video/test-1/", "--note", "my note", "--json"]) == 0
    f = tmp_path / "BlackDragon" / "links_user.json"
    assert f.is_file()
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["links"][0]["note"] == "my note" and data["links"][0]["category"] == "stock-media"
    capsys.readouterr()
    assert L.main(["find", "my note", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["matches"] == 1
    for bad in ("https://x.com/a?token=abc", "https://a.b/c?X-Amz-Signature=1", "http://localhost:8000/x", "https://u:p@host.com/x", "https://a.com/?email=a@b.com"):
        assert L.main(["add", bad]) == 2
    assert len(json.loads(f.read_text(encoding="utf-8"))["links"]) == 1
    assert not (DATA.parent / "links_user.json").exists()
