"""Mimic trace over moving footage: --tmin keeps the small dots, --colour keeps one colour of a multi-colour header."""
import json, os, subprocess, sys, tempfile, unittest
try:                       # optional media stack: CI installs it (red-rose-v11.yml); a bare machine skips, never errors
    import numpy as np, cv2
except ImportError:        # pragma: no cover - depends on the machine
    np = cv2 = None

HERE = os.path.dirname(os.path.abspath(__file__))
MIMIC = os.path.join(HERE, 'agent', 'mimic', 'mimic.py')


def _video(path):
    """6 s at 10 fps, moving bright noise; still white bar + small white dot (a letter and its dot) and a yellow block."""
    rng = np.random.default_rng(3); w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), 10, (1080, 1920))
    base = rng.integers(60, 235, (1920 + 400, 1080, 3), dtype=np.uint8); base = cv2.GaussianBlur(base, (31, 31), 0)
    for i in range(60):
        f = base[i * 6:i * 6 + 1920].copy()
        cv2.rectangle(f, (300, 900), (700, 930), (252, 252, 252), -1)      # letter body
        cv2.rectangle(f, (480, 860), (492, 872), (252, 252, 252), -1)      # its dot, 12 px
        cv2.rectangle(f, (300, 300), (500, 360), (0, 232, 254), -1)        # yellow header block (BGR)
        cv2.rectangle(f, (550, 300), (700, 360), (95, 201, 25), -1)        # green block next to it
        w.write(f)
    w.release()


def _trace(video, out, *args):
    subprocess.run([sys.executable, '-I', MIMIC, 'trace', video, '--out', out, *args], check=True, capture_output=True)
    with open(out + '.json', encoding='utf-8') as f:
        return json.load(f)


def _shapes(el):
    import re
    out = []
    for s in re.findall(r'M[^MZ]*Z', el['path']):
        p = np.array([[float(a), float(b)] for a, b in re.findall(r'([\d.]+) ([\d.]+)', s)])
        out.append((p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()))
    return out


def _check_tmin_keeps_dot_and_drops_moving_background():
    d = tempfile.mkdtemp(); v = os.path.join(d, 'v.mp4'); _video(v)
    el = _trace(v, os.path.join(d, 'line'), '--box', '250,820,760,960', '--colour', '#fbfbfb', '--tol', '90', '--tmin', '0.5,5.5')
    sh = _shapes(el)
    assert any(470 <= x0 <= 486 and 852 <= y0 <= 866 and x1 <= 500 for x0, y0, x1, y1 in sh), sh      # the dot survives
    assert any(x0 <= 305 and x1 >= 695 for x0, y0, x1, y1 in sh), sh                                  # the body survives
    assert len(sh) <= 4, sh                                                                           # no noise blobs


def _check_colour_trace_keeps_only_that_colour():
    d = tempfile.mkdtemp(); v = os.path.join(d, 'v.mp4'); _video(v)
    el = _trace(v, os.path.join(d, 'hy'), '--box', '280,280,720,380', '--colour', '#fee800', '--tol', '120', '--tmin', '0.5,5.5')
    x0, y0, x1, y1 = el['box']
    assert 295 <= x0 <= 305 and x1 <= 510, el['box']        # the green block next to it is not part of the yellow trace
    f = el['fill'].lstrip('#'); r, g, b = (int(f[i:i + 2], 16) for i in (0, 2, 4))
    assert r > 220 and g > 200 and b < 80, el['fill']


@unittest.skipIf(cv2 is None, "numpy/opencv not installed (pip install numpy opencv-python-headless)")
class MimicTraceV55(unittest.TestCase):
    """Run under `unittest discover` (the CI runner); the checks were pytest-only functions before."""

    def test_tmin_keeps_dot_and_drops_moving_background(self):
        _check_tmin_keeps_dot_and_drops_moving_background()

    def test_colour_trace_keeps_only_that_colour(self):
        _check_colour_trace_keeps_only_that_colour()


if __name__ == "__main__":
    unittest.main()
