"""lift: a still text with outline over moving footage comes back pixel for pixel, and its zoom is tracked."""
import json, os, subprocess, sys, tempfile, unittest
try:                       # optional media stack: a bare machine skips, never errors
    import numpy as np, cv2
except ImportError:        # pragma: no cover - depends on the machine
    np = cv2 = None

HERE = os.path.dirname(os.path.abspath(__file__))
LIFT = os.path.join(HERE, 'agent', 'mimic', 'lift.py')


def _text_layer():
    """RGBA text: white bar with a dark brown 2 px outline, and a small dot."""
    a = np.zeros((1024, 576), np.uint8); c = np.zeros((1024, 576, 3), np.uint8)
    cv2.rectangle(a, (198, 498), (382, 522), 255, -1); cv2.rectangle(a, (284, 478), (294, 488), 255, -1)
    c[a > 0] = (27, 40, 64)                                  # outline colour (BGR)
    inner = cv2.erode(a, np.ones((5, 5), np.uint8)); c[inner > 0] = (251, 251, 251)
    return c, a


def _video(path, zoom_from=2.0):
    """4 s at 30 fps, 576x1024: moving noise; the text stands still, then zooms 0 -> 10 % after zoom_from."""
    rng = np.random.default_rng(5); base = cv2.GaussianBlur(rng.integers(30, 200, (1024 + 400, 576, 3), dtype=np.uint8), (41, 41), 0)
    c, a = _text_layer(); w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), 30, (576, 1024))
    for i in range(120):
        t = i / 30; f = base[i * 3:i * 3 + 1024].copy().astype(np.float32)
        z = 1 + 0.1 * max(0, t - zoom_from) / 2
        M = cv2.getRotationMatrix2D((290, 510), 0, z)
        cz = cv2.warpAffine(c, M, (576, 1024)).astype(np.float32); az = cv2.warpAffine(a, M, (576, 1024)).astype(np.float32)[..., None] / 255
        w.write((cz * az + f * (1 - az)).astype(np.uint8))
    w.release()


def _check_lift_recovers_text_and_zoom():
    d = tempfile.mkdtemp(); v = os.path.join(d, 'v.mp4'); _video(v)
    items = [dict(name='line', box=[300, 860, 760, 1000], span=[0, 4], steady=[[0.1, 1.9]], colours=['#fbfbfb'], tol=110)]
    with open(os.path.join(d, 'items.json'), 'w', encoding='utf-8') as f:
        json.dump(items, f)
    out = os.path.join(d, 'lift')
    subprocess.run([sys.executable, '-I', LIFT, 'extract', v, os.path.join(d, 'items.json'), out], check=True, capture_output=True)
    spr = cv2.imread(os.path.join(out, 'items', 'line.png'), cv2.IMREAD_UNCHANGED)
    core = spr[..., 3] > 230
    assert core.sum() > 3000, core.sum()                                       # bar, outline and dot all lifted
    fill = spr[..., :3][core & (spr[..., :3].min(2) > 200)]
    assert len(fill) > 2000 and np.abs(fill.astype(int) - 251).mean() < 12      # the fill colour is the source's
    # the outline came along, dark; the video codec bleeds the footage into it, and the lift keeps that mix
    dark = spr[..., :3][(spr[..., 3] > 150) & (spr[..., :3].max(2) < 90)]
    assert len(dark) > 300, len(dark)
    with open(os.path.join(out, 'tracks.json'), encoding='utf-8') as f:
        tr = json.load(f)['items'][0]['track']
    sc = [np.sqrt(abs(np.linalg.det(np.array(r['warp'])[:, :2]))) for r in tr if r['found']]
    assert abs(sc[0] - 1) < 0.02 and sc[-1] > 1.06, (sc[0], sc[-1])           # still, then the zoom is followed
    r = subprocess.run([sys.executable, '-I', LIFT, 'verify', v, out], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@unittest.skipIf(cv2 is None, "numpy/opencv not installed (pip install numpy opencv-python-headless)")
class MimicLiftV56(unittest.TestCase):
    def test_lift_recovers_text_and_zoom(self):
        _check_lift_recovers_text_and_zoom()


if __name__ == "__main__":
    unittest.main()
