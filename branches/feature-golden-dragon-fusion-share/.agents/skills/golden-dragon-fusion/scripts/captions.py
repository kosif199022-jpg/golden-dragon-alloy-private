"""Convert numbered UTF-8 SRT cues to WebVTT, preserving text and cue timing."""
import re
from pathlib import Path
from srt_words import read_srt


def convert(source, output):
    if output is None or output.suffix.lower() != ".vtt":
        raise ValueError("Supply a new .vtt output")
    original=source.read_text(encoding="utf-8-sig").strip()
    blocks=re.split(r"\n\s*\n", original)
    cues=read_srt(source)
    if not cues or len(cues)!=len(blocks):
        raise ValueError("Malformed or unsupported SRT cues")
    lines=["WEBVTT",""]
    previous=-1
    for block,(start,end,text) in zip(blocks,cues):
        raw=block.splitlines()
        if len(raw)<3 or not raw[0].strip().isdigit():
            raise ValueError("Missing cue number or text")
        match=re.fullmatch(r"(\d{2}:[0-5]\d:[0-5]\d,\d{3}) --> (\d{2}:[0-5]\d:[0-5]\d,\d{3})",raw[1])
        if not match or start<previous or end<=start or not text or text!="\n".join(raw[2:]).strip():
            raise ValueError("Invalid cue timing or text")
        lines.extend([" --> ".join(v.replace(",",".") for v in match.groups()),text,""])
        previous=start
    with output.open("x",encoding="utf-8",newline="\n") as stream:
        stream.write("\n".join(lines)+"\n")
    return {"captions":{"output":str(output.resolve()),"cues":len(cues),"last_end":cues[-1][1]}}
