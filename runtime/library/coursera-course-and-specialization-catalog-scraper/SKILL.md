---
name: coursera-course-and-specialization-catalog-scraper
description: "Search Coursera's course and specialization catalog by keyword, difficulty or partner university, with rating, learner count, enrollment type and course links. Output fields: name, partnerName, difficultyLevel, avgRating, learnerCount and more, as JSON rows. Use it for requests like \"Coursera course scraper\", or a CSV/JSON export of public Coursera data."
---

# Coursera Course & Specialization Catalog Scraper

Search Coursera's course and specialization catalog by keyword, difficulty or partner university, with rating, learner count, enrollment type and course links.

- Actor: https://apify.com/nimbryxo-studio/coursera-course-and-specialization-catalog-scraper (ID `nimbryxo-studio~coursera-course-and-specialization-catalog-scraper`)
- n8n workflow for the same Actor: https://github.com/bolvein-firex/scraping-n8n-workflows/blob/main/docs/coursera-course-and-specialization-catalog-scraper.md
- Example input: `references/example-input.json`
- Input schema: `references/input-schema.json`
- Output fields: `references/output-fields.json`

## When to use

Use this skill when the user wants:

- Coursera course scraper
- a repeatable export of public Coursera data as CSV or JSON

Do not use it for private, login-protected or paywalled data.

## What it returns

One JSON row per result. Columns from the Actor's dataset schema:

- `name`: Name
- `partnerName`: Partner Name
- `difficultyLevel`: Difficulty Level
- `avgRating`: Avg Rating
- `learnerCount`: Learner Count
- `courseUrl`: Course Url

All 7 declared fields: `references/output-fields.json`.

## Inputs

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `mode` | string | yes | search | What to fetch. `bySlug`, `byUrl` and `byIds` always return detail fields for the looked-up products. |
| `query` | string | no |  | Keyword search (mode=search, searchSpecializations). Optional narrowing keyword for byCategory and byPartner. |
| `startUrls` | array | no | [] | Course, specialization, professional certificate, guided project, degree or certificate page, or a Coursera search / courses URL. Search URLs are converted into catalog filters. |
| `slugs` | array | no | [] | Course or specialization slugs, e.g. `machine-learning`. A full Coursera URL is also accepted. |
| `productIds` | array | no | [] | Coursera product IDs such as `course~8UjeMk-mEeit4g4GsxE4dg` or `s12n~nOOfCDWeEeuiZgo2K4rorQ`. Bare course IDs are also accepted. |
| `productTypes` | array | no | [] | Limit results to these Coursera product types. Leave empty for every type. |
| `difficulties` | array | no | [] | Only include products at these difficulty levels. |
| `durations` | array | no | [] | Only include products in these duration bands. |
| `costs` | array | no | [] | Only include products with these cost labels. |
| `topics` | array | no | [] | Only include products in these subject areas (mode=byCategory requires at least one). |
| `languages` | array | no | [] | Only include products available in these content languages. |
| `subtitleLanguages` | array | no | [] | Only include products with subtitles in these languages. |
| `handsOnLearningTypes` | array | no | [] | Only include products with these hands-on learning formats. |
| `tools` | array | no | [] | Only include products that teach these tools or software skills. |

7 more optional fields on the Actor's Input tab.

Example (`references/example-input.json`):

```json
{
  "query": "machine learning",
  "productTypes": [
    "COURSE"
  ],
  "maxItems": 25,
  "mode": "search"
}
```

The input passes the Actor's input schema (checked at every publish). First run: `maxItems` = 25, small enough for the 300-second sync wait; raise it once the rows look right.

## Run it

Set `APIFY_TOKEN`, then call the synchronous endpoint for small and medium runs (it waits up to 300 seconds):

```bash
curl -s -X POST "https://api.apify.com/v2/acts/nimbryxo-studio~coursera-course-and-specialization-catalog-scraper/run-sync-get-dataset-items" \
  -H "Authorization: Bearer $APIFY_TOKEN" \
  -H "Content-Type: application/json" \
  -d @references/example-input.json > output.json
```

Or with Node 18+: `node scripts/run.mjs [input.json]`.

For large runs, start an async run and read its dataset when it finishes:

```bash
RUN=$(curl -s -X POST "https://api.apify.com/v2/acts/nimbryxo-studio~coursera-course-and-specialization-catalog-scraper/runs" \
  -H "Authorization: Bearer $APIFY_TOKEN" -H "Content-Type: application/json" \
  -d @references/example-input.json)
RUN_ID=$(echo "$RUN" | jq -r '.data.id'); DATASET=$(echo "$RUN" | jq -r '.data.defaultDatasetId')
curl -s "https://api.apify.com/v2/actor-runs/$RUN_ID?waitForFinish=60" -H "Authorization: Bearer $APIFY_TOKEN" | jq -r '.data.status'
curl -s "https://api.apify.com/v2/datasets/$DATASET/items?format=json" -H "Authorization: Bearer $APIFY_TOKEN" > output.json
```

## Cost and limits

- Apify bills the Actor's usage on your account; the Actor's Pricing tab shows the current price.
- Keep the limit in the input small for a first run.

## Guardrails

- Public data only. Do not pass cookies, sessions or private account data.
- Do not use the output for spam, harassment or unlawful discrimination.
- Check the target site's terms and local law before running at scale.
