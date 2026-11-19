import importlib.util, pathlib, subprocess, sys
import pytest
ROOT = pathlib.Path(__file__).resolve().parents[1].parent

def _load(rel):
    spec = importlib.util.spec_from_file_location("m", ROOT / rel); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_reftiming_runs_and_split():
    np = pytest.importorskip("numpy")
    rt = _load("tools/onscreen/ref_timing.py")
    f = np.zeros((100, 10, 40)); f[10:40, 2:8, 5:20] = 255; f[40:70, 2:8, 22:38] = 255  # two lines back to back
    runs = rt.runs_from_frames(f, 25.0)
    assert runs == [(0.4, 1.6), (1.6, 2.8)]

def test_prender_splits_ranges(tmp_path):
    sh = ROOT / "tools/hf_sandbox/prender.sh"
    r = subprocess.run(["bash", str(sh), "4", "10", "--", "bash", "-c", 'echo $RANGE > r_${RANGE%,*}.txt'], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    got = sorted(p.read_text().strip() for p in tmp_path.glob("r_*.txt"))
    assert got == ["0,3", "3,6", "6,9", "9,10"]

def test_paste_writes_prender_and_qc_has_bitrate_gate():
    out = subprocess.run([sys.executable, str(ROOT / "scripts/dragon.py"), "tool", "hf", "paste", "demo"], capture_output=True, text=True).stdout
    assert "cat > prender.sh <<'XEOF'" in out and "MBPS" in out

def test_re_tool_no_longer_shadows_stdlib():
    r = subprocess.run([sys.executable, str(ROOT / "tools/re/re.py"), "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "partially initialized module 're'" not in r.stderr
