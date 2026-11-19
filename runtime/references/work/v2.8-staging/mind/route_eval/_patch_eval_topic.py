from pathlib import Path
p = Path(__file__).resolve().parent / "route_eval2.py"
c = p.read_text(encoding="utf-8")
assert "use_topic" not in c


def rep(old, new):
    global c
    assert c.count(old) == 1, old[:60]
    c = c.replace(old, new)


rep('use_ctx, calib, novel, as_json = "--ctx" in args, "--calib" in args, "--novel" in args, "--json" in args',
    'use_ctx, calib, novel, as_json, use_topic = "--ctx" in args or "--topic" in args, "--calib" in args, "--novel" in args, "--json" in args, "--topic" in args')
rep('--json   one JSON line per set (used by rd.py selftest as the anti-regression gate)',
    '--json   one JSON line per set (used by rd.py selftest as the anti-regression gate)\n'
    '--topic  fresh set: the router gets the decayed topic of every earlier message of the same session (what brief() keeps\n'
    '         in MEM/last_turn.json), each history message scored with itself hidden from the memory; old set: same as --ctx')
rep('''def predict(q, prev):
    u = rd.understand(q)
    if use_ctx and takes_prev and prev:
        pb, _ = rd.route(u["text"], prev=rd.understand(prev)["text"])''',
    '''TOPIC = {}
if use_topic and hasattr(rd, "topic_update"):
    _pbs, _sess, _t = rd.playbooks(), None, {}
    for _r in json.loads((HERE / "fresh_cc.json").read_text(encoding="utf-8")):
        if _r["src"] != _sess:
            _sess, _t = _r["src"], {}
        TOPIC[_r["fid"]] = dict(_t)
        if has_mem:
            rd.EX_EXCLUDE.clear()
            rd.EX_EXCLUDE.update(TEST_KEYS)
            rd.EX_EXCLUDE.add(rd.ex_key(_r["q"]))
        _t = rd.topic_update(_t, rd._pb_scores(rd.understand(_r["q"])["text"], _pbs)[0])


def predict(q, prev, topic=None):
    u = rd.understand(q)
    if topic:
        pb, _ = rd.route(u["text"], prev=topic)
    elif use_ctx and takes_prev and prev:
        pb, _ = rd.route(u["text"], prev=rd.understand(prev)["text"])''')
rep('        top, r3, conf = predict(r["q"], r["prev"])',
    '        top, r3, conf = predict(r["q"], r["prev"], TOPIC.get(r["id"]) if name == "fresh" else None)')
rep('"ctx": bool(use_ctx and takes_prev), "n": n,',
    '"ctx": ("topic" if use_topic and name == "fresh" and TOPIC else bool(use_ctx and takes_prev)), "n": n,')
rep("ctx={'on ' if res['ctx'] else 'off'}",
    "ctx={res['ctx'] if res['ctx'] == 'topic' else ('on' if res['ctx'] else 'off'):<5}")
p.write_text(c, encoding="utf-8")
print("patched")
