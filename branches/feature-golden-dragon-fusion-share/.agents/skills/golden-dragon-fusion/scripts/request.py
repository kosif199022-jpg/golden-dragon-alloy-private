"""Execute the supported parts of a single media and file-inspection request."""
import argparse
import json
import re
from pathlib import Path

from fusion import inspect_windows
from render_vertical import render


def execute(request, sources, output):
    words = request.casefold()
    vertical = re.search(r"vertical|portrait|9:16|رأسي|راسي|عمودي|طولي", words)
    inspect = re.search(r"inspect|fingerprint|بصم|افحص|فحص", words)
    if len(sources)==1 and sources[0].suffix.lower()==".srt" and re.search(r"vtt|webvtt",words):
        from captions import convert
        return convert(sources[0],output)
    sheets = [p for p in sources if p.suffix.lower() == ".csv"]
    if sheets:
        if len(sources) != 1 or not vertical or not output or not re.search(r"inventory|stock|جرد|مخزون", words):
            raise ValueError("Supply one inventory CSV and a new MP4 path for a vertical inventory report")
        from inventory_reel import report
        return report(sheets[0], output)
    videos = [p for p in sources if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".avi", ".webm"}]
    binaries = [p for p in sources if p.suffix.lower() in {".exe", ".dll"}]
    if not all(p.is_file() for p in sources):
        raise ValueError("A requested input file is missing")
    if len(videos) + len(binaries) != len(sources):
        raise ValueError("Unsupported input type")
    if videos and (not vertical or len(videos) != 1):
        raise ValueError("Video input requires one vertical conversion request")
    if binaries and not inspect:
        raise ValueError("Windows binary input requires an inspection request")
    if bool(output) != bool(videos):
        raise ValueError("Supply an MP4 output path only for video conversion")
    report = {"binary_inspections": [inspect_windows(p) for p in binaries]}
    if videos:
        report["vertical_video"] = render(videos[0], output)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request")
    parser.add_argument("inputs", nargs="*", type=Path)
    parser.add_argument("--method", action="store_true", help="Return the unified review method for a task")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from experience import load_policy, review, verify
    policy = load_policy()
    if args.method:
        if args.inputs or args.output:
            parser.error("--method takes a request only")
        from production_method import caption_method
        response = {"mode": "method", "checks": review(args.request, policy)}
        decisions = caption_method(args.request)
        if decisions:
            response["production_method"] = decisions
    else:
        if not args.inputs:
            parser.error("Supply input files for execution, or use --method for quality checks")
        response = execute(args.request, args.inputs, args.output)
        evidence = verify(response, args.inputs)
        response["verified_properties"] = evidence
        response["review_checks"] = review(args.request, policy, evidence.keys())
    print(json.dumps(response, ensure_ascii=False))
