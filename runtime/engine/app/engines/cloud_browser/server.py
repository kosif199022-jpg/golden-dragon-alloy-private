#!/usr/bin/env python3
"""سحاب (Sahab) — متصفح سحابي.

متصفح Chromium حقيقي شغّال على السيرفر (headless)، والصورة بتتبث للعميل لايف
عن طريق CDP Page.startScreencast، والماوس والكيبورد بيرجعوا عن طريق CDP Input.*.
العميل أي متصفح عادي (موبايل أو كمبيوتر)، وكل الصفحات بتتفتح على السيرفر مش على جهاز العميل.

تشغيل:  python server.py            (محلي على 127.0.0.1:8800)
       python server.py --host 0.0.0.0 --port 8800   (سحابي، بيقفل الشبكات الداخلية تلقائي)
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import ipaddress
import json
import logging
import os
import re
import secrets
import socket
import time
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from aiohttp import WSMsgType, web
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
log = logging.getLogger("sahab")

# أنماط إعلانات وتتبع بتتقفل على مستوى الشبكة (CDP Network.setBlockedURLs، من غير ما يتعطل الكاش)
AD_PATTERNS = [
    "*doubleclick.net*", "*googlesyndication.com*", "*googleadservices.com*",
    "*google-analytics.com*", "*adservice.google.*", "*scorecardresearch.com*",
    "*taboola.com*", "*outbrain.com*", "*adnxs.com*", "*criteo.com*", "*criteo.net*",
    "*amazon-adsystem.com*", "*hotjar.com*", "*moatads.com*", "*pubmatic.com*",
    "*rubiconproject.com*", "*openx.net*", "*quantserve.com*", "*adsrvr.org*",
    "*popads.net*", "*propellerads.com*", "*mgid.com*", "*revcontent.com*",
    "*zedo.com*", "*yieldmo.com*", "*smartadserver.com*", "*teads.tv*",
]

SEARCH = {
    "google": "https://www.google.com/search?q=",
    "ddg": "https://duckduckgo.com/?q=",
    "bing": "https://www.bing.com/search?q=",
}

FAVICON_JS = """() => {
  const l = document.querySelector('link[rel~="icon"],link[rel="shortcut icon"],link[rel="apple-touch-icon"]');
  return l ? l.href : (location.protocol.startsWith('http') ? location.origin + '/favicon.ico' : '');
}"""

CURSOR_JS = """([x, y]) => {
  const e = document.elementFromPoint(x, y);
  if (!e) return 'default';
  let c = getComputedStyle(e).cursor;
  if (c === 'auto') {
    const t = e.tagName;
    if (t === 'TEXTAREA' || e.isContentEditable || (t === 'INPUT' && !/^(button|submit|checkbox|radio|range|color|file|image|reset)$/i.test(e.type))) c = 'text';
    else if (e.closest('a[href]')) c = 'pointer';
    else c = 'default';
  }
  return c;
}"""


def resolve_input(text: str, engine: str) -> str:
    """تحويل اللي المستخدم كتبه في شريط العنوان لرابط أو بحث."""
    s = text.strip()
    if not s:
        return "about:blank"
    m = re.match(r"^([a-zA-Z][\w+.-]*):", s)
    if m and not re.match(r"^[\w.-]+:\d+", s):
        scheme = m.group(1).lower()
        if scheme in ("http", "https"):
            return s
        if s.lower() == "about:blank":
            return s
        return SEARCH[engine] + quote_plus(s)  # file: / chrome: / javascript: ممنوعين
    if " " not in s and (re.match(r"^(localhost|\d{1,3}(\.\d{1,3}){3})(:\d+)?(/|$)", s)):
        return "http://" + s
    if " " not in s and re.search(r"\.[a-zA-Z؀-ۿ]{2,}(:\d+)?(/|$|\?)", s):
        return "https://" + s
    return SEARCH[engine] + quote_plus(s)


class Tab:
    def __init__(self, tid: int, page, cdp):
        self.id = tid
        self.page = page
        self.cdp = cdp
        self.title = ""
        self.url = page.url
        self.loading = False
        self.favicon = ""
        self.zoom = 1.0
        self.dialog = None
        self.filechooser = None
        self.main_frame_id = None
        self.streaming = False

    def info(self):
        return {"id": self.id, "title": self.title or self.url or "تاب جديد", "url": self.url,
                "loading": self.loading, "hasIcon": bool(self.favicon), "zoom": self.zoom}


class Sahab:
    def __init__(self, args):
        self.args = args
        self.tabs: dict[int, Tab] = {}
        self.order: list[int] = []
        self.active: int | None = None
        self.clients: set[web.WebSocketResponse] = set()
        self._next = 1
        self.view = {"w": 1280, "h": 800, "dpr": 1.0}
        self.quality = args.quality
        self.adblock = not args.no_adblock
        self.engine = args.engine
        self.data = Path(args.data).resolve()
        self.downloads = self.data / "downloads"
        self.uploads = self.data / "uploads"
        for d in (self.data, self.downloads, self.uploads):
            d.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data / "state.json"
        self.state = {"bookmarks": [], "history": []}
        if self.state_file.exists():
            try:
                self.state.update(json.loads(self.state_file.read_text("utf-8")))
            except Exception:
                log.warning("state.json تالف، هبدأ من جديد")
        self._dns: dict[str, bool] = {}
        self._icons: dict[str, tuple[bytes, str]] = {}
        self._cursor = "default"
        self._cursor_task = None
        self._mouse = (0, 0)
        self._save_task = None
        self._adopting: dict = {}

    # ------------------------------------------------------------ lifecycle
    async def start(self):
        self.pw = await async_playwright().start()
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-features=Translate,MediaRouter",
            "--force-color-profile=srgb",
        ]
        profile = self.data / "profile"
        if self.args.doh:
            self._enable_doh(profile)
        self.ctx = await self.pw.chromium.launch_persistent_context(
            str(profile),
            headless=True,
            channel="chrome" if self.args.use_chrome else "chromium",
            no_viewport=True,
            accept_downloads=True,
            locale=self.args.locale,
            args=launch_args,
            ignore_default_args=["--enable-automation"],
        )
        if self.args.block_private:
            await self.ctx.route("**/*", self._guard)
        self.ctx.on("page", lambda p: asyncio.ensure_future(self._adopt(p, activate=True)))
        for p in list(self.ctx.pages):
            await self._adopt(p)
        if not self.tabs:
            await self.new_tab(self.args.home)
        elif self.active is None:
            await self.activate(self.order[0])
        asyncio.ensure_future(self._title_poller())

    def _enable_doh(self, profile: Path):
        """DNS آمن (DoH) جوه Chromium: بيتخطى أي DNS محلي بيرجّع عناوين غلط أو محجوبة."""
        profile.mkdir(parents=True, exist_ok=True)
        ls = profile / "Local State"
        try:
            state = json.loads(ls.read_text("utf-8")) if ls.exists() else {}
        except Exception:
            state = {}
        state["dns_over_https"] = {"mode": "secure", "templates": self.args.doh}
        ls.write_text(json.dumps(state), "utf-8")

    async def stop(self):
        self._save_now()
        try:
            await self.ctx.close()
        finally:
            await self.pw.stop()

    # ------------------------------------------------------------ security
    async def _is_private(self, host: str | None) -> bool:
        if not host:
            return True
        if host in self._dns:
            return self._dns[host]
        try:
            ips = [ipaddress.ip_address(host)]
        except ValueError:
            try:
                infos = await asyncio.get_running_loop().getaddrinfo(host, None)
                ips = [ipaddress.ip_address(i[4][0]) for i in infos]
            except Exception:
                ips = []
        bad = any(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                  or ip.is_multicast or ip.is_unspecified for ip in ips)
        self._dns[host] = bad
        return bad

    async def _guard(self, route):
        u = urlparse(route.request.url)
        if u.scheme in ("http", "https", "ws", "wss"):
            if await self._is_private(u.hostname):
                return await route.abort("blockedbyclient")
        elif u.scheme == "file":
            return await route.abort("blockedbyclient")
        await route.fallback()

    # ------------------------------------------------------------ tabs
    def _tab_of(self, page) -> Tab | None:
        for t in self.tabs.values():
            if t.page is page:
                return t
        return None

    async def _adopt(self, page, activate=False):
        existing = self._tab_of(page)
        if existing:
            return existing
        if id(page) in self._adopting:  # فيه adopt تاني شغال على نفس الصفحة: استناه
            return await asyncio.shield(self._adopting[id(page)])
        fut = asyncio.get_running_loop().create_future()
        self._adopting[id(page)] = fut
        try:
            tab = await self._adopt_inner(page, activate)
            fut.set_result(tab)
            return tab
        except Exception as e:
            fut.set_exception(e)
            raise
        finally:
            self._adopting.pop(id(page), None)

    async def _adopt_inner(self, page, activate):
        cdp = await self.ctx.new_cdp_session(page)
        tab = Tab(self._next, page, cdp)
        self._next += 1
        self.tabs[tab.id] = tab
        self.order.append(tab.id)
        await cdp.send("Page.enable")
        await cdp.send("Network.enable")
        await self._apply_adblock(tab)
        try:
            tree = await cdp.send("Page.getFrameTree")
            tab.main_frame_id = tree["frameTree"]["frame"]["id"]
        except Exception:
            pass

        cdp.on("Page.screencastFrame", lambda p: asyncio.ensure_future(self._on_frame(tab, p)))
        cdp.on("Page.frameStartedLoading", lambda p: self._loading(tab, p, True))
        cdp.on("Page.frameStoppedLoading", lambda p: self._loading(tab, p, False))
        page.on("framenavigated", lambda f: f == page.main_frame and asyncio.ensure_future(self._on_nav(tab)))
        page.on("load", lambda _: asyncio.ensure_future(self._on_load(tab)))
        page.on("close", lambda _: asyncio.ensure_future(self._on_close(tab)))
        page.on("download", lambda d: asyncio.ensure_future(self._on_download(d)))
        page.on("dialog", lambda d: asyncio.ensure_future(self._on_dialog(tab, d)))
        page.on("filechooser", lambda fc: asyncio.ensure_future(self._on_filechooser(tab, fc)))
        if activate or self.active is None:
            await self.activate(tab.id)
        else:
            self.broadcast_tabs()
        return tab

    async def new_tab(self, url="about:blank"):
        page = await self.ctx.new_page()
        tab = await self._adopt(page, activate=True)
        if self.active != tab.id:
            await self.activate(tab.id)
        if url and url != "about:blank":
            asyncio.ensure_future(self._goto(tab, url))
        return tab

    async def close_tab(self, tid):
        tab = self.tabs.get(tid)
        if not tab:
            return
        if len(self.tabs) == 1:
            await self.new_tab()
        await tab.page.close()

    async def _on_close(self, tab: Tab):
        if tab.id not in self.tabs:
            return
        idx = self.order.index(tab.id)
        del self.tabs[tab.id]
        self.order.remove(tab.id)
        if self.active == tab.id:
            self.active = None
            if self.order:
                await self.activate(self.order[min(idx, len(self.order) - 1)])
        self.broadcast_tabs()

    async def activate(self, tid):
        tab = self.tabs.get(tid)
        if not tab:
            return
        old = self.tabs.get(self.active) if self.active else None
        if old and old is not tab and old.streaming:
            try:
                await old.cdp.send("Page.stopScreencast")
            except Exception:
                pass
            old.streaming = False
        self.active = tid
        try:
            await tab.page.bring_to_front()
        except Exception:
            pass
        await self._apply_metrics(tab)
        await self._start_stream(tab)
        self.broadcast_tabs()

    async def _apply_metrics(self, tab: Tab):
        z, v = tab.zoom, self.view
        await tab.cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": max(200, int(v["w"] / z)), "height": max(150, int(v["h"] / z)),
            "deviceScaleFactor": v["dpr"] * z, "mobile": False,
        })

    async def _start_stream(self, tab: Tab):
        v = self.view
        if tab.streaming:
            try:
                await tab.cdp.send("Page.stopScreencast")
            except Exception:
                pass
        await tab.cdp.send("Page.startScreencast", {
            "format": "jpeg", "quality": self.quality,
            "maxWidth": int(v["w"] * v["dpr"]), "maxHeight": int(v["h"] * v["dpr"]),
            "everyNthFrame": 1,
        })
        tab.streaming = True
        # الـ screencast مابيبعتش فريم غير لما الصفحة تتغير، فنبعت صورة أولى فورًا
        try:
            shot = await tab.cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": self.quality})
            await self._send_frame(base64.b64decode(shot["data"]))
        except Exception:
            pass

    async def _on_frame(self, tab: Tab, p):
        try:
            if tab.id == self.active:
                await self._send_frame(base64.b64decode(p["data"]))
        finally:
            try:
                await tab.cdp.send("Page.screencastFrameAck", {"sessionId": p["sessionId"]})
            except Exception:
                pass

    async def _send_frame(self, data: bytes):
        dead = []
        for ws in list(self.clients):
            try:
                await asyncio.wait_for(ws.send_bytes(data), 3)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    # ------------------------------------------------------------ page events
    def _loading(self, tab: Tab, p, val):
        if tab.main_frame_id and p.get("frameId") != tab.main_frame_id:
            return
        tab.loading = val
        self.broadcast_tabs()

    async def _on_nav(self, tab: Tab):
        tab.url = tab.page.url
        tab.favicon = ""
        self.broadcast_tabs()

    async def _on_load(self, tab: Tab):
        try:
            tab.title = await tab.page.title()
            tab.url = tab.page.url
            tab.favicon = await tab.page.evaluate(FAVICON_JS) or ""
        except Exception:
            pass
        if tab.url.startswith("http"):
            h = self.state["history"]
            if not h or h[-1]["url"] != tab.url:
                h.append({"url": tab.url, "title": tab.title, "ts": int(time.time())})
                del h[:-1000]
                self._save_soon()
        self.broadcast_tabs()

    async def _title_poller(self):
        while True:
            await asyncio.sleep(1.5)
            changed = False
            for t in list(self.tabs.values()):
                try:
                    title = await t.page.title()
                    if title != t.title or t.page.url != t.url:
                        t.title, t.url, changed = title, t.page.url, True
                except Exception:
                    pass
            if changed:
                self.broadcast_tabs()

    async def _on_download(self, d):
        name = re.sub(r'[\\/:*?"<>|]+', "_", d.suggested_filename or "download") or "download"
        path = self.downloads / name
        stem, suf, n = path.stem, path.suffix, 1
        while path.exists():
            path = self.downloads / f"{stem} ({n}){suf}"
            n += 1
        self.broadcast({"t": "download", "state": "start", "name": path.name})
        try:
            await d.save_as(str(path))
            self.broadcast({"t": "download", "state": "done", "name": path.name, "size": path.stat().st_size})
        except Exception as e:
            self.broadcast({"t": "download", "state": "failed", "name": path.name, "error": str(e)})

    async def _on_dialog(self, tab: Tab, d):
        tab.dialog = d
        self.broadcast({"t": "dialog", "tab": tab.id, "kind": d.type, "message": d.message,
                        "default": d.default_value})
        await asyncio.sleep(120)
        if tab.dialog is d:  # محدش رد خلال دقيقتين
            tab.dialog = None
            try:
                await d.dismiss()
            except Exception:
                pass

    async def _on_filechooser(self, tab: Tab, fc):
        tab.filechooser = fc
        self.broadcast({"t": "filechooser", "tab": tab.id, "multiple": fc.is_multiple()})

    # ------------------------------------------------------------ settings
    async def _apply_adblock(self, tab: Tab):
        await tab.cdp.send("Network.setBlockedURLs", {"urls": AD_PATTERNS if self.adblock else []})

    def _save_soon(self):
        if self._save_task and not self._save_task.done():
            return

        async def later():
            await asyncio.sleep(2)
            self._save_now()
        self._save_task = asyncio.ensure_future(later())

    def _save_now(self):
        self.state_file.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), "utf-8")

    # ------------------------------------------------------------ broadcast
    def snapshot(self):
        cur = self.tabs.get(self.active)
        return {"t": "tabs", "tabs": [self.tabs[i].info() for i in self.order], "active": self.active,
                "bookmarked": bool(cur and any(b["url"] == cur.url for b in self.state["bookmarks"])),
                "adblock": self.adblock, "quality": self.quality, "engine": self.engine,
                "view": self.view}

    def broadcast_tabs(self):
        self.broadcast(self.snapshot())

    def broadcast(self, msg):
        s = json.dumps(msg, ensure_ascii=False)
        for ws in list(self.clients):
            if not ws.closed:
                asyncio.ensure_future(ws.send_str(s))

    # ------------------------------------------------------------ input
    async def _goto(self, tab: Tab, url):
        try:
            await tab.page.goto(url, wait_until="commit", timeout=45000)
        except Exception as e:
            self.broadcast({"t": "toast", "text": f"مقدرتش أفتح الصفحة: {str(e).splitlines()[0][:160]}"})

    async def _update_cursor(self, tab: Tab):
        await asyncio.sleep(0.08)
        self._cursor_task = None
        x, y = self._mouse
        try:
            c = await tab.page.evaluate(CURSOR_JS, [x, y])
        except Exception:
            return
        if c != self._cursor:
            self._cursor = c
            self.broadcast({"t": "cursor", "c": c})

    async def handle(self, ws, m):
        t = m.get("t")
        tab = self.tabs.get(self.active)
        if t == "ping":
            await ws.send_str(json.dumps({"t": "pong", "ts": m.get("ts")}))
            return
        if t == "resize":
            self.view = {"w": max(200, int(m["w"])), "h": max(150, int(m["h"])),
                         "dpr": min(3.0, max(1.0, float(m.get("dpr", 1))))}
            if tab:
                await self._apply_metrics(tab)
                await self._start_stream(tab)
            return
        if t == "newtab":
            await self.new_tab(resolve_input(m["url"], self.engine) if m.get("url") else "about:blank")
            return
        if t == "activate":
            await self.activate(int(m["id"]))
            return
        if t == "close":
            await self.close_tab(int(m.get("id", self.active)))
            return
        if t == "adblock":
            self.adblock = bool(m["on"])
            for tb in self.tabs.values():
                await self._apply_adblock(tb)
            self.broadcast_tabs()
            return
        if t == "quality":
            self.quality = max(20, min(100, int(m["q"])))
            if tab:
                await self._start_stream(tab)
            self.broadcast_tabs()
            return
        if t == "engine" and m.get("e") in SEARCH:
            self.engine = m["e"]
            self.broadcast_tabs()
            return
        if not tab:
            return
        cdp, z = tab.cdp, tab.zoom

        if t == "mouse":
            x, y = m["x"] / z, m["y"] / z
            await cdp.send("Input.dispatchMouseEvent", {
                "type": m["e"], "x": x, "y": y, "button": m.get("b", "none"),
                "buttons": m.get("bs", 0), "clickCount": m.get("c", 0), "modifiers": m.get("mod", 0)})
            if m["e"] == "mouseMoved":
                self._mouse = (x, y)
                if not self._cursor_task:
                    self._cursor_task = asyncio.ensure_future(self._update_cursor(tab))
        elif t == "wheel":
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseWheel", "x": m["x"] / z, "y": m["y"] / z,
                "deltaX": m.get("dx", 0), "deltaY": m.get("dy", 0), "modifiers": m.get("mod", 0)})
        elif t == "key":
            ev = {"type": m["e"], "modifiers": m.get("mod", 0), "key": m.get("key", ""),
                  "code": m.get("code", ""), "windowsVirtualKeyCode": m.get("kc", 0),
                  "nativeVirtualKeyCode": m.get("kc", 0)}
            if m.get("text"):
                ev["text"] = ev["unmodifiedText"] = m["text"]
            if m.get("cmd"):
                ev["commands"] = m["cmd"]
            await cdp.send("Input.dispatchKeyEvent", ev)
            if m.get("cmd") and set(m["cmd"]) & {"copy", "cut"}:
                await self._send_selection(ws, tab)
        elif t == "text":
            await cdp.send("Input.insertText", {"text": m["text"]})
        elif t == "copy":
            await self._send_selection(ws, tab)
        elif t == "nav":
            await self._goto(tab, resolve_input(m["url"], self.engine))
        elif t == "back":
            await tab.page.go_back(wait_until="commit")
        elif t == "forward":
            await tab.page.go_forward(wait_until="commit")
        elif t == "reload":
            await tab.page.reload(wait_until="commit")
        elif t == "stop":
            await cdp.send("Page.stopLoading")
        elif t == "zoom":
            tab.zoom = 1.0 if m.get("reset") else round(max(0.25, min(5.0, tab.zoom * (1.1 if m["d"] > 0 else 1 / 1.1))), 2)
            await self._apply_metrics(tab)
            await self._start_stream(tab)
            self.broadcast_tabs()
        elif t == "find":
            found = await tab.page.evaluate("([s, b]) => window.find(s, false, b, true)", [m["q"], bool(m.get("back"))])
            await ws.send_str(json.dumps({"t": "found", "ok": found}))
        elif t == "dialog" and tab.dialog:
            d, tab.dialog = tab.dialog, None
            if m.get("accept"):
                await (d.accept(m.get("text", "")) if d.type == "prompt" else d.accept())
            else:
                await d.dismiss()
        elif t == "bookmark":
            bms = self.state["bookmarks"]
            hit = [b for b in bms if b["url"] == tab.url]
            if hit:
                bms.remove(hit[0])
            elif tab.url.startswith("http"):
                bms.append({"url": tab.url, "title": tab.title or tab.url})
            self._save_soon()
            self.broadcast_tabs()

    async def _send_selection(self, ws, tab):
        await asyncio.sleep(0.05)
        try:
            txt = await tab.page.evaluate("() => { const a = document.activeElement;"
                                          " if (a && (a.tagName==='TEXTAREA'||a.tagName==='INPUT') && a.selectionStart!=null)"
                                          " return a.value.substring(a.selectionStart, a.selectionEnd);"
                                          " return String(getSelection()); }")
        except Exception:
            txt = ""
        if txt:
            await ws.send_str(json.dumps({"t": "clipboard", "text": txt}, ensure_ascii=False))


# ================================================================== HTTP layer
def build_app(sb: Sahab, token: str | None):
    @web.middleware
    async def auth(request, handler):
        if token is None or request.path.startswith("/static/"):
            return await handler(request)
        q = request.query.get("token")
        if q and secrets.compare_digest(q, token):
            resp = web.HTTPFound("/")
            resp.set_cookie("sahab", token, httponly=True, samesite="Strict", max_age=30 * 86400)
            raise resp
        c = request.cookies.get("sahab", "")
        if not secrets.compare_digest(c, token):
            return web.Response(status=401, text="401 — افتح الرابط اللي فيه ?token= من شاشة السيرفر.",
                                content_type="text/plain", charset="utf-8")
        return await handler(request)

    app = web.Application(middlewares=[auth], client_max_size=512 * 1024 * 1024)

    async def index(_):
        return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    async def ws_handler(request):
        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=8 * 1024 * 1024)
        await ws.prepare(request)
        sb.clients.add(ws)
        await ws.send_str(json.dumps(sb.snapshot(), ensure_ascii=False))
        tab = sb.tabs.get(sb.active)
        if tab:
            asyncio.ensure_future(sb._start_stream(tab))
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                try:
                    await sb.handle(ws, json.loads(msg.data))
                except Exception as e:
                    log.debug("input error: %s", e)
        finally:
            sb.clients.discard(ws)
        return ws

    async def favicon(request):
        tab = sb.tabs.get(int(request.match_info["tid"]))
        url = tab.favicon if tab else ""
        if not url.startswith("http"):
            raise web.HTTPNotFound()
        if url not in sb._icons:
            if sb.args.block_private and await sb._is_private(urlparse(url).hostname):
                raise web.HTTPNotFound()
            try:
                r = await sb.ctx.request.get(url, timeout=5000, max_redirects=3)
                body = await r.body()
                ctype = r.headers.get("content-type", "image/x-icon")
                if not r.ok or len(body) > 512 * 1024 or not ctype.startswith("image"):
                    raise ValueError
                sb._icons[url] = (body, ctype)
            except Exception:
                sb._icons[url] = (b"", "")
        body, ctype = sb._icons[url]
        if not body:
            raise web.HTTPNotFound()
        return web.Response(body=body, content_type=ctype.split(";")[0], headers={"Cache-Control": "max-age=3600"})

    async def downloads(_):
        files = sorted(sb.downloads.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        return web.json_response([{"name": f.name, "size": f.stat().st_size} for f in files if f.is_file()])

    async def download_file(request):
        name = request.match_info["name"]
        p = (sb.downloads / name).resolve()
        if p.parent != sb.downloads or not p.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(p, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote_plus(name)}"})

    async def upload(request):
        tab = sb.tabs.get(int(request.match_info["tid"]))
        if not tab or not tab.filechooser:
            raise web.HTTPBadRequest(text="مفيش نافذة رفع مفتوحة")
        reader = await request.multipart()
        folder = sb.uploads / secrets.token_hex(6)
        folder.mkdir()
        paths = []
        while (part := await reader.next()) is not None:
            if not part.filename:
                continue
            name = re.sub(r'[\\/:*?"<>|]+', "_", part.filename)
            dest = folder / name
            with dest.open("wb") as f:
                while chunk := await part.read_chunk():
                    f.write(chunk)
            paths.append(str(dest))
        fc, tab.filechooser = tab.filechooser, None
        await fc.set_files(paths if fc.is_multiple() else paths[:1])
        return web.json_response({"ok": True, "files": len(paths)})

    async def cancel_upload(request):
        tab = sb.tabs.get(int(request.match_info["tid"]))
        if tab:
            tab.filechooser = None
        return web.json_response({"ok": True})

    async def screenshot(request):
        tab = sb.tabs.get(sb.active)
        if not tab:
            raise web.HTTPNotFound()
        png = await tab.page.screenshot(full_page=request.query.get("full") == "1", type="png")
        return web.Response(body=png, content_type="image/png",
                            headers={"Content-Disposition": f'attachment; filename="sahab-{int(time.time())}.png"'})

    async def pdf(_):
        tab = sb.tabs.get(sb.active)
        if not tab:
            raise web.HTTPNotFound()
        data = await tab.page.pdf(print_background=True)
        return web.Response(body=data, content_type="application/pdf",
                            headers={"Content-Disposition": f'attachment; filename="sahab-{int(time.time())}.pdf"'})

    async def state(_):
        return web.json_response({"bookmarks": sb.state["bookmarks"],
                                  "history": list(reversed(sb.state["history"][-300:]))})

    app.add_routes([
        web.get("/", index), web.get("/ws", ws_handler),
        web.get("/api/favicon/{tid}", favicon), web.get("/api/downloads", downloads),
        web.get("/api/downloads/{name}", download_file), web.post("/api/upload/{tid}", upload),
        web.post("/api/upload/{tid}/cancel", cancel_upload),
        web.get("/api/screenshot", screenshot), web.get("/api/pdf", pdf), web.get("/api/state", state),
        web.static("/static", STATIC),
    ])

    async def on_start(_):
        await sb.start()

    async def on_stop(_):
        await sb.stop()

    app.on_startup.append(on_start)
    app.on_cleanup.append(on_stop)
    return app


def main():
    ap = argparse.ArgumentParser(description="سحاب — متصفح سحابي مبني على Chromium")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--data", default=os.environ.get("SAHAB_DATA") or str(Path(os.environ.get("LOCALAPPDATA", ROOT)) / "BlackDragon" / "sahab"), help="مكان البروفايل والتحميلات والإشارات")
    ap.add_argument("--home", default="about:blank")
    ap.add_argument("--engine", default="ddg", choices=list(SEARCH))
    ap.add_argument("--locale", default="ar-EG")
    ap.add_argument("--quality", type=int, default=80, help="جودة JPEG للبث 20-100")
    ap.add_argument("--use-chrome", action="store_true", help="استخدم Google Chrome المتسطّب بدل Chromium")
    ap.add_argument("--no-adblock", action="store_true")
    ap.add_argument("--token", default=None, help="كلمة الدخول (لو مش محددة بتتولد عشوائي)")
    ap.add_argument("--no-auth", action="store_true", help="من غير كلمة دخول (محلي بس)")
    ap.add_argument("--block-private", choices=["auto", "on", "off"], default="auto",
                    help="منع الوصول للشبكات الداخلية (SSRF). auto = يشتغل لو السيرفر مفتوح على الشبكة")
    ap.add_argument("--doh", default="https://1.1.1.1/dns-query https://8.8.8.8/dns-query",
                    help="سيرفرات DNS-over-HTTPS (مسافة بينهم)")
    ap.add_argument("--no-doh", action="store_const", const="", dest="doh", help="استخدم DNS الجهاز العادي")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(message)s")

    local = args.host in ("127.0.0.1", "localhost", "::1")
    args.block_private = (args.block_private == "on") or (args.block_private == "auto" and not local)
    if args.no_auth and not local:
        raise SystemExit("ممنوع --no-auth والسيرفر مفتوح على الشبكة.")
    token = None if args.no_auth else (args.token or secrets.token_urlsafe(18))

    sb = Sahab(args)
    app = build_app(sb, token)
    shown = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    url = f"http://{shown}:{args.port}/" + (f"?token={token}" if token else "")
    print(f"\n  سحاب شغّال ← {url}\n  حماية الشبكة الداخلية: {'شغالة' if args.block_private else 'مقفولة'}\n", flush=True)
    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
