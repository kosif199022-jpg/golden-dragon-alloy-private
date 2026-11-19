"""v1.2 songs engine: align() + spans() find which pieces of a song a montage uses and where the editor cut (a reel
whose audio is song 20-35 s + 48-56 s must give two pieces, offsets 20 and 33), and lyrics_sheet() stacks the caption
band of a video in a labelled grid (whisper garbles sung Arabic, so lyrics are read from the picture).
Every file is made here with ffmpeg lavfi in tmp_path, under Arabic names on purpose: no network, no owner files."""
import json, sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engines import songs  # noqa: E402
from engines.media import exe, ffmpeg  # noqa: E402

try:
    exe("ffmpeg"), exe("ffprobe")
except FileNotFoundError:
    pytest.skip("ffmpeg/ffprobe not installed", allow_module_level=True)
Image = pytest.importorskip("PIL.Image")

# 60 s "song": noise gated by three unrelated sines under a slow swell, so no two stretches of a few seconds look alike
SONG = (r"aevalsrc='(0.12+0.88*gt(sin(2*PI*1.7*t)+sin(2*PI*2.9*t+1)+sin(2*PI*0.53*t+2)\,0.4))"
        r"*(0.35+0.65*abs(sin(2*PI*0.071*t)))*(2*random(0)-1)':s=8000:d=60")
QUOTE = "sine=f=330:r=8000:d=6,tremolo=f=5.3:d=0.8"   # stands in for a spoken quote: nothing like the song
P, L = songs.SHEET_PAD, songs.SHEET_LABEL


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    d = tmp_path_factory.mktemp("songs") / "أغاني"
    d.mkdir()
    lib = {"dir": d, "song": d / "أغنية.wav", "quote": d / "اقتباس.wav"}
    ffmpeg("-f", "lavfi", "-i", SONG, "-c:a", "pcm_s16le", lib["song"])
    ffmpeg("-f", "lavfi", "-i", QUOTE, "-c:a", "pcm_s16le", lib["quote"])
    return lib


def montage(lib, name, pieces):
    """A reel: pieces [(source, start, end)] joined in order, AAC in MP4 under a tiny H.264 picture.
    One input per piece, so older ffmpeg builds that refuse a reused input label work too."""
    args, graph = [], []
    for n, (src, a, b) in enumerate(pieces):
        args += ["-i", lib[src]]
        graph.append(f"[{n}:a]atrim={a}:{b},asetpts=PTS-STARTPTS[p{n}]")
    k, total = len(pieces), sum(b - a for _, a, b in pieces)
    graph.append("".join(f"[p{n}]" for n in range(k)) + f"concat=n={k}:v=0:a=1[a]")
    out = lib["dir"] / name
    ffmpeg(*args, "-f", "lavfi", "-i", f"color=c=gray:s=64x64:r=10:d={total}", "-filter_complex", ";".join(graph),
           "-map", f"{k}:v", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "96k", "-shortest", out)
    return out


@pytest.fixture(scope="module")
def two(lib):
    """The reel from the task: song 20-35 s then song 48-56 s (23 s)."""
    return montage(lib, "مونتاج.mp4", [("song", 20, 35), ("song", 48, 56)])


# ---------------------------------------------------------------- align / spans

def test_two_pieces_and_the_cut(lib, two):
    w = songs.align(two, lib["song"])
    assert w.ref_s == pytest.approx(23, abs=0.05) and w.song_s == pytest.approx(60, abs=0.05)
    assert all(set(x) == {"ref_t", "song_t", "offset", "score", "win"} for x in w)
    json.dumps(list(w))                                   # plain floats, JSON-ready
    sp = songs.spans(w)
    assert len(sp) == 2, sp
    a, b = sp
    assert a["offset"] == pytest.approx(20, abs=0.1) and b["offset"] == pytest.approx(33, abs=0.1)
    assert a["ref_start"] == pytest.approx(0, abs=0.05) and a["ref_end"] == pytest.approx(15, abs=0.05)
    assert b["ref_start"] == a["ref_end"] and b["ref_end"] == pytest.approx(23, abs=0.1)   # the editor's cut
    assert a["song_start"] == pytest.approx(20, abs=0.1) and a["song_end"] == pytest.approx(35, abs=0.1)
    assert b["song_start"] == pytest.approx(48, abs=0.1) and b["song_end"] == pytest.approx(56, abs=0.1)
    assert a["score"] > 0.9 and b["score"] > 0.9 and a["windows"] >= 3 and b["windows"] >= 1
    assert songs.gaps(sp, w.ref_s) == []


def test_window_across_the_cut_is_not_a_piece(lib, two):
    """Every window size from 4 to 8 s gives the same two pieces, although windows that straddle the cut find a
    third, wrong offset somewhere in the song."""
    for win, hop in ((4, 2), (5, 1), (8, 4)):
        sp = songs.spans(songs.align(two, lib["song"], win=win, hop=hop))
        assert [round(x["offset"]) for x in sp] == [20, 33], (win, hop, sp)
        assert sp[0]["ref_end"] == pytest.approx(15, abs=0.05)


