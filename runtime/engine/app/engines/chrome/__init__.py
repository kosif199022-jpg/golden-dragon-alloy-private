"""Chrome control: drive the real Google Chrome on this machine from the Black Dragon — tabs, navigate, read, click, type, screenshots, PDF.

Chrome is started with --remote-debugging-port on a dedicated Dragon profile (%LOCALAPPDATA%\\BlackDragon\\chrome\\profile;
Chrome refuses remote debugging on the user's default profile, and keeping it separate protects the personal profile).
Every command connects over CDP with Playwright, acts on the "current" tab, and disconnects — Chrome stays open.
`snapshot` numbers every visible interactive element (links, buttons, inputs) so later commands can say `--ref 7`.
Safety: typing into password or payment-card fields is refused; sending/buying/posting needs the user's explicit yes.
"""
import json, os, shutil, subprocess, time, urllib.request
from contextlib import contextmanager
from pathlib import Path

DATA = Path(os.environ.get("DRAGON_CHROME_DATA") or Path(os.environ.get("LOCALAPPDATA", ".")) / "BlackDragon" / "chrome")
PROFILE = DATA / "profile"
STATE = DATA / "state.json"
PORT = int(os.environ.get("DRAGON_CHROME_PORT", "9222"))

SNAPSHOT_JS = r"""(max) => {
  const sel = 'a[href],button,input:not([type=hidden]),textarea,select,summary,[role=button],[role=link],[role=tab],' +
              '[role=menuitem],[role=checkbox],[role=option],[role=searchbox],[role=textbox],[contenteditable=""],' +
              '[contenteditable=true],[onclick]';
  document.querySelectorAll('[data-dragon-ref]').forEach(e => e.removeAttribute('data-dragon-ref'));
  const out = []; let n = 0;
  for (const e of document.querySelectorAll(sel)) {
    const r = e.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const st = getComputedStyle(e);
    if (st.visibility === 'hidden' || st.display === 'none' || st.opacity === '0') continue;
    n++; e.setAttribute('data-dragon-ref', String(n));
    const label = (e.getAttribute('aria-label') || e.innerText || e.value || e.placeholder || e.title ||
                   e.getAttribute('alt') || e.name || '').trim().replace(/\s+/g, ' ').slice(0, 90);
    const item = {ref: n, tag: e.tagName.toLowerCase(), label,
                  inView: r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth};
    const kind = e.type || e.getAttribute('role'); if (kind) item.type = kind;
    if (e.href) item.href = e.href.slice(0, 160);
    out.push(item);
    if (n >= max) break;
  }
  return out;
}"""

GUARD_JS = """e => {
  const t = (e.type || '').toLowerCase(), ac = (e.autocomplete || '').toLowerCase(), nm = ((e.name || '') + ' ' + (e.id || '')).toLowerCase();
  if (t === 'password' || ac.includes('password')) return 'password';
  if (ac.startsWith('cc-') || /card.?num|cardnumber|cvc|cvv|security.?code|expir/.test(nm)) return 'payment';
  return '';
}"""


