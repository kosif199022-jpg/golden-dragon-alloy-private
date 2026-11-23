"""V43: original, deterministic Abu Cap reel motion reconstruction (read-only).

Distilled from the owner's 22-second lions/ladder storyboard and seek-driven SVG.
No original video frames, track, font, JS runtime, archived binaries or legacy
modules are embedded. This is a simplified ORIGINAL vector reconstruction,
not pixel-identical reproduction of the referenced reel.
"""
from __future__ import annotations

import math
from html import escape

OPS = ("story", "pose", "svg")
DURATION = 22.0
FPS = 30
WIDTH, HEIGHT = 1080, 1920

_BEATS = (
    (0.0, 2.8, "الخطر", "الأسود تقترب"),
    (2.8, 5.6, "الهروب", "الصعود إلى الشجرة"),
    (5.6, 8.4, "الاطمئنان", "الأعلى يبدو آمنًا"),
    (8.4, 11.2, "المفاجأة", "الأسد يعود بسلم"),
    (11.2, 14.6, "الفكرة", "انتظار القيلولة"),
    (14.6, 17.4, "الفرصة", "الأسود تنام"),
    (17.4, 19.6, "الانسحاب", "الهروب الهادئ"),
    (19.6, 22.0, "الخاتمة", "الذكاء لا يعني الصعود أعلى"),
)


def _n(x, label):
    if type(x) not in (int, float) or not math.isfinite(x):
        raise ValueError(label + " must be finite numeric")
    return float(x)


def _unit(t):
    return max(0.0, min(1.0, t))


def _smooth(t):
    u = _unit(t)
    return u*u*(3-2*u)


def _lerp(a,b,t):
    return a+(b-a)*_smooth(t)


def _segment(t,a,b):
    return _unit((t-a)/(b-a))


def _time(params):
    if type(params) is not dict or set(params)-{"seconds","fps","caption"}:
        raise ValueError("expected only seconds, fps, caption")
    seconds = _n(params.get("seconds",0), "seconds")
    if seconds < 0 or seconds > DURATION:
        raise ValueError("seconds outside reel")
    fps = params.get("fps",FPS)
    if type(fps) is not int or fps != FPS:
        raise ValueError("original storyboard is 30 fps")
    return seconds


def _pose(seconds):
    t = seconds
    if t < 2.6:
        lion_x = _lerp(-260, 380, _segment(t,0,2.6))
        lion_mode = "walk"
    elif t < 7:
        lion_x, lion_mode = 380, "sit"
    elif t < 8.4:
        lion_x, lion_mode = _lerp(380, 1300, _segment(t,7,8.4)), "walk"
    elif t < 10.4:
        lion_x, lion_mode = _lerp(1300,870,_segment(t,8.6,10.4)), "walk"
    elif t < 12.6:
        lion_x, lion_mode = _lerp(870,470,_segment(t,11.2,12.6)), "walk"
    else:
        lion_x = 470
        lion_mode = "sleep" if t >= 14.6 else "sit"

    if t < 2.8:
        cap_x, cap_y = 560, 1505
        friend_x, friend_y = 860, 1505
    elif t < 5.6:
        cap_x = _lerp(560,630,_segment(t,2.8,3.4))
        cap_y = _lerp(1505,760,_segment(t,3.4,5.6))
        friend_x = _lerp(860,770,_segment(t,2.8,3.6))
        friend_y = _lerp(1505,992,_segment(t,3.6,5.4))
    elif t < 16:
        cap_x, cap_y = 630,760
        friend_x, friend_y = 820,992
    elif t < 17.4:
        cap_x, cap_y = 630,_lerp(760,1505,_segment(t,16,17.4))
        friend_x, friend_y = 770,_lerp(992,1505,_segment(t,16,17.2))
    else:
        cap_x, cap_y = _lerp(630,1320,_segment(t,17.4,19.6)), 1505
        friend_x, friend_y = _lerp(770,1400,_segment(t,17.2,19.4)),1505

    if t < 8.4:
        ladder = "hidden"
    elif t < 10.4:
        ladder = "carried_by_lion"
    elif t < 16.2:
        ladder = "leaning_on_tree"
    elif t < 17.4:
        ladder = "hidden"
    else:
        ladder = "carried_by_cap"

    beat_index = next((i for i,b in enumerate(_BEATS) if b[0] <= t < b[1]),len(_BEATS)-1)
    return {
        "seconds":round(t,4), "frame":min(round(t*FPS),int(DURATION*FPS)),
        "beat_index":beat_index+1,"beat":_BEATS[beat_index][2],
        "cap":{"x":round(cap_x,2),"y":round(cap_y,2),
               "expression":"shh" if t>=16 else ("surprised" if 1.2<t<5.6 or 10.4<t<16 else "smile")},
        "friend":{"x":round(friend_x,2),"y":round(friend_y,2),
                  "expression":"idea" if 11.4<t<14.8 else "shh" if t>=16 else "alert"},
        "lion_primary":{"x":round(lion_x,2),"y":1505,"pose":lion_mode},
        "lion_secondary":{"x":160,"y":1505,"pose":"sleep" if t>=14.9 else "sit"},
        "ladder":ladder, "end_card_visible":t>=19.4,
        "description":"Editable conceptual pose data from original reference timing; not source pixel reconstruction."
    }


