import zipfile, sys, collections
from pathlib import Path
new = Path.home() / "OneDrive" / "Desktop" / "red-dragon-v2.8.0.zip"
olds = sorted((Path.home() / "OneDrive" / "Desktop").glob("red-dragon-v2.7*.zip")) + sorted((Path.home() / "rd-staging" / "backups").glob("*.zip"))
z = zipfile.ZipFile(new)
inf = z.infolist()
print("biggest compressed:")
for i in sorted(inf, key=lambda i: -i.compress_size)[:15]:
    print(f"  {i.compress_size/1e6:6.2f} MB  {i.filename}")
top = collections.Counter()
for i in inf:
    parts = i.filename.split("/")
    top["/".join(parts[1:3]) if len(parts) > 3 else "/".join(parts[1:2])] += i.compress_size
print("by folder (top 12):")
for k, v in top.most_common(12):
    print(f"  {v/1e6:6.2f} MB  {k}")
for o in olds:
    try:
        oz = zipfile.ZipFile(o)
    except Exception as e:
        print("skip", o.name, e)
        continue
    on = {"/".join(n.split("/")[1:]): i.compress_size for n, i in ((i.filename, i) for i in oz.infolist())}
    nn = {"/".join(i.filename.split("/")[1:]): i.compress_size for i in inf}
    added = {k: v for k, v in nn.items() if k not in on}
    print(f"vs {o.name}: old {o.stat().st_size/1e6:.1f} MB, {len(on)} entries; added {len(added)} files = {sum(added.values())/1e6:.1f} MB")
    for k, v in sorted(added.items(), key=lambda kv: -kv[1])[:8]:
        print(f"    + {v/1e6:6.2f} MB  {k}")
    break
