import json, glob, os, re, sys
base = r"C:\Users\cinde\dragon-research\top1000"
items = []
for f in sorted(glob.glob(base + r"\raw\p*.json"), key=lambda x: int(os.path.basename(x)[1:-5])):
    items += json.load(open(f, encoding="utf-8"))["items"]
meta = {i["full_name"].lower(): (n, i) for n, i in enumerate(items, 1)}
dl = {}
if os.path.exists(base + r"\raw\downloads.json"):
    dl = {k.lower(): v for k, v in json.load(open(base + r"\raw\downloads.json", encoding="utf-8")).items()}
out, seen, bad = [], set(), 0
for f in sorted(glob.glob(base + r"\research\batch_*.jsonl")):
    for ln in open(f, encoding="utf-8-sig"):
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except Exception:
            bad += 1
            continue
        k = r.get("repo", "").lower()
        if k not in meta or k in seen:
            bad += 1
            continue
        seen.add(k)
        rank, i = meta[k]
        r["repo"] = i["full_name"]
        r["rank"] = rank
        r["stars"] = i["stargazers_count"]
        r["forks"] = i["forks_count"]
        r["lang"] = i["language"] or ""
        r["pushed"] = i["pushed_at"][:10]
        r["topics"] = " ".join(i.get("topics", [])[:10])
        r["desc"] = (i["description"] or "")[:240]
        r["url"] = i["html_url"]
        if i["archived"]:
            r["alive"] = "archived"
        d = dl.get(k, {})
        r["release_downloads"] = d.get("release_downloads_recent100", 0)
        r["latest_release"] = d.get("latest_release")
        for key in ("value_for_claude", "owner_relevance"):
            try:
                r[key] = int(r.get(key) or 0)
            except Exception:
                r[key] = 0
        out.append(r)
BLOCKED = {  # never recommend: licence circumvention / resale or abuse of paid AI access / patching others' apps
    "massgravel/microsoft-activation-scripts": "Windows/Office activation without a licence",
    "zbezj/heu_kms_activator": "Windows/Office activation without a licence",
    "wei-shaw/sub2api": "redistributes paid AI subscription quotas",
    "chatanywhere/gpt_api_free": "third-party resold API keys",
    "xtekky/gpt4free": "unofficial access to paid model providers",
    "alishahryar1/free-claude-code": "routes coding agents to unofficial free gateways",
    "ebony-vinyl/dsh-our-free-model": "unofficial free gateways, remote self-update, ad channel",
    "huiyadanli/revokemsgpatcher": "binary-patches third-party chat apps",
}
CONSENT = {  # allowed only with explicit authorisation / consent, said out loud
    "voice": ("needs consent of the voice owner", ["debpalash/voicestudio", "jamiepine/voicebox", "rvc-boss/gpt-sovits",
              "myshell-ai/openvoice", "coqui-ai/tts", "rvc-project/retrieval-based-voice-conversion-webui", "suno-ai/bark"]),
    "face": ("needs consent of the person whose face is used; label output as synthetic", ["hacksider/deep-live-cam", "deepfakes/faceswap"]),
    "sec": ("only against systems you own or are authorised in writing to test", ["rapid7/metasploit-framework", "sqlmapproject/sqlmap",
            "swisskyrepo/payloadsallthethings", "danielmiessler/seclists", "z4nzu/hackingtool", "usestrix/strix", "lissy93/web-check"]),
    "osint": ("people lookups only with a lawful purpose; never stalk or dox", ["soxoj/maigret", "sherlock-project/sherlock"]),
    "net": ("check local law before using circumvention tools", ["2dust/v2rayng", "v2ray/v2ray-core", "bannedbook/fanqiang",
            "freefq/free", "flowseal/zapret-discord-youtube"]),
    "root": ("rooting voids warranties and can brick devices; owner's own device only", ["topjohnwu/magisk"]),
    "leak": ("study material only; do not reuse vendors' prompts in products", ["x1xhlol/system-prompts-and-models-of-ai-tools",
             "asgeirtj/system_prompts_leaks", "elder-plinius/cl4r1t4s"]),
}
consent_map = {repo: note for _, (note, repos) in CONSENT.items() for repo in repos}
audit = {}
ap = base + r"\research\audit_result.jsonl"
if os.path.exists(ap):
    for ln in open(ap, encoding="utf-8"):
        a = json.loads(ln)
        audit[a["repo"].lower()] = a
fixed = 0
for r in out:
    k = r["repo"].lower()
    a = audit.get(k)
    if a:
        r["install_verified"] = a["verdict"] in ("ok", "fix")
        if a["verdict"] == "fix" and a.get("install_windows"):
            r["install_windows"] = a["install_windows"]
            if a.get("windows_ok"):
                r["windows_ok"] = a["windows_ok"]
            fixed += 1
    if k in BLOCKED:
        r["policy"], r["policy_note"], r["value_for_claude"] = "blocked", BLOCKED[k], 0
    elif k in consent_map:
        r["policy"], r["policy_note"] = "consent", consent_map[k]
    elif re.search(r"voice[ -]?clon|clon\w* (a |any )?voice|voice conversion|zero-shot (tts|voice)", (r.get("what","")+" "+r.get("desc","")), re.I):
        r["policy"], r["policy_note"] = "consent", CONSENT["voice"][0]
    elif re.search(r"face[ -]?swap|deepfake", (r.get("what","")+" "+r.get("desc","")), re.I):
        r["policy"], r["policy_note"] = "consent", CONSENT["face"][0]
    else:
        r["policy"] = ""
print("audit applied:", len(audit), "fixed:", fixed,
      "blocked:", sum(r["policy"] == "blocked" for r in out), "consent:", sum(r["policy"] == "consent" for r in out))
out.sort(key=lambda r: r["rank"])
missing = [i["full_name"] for k, (n, i) in meta.items() if k not in seen]
dst = base + r"\skill\github-atlas\data\atlas.jsonl"
os.makedirs(os.path.dirname(dst), exist_ok=True)
with open(dst, "w", encoding="utf-8") as fh:
    for r in out:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print("merged", len(out), "bad", bad, "missing", len(missing))
if missing:
    print("missing:", ", ".join(missing[:40]))
