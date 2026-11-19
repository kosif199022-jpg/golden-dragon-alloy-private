"""claude_bridge - Krita plugin: run Python jobs dropped into a local folder, inside the real
Krita GUI, so Claude can paint with Krita's own brush engine while the user watches.

Folder: %APPDATA%/krita/claude_bridge/{inbox,outbox}, heartbeat.json
A job is a .py file. It runs on Krita's GUI thread with these names available:
  k, ManagedColor, InfoObject, QtCore, QtGui, QPointF, QPoint, QRectF, QPainterPath,
  canvas(w, h, name, bg)          -> (doc, view)  new document shown in a window
  active()                        -> (doc, view)  current document/view
  layer(doc, name)                -> new paint layer on top, made active
  brush(view, preset, size, color, opacity, flow) -> real Krita preset name used
  stroke(node, pts, pause)        -> pts [(x, y, pressure)], painted with the active brush
  path(node, painter_path)        -> one stroke along a QPainterPath
  pump(ms)                        -> let the UI repaint (so the user sees progress)
  save(doc, path) / export(doc, path)
  result = {...}                  -> returned to the caller
Nothing here touches the network. Delete the plugin folder + .desktop file to remove it.
"""
import glob
import json
import os
import time
import traceback

from krita import Extension, InfoObject, Krita, ManagedColor
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QPoint, QPointF, QRectF, QTimer
from PyQt5.QtGui import QPainterPath
from PyQt5.QtWidgets import QApplication

BASE = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "krita", "claude_bridge")
INBOX = os.path.join(BASE, "inbox")
OUTBOX = os.path.join(BASE, "outbox")


# ------------------------------------------------------------------ helpers for jobs
def pump(ms=30):
    end = time.time() + ms / 1000.0
    while True:
        QApplication.processEvents()
        if time.time() >= end:
            break
        time.sleep(0.005)


def _hex(c):
    c = c.lstrip("#")
    return [int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]


def canvas(w=1600, h=1200, name="claude", bg="#ffffff"):
    k = Krita.instance()
    doc = k.createDocument(int(w), int(h), name, "RGBA", "U8", "", 72.0)
    win = k.activeWindow() or (k.windows()[0] if k.windows() else None)
    if win is None:
        win = k.openWindow()
        win.qwindow().show()
    view = win.addView(doc)
    win.showView(view)
    k.setActiveDocument(doc)
    if bg and bg != "transparent":
        base = doc.rootNode().childNodes()[0]
        r, g, b = [int(round(x * 255)) for x in _hex(bg)]
        base.setPixelData(bytes([b, g, r, 255]) * (w * h), 0, 0, w, h)
        doc.refreshProjection()
    pump(200)
    return doc, view


def active():
    k = Krita.instance()
    win = k.activeWindow()
    view = win.activeView() if win else None
    return (view.document() if view else k.activeDocument()), view


def layer(doc, name="paint"):
    n = doc.createNode(name, "paintlayer")
    doc.rootNode().addChildNode(n, None)
    doc.setActiveNode(n)
    pump(50)
    return n


def brush(view, preset=None, size=None, color=None, opacity=None, flow=None):
    k = Krita.instance()
    if preset:
        presets = k.resources("preset")
        name = preset if preset in presets else next((n for n in sorted(presets) if preset.lower() in n.lower()), None)
        if name is None:
            raise KeyError("no brush preset matching %r" % preset)
        view.setCurrentBrushPreset(presets[name])
    if color:
        mc = ManagedColor("RGBA", "U8", "")
        r, g, b = _hex(color)
        mc.setComponents([b, g, r, 1.0])  # component order for RGBA/U8 is B,G,R,A
        view.setForeGroundColor(mc)
    if size is not None:
        view.setBrushSize(float(size))
    if opacity is not None:
        view.setPaintingOpacity(float(opacity))
    if flow is not None:
        view.setPaintingFlow(float(flow))
    return view.currentBrushPreset().name()


def stroke(node, pts, pause=0):
    """Pressure stroke: consecutive segments through Node.paintLine (real brush engine)."""
    pts = [tuple(p) + (1.0,) * (3 - len(p)) for p in pts]
    for a, b in zip(pts, pts[1:]):
        node.paintLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]), float(a[2]), float(b[2]))
        if pause:
            pump(pause)
    return len(pts)


def path(node, painter_path, stroke_style="foregroundColor", fill_style="none"):
    node.paintPath(painter_path, stroke_style, fill_style)


def save(doc, p):
    doc.waitForDone()
    return doc.saveAs(p)


def export(doc, p):
    doc.waitForDone()
    doc.refreshProjection()
    return doc.exportImage(p, InfoObject())


def quit_krita(close_unsaved=True):
    k = Krita.instance()
    for d in list(k.documents()):
        if close_unsaved:
            d.setModified(False)
        d.close()
    QTimer.singleShot(300, QApplication.instance().quit)


API = dict(k=None, ManagedColor=ManagedColor, InfoObject=InfoObject, QtCore=QtCore, QtGui=QtGui,
           QPointF=QPointF, QPoint=QPoint, QRectF=QRectF, QPainterPath=QPainterPath,
           canvas=canvas, active=active, layer=layer, brush=brush, stroke=stroke, path=path,
           pump=pump, save=save, export=export, quit_krita=quit_krita)


# ------------------------------------------------------------------ the extension
class ClaudeBridge(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        self.timer = None
        self.last_beat = 0
        self.busy = False

    def setup(self):
        for d in (INBOX, OUTBOX):
            os.makedirs(d, exist_ok=True)
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(250)

    def createActions(self, window):
        pass

    def beat(self, state="idle"):
        info = {"pid": os.getpid(), "time": time.time(), "state": state,
                "version": Krita.instance().version(), "windows": len(Krita.instance().windows())}
        tmp = os.path.join(BASE, "heartbeat.json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(info, fh)
        os.replace(tmp, os.path.join(BASE, "heartbeat.json"))
        self.last_beat = time.time()

    def tick(self):
        if self.busy:
            return
        if time.time() - self.last_beat > 1.5:
            self.beat()
        jobs = sorted(glob.glob(os.path.join(INBOX, "*.py")))
        if not jobs:
            return
        if not Krita.instance().windows():  # main window not up yet
            return
        self.busy = True
        try:
            for job in jobs:
                self.run(job)
        finally:
            self.busy = False

    def run(self, job):
        name = os.path.splitext(os.path.basename(job))[0]
        running = job[:-3] + ".running"
        try:
            os.replace(job, running)  # claim it
        except OSError:
            return
        self.beat("running " + name)
        out = {"job": name, "ok": False, "started": time.time()}
        g = dict(API)
        g["k"] = Krita.instance()
        g["result"] = {}
        try:
            with open(running, "r", encoding="utf-8") as fh:
                code = fh.read()
            exec(compile(code, name + ".py", "exec"), g)
            out["ok"] = True
            out["result"] = g.get("result")
        except Exception as e:  # noqa: BLE001  never let it reach Krita's excepthook dialog
            out["error"] = repr(e)
            out["trace"] = traceback.format_exc()[-2500:]
        out["seconds"] = round(time.time() - out["started"], 2)
        tmp = os.path.join(OUTBOX, name + ".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
        os.replace(tmp, os.path.join(OUTBOX, name + ".json"))
        try:
            os.remove(running)
        except OSError:
            pass
        self.beat()


Krita.instance().addExtension(ClaudeBridge(Krita.instance()))