def test_inserted_quote_is_a_gap_and_the_song_waits(lib):
    """song 20-35, a 4 s quote, then song 35-45: the offset drops by 4 (the song waited), the quote is a gap."""
    ref = montage(lib, "اقتباس_في_الوسط.mp4", [("song", 20, 35), ("quote", 0, 4), ("song", 35, 45)])
    w = songs.align(ref, lib["song"])
    sp = songs.spans(w)
    assert len(sp) == 2, sp
    a, b = sp
    assert a["offset"] == pytest.approx(20, abs=0.1) and b["offset"] == pytest.approx(16, abs=0.1)
    assert a["ref_end"] == pytest.approx(15, abs=0.1) and b["ref_start"] == pytest.approx(19, abs=0.1)
    assert b["song_start"] == pytest.approx(a["song_end"], abs=0.15)          # resumed where it stopped
    (g,) = songs.gaps(sp, w.ref_s)
    assert g["ref_start"] == pytest.approx(15, abs=0.1) and g["ref_end"] == pytest.approx(19, abs=0.1)
    m = songs.match(ref, lib["song"])
    assert m["spans"] == sp and m["gaps"] == [g] and len(m["windows"]) == len(w)


def test_unrelated_or_silent_audio_has_no_piece(lib, tmp_path):
    assert songs.spans(songs.align(lib["quote"], lib["song"])) == []
    silent = tmp_path / "صمت.wav"
    ffmpeg("-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono", "-t", "8", "-c:a", "pcm_s16le", silent)
    w = songs.align(silent, lib["song"])
    assert w and all(x["offset"] is None and x["score"] == 0 for x in w)
    assert songs.spans(w) == [] and songs.gaps([], w.ref_s) == [{"ref_start": 0.0, "ref_end": w.ref_s}]


def test_ref_shorter_than_the_window_is_one_window(lib, tmp_path):
    ref = tmp_path / "قصير.wav"
    ffmpeg("-i", lib["song"], "-ss", "30", "-t", "4", "-c:a", "pcm_s16le", ref)
    w = songs.align(ref, lib["song"])
    assert len(w) == 1 and w[0]["win"] == pytest.approx(4, abs=0.01) and w[0]["offset"] == pytest.approx(30, abs=0.05)
    (x,) = songs.spans(w)
    assert x["offset"] == pytest.approx(30, abs=0.05) and x["ref_start"] == 0 and x["ref_end"] == pytest.approx(4, abs=0.05)


def test_plain_window_list_from_json(lib, two):
    """Windows reloaded from JSON (no envelopes) still merge into the two pieces, at window precision."""
    w = json.loads(json.dumps(list(songs.align(two, lib["song"]))))
    sp = songs.spans(w)
    assert [round(x["offset"]) for x in sp] == [20, 33]
    assert sp[0]["ref_start"] == 0 and sp[0]["ref_end"] <= sp[1]["ref_start"] + 1e-9


def test_file_without_audio_raises(tmp_path):
    v = tmp_path / "بلا_صوت.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc=s=64x64:d=2:r=10", "-c:v", "libx264", "-preset", "ultrafast", v)
    with pytest.raises(ValueError, match="no audio"):
        songs.align(v, v)


def test_engine_and_dragon_cli_align(lib, two, tmp_path, capsys):
    out = tmp_path / "خريطة.json"
    songs.main(["align", str(two), str(lib["song"]), "--out", str(out)])
    text = capsys.readouterr().out
    assert "piece 1" in text and "piece 2" in text and "offset +20.000" in text
    m = json.loads(out.read_text(encoding="utf-8"))
    assert [round(x["offset"]) for x in m["spans"]] == [20, 33] and m["gaps"] == []
    from dragon import cli
    out2 = tmp_path / "dragon_map.json"
    cli.main(["align", str(two), str(lib["song"]), "--out", str(out2)])   # wording is cli.py's; check the saved map
    m2 = json.loads(out2.read_text(encoding="utf-8"))
    assert [round(x["offset"]) for x in m2["spans"]] == [20, 33] and len(m2["windows"]) == len(m["windows"])


# ---------------------------------------------------------------- lyrics sheet

