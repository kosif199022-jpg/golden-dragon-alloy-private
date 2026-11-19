"""Computer + Chrome control for the Black Dragon app.

computer_*  : screenshot, mouse, keyboard, windows (ctypes, no extra packages). Emergency stop: move the mouse to the
              top-left corner of the screen and every following action is refused until the user re-enables control.
BrowserBridge: a 127.0.0.1 HTTP long-poll bridge the «التنين الأسود» Chrome extension connects to (token-paired).
"""
import base64, ctypes, io, json, os, queue, re, secrets, threading, time, uuid
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

user32 = ctypes.windll.user32 if os.name == "nt" else None
if user32:
    user32.VkKeyScanW.restype = ctypes.c_short   # SHORT: -1 means "no key", high byte = Shift state
BRIDGE_PORT = 47851


class Stopped(Exception):
    pass


# ----------------------------------------------------------------------------------------------------- computer
class Computer:
    def __init__(self):
        self.scale = 1.0          # screenshot pixel -> screen pixel
        self.halted = False
        self.target = None        # window last focused by focus(); typing reports where it went

    # emergency stop: mouse in the top-left corner
    def check(self):
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        # the corner counts only when the user put the mouse there, not when our own move/click did
        if pt.x <= 2 and pt.y <= 2 and (pt.x, pt.y) != getattr(self, "_last_set", None):
            self.halted = True
        if self.halted:
            raise Stopped("التحكم اتوقف بفرملة الطوارئ (الماوس في الركن الشمال اللي فوق). المستخدم لازم يفعّله تاني.")

    def screenshot(self, max_w=1440):
        from PIL import ImageGrab
        im = ImageGrab.grab()
        w, h = im.size
        self.scale = max(1.0, w / max_w)
        if self.scale > 1:
            im = im.resize((int(w / self.scale), int(h / self.scale)))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=80)
        return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}, im.size

    def _xy(self, x, y):
        return int(round(x * self.scale)), int(round(y * self.scale))

    def move(self, x, y):
        self.check()
        X, Y = self._xy(x, y)
        self._last_set = (X, Y)
        user32.SetCursorPos(X, Y)

    def click(self, x, y, button="left", double=False):
        self.move(x, y)
        down, up = {"left": (0x2, 0x4), "right": (0x8, 0x10), "middle": (0x20, 0x40)}[button]
        for _ in range(2 if double else 1):
            user32.mouse_event(down, 0, 0, 0, 0)
            user32.mouse_event(up, 0, 0, 0, 0)
            time.sleep(0.06)

    def scroll(self, amount):
        self.check()
        user32.mouse_event(0x0800, 0, 0, int(amount) * 120, 0)

    # keyboard via SendInput (unicode for text, virtual keys for combos)
    def _send_key(self, vk=0, scan=0, flags=0):
        class KI(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p)]

        class MI(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p)]

        class U(ctypes.Union):
            _fields_ = [("ki", KI), ("mi", MI)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", U)]

        inp = INPUT(1, U(ki=KI(vk, scan, flags, 0, None)))
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def type_text(self, text):
        self.check()
        for i, ch in enumerate(text):
            if i % 8 == 0:
                self.check()   # the emergency stop works mid-text too
            if ch == "\n":
                self.key("enter")
                continue
            raw = ch.encode("utf-16-le")            # characters outside the BMP become two UTF-16 units
            codes = [int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2)]
            for c in codes:
                self._send_key(0, c, 0x0004)            # KEYEVENTF_UNICODE
                self._send_key(0, c, 0x0004 | 0x0002)   # + KEYUP
            time.sleep(0.004)

    VK = {"ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "enter": 0x0D, "return": 0x0D, "esc": 0x1B,
          "escape": 0x1B, "tab": 0x09, "space": 0x20, "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "home": 0x24, "end": 0x23,
          "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "insert": 0x2D,
          "printscreen": 0x2C, "capslock": 0x14, **{f"f{i}": 0x6F + i for i in range(1, 13)}}

    def key(self, combo):
        self.check()
        parts = [p.strip().lower() for p in combo.replace(" ", "").split("+") if p.strip()]
        vks = []
        for p in parts:
            if p in self.VK:
                vks.append(self.VK[p])
            elif len(p) == 1 and p.isascii() and p.isalnum():
                vks.append(ord(p.upper()))
            elif len(p) == 1:
                ks = user32.VkKeyScanW(ord(p))
                if ks == -1 or ks & 0xFF == 0xFF:
                    raise ValueError(f"مفتاح مش موجود على الكيبورد: {p}")
                if (ks >> 8) & 1 and 0x10 not in vks:   # symbols like ? need Shift
                    vks.append(0x10)
                vks.append(ks & 0xFF)
            else:
                raise ValueError(f"مفتاح مش معروف: {p}")
        for v in vks:
            self._send_key(v, 0, 0)
        for v in reversed(vks):
            self._send_key(v, 0, 0x0002)

    def windows(self):
        out = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _):
            if user32.IsWindowVisible(h) and user32.GetWindowTextLengthW(h):
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(h, buf, 512)
                out.append(buf.value)
            return True
        user32.EnumWindows(cb, 0)
        return [t for t in out if t.strip() and t not in ("Program Manager",)]

    def _find(self, title_part):
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _):
            if user32.IsWindowVisible(h):
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(h, buf, 512)
                if title_part.lower() in buf.value.lower():
                    found.append((h, buf.value))
                    return False
            return True
        user32.EnumWindows(cb, 0)
        if not found:
            raise ValueError(f"مفيش نافذة فيها «{title_part}»")
        return found[0]

    def window(self, title_part, op, x=None, y=None, w=None, h=None):
        """Move / resize / maximize / minimize / restore a window (coordinates in screenshot pixels like clicks)."""
        self.check()
        hwnd, t = self._find(title_part)
        if op == "maximize":
            user32.ShowWindow(hwnd, 3)
        elif op == "minimize":
            user32.ShowWindow(hwnd, 6)
        elif op == "restore":
            user32.ShowWindow(hwnd, 9)
        elif op in ("move", "resize", "set"):
            user32.ShowWindow(hwnd, 9)
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            X = int(x * self.scale) if x is not None else r.left
            Y = int(y * self.scale) if y is not None else r.top
            W = int(w * self.scale) if w is not None else r.right - r.left
            H = int(h * self.scale) if h is not None else r.bottom - r.top
            user32.MoveWindow(hwnd, X, Y, W, H, True)
        else:
            raise ValueError(f"عملية مش معروفة: {op}")
        return t

    def focus(self, title_part):
        self.check()
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _):
            if user32.IsWindowVisible(h):
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(h, buf, 512)
                if title_part.lower() in buf.value.lower():
                    found.append((h, buf.value))
                    return False
            return True
        user32.EnumWindows(cb, 0)
        if not found:
            raise ValueError(f"مفيش نافذة فيها «{title_part}»")
        h, t = found[0]
        if user32.IsIconic(h):
            user32.ShowWindow(h, 9)
        # Windows only lets the foreground thread hand over focus: borrow its input queue for a moment
        fg = user32.GetForegroundWindow()
        me = ctypes.windll.kernel32.GetCurrentThreadId()
        other = user32.GetWindowThreadProcessId(fg, None)
        user32.AttachThreadInput(other, me, True)
        user32.BringWindowToTop(h)
        user32.SetForegroundWindow(h)
        user32.AttachThreadInput(other, me, False)
        time.sleep(0.2)
        if user32.GetForegroundWindow() != h:
            raise RuntimeError(f"مقدرتش أجيب «{t}» لقدام. اضغط عليها بالماوس (click) الأول.")
        self.target = h
        return t

    def foreground_title(self):
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(user32.GetForegroundWindow(), buf, 512)
        return buf.value

    def drag(self, x1, y1, x2, y2, steps=24):
        """Press at (x1,y1), glide to (x2,y2), release: moving files, sliders, selections, drawing."""
        self.move(x1, y1)
        user32.mouse_event(0x2, 0, 0, 0, 0)
        try:
            for i in range(1, steps + 1):
                time.sleep(0.012)
                X, Y = self._xy(x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps)
                self._last_set = (X, Y)
                user32.SetCursorPos(X, Y)
            time.sleep(0.08)
        finally:
            user32.mouse_event(0x4, 0, 0, 0, 0)

    def cursor(self):
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return int(pt.x / self.scale), int(pt.y / self.scale)

    def zoom(self, x, y, w, h, out_w=1200):
        """A sharp crop of a screen region (screenshot pixels), for small text the full screenshot blurs."""
        from PIL import ImageGrab
        self.check()
        X, Y = self._xy(x, y)
        W, H = max(8, int(w * self.scale)), max(8, int(h * self.scale))
        im = ImageGrab.grab(bbox=(X, Y, X + W, Y + H))
        if im.size[0] < out_w:
            k = min(3.0, out_w / im.size[0])
            im = im.resize((int(im.size[0] * k), int(im.size[1] * k)))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=88)
        return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}


