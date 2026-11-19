# Sources and method

**Snapshot date:** 2026-11-11.

## How the data was collected

### 1. Repo list
- Taken from the GitHub search API with `q=stars:>1000`, `sort=stars`, 10 pages of 100 results.
- 1000 unique repos, from codecrafters-io/build-your-own-x (561,670 stars) down to balena-io/etcher (34,683 stars).
- 1000 is also the hard cap of GitHub search.
- The raw pages are in `data/raw/p1..p10.json`, and the list is in `data/top1000.csv`.

### 2. "Downloads"
- GitHub has no per-repo download counter.
- `release_downloads` is the sum of `download_count` over the assets of the newest 100 releases (`GET /repos/{r}/releases?per_page=100`).
- 450 repos publish release assets. The rest ship through pip, npm, source or app stores, so they show 0. **0 does not mean unpopular.**
- Top by this measure: uv 741M, jq 313M, Rufus 274M, yarn 267M, yt-dlp 241M.

### 3. Per-repo analysis
- 10 parallel agents each read the README of 100 repos through `gh api`. Usually they read the first 6000 characters; batch 08 read shorter excerpts.
- For each repo they filled the fixed schema in `data/AGENT_BRIEF.md`.
- They never cloned or ran anything.
- Batch reports are in `data/reports/batch_01..10.md`. The batch 10 report was not written because the agent hit a rate limit after finishing its JSONL.

### 4. Install audit
- The 100 highest-value / most uncertain install lines were re-checked against the full README and release assets.
- Results: 62 ok, 37 corrected, 1 unsure.
- `install_verified: true` marks the 99 lines that were confirmed or corrected.

### 5. Policy layer
- `blocked` (8 repos) and `consent` (30 repos) were assigned by hand.
- Voice-cloning and face-swap repos are also auto-flagged from their descriptions (see `references/safety.md`).

### 6. Installed check
- `atlas.py` maps about 45 repos to their executable and checks `PATH` at run time.

## Known limits

- **Unconfirmed installs:** 246 install lines still carry `?`. Confirm them from the README before running.
- **Scores are judgement:** `value_for_claude` and `owner_relevance` are model judgements from README text, not measurements.
- **The ranking is stars, not quality:** the list includes memes, course notes and Chinese-language study material. These have value 0 and sink in search.
- **Data goes stale:** stars and maintenance status change. Run `atlas.py refresh` (about 1000 API calls) to update stars, push dates and archived flags.
