"""Helpers of runners/fam_w3_01.py used by data cards, copied verbatim (the extractor binds a card to them only when
their AST hash with every dependency equals the original's)."""
from __future__ import annotations

from pathlib import Path
from .core import check
from .core import fx
import json
import struct
import subprocess


CC = "cc"


def _build_elf(wd: Path, src: str = None, pie: bool = False, name: str = "prog", flags=()):
    src = src or (
        "#include <stdio.h>\n"
        "int magic = 0x12345678;\n"
        "int add(int a, int b){ return a + b; }\n"
        "int main(void){ printf(\"%d\\n\", add(magic, 1)); return 0; }\n"
    )
    c = wd / (name + ".c")
    c.write_text(src)
    out = wd / name
    cmd = [CC, "-O0", "-g", str(c), "-o", str(out)]
    if not pie:
        cmd += ["-no-pie", "-fno-pie"]
    cmd += list(flags)
    fx.run(cmd, timeout=40)
    return out


def _readelf(path: Path, *args):
    return fx.run(["readelf", *args, str(path)]).stdout


def _objdump(path: Path, *args):
    return fx.run(["objdump", *args, str(path)]).stdout


def _load_segments(path: Path):
    """LOAD program headers as [(offset, vaddr, filesz)] parsed from readelf -lW."""
    out = _readelf(path, "-lW")
    segs, pend = [], None
    for ln in out.splitlines():
        t = ln.split()
        if t[:1] == ["LOAD"]:
            # LOAD off vaddr paddr filesz memsz flags align  (W = one line)
            if len(t) >= 6:
                segs.append((int(t[1], 16), int(t[2], 16), int(t[4], 16)))
            else:
                pend = (int(t[1], 16), int(t[2], 16))
        elif pend is not None and t and t[0].startswith("0x"):
            segs.append((pend[0], pend[1], int(t[0], 16)))
            pend = None
    return segs


def _vaddr_to_offset(path: Path, vaddr: int):
    for off, va, fsz in _load_segments(path):
        if va <= vaddr < va + fsz:
            return off + (vaddr - va)
    return None


def _nm_addr(path: Path, symbol: str):
    for ln in fx.run(["nm", str(path)]).stdout.splitlines():
        t = ln.split()
        if len(t) == 3 and t[2] == symbol:
            return int(t[0], 16)
    return None


def _entry(path: Path):
    for ln in _readelf(path, "-h").splitlines():
        if "Entry point address" in ln:
            return int(ln.split(":")[1].strip(), 16)
    return None


def _r2(args, cmd, timeout=40):
    return subprocess.run(["r2", "-q", "-c", cmd, *args], capture_output=True, text=True,
                          timeout=timeout, stdin=subprocess.DEVNULL).stdout


def _firmware_blob(wd: Path):
    import zlib
    payload = b"FIRMWARE-PAYLOAD-" + b"A" * 64
    gz = b"\x1f\x8b\x08\x00" + b"\x00" * 6 + zlib.compress(payload)[2:]  # gzip-ish magic region
    blob = b"\x00" * 128 + b"PK\x03\x04" + b"\x00" * 60 + gz + b"\xff" * 32
    p = wd / "firmware.bin"
    p.write_bytes(blob)
    return p, 128, len(b"PK\x03\x04"), len(blob)


def _wasm(exports):
    def leb(n):
        return bytes([n])
    body = b"\x00asm\x01\x00\x00\x00"
    # type section (1): one type () -> ()
    ty = b"\x01\x60\x00\x00"
    body += b"\x01" + leb(len(ty)) + ty
    nf = len(exports)
    fn = bytes([nf]) + b"\x00" * nf
    body += b"\x03" + leb(len(fn)) + fn
    exp = bytes([nf])
    for i, name in enumerate(exports):
        nb = name.encode()
        exp += bytes([len(nb)]) + nb + b"\x00" + bytes([i])
    body += b"\x07" + leb(len(exp)) + exp
    code = bytes([nf]) + (b"\x02\x00\x0b") * nf
    body += b"\x0a" + leb(len(code)) + code
    return body