# ----------------------------------------------------------------------------------------------------- whole PC
# Windows Core Audio (IAudioEndpointVolume) through PowerShell + inline C#: the real master level, read and set exactly.
AUDIO_PS = r"""
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume { int f(); int g(); int h(); int i();
  int SetMasterVolumeLevelScalar(float fLevel, Guid pguidEventContext); int j();
  int GetMasterVolumeLevelScalar(out float pfLevel); int k(); int l(); int m(); int n();
  int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, Guid pguidEventContext); int GetMute(out bool pbMute); }
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice { int Activate(ref Guid id, int clsCtx, IntPtr activationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface); }
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator { int f(); int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice); }
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumeratorComObject { }
public class BDAudio {
  static IAudioEndpointVolume Vol() { var e = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator; IMMDevice d = null;
    Marshal.ThrowExceptionForHR(e.GetDefaultAudioEndpoint(0, 1, out d)); Guid id = typeof(IAudioEndpointVolume).GUID; object o;
    Marshal.ThrowExceptionForHR(d.Activate(ref id, 23, IntPtr.Zero, out o)); return (IAudioEndpointVolume)o; }
  public static float Get() { float v; Marshal.ThrowExceptionForHR(Vol().GetMasterVolumeLevelScalar(out v)); return v; }
  public static void Set(float v) { Marshal.ThrowExceptionForHR(Vol().SetMasterVolumeLevelScalar(v, Guid.Empty)); }
  public static bool Muted() { bool m; Marshal.ThrowExceptionForHR(Vol().GetMute(out m)); return m; }
}
'@ -ErrorAction Stop
"""


