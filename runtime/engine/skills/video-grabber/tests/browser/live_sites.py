#!/usr/bin/env python3
"""Live smoke test: sniff real public test pages, take a screenshot, check proxy_pool.

    python tests/browser/live_sites.py [OUT_DIR] [--only NAME]

Writes <OUT_DIR>/sniff_<name>.json, screenshot_*.png, text_*.json, summary.json.
Needs internet. Not part of the offline pytest suite.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from ghost_browser import GhostBrowser  # noqa: E402
from proxy_pool import ProxyPool, describe  # noqa: E402

SITES = {
    "mux_test_streams": "https://test-streams.mux.dev/",
    "bitmovin_stream_test": "https://bitmovin.com/demos/stream-test",
    "w3schools_html5_video": "https://www.w3schools.com/html/html5_video.asp",
    "vimeo_public": "https://vimeo.com/76979871",
    "dailymotion_public": "https://www.dailymotion.com/video/x8j5f2u",
    "bitmovin_drm": "https://bitmovin.com/demos/drm",
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    out = Path(args[0] if args else ".").resolve()
    out.mkdir(parents=True, exist_ok=True)
    summary = {"started": time.strftime("%Y-%m-%d %H:%M:%S")}

    pool = ProxyPool.from_sources(check=True)
    summary["proxy_pool"] = pool.summary()
    summary["direct_ip"] = ProxyPool.current_ip(None)

    with GhostBrowser(proxy=pool if len(pool) else None) as gb:
        for name, url in SITES.items():
            if only and name != only:
                continue
            t0 = time.time()
            try:
                r = gb.sniff(url, wait=20)
                (out / f"sniff_{name}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
                summary[name] = {"ok": bool(r["media"]), "n_media": len(r["media"]),
                                 "kinds": sorted({m["kind"] for m in r["media"]}),
                                 "best": r["best"]["url"] if r["best"] else None,
                                 "best_kind": r["best"]["kind"] if r["best"] else None,
                                 "captcha": r["captcha"], "drm": r["drm"], "drm_systems": r["drm_systems"],
                                 "embeds": r["embeds"][:3], "secs": round(time.time() - t0, 1)}
            except Exception as e:  # noqa: BLE001
                summary[name] = {"ok": False, "error": str(e).splitlines()[0][:300], "secs": round(time.time() - t0, 1)}
            print(name, json.dumps(summary[name], ensure_ascii=False), flush=True)
        if not only:
            shot = gb.screenshot("https://test-streams.mux.dev/", str(out / "screenshot_mux.png"), full_page=True)
            txt = gb.fetch_text("https://www.w3schools.com/html/html5_video.asp")
            (out / "text_w3schools.json").write_text(json.dumps(txt, ensure_ascii=False, indent=2), encoding="utf-8")
            ck = gb.export_cookies(str(out / "cookies_w3schools.txt"))
            summary["screenshot"] = shot
            summary["text"] = {"title": txt["title"], "chars": len(txt["text"]), "links": len(txt["links"])}
            summary["cookies"] = ck
            summary["egress"] = describe(gb.proxy)
    (out / ("summary.json" if not only else f"summary_{only}.json")).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "proxy_pool"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
