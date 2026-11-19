from pathlib import Path
from zipfile import ZIP_DEFLATED,ZipFile,ZipInfo

def build(root):
    components={"SKILL.md":root/"SKILL.md","__main__.py":root/"scripts/request.py"}
    for name in ("fusion.py","render_vertical.py","inventory_reel.py","experience.py","policy.json","captions.py","srt_words.py","production_method.py"):
        components[name]=root/"scripts"/name
    with ZipFile(root/"golden_dragon.pyz","w") as archive:
        for name,path in sorted(components.items()):
            item=ZipInfo(name,(2020,1,1,0,0,0))
            archive.writestr(item,path.read_bytes(),compress_type=ZIP_DEFLATED)

if __name__=="__main__":
    build(Path(__file__).resolve().parent.parent)