class System:
    """The PC beyond the mouse and keyboard: programs, processes, services, sound, brightness, clipboard, power, settings.
    Read actions run at once; the ones in DANGER change or stop something and the app asks the user first."""

    DANGER = {"kill", "service_start", "service_stop", "service_restart", "shutdown", "restart", "sleep", "logoff", "hibernate",
              "uninstall", "startup_disable"}
    ACTIONS = ["info", "processes", "kill", "apps", "launch", "services", "service_start", "service_stop", "service_restart",
               "volume", "mute", "brightness", "clipboard_get", "clipboard_set", "lock", "sleep", "hibernate", "shutdown", "restart",
               "logoff", "cancel_shutdown", "settings", "displays", "network", "wifi", "startup", "startup_disable", "installed",
               "uninstall", "disks", "battery", "notify"]

    @staticmethod
    def ps(script, timeout=60, stdin=None):
        import subprocess
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
               "[Console]::OutputEncoding=[Console]::InputEncoding=New-Object Text.UTF8Encoding $false; $ProgressPreference='SilentlyContinue'; " + script]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000)
        try:
            so, se = p.communicate(input=stdin.encode("utf-8") if stdin is not None else None, timeout=timeout)
        except subprocess.TimeoutExpired:
            # subprocess.run kills only powershell itself, then waits on pipes its children (winget, msiexec) still hold
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True, creationflags=0x08000000)
            try:
                p.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            raise
        out = (so or b"").decode("utf-8", "replace").strip()
        err = (se or b"").decode("utf-8", "replace").strip()
        return (out + ("\n" + err if err else "")).strip() or ("تم" if p.returncode == 0 else f"exit {p.returncode}"), p.returncode != 0

    @staticmethod
    def q(s):
        """A PowerShell single-quoted literal. PowerShell also ends a literal at the curly quotes ‘ ’ ‚ ‛, so all of them are doubled."""
        return "'" + re.sub("['‘’‚‛]", lambda m: m.group() * 2, str(s)) + "'"

    def _vk(self, vk, n=1):
        for _ in range(n):
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, 2, 0)
            time.sleep(0.01)

    def describe(self, act, a):
        """One plain-Arabic line shown on the approval card."""
        t = a.get("target") or a.get("text") or ""
        return {"kill": f"قفل البرنامج/العملية: {t}", "service_start": f"تشغيل خدمة ويندوز: {t}", "service_stop": f"إيقاف خدمة ويندوز: {t}",
                "service_restart": f"إعادة تشغيل خدمة ويندوز: {t}", "shutdown": "إطفاء الكمبيوتر (بعد 30 ثانية)",
                "restart": "إعادة تشغيل الكمبيوتر (بعد 30 ثانية)", "sleep": "وضع السكون", "hibernate": "وضع الإسبات",
                "logoff": "تسجيل خروج من ويندوز (بيقفل كل البرامج)", "uninstall": f"إزالة برنامج: {t}",
                "startup_disable": f"منع برنامج من التشغيل مع ويندوز: {t}"}.get(act, act)

    def run(self, act, a):
        q, ps = self.q, self.ps
        t = str(a.get("target") or a.get("text") or "").strip()
        n = int(a.get("amount") or 0)
        if act == "info":
            return ps("$o=Get-CimInstance Win32_OperatingSystem; $c=Get-CimInstance Win32_Processor | Select-Object -First 1; "
                      "$g=(Get-CimInstance Win32_VideoController | ForEach-Object Name) -join ', '; "
                      "\"OS: $($o.Caption) $($o.Version) | PC: $env:COMPUTERNAME | user: $env:USERNAME\"; "
                      "\"CPU: $($c.Name) ($($c.NumberOfLogicalProcessors) threads) load $($c.LoadPercentage)%\"; "
                      "\"RAM: $([math]::Round(($o.TotalVisibleMemorySize-$o.FreePhysicalMemory)/1MB,1)) / $([math]::Round($o.TotalVisibleMemorySize/1MB,1)) GB used\"; "
                      "\"GPU: $g\"; \"Uptime: $([math]::Round(((Get-Date)-$o.LastBootUpTime).TotalHours,1)) h\"; "
                      "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object { \"Disk $($_.DeviceID) $([math]::Round($_.FreeSpace/1GB,1)) GB free of $([math]::Round($_.Size/1GB,1))\" }")
        if act == "processes":
            flt = f"| Where-Object {{ $_.ProcessName -like {q('*' + t + '*')} -or $_.MainWindowTitle -like {q('*' + t + '*')} }} " if t else ""
            return ps(f"Get-Process {flt}| Sort-Object WS -Descending | Select-Object -First {n or 40} Id, ProcessName, "
                      "@{n='MB';e={[int]($_.WS/1MB)}}, @{n='CPUs';e={[int]$_.CPU}}, MainWindowTitle | Format-Table -AutoSize | Out-String -Width 200")
        if act == "kill":
            if not t:
                return "اكتب في target رقم العملية (PID) أو اسم البرنامج", True
            if t.isdigit():
                if int(t) == os.getpid():
                    return "ده التطبيق نفسه", True
                return ps(f"Stop-Process -Id {int(t)} -Force -PassThru | ForEach-Object {{ \"stopped $($_.ProcessName) ($($_.Id))\" }}")
            name = t[:-4] if t.lower().endswith(".exe") else t
            if name.lower() in ("blackdragon", "goldendragon", "explorer", "csrss", "winlogon", "lsass", "services", "smss", "wininit", "system", "svchost", "dwm"):
                return f"«{name}» من أساسيات ويندوز أو التطبيق نفسه، مش هتتقفل من هنا", True
            return ps(f"Get-Process -Name {q(name)} -ErrorAction Stop | Stop-Process -Force -PassThru | ForEach-Object {{ \"stopped $($_.ProcessName) ($($_.Id))\" }}")
        if act == "apps":
            flt = f"| Where-Object {{ $_.Name -like {q('*' + t + '*')} }} " if t else ""
            return ps(f"Get-StartApps {flt}| Sort-Object Name | Select-Object -First {n or 150} Name, AppID | Format-Table -AutoSize | Out-String -Width 220")
        if act == "launch":
            if not t:
                return "اكتب اسم البرنامج في target", True
            if os.path.exists(t) or "://" in t or t.lower().startswith(("ms-settings:", "shell:")):
                os.startfile(t)
                return f"opened {t}", False
            return ps(f"$a=Get-StartApps | Where-Object {{ $_.Name -like {q('*' + t + '*')} }} | Sort-Object {{ $_.Name.Length }} | Select-Object -First 1; "
                      f"if($a){{ Start-Process ('shell:AppsFolder\\'+$a.AppID); \"launched: $($a.Name)\" }} "
                      f"else {{ try {{ Start-Process {q(t)} -ErrorAction Stop; 'started: '+{q(t)} }} catch {{ Write-Error ('مفيش برنامج اسمه '+{q(t)}+'. جرّب action=apps'); exit 1 }} }}")
        if act == "services":
            flt = f"| Where-Object {{ $_.Name -like {q('*' + t + '*')} -or $_.DisplayName -like {q('*' + t + '*')} }} " if t else "| Where-Object Status -eq 'Running' "
            return ps(f"Get-Service {flt}| Select-Object -First {n or 120} Status, Name, DisplayName | Format-Table -AutoSize | Out-String -Width 200")
        if act in ("service_start", "service_stop", "service_restart"):
            if not t:
                return "اكتب اسم الخدمة في target", True
            verb = {"service_start": "Start-Service", "service_stop": "Stop-Service -Force", "service_restart": "Restart-Service -Force"}[act]
            out, err = ps(f"{verb} -Name {q(t)} -ErrorAction Stop; Get-Service -Name {q(t)} | ForEach-Object {{ \"$($_.Name): $($_.Status)\" }}")
            if err and ("denied" in out.lower() or "cannot open" in out.lower()):
                out += "\n(الخدمة دي محتاجة صلاحيات مدير: شغّل التطبيق كمسؤول Run as administrator)"
            return out, err
        if act == "volume":
            if a.get("amount") is None:
                return ps(AUDIO_PS + "\"volume $([math]::Round([BDAudio]::Get()*100))% muted=$([BDAudio]::Muted())\"")
            lvl = max(0, min(100, n))
            out, err = ps(AUDIO_PS + f"[BDAudio]::Set({lvl / 100}); \"volume set to $([math]::Round([BDAudio]::Get()*100))%\"")
            if err:                            # Core Audio unavailable: fall back to the volume keys (each press = 2%)
                self._vk(0xAE, 50)
                self._vk(0xAF, round(lvl / 2))
                return f"volume set to ~{round(lvl / 2) * 2}%", False
            return out, err
        if act == "mute":
            self._vk(0xAD)
            time.sleep(0.15)
            out, err = ps(AUDIO_PS + "\"muted=$([BDAudio]::Muted())\"")
            return ("mute toggled" if err else "mute toggled: " + out.strip()), False
        if act == "brightness":
            if a.get("amount") is None:
                return ps("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop).CurrentBrightness | ForEach-Object { \"brightness $_%\" }")
            lvl = max(0, min(100, n))
            return ps(f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop) | "
                      f"Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1;Brightness={lvl}}} | Out-Null; 'brightness set to {lvl}%'")
        if act == "clipboard_get":
            out, err = ps("Get-Clipboard -Raw")
            return (out[:20000] if out != "تم" else "(الحافظة فاضية أو فيها حاجة مش نص)"), err
        if act == "clipboard_set":
            return ps("$t=[Console]::In.ReadToEnd(); Set-Clipboard -Value $t; \"clipboard set ($($t.Length) chars)\"", stdin=str(a.get("text") or ""))
        if act == "lock":
            user32.LockWorkStation()
            return "locked", False
        if act == "sleep":
            return ps("Add-Type -AssemblyName System.Windows.Forms; [void][System.Windows.Forms.Application]::SetSuspendState('Suspend',$false,$false); 'sleeping'")
        if act == "hibernate":
            return ps("shutdown /h; 'hibernating'")
        if act in ("shutdown", "restart"):
            return ps(f"shutdown /{'s' if act == 'shutdown' else 'r'} /t 30 /c 'Black Dragon: {act} in 30s (cancel: shutdown /a)'; "
                      f"'{act} in 30 seconds. cancel with action=cancel_shutdown'")
        if act == "cancel_shutdown":
            return ps("shutdown /a; 'cancelled'")
        if act == "logoff":
            return ps("shutdown /l; 'logging off'")
        if act == "settings":
            page = t or ""
            if page and not re.fullmatch(r"[A-Za-z0-9_\-]+", page.replace("ms-settings:", "")):
                return "اسم صفحة الإعدادات غلط. أمثلة: display, sound, bluetooth, network-wifi, windowsupdate, apps-volume, personalization, storagesense", True
            os.startfile("ms-settings:" + page.replace("ms-settings:", ""))
            return f"opened Windows Settings: {page or 'home'}", False
        if act == "displays":
            return ps("Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::AllScreens | ForEach-Object { "
                      "\"$($_.DeviceName) $($_.Bounds.Width)x$($_.Bounds.Height) at ($($_.Bounds.X),$($_.Bounds.Y)) primary=$($_.Primary)\" }")
        if act == "network":
            return ps("Get-NetIPConfiguration | Where-Object { $_.IPv4Address } | ForEach-Object { "
                      "\"$($_.InterfaceAlias): $($_.IPv4Address.IPAddress) gw $($_.IPv4DefaultGateway.NextHop) dns $($_.DNSServer.ServerAddresses -join ',')\" }; "
                      "Get-NetAdapter | Where-Object Status -eq 'Up' | ForEach-Object { \"$($_.Name): $($_.InterfaceDescription) $($_.LinkSpeed)\" }")
        if act == "wifi":
            return ps("netsh wlan show interfaces | Select-String 'SSID|Signal|State|Radio type|Receive rate' | ForEach-Object { $_.Line.Trim() }")
        if act == "startup":
            return ps("Get-CimInstance Win32_StartupCommand | Select-Object Name, Location, Command | Format-Table -Wrap -AutoSize | Out-String -Width 220")
        if act == "startup_disable":
            if not t:
                return "اكتب اسم العنصر زي ما ظهر في action=startup", True
            return ps(f"$n={q(t)}; $done=$false; foreach($k in 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run') {{ "
                      "if((Get-ItemProperty $k -ErrorAction SilentlyContinue).PSObject.Properties.Name -contains $n) { "
                      "$v=(Get-ItemProperty $k).$n; New-Item 'HKCU:\\Software\\BlackDragon\\DisabledStartup' -Force | Out-Null; "
                      "Set-ItemProperty 'HKCU:\\Software\\BlackDragon\\DisabledStartup' -Name $n -Value $v; Remove-ItemProperty $k -Name $n; $done=$true } }; "
                      "if($done){\"disabled startup item: $n (القيمة القديمة محفوظة في HKCU\\Software\\BlackDragon\\DisabledStartup)\"} "
                      "else { Write-Error 'العنصر ده مش في مفتاح Run بتاع المستخدم. اقفله من Task Manager > Startup'; exit 1 }")
        if act == "installed":
            flt = f"| Where-Object {{ $_.DisplayName -like {q('*' + t + '*')} }} " if t else ""
            return ps("$k='HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*','HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',"
                      "'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'; Get-ItemProperty $k -ErrorAction SilentlyContinue | Where-Object DisplayName "
                      f"{flt}| Sort-Object DisplayName -Unique | Select-Object -First {n or 200} DisplayName, DisplayVersion, Publisher | Format-Table -AutoSize | Out-String -Width 200")
        if act == "uninstall":
            if not t:
                return "اكتب اسم البرنامج في target", True
            return ps(f"winget uninstall --name {q(t)} --exact --silent --accept-source-agreements --disable-interactivity 2>&1 | Select-Object -Last 6", timeout=600)
        if act == "disks":
            return ps("Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter, FileSystemLabel, FileSystem, @{n='FreeGB';e={[math]::Round($_.SizeRemaining/1GB,1)}}, "
                      "@{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}}, HealthStatus | Format-Table -AutoSize | Out-String -Width 160")
        if act == "battery":
            return ps("$b=Get-CimInstance Win32_Battery; if($b){ \"battery $($b.EstimatedChargeRemaining)% $(if($b.BatteryStatus -eq 2){'charging'}else{\"on battery, about $($b.EstimatedRunTime) min left\"})\" } else { 'no battery (desktop PC)' }")
        if act == "notify":
            if not t:
                return "اكتب نص الإشعار في text", True
            return ps("Add-Type -AssemblyName System.Windows.Forms; $n=New-Object System.Windows.Forms.NotifyIcon; $n.Icon=[System.Drawing.SystemIcons]::Information; "
                      f"$n.Visible=$true; $n.ShowBalloonTip(6000, 'التنين الذهبي', {q(t[:240])}, 'Info'); Start-Sleep 6; $n.Dispose(); 'notified'", timeout=20)
        return f"unknown system action {act}. المتاح: {', '.join(self.ACTIONS)}", True


