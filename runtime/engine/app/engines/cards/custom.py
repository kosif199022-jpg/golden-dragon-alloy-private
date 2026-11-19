"""Hand ports of cards too bespoke for formula data.

CUSTOM[id](wd) -> (checks, outputs), used only when the extractor cannot express the card as data.
NEEDS lists the pack helpers these ports call, so tools/extract_cards.py keeps them in engines/cards/lib.
"""
from __future__ import annotations

from pathlib import Path

NEEDS = [("fam_music_beat_sound", n) for n in ("clicks", "save", "cut_video", "cut_frames", "frame_err", "onsets",
                                               "load_any", "jdump", "SR")]


def _m():
    from .lib import fam_music_beat_sound as m
    return m


def beat_grid(wd, bpm, n_beats, secs, expect_step, doc=None, lead=0, tol=1, fps=30):
    """music-beat-sound _grid_card: cuts every n beats at bpm, rendered over a click track and found again in the picture
    (frame differences) and in the sound (onsets); negative control: the uncut clip has no cuts."""
    m, wd = _m(), Path(wd)
    step = n_beats * 60.0 / bpm
    cuts, k = [], 1
    while k * step < secs - 0.15:
        cuts.append(round(k * step, 6))
        k += 1
    x, _ = m.clicks(bpm, secs)
    audio = m.save(wd, "music.wav", x)
    planned = [int(round(t * fps)) - lead for t in cuts]
    v = m.cut_video(wd / "cuts.mp4", [f / fps for f in planned], secs, fps, audio=audio)
    found, _ = m.cut_frames(v)
    f0, _ = m.cut_frames(m.cut_video(wd / "uncut.mp4", [], secs, fps))
    on_f = [o * fps for o in m.onsets(m.load_any(v)[0], m.SR, 0.3, 0.1)]
    worst = max(min(abs(f + lead - o) for o in on_f) for f in found) if found and on_f else 99
    check = m.check
    checks = [check("cut interval = %s beats at %s BPM = %.4f s" % (n_beats, bpm, expect_step), abs(step - expect_step) < 5e-4, step, expect_step),
              check("rendered cuts at the planned frames", m.frame_err(found, planned) == 0 and len(found) == len(planned), found, planned),
              check("each cut within %d frame(s) of a beat heard in the file" % tol, worst <= tol, worst, "<= %d" % tol),
              check("negative control: the uncut clip has no cuts", m.frame_err(f0, planned) > tol, len(f0), "> 0 needed")]
    edl = m.jdump(wd / "cuts.edl.json", {"fps": fps, "cuts_s": [round(f / fps, 4) for f in planned], "bpm": bpm})
    return checks, [v, edl]


# _grid_card cards (fallback when the extractor cannot express them as data): id -> (bpm, n_beats, secs, step, tol)
_GRID = {"BEAT-181": (150, 2, 4.0, 0.8, 1), "BEAT-185": (120, 4, 6.0, 2.0, 1), "BEAT-191": (150, 1, 3.0, 0.4, 1),
         "BEAT-204": (120, 3, 5.0, 1.5, 1), "BEAT-210": (128, 4, 6.0, 1.875, 1), "BEAT-202": (128, 4, 6.0, 1.875, 1),
         "BEAT-32": (120, 4, 6.5, 2.0, 1), "BEAT-266": (120, 1, 3.0, 0.5, 1), "BEAT-250": (100, 1, 3.0, 0.6, 1),
         "BEAT-286": (110, 2, 4.0, 60 / 110 * 2, 1), "BEAT-292": (128, 1, 3.0, 0.46875, 2), "BEAT-288": (105, 1, 3.0, 60 / 105, 2)}
CUSTOM: dict = {cid: (lambda wd, p=p: beat_grid(wd, *p[:4], tol=p[4])) for cid, p in _GRID.items()}