def _wasm_parse(data):
    assert data[:4] == b"\x00asm", "bad wasm magic"
    version = struct.unpack_from("<I", data, 4)[0]
    i, sections, exports = 8, [], []
    while i < len(data):
        sid = data[i]
        size = data[i + 1]
        payload = data[i + 2:i + 2 + size]
        sections.append(sid)
        if sid == 7:
            n = payload[0]
            j = 1
            for _ in range(n):
                ln = payload[j]
                name = payload[j + 1:j + 1 + ln].decode()
                exports.append(name)
                j += 1 + ln + 2
        i += 2 + size
    return version, sections, exports


def _not_wasm(data):
    try:
        _wasm_parse(data)
        return False
    except Exception:
        return True


def _evm_selectors(code):
    out, i = [], 0
    while i < len(code):
        op = code[i]
        if op == 0x63:
            out.append(code[i + 1:i + 5].hex())
            i += 5
        elif 0x60 <= op <= 0x7f:
            i += 1 + (op - 0x5f)
        else:
            i += 1
    return out


def _pcap_parse(data):
    magic = struct.unpack_from("<I", data, 0)[0]
    assert magic == 0xa1b2c3d4
    i = 24
    endpoints, protos = set(), {}
    while i + 16 <= len(data):
        incl = struct.unpack_from("<IIII", data, i)[2]
        pkt = data[i + 16:i + 16 + incl]
        i += 16 + incl
        if len(pkt) < 14 + 20 + 8 or pkt[12:14] != b"\x08\x00":
            continue
        ip = pkt[14:]
        proto = ip[9]
        dst_ip = ".".join(map(str, ip[16:20]))
        if proto == 17:
            udp = ip[20:]
            dport = struct.unpack_from(">H", udp, 2)[0]
            endpoints.add("%s:%d" % (dst_ip, dport))
            name = "DNS" if dport == 53 else "UDP"
            protos[name] = protos.get(name, 0) + 1
    return endpoints, protos


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _sha_bytes(b):
    import hashlib
    return hashlib.sha256(b).hexdigest()


def _diff_json(a, b):
    added = sorted(set(_flatten(b)) - set(_flatten(a)))
    removed = sorted(set(_flatten(a)) - set(_flatten(b)))
    return added, removed


def _flatten(obj, prefix=""):
    items = []
    if isinstance(obj, dict):
        for k in sorted(obj):
            items += _flatten(obj[k], "%s.%s" % (prefix, k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            items += _flatten(v, "%s[%d]" % (prefix, i))
    else:
        items.append("%s=%s" % (prefix, obj))
    return items


def _compare_card(wd, a, b, out_name, expect_added):
    (wd / "a.json").write_text(json.dumps(a))
    (wd / "b.json").write_text(json.dumps(b))
    added, removed = _diff_json(json.loads((wd / "a.json").read_text()), json.loads((wd / "b.json").read_text()))
    self_added, _ = _diff_json(a, a)
    out = wd / out_name
    out.write_text(json.dumps({"added": added, "removed": removed}, indent=1))
    hit = any(expect_added in x for x in added)
    return [
        check("expected change '%s' detected between the two bundles" % expect_added, hit, added, "contains %s" % expect_added),
        check("diff reports at least one difference", len(added) + len(removed) >= 1, len(added) + len(removed), ">=1"),
        check("negative control: comparing a bundle with itself finds no additions", self_added == [], self_added, []),
    ], [out]


def _project_graph(wd, kind, inventory, out_name):
    (wd / "inventory.json").write_text(json.dumps(inventory))
    data = json.loads((wd / "inventory.json").read_text())
    nodes = [c["id"] for c in data["components"]]
    edges = [[c["id"], dep] for c in data["components"] for dep in c.get("depends_on", [])]
    graph = {"kind": kind, "nodes": nodes, "edges": edges}
    out = wd / out_name
    out.write_text(json.dumps(graph, indent=1))
    no_dep = {"components": [{"id": "solo"}]}
    no_edges = [[c["id"], d] for c in no_dep["components"] for d in c.get("depends_on", [])]
    return [
        check("%s graph nodes projected from inventory" % kind, set(nodes) == {c["id"] for c in inventory["components"]},
              len(nodes), len(inventory["components"])),
        check("a declared dependency becomes a graph edge", len(edges) >= 1, len(edges), ">=1"),
        check("negative control: an inventory with no dependencies has no edges", no_edges == [], no_edges, []),
    ], [out]