# ----------------------------------------------------------------------------------------------------- Chrome bridge
class BrowserBridge:
    """The Chrome extension long-polls GET /poll and answers with POST /result. Only chrome-extension origins with the
    right token are served; the token is shown in the app's settings and pasted once into the extension popup."""

    def __init__(self, token):
        self.token, self.q, self.waiting = token, queue.Queue(), {}
        self.last_seen, self.info, self.ok = 0.0, {}, False
        self.on_control = None    # set by the app: handles /control calls from the MCP server
        self.on_app = None        # set by the app: handles /app calls (other Claude Code sessions talking to the app's chats)
        bridge = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _cors(self):
                origin = self.headers.get("Origin", "")
                if origin.startswith("chrome-extension://"):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Access-Control-Allow-Headers", "Content-Type")
                    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

            def _json(self, code, obj):
                body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self._cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _authed(self):
                q = parse_qs(urlparse(self.path).query)
                origin = self.headers.get("Origin", "")
                return q.get("t", [""])[0] == bridge.token and (not origin or origin.startswith("chrome-extension://")), q

            def do_OPTIONS(self):
                self.send_response(204)
                self._cors()
                self.end_headers()

            def do_GET(self):
                ok, q = self._authed()
                if urlparse(self.path).path != "/poll":
                    return self._json(404, {})
                if not ok:
                    return self._json(403, {"error": "bad token"})
                bridge.last_seen = time.time()
                bridge.info = {"version": q.get("v", [""])[0], "agent": self.headers.get("User-Agent", "")[:120]}
                cmd = {"type": "noop"}
                end = time.time() + 20
                while time.time() < end:
                    try:
                        c2 = bridge.q.get(timeout=max(0.1, end - time.time()))
                    except queue.Empty:
                        break
                    if c2.get("deadline", 0) >= time.time():   # skip commands whose caller already gave up
                        cmd = c2
                        break
                bridge.last_seen = time.time()
                self._json(200, cmd)

            def do_POST(self):
                ok, _ = self._authed()
                if not ok:
                    return self._json(403, {})
                if urlparse(self.path).path == "/control":       # Claude Code's MCP control server (mcp_control.py)
                    n = int(self.headers.get("Content-Length", "0") or 0)
                    try:
                        req = json.loads(self.rfile.read(n).decode("utf-8"))
                        res = bridge.on_control(req) if bridge.on_control else {"error": True, "content": [{"type": "text", "text": "control off"}]}
                    except Exception as e:
                        res = {"error": True, "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}]}
                    return self._json(200, res)
                if urlparse(self.path).path == "/app":           # status / chats / read / send from mcp_dragon.py (blackdragon_app)
                    n = int(self.headers.get("Content-Length", "0") or 0)
                    try:
                        req = json.loads(self.rfile.read(n).decode("utf-8"))
                        res = bridge.on_app(req) if bridge.on_app else {"ok": False, "error": "app link off"}
                    except Exception as e:
                        res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                    return self._json(200, res)
                if urlparse(self.path).path != "/result":
                    return self._json(403, {})
                n = int(self.headers.get("Content-Length", "0") or 0)
                try:
                    res = json.loads(self.rfile.read(n).decode("utf-8"))
                except ValueError:
                    return self._json(400, {})
                w = bridge.waiting.get(res.get("id"))
                if w:
                    w["result"] = res
                    w["event"].set()
                bridge.last_seen = time.time()
                self._json(200, {"ok": True})

        class ExclusiveServer(ThreadingHTTPServer):
            allow_reuse_address = False      # on Windows SO_REUSEADDR would let a 2nd process share the port

            def server_bind(self):
                import socket
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                super().server_bind()

        try:
            self.httpd = ExclusiveServer(("127.0.0.1", BRIDGE_PORT), H)
            threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
            self.ok = True
        except OSError as e:          # another copy of the app already owns the port
            self.error = str(e)

    @property
    def connected(self):
        return time.time() - self.last_seen < 45

    def call(self, action, params, timeout=90):
        if not self.ok:
            raise RuntimeError("جسر كروم مش شغال (فيه نسخة تانية من التطبيق فاتحة؟)")
        if not self.connected:
            raise RuntimeError("إضافة كروم مش متوصلة. افتح كروم، واتأكد إن إضافة «التنين الذهبي» متثبتة ومكتوب فيها كود الربط من الإعدادات.")
        cid = uuid.uuid4().hex
        w = {"event": threading.Event(), "result": None}
        self.waiting[cid] = w
        self.q.put({"type": "cmd", "id": cid, "action": action, "params": params, "deadline": time.time() + timeout})
        try:
            if not w["event"].wait(timeout):
                raise TimeoutError("الإضافة ما ردّتش في الوقت")
        finally:
            self.waiting.pop(cid, None)
        r = w["result"] or {}
        if not r.get("ok"):
            raise RuntimeError(r.get("error") or "فشل في كروم")
        return r.get("data")


def new_token():
    return secrets.token_urlsafe(12)
