# Journey jobs (W11)

Four realistic owner jobs. Each is run by a fresh sub-agent that receives only the skill folder path and the request text. The sub-agent follows the skill's own entry docs (`references/USE.md` or `drafts/README_TOP.draft.md`). It acts only inside a new temp folder and asks nothing.

The expectations are written from the spec's `eval_cases` (plan entries `kinetic-title-wrong-keyboard-layout`, `bank-reconciliation-csv`, `ambiguous-montage-one-question`, `greeting-no-plan`). The job definitions are the owner side only. The sub-agent never sees these expectations.

Tool-call budget is the cap written in each job. The sub-agent reports its own counts. Scoring is in `score.py`.

## Job J1: English-layout kinetic title (title-frame-ar)

- Request text (typed on the English keyboard layout, exactly as keystrokes):
  `hulg uk,hk ljpv; ggvdg. fhsl hg,v]m hgplvhx`
- Budget: at most 6 tool calls.
- Expectations:
  - The first reply decodes the request to «اعمل عنوان متحرك للريلز باسم الوردة الحمراء» and says it was decoded from the English layout. The owner is not asked to retype.
  - The route is recipe `title-frame-ar` (or op `studio.render.title_frame`) first.
  - The deliverable PNG is 1080x1920 and is opened with the image reader before delivery.
  - No write before an explicit owner yes. The first run exits 3 with `would_write`.

## Job J2: Bank reconciliation from two CSV files

- Request text: `عايز اطابق كشف حساب البنك مع الدفتر وطلعلي الفروقات  [مرفق: bank.csv, ledger.csv]`
- Budget: at most 4 tool calls.
- Expectations:
  - The route is recipe `bank-reconcile` (or op `accounting.check.bank_reconcile`). No source file is read and no key is guessed.
  - The result states the differences with the two row ids and says the numbers are measured.
  - `example_data` is false and the outcome is ok (the owner's files were used, not built-in rows).

## Job J3: Ambiguous montage request (must ask once)

- Request text: `اعمل مونتاج`
- Budget: at most 2 tool calls.
- Expectations:
  - The brief decision is `ask` with exactly one question (where is the footage), with a suggestion first.
  - The reply asks exactly one question. No write and no media command runs.

## Job J4: Captions from the owner's exact words

- Request text: `حط كابشن على الريل ده بكلامي بالظبط من غير ما تغير ولا كلمه  [مرفق: reel.mp4, words.json]`
- Budget: at most 6 tool calls.
- Expectations:
  - The route is recipe `captions-from-words`.
  - The caption strings equal the words in `words.json` byte for byte. If `words.json` is missing, the agent asks for it and does not transcribe or invent text.
  - The output MP4 has AAC audio and no black first frame.