def story(params):
    if type(params) is not dict or params:
        raise ValueError("story takes no parameters")
    return {"name":"Abu Cap — lions and ladder", "duration_seconds":DURATION,
            "fps":FPS,"total_frames":int(FPS*DURATION),
            "canvas":{"width":WIDTH,"height":HEIGHT},
            "beats":[{"start":start,"end_exclusive":end,"label":label,"action":action,
                      "start_frame":round(start*FPS),"end_frame_exclusive":round(end*FPS)}
                     for start,end,label,action in _BEATS],
            "characters":["ابو كاب","ابو نضارة","lion 1","lion 2"],
            "runtime_external_dependencies":False,
            "original_media_embedded":False,
            "audio_embedded":False,
            "note":"The original archive includes a CC BY 3.0 music credit; no soundtrack is included or relicensed."}


def pose(params):
    return {"status":"evaluated_not_rendered", **_pose(_time(params))}


def _stick(p, *, cap):
    x,y=p["x"],p["y"]
    colour="#e53942" if cap else "#397bc7"
    head=("<path d='M -46 -50 Q -48 -92 20 -88 L 62 -70 L 62 -57 L -15 -57 Z' fill='#e53942'/>"
          if cap else
          "<circle cx='-20' cy='-30' r='22' fill='none' stroke='#202020' stroke-width='7'/>"
          "<circle cx='20' cy='-30' r='22' fill='none' stroke='#202020' stroke-width='7'/>"
          "<path d='M0 -30 h8' stroke='#202020' stroke-width='5'/>")
    mouth="<ellipse cx='0' cy='-4' rx='9' ry='12' fill='#191919'/>" if p["expression"]=="surprised" else "<path d='M-12 -7 Q0 6 12 -7' stroke='#191919' stroke-width='4' fill='none'/>"
    return (f'<g transform="translate({x:.2f},{y:.2f})">'
            f'<path d="M0 -190 v105" stroke="{colour}" stroke-width="38" stroke-linecap="round"/>'
            '<path d="M-25 -82 l-42 82 M25 -82 l42 82 M-10 -150 l-60 38 M10 -150 l60 38" fill="none" stroke="#242021" stroke-width="13" stroke-linecap="round"/>'
            '<circle cx="0" cy="-244" r="50" fill="white" stroke="#242021" stroke-width="7"/>'
            f'<g transform="translate(0,-240)">{head}<circle cx="-20" cy="-5" r="5" fill="#181818"/>'
            f'<circle cx="20" cy="-5" r="5" fill="#181818"/>{mouth}</g></g>')


