"""Run an installed fusion workflow and report its observed result."""
import argparse
import hashlib
import json
from pathlib import Path

from render_vertical import render


def inspect_windows(path):
    import pefile
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    with pefile.PE(str(path), fast_load=True) as binary:
        return {"file": path.name, "bytes": path.stat().st_size, "sha256": digest,
                "machine": hex(binary.FILE_HEADER.Machine),
                "sections": [section.Name.rstrip(b"\0").decode("ascii", "replace")
                             for section in binary.sections]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("inspect-windows").add_argument("source", type=Path)
    video = actions.add_parser("vertical-video")
    video.add_argument("source", type=Path)
    video.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "inspect-windows":
        print(json.dumps(inspect_windows(args.source), ensure_ascii=False))
    else:
        print(json.dumps(render(args.source, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