# ------------------------------------------------------------------ process
def exe() -> str:
    """chrome.exe: $CHROME, the standard install folders, then PATH."""
    cands = [os.environ.get("CHROME")]
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
        if base:
            cands.append(str(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"))
    cands += [shutil.which("chrome"), shutil.which("google-chrome")]
    for c in cands:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError("Google Chrome not found: install it or set CHROME=path\\to\\chrome.exe")


def _endpoint(port=PORT):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
            return json.loads(r.read())
    except Exception:
        return None


def launch(url=None, headless=False, port=PORT, wait=30) -> dict:
    """Start the Dragon Chrome (idempotent). A normal Chrome window the user can also see and use."""
    info = _endpoint(port)
    if info:
        if url:
            with session(port) as s:
                s.open(url)
        return {"running": True, "already": True, "port": port, "browser": info.get("Browser")}
    PROFILE.mkdir(parents=True, exist_ok=True)
    args = [exe(), f"--remote-debugging-port={port}", "--remote-allow-origins=http://127.0.0.1",
            f"--user-data-dir={PROFILE}", "--no-first-run", "--no-default-browser-check"]
    if headless:
        args.append("--headless=new")
    args.append(url or "about:blank")
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    t0 = time.time()
    while time.time() - t0 < wait:
        info = _endpoint(port)
        if info:
            return {"running": True, "already": False, "port": port, "browser": info.get("Browser"), "profile": str(PROFILE)}
        time.sleep(0.4)
    raise TimeoutError(f"Chrome ما فتحش منفذ التحكم {port} خلال {wait} ثانية")


def doctor(port=PORT) -> dict:
    try:
        path = exe()
    except FileNotFoundError as e:
        return {"chrome": None, "error": str(e)}
    # فولدرات النسخ جنب chrome.exe (زي 156.0.8078.81)؛ الأقدم هي الشغالة لو فيه تحديث مستني
    vers = sorted((d.name for d in Path(path).parent.iterdir() if d.is_dir() and d.name[:1].isdigit()),
                  key=lambda s: [int(x) for x in s.split(".") if x.isdigit()])
    ver = vers[0] if vers else None
    info = _endpoint(port)
    return {"chrome": path, "version": ver, "profile": str(PROFILE), "port": port,
            "running": bool(info), "browser": info.get("Browser") if info else None}


# ------------------------------------------------------------------ session
class Session:
    """One CDP connection to the Dragon Chrome. Use through `with session() as s:`."""

    def __init__(self, browser, port):
        self.browser, self.port = browser, port
        self.ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    # ---- tabs
    def _tid(self, page):
        cdp = self.ctx.new_cdp_session(page)
        try:
            return cdp.send("Target.getTargetInfo")["targetInfo"]["targetId"]
        finally:
            cdp.detach()

    def pages(self):
        return [p for p in self.ctx.pages if not p.url.startswith(("devtools://", "chrome-extension://"))]

    def _remember(self, page):
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"current": self._tid(page)}), "utf-8")

    @property
    def page(self):
        pages = self.pages()
        if not pages:
            p = self.ctx.new_page(); self._remember(p); return p
        try:
            cur = json.loads(STATE.read_text("utf-8")).get("current")
        except Exception:
            cur = None
        for p in pages:
            if cur and self._tid(p) == cur:
                return p
        return pages[-1]

    def tabs(self):
        cur = self.page
        return [{"index": i, "title": p.title(), "url": p.url, "current": p is cur} for i, p in enumerate(self.pages())]

    def use(self, which):
        pages = self.pages()
        if str(which).isdigit() and int(which) < len(pages):
            p = pages[int(which)]
        else:
            hits = [p for p in pages if str(which).lower() in (p.url + " " + p.title()).lower()]
            if not hits:
                raise LookupError(f"مفيش تاب فيه: {which}")
            p = hits[0]
        p.bring_to_front(); self._remember(p)
        return {"title": p.title(), "url": p.url}

    def open(self, url):
        p = self.ctx.new_page()
        self._remember(p)
        if url:
            p.goto(_norm(url), wait_until="domcontentloaded", timeout=45000)
        p.bring_to_front()
        return {"title": p.title(), "url": p.url}

    def close(self, which=None):
        p = self.page if which is None else self.pages()[int(which)]
        url = p.url; p.close()
        return {"closed": url}

    # ---- navigation
    def go(self, url):
        p = self.page
        p.goto(_norm(url), wait_until="domcontentloaded", timeout=45000)
        return {"title": p.title(), "url": p.url}

    def nav(self, how):
        p = self.page
        {"back": p.go_back, "forward": p.go_forward, "reload": p.reload}[how](wait_until="domcontentloaded")
        return {"title": p.title(), "url": p.url}

    # ---- reading
    def text(self, selector=None, max_chars=20000):
        p = self.page
        t = p.inner_text(selector or "body", timeout=10000)
        return {"title": p.title(), "url": p.url, "chars": len(t), "text": t[:max_chars]}

    def snapshot(self, max_items=150):
        p = self.page
        return {"title": p.title(), "url": p.url, "elements": p.evaluate(SNAPSHOT_JS, max_items)}

    def links(self, max_items=200):
        p = self.page
        return p.evaluate("""m => [...document.querySelectorAll('a[href]')].slice(0, m)
            .map(a => ({text: (a.innerText || a.title || '').trim().replace(/\\s+/g, ' ').slice(0, 90), href: a.href}))
            .filter(l => l.href.startsWith('http'))""", max_items)

    def evaluate(self, js):
        return self.page.evaluate(js)

    # ---- acting
    def _target(self, ref=None, selector=None, text=None):
        p = self.page
        if ref is not None:
            loc = p.locator(f'[data-dragon-ref="{int(ref)}"]')
            if not loc.count():
                raise LookupError(f"ref {ref} مش موجود — اعمل snapshot تاني (الصفحة اتغيرت)")
            return loc.first
        if selector:
            return p.locator(selector).first
        if text:
            return p.get_by_text(text, exact=False).first
        raise ValueError("حدّد --ref أو --selector أو --text")

    def click(self, ref=None, selector=None, text=None, xy=None, button="left", double=False):
        p = self.page
        if xy:
            p.mouse.click(float(xy[0]), float(xy[1]), button=button, click_count=2 if double else 1)
        else:
            loc = self._target(ref, selector, text)
            (loc.dblclick if double else loc.click)(button=button, timeout=10000)
        p.wait_for_timeout(600)
        return {"title": p.title(), "url": p.url}

    def type(self, value, ref=None, selector=None, text=None, enter=False, append=False):
        loc = self._target(ref, selector, text)
        kind = loc.evaluate(GUARD_JS)
        if kind:
            raise PermissionError(f"ممنوع: ده حقل {'باسورد' if kind == 'password' else 'بيانات دفع'} — المستخدم يكتبه بنفسه")
        if append:
            loc.click(); loc.press("End"); loc.press_sequentially(value, delay=15)
        else:
            loc.fill(value, timeout=10000)
        if enter:
            loc.press("Enter"); self.page.wait_for_timeout(800)
        return {"typed": len(value), "url": self.page.url}

    def press(self, key):
        self.page.keyboard.press(key)
        return {"pressed": key}

    def scroll(self, dy=800, dx=0):
        p = self.page
        p.mouse.wheel(dx, dy); p.wait_for_timeout(400)
        return {"scrollY": p.evaluate("scrollY")}

    def wait(self, selector=None, ms=None, state="visible"):
        p = self.page
        if selector:
            p.wait_for_selector(selector, state=state, timeout=ms or 30000)
        else:
            p.wait_for_timeout(ms or 1000)
        return {"url": p.url}

    # ---- output
    def shot(self, out, full=False, selector=None):
        p = self.page
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        (p.locator(selector).first.screenshot(path=str(out)) if selector else p.screenshot(path=str(out), full_page=full))
        return {"file": str(Path(out).resolve()), "url": p.url}

    def pdf(self, out):
        """PDF via CDP Page.printToPDF (works in headed Chrome too)."""
        import base64
        p = self.page
        cdp = self.ctx.new_cdp_session(p)
        try:
            data = cdp.send("Page.printToPDF", {"printBackground": True, "preferCSSPageSize": True})["data"]
        finally:
            cdp.detach()
        Path(out).write_bytes(base64.b64decode(data))
        return {"file": str(Path(out).resolve()), "url": p.url}


def _norm(url: str) -> str:
    u = url.strip()
    if "://" in u or u.startswith(("about:", "data:", "chrome:", "file:")):
        return u
    if " " in u or "." not in u:
        from urllib.parse import quote_plus
        return "https://duckduckgo.com/?q=" + quote_plus(u)
    return "https://" + u


@contextmanager
def session(port=PORT, autostart=True):
    if not _endpoint(port):
        if not autostart:
            raise ConnectionError(f"Dragon Chrome مش شغال على {port} — شغّله: python -m dragon run chrome launch")
        launch(port=port)
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        yield Session(browser, port)
    finally:
        pw.stop()  # بيقطع الاتصال بس — Chrome بيفضل مفتوح


def quit(port=PORT) -> dict:
    """Close the Dragon Chrome (only the debugging instance on the Dragon profile, never the user's own Chrome)."""
    if not _endpoint(port):
        return {"closed": False, "reason": "مش شغال"}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        try:
            b.new_browser_cdp_session().send("Browser.close")
        except Exception:
            pass
    return {"closed": True, "port": port}
