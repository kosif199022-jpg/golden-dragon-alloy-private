import zipfile, collections
from pathlib import Path
desk = Path.home() / "OneDrive" / "Desktop"
new = desk / "red-dragon-v2.8.0.zip"
cands = [p for p in desk.glob("red-dragon*.zip") if p != new and p.stat().st_size > 30e6]
cands += [p for p in (Path.home() / "rd-staging" / "backups").glob("*.zip") if p.stat().st_size > 30e6]
print("full old zips:", [(p.name, round(p.stat().st_size / 1e6, 1)) for p in cands])


def load(p):
    z = zipfile.ZipFile(p)
    d = {}
    for i in z.infolist():
        if i.is_dir():
            continue
        parts = i.filename.split("/")
        key = "/".join(parts[1:]) if parts[0] in ("red-dragon",) else i.filename
        d[key] = i.compress_size
    return d


nn = load(new)
mind = collections.Counter()
for k, v in nn.items():
    if k.startswith("mind/"):
        mind["/".join(k.split("/")[:2])] += v
print("mind total MB:", round(sum(mind.values()) / 1e6, 2))
for k, v in mind.most_common(6):
    print(f"   {v/1e6:6.2f} MB  {k}")
if cands:
    best = max(cands, key=lambda p: p.stat().st_mtime)
    on = load(best)
    added = {k: v for k, v in nn.items() if k not in on}
    removed = [k for k in on if k not in nn]
    grown = {k: nn[k] - on[k] for k in nn if k in on and nn[k] - on[k] > 50e3}
    print(f"vs {best.name} ({best.stat().st_size/1e6:.1f} MB, {len(on)} files): added {len(added)} = {sum(added.values())/1e6:.1f} MB, removed {len(removed)}, grown>50KB {len(grown)} = {sum(grown.values())/1e6:.1f} MB")
    tops = collections.Counter()
    for k, v in added.items():
        tops["/".join(k.split("/")[:2])] += v
    for k, v in tops.most_common(8):
        print(f"   + {v/1e6:6.2f} MB  {k}/")
    for k, v in sorted(grown.items(), key=lambda kv: -kv[1])[:5]:
        print(f"   ^ {v/1e6:6.2f} MB  {k}")
    print("removed sample:", removed[:8])