def clip(path, size="320x240", d=8, src="testsrc", vf=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    args = ["-f", "lavfi", "-i", f"{src}{':' if '=' in src else '='}s={size}:d={d}:r=5"]
    if vf:
        args += ["-vf", vf]
    ffmpeg(*args, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", path)
    return path


def grid(cols, rows, tw, th):
    return cols * tw + (cols + 1) * P, rows * (L + th) + (rows + 1) * P


def cell_mean(im, col, row, tw, th):
    """Mean RGB of the picture area of one grid cell (under its label strip)."""
    x, y = P + col * (tw + P), P + row * (L + th + P) + L
    return tuple(np.asarray(im.crop((x + 2, y + 2, x + tw - 2, y + th - 2)), dtype=float).reshape(-1, 3).mean(axis=0))


def test_lyrics_sheet_grid_has_one_tile_per_time(tmp_path):
    v = clip(tmp_path / "فيديو" / "كلمات.mp4")
    out = tmp_path / "ورقة.jpg"
    r = songs.lyrics_sheet(v, out, band=(100, 196), times=[0.5, 2, 3.5, 5, 6.5], cols=2, width=200)
    assert Path(r) == out and out.exists()
    im = Image.open(out)
    assert im.format == "JPEG" and im.size == grid(2, 3, 200, 60)      # 96 px band scaled to 200 wide: 200x60 tiles
    im = im.convert("RGB")
    for i in range(5):                                                   # five pictures ...
        assert max(abs(c - 24) for c in cell_mean(im, i % 2, i // 2, 200, 60)) > 20
    assert max(abs(c - 24) for c in cell_mean(im, 1, 2, 200, 60)) < 6    # ... and an empty sixth cell
    label = np.asarray(im.crop((P, P, P + 60, P + L - 2))).reshape(-1, 3).astype(int)   # time label, top-left, yellow
    assert ((label[:, 0] > 200) & (label[:, 1] > 150) & (label[:, 2] < 120)).any()


def test_lyrics_sheet_default_band_is_the_bottom_caption_strip(tmp_path):
    """Default band = 0.84-0.94 of the height: on a 270x480 reel that is rows 403-451, painted red here."""
    v = clip(tmp_path / "ريل.mp4", size="270x480", d=2, src="color=c=blue",
             vf="drawbox=x=0:y=403:w=iw:h=48:color=red:t=fill")
    out = tmp_path / "band.jpg"
    songs.lyrics_sheet(v, out, times="1")
    im = Image.open(out).convert("RGB")
    assert im.size == grid(1, 1, 460, 82)                                # 270x48 scaled to 460 wide
    r, g, b = cell_mean(im, 0, 0, 460, 82)
    assert r > 180 and g < 70 and b < 70


def test_lyrics_sheet_keeps_a_wide_band_readable(tmp_path):
    """A 960-wide band 80 px tall would be 38 px at 460 wide: it is kept at min_h=48 (576 wide) unless min_h=0."""
    v = clip(tmp_path / "واسع.mp4", size="960x540", d=2)
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    songs.lyrics_sheet(v, a, band="450:530", times=[1])
    songs.lyrics_sheet(v, b, band=(450, 530), times=[1], min_h=0)
    assert Image.open(a).size == grid(1, 1, 576, 48) and Image.open(b).size == grid(1, 1, 460, 38)


def test_lyrics_sheet_times_from_every_and_transcript(tmp_path):
    v = clip(tmp_path / "مقطع.mp4")                                       # 8 s
    assert songs._times("17,21.5", None, None, 60) == [17.0, 21.5]
    assert songs._times([30, 2], 4, None, 10) == [2.0, 6.0]             # every 4 s: slot middles 2, 6; 30 s is past the end
    out = songs.lyrics_sheet(v, tmp_path / "every.jpg", every=3, cols=3, width=200, band=(100, 196))
    assert Image.open(out).size == grid(3, 1, 200, 60)                   # 1.5, 4.5, 7.5
    lines = [{"start": 1.0, "end": 2.0, "text": "سطر أول", "words": []}, {"start": 3.0, "end": 5.0, "text": "سطر ثان"},
             {"start": 9.0, "end": 10.0, "text": "بعد النهاية"}]
    words = tmp_path / "كلمات.json"
    words.write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
    assert songs._times(None, None, words, 8) == [1.5, 4.0]
    assert songs._times([1.5], None, {"lines": lines}, 8) == [1.5, 4.0]
    out = songs.lyrics_sheet(v, tmp_path / "words.jpg", transcript=words, times=[1.5], width=200, band=(100, 196))
    assert Image.open(out).size == grid(2, 1, 200, 60)


def test_lyrics_sheet_errors(lib, tmp_path):
    v = clip(tmp_path / "v.mp4", d=2)
    with pytest.raises(ValueError, match="no times"):
        songs.lyrics_sheet(v, tmp_path / "x.jpg")
    with pytest.raises(ValueError, match="no times"):
        songs.lyrics_sheet(v, tmp_path / "x.jpg", times=[5, 9])           # all past the end
    with pytest.raises(ValueError, match="no video"):
        songs.lyrics_sheet(lib["song"], tmp_path / "x.jpg", times=[1])
    with pytest.raises(ValueError, match="empty band"):
        songs.lyrics_sheet(v, tmp_path / "x.jpg", times=[1], band=(200, 100))


def test_dragon_cli_lyrics_sheet(tmp_path, capsys):
    from dragon import cli
    v = clip(tmp_path / "فيديو.mp4", d=3)
    out = tmp_path / "ورقة.jpg"
    cli.main(["lyrics-sheet", str(v), str(out), "--band", "100:196", "--times", "0.5,2"])
    assert "lyrics sheet ->" in capsys.readouterr().out
    assert Image.open(out).size == grid(2, 1, 460, 138)                  # 320x96 band scaled to 460 wide