def _lion(obj, second=False):
    x,y=obj["x"],obj["y"]
    sleep=obj["pose"]=="sleep"
    bob=0 if sleep else 5
    body_y=34 if sleep else 0
    return (f'<g transform="translate({x:.2f},{y+body_y+bob:.2f}) scale(.85)">'
            '<ellipse cx="0" cy="-90" rx="118" ry="65" fill="#e9b458" stroke="#76451f" stroke-width="6"/>'
            '<path d="M-90 -42 v42 M-30 -42 v42 M40 -42 v42 M95 -42 v42" stroke="#e9b458" stroke-width="27" stroke-linecap="round"/>'
            '<circle cx="112" cy="-180" r="89" fill="#a55c28" stroke="#75451d" stroke-width="7"/>'
            '<circle cx="112" cy="-180" r="61" fill="#ecc16c" stroke="#75451d" stroke-width="5"/>'
            + ('<path d="M 85 -182 Q99 -175 106 -182 M 125 -182 Q139 -175 146 -182" fill="none" stroke="#38291b" stroke-width="5"/>'
               if sleep else
               '<circle cx="94" cy="-190" r="7" fill="#38291b"/><circle cx="133" cy="-190" r="7" fill="#38291b"/>')
            + '<path d="M105 -158 Q115 -148 126 -158" fill="none" stroke="#38291b" stroke-width="5"/></g>')


def _ladder(p):
    mode=p["ladder"]
    if mode=="hidden":
        return ""
    if mode=="leaning_on_tree":
        x,y,rotate=560,1505,-14
    elif mode=="carried_by_lion":
        x,y,rotate=p["lion_primary"]["x"]+170,1350,90
    else:
        x,y,rotate=p["cap"]["x"]+160,1320,90
    parts=[f'<g transform="translate({x:.2f},{y:.2f}) rotate({rotate})">',
           '<path d="M0 0 V-550 M80 0 V-550" stroke="#9c643a" stroke-width="15" stroke-linecap="round"/>']
    for n in range(1,9):
        ystep=-n*60
        parts.append(f'<path d="M0 {ystep} H80" stroke="#cb9856" stroke-width="13"/>')
    parts.append("</g>")
    return "".join(parts)


def svg(params):
    t=_time(params)
    p=_pose(t)
    caption=params.get("caption","")
    if type(caption) is not str or len(caption)>100:
        raise ValueError("caption must be a string <=100 characters")
    caption_xml=escape(caption)
    # Restrict text to vector fallback fonts. Arabic shaping depends on the SVG rasterizer.
    background=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">'
                '<rect width="1080" height="1920" fill="#a9dcf5"/>'
                '<circle cx="900" cy="190" r="80" fill="#ffd66b"/>'
                '<path d="M0 1300 Q400 1000 850 1310 T1080 1250 V1920 H0Z" fill="#7acc59"/>'
                '<path d="M0 1510 H1080 V1650 H0Z" fill="#916139"/>'
                '<path d="M665 1510 V680 h70 v830" fill="#9b6937" stroke="#745024" stroke-width="7"/>'
                '<circle cx="705" cy="565" r="180" fill="#54ad46"/>'
                '<circle cx="590" cy="610" r="125" fill="#5dbc55"/>')
    output=[background,_lion(p["lion_secondary"],True),_lion(p["lion_primary"]),_ladder(p),
            _stick(p["friend"],cap=False),_stick(p["cap"],cap=True)]
    if caption:
        output.append(f'<text x="540" y="164" text-anchor="middle" font-size="45" fill="#172436">{caption_xml}</text>')
    if p["end_card_visible"]:
        output.append('<rect x="140" y="400" width="800" height="480" rx="70" fill="#ffffff" opacity=".92"/>'
                      '<text x="540" y="580" font-size="54" text-anchor="middle" fill="#202020">Smart beats tall</text>')
    output.append("</svg>")
    return {"status":"original_svg_frame_not_video","seconds":round(t,4),
            "svg":"".join(output),"width":WIDTH,"height":HEIGHT,
            "limitations":"Illustrative original SVG, not pixel-identical source frame. No audio, original font or user assets loaded."}


def run(op, params):
    if op not in OPS:
        raise ValueError("unknown reel operation")
    return {"story":story,"pose":pose,"svg":svg}[op](params)
