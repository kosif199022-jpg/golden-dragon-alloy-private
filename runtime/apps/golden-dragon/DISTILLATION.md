# Golden Dragon skill distillation — experimental

This implementation is a **static, non-destructive** knowledge index, not an executable merger of tools or an AI semantic understanding of every skill.

## Run locally

From `apps/golden-dragon`:

```powershell
python -X utf8 forge/distill_skills.py "C:\path\to\skills" --output "distilled-knowledge.json"
python -X utf8 forge/query_distilled.py "distilled-knowledge.json" "video animation"
python -m unittest discover -s tests -p "test_distill_skills.py" -v
```

The JSON retains full section bodies and source filenames. Review it for secrets or copyrighted third-party content before sharing or committing. Do not commit generated knowledge by default.

## Limitations and next integration gate

- Exact normalized duplicates only, not semantic duplicates.
- Retrieval uses lexical overlap, not semantic embeddings.
- No automatic tool execution, source deletion, model synthesis, or app UI integration.
- No runtime tests or Windows executable build have been performed as part of these commits.
- Before connecting to the application's `fusion` interface, run tests, review licensing/security, benchmark retrieval against representative user tasks, and add an explicit user-approved execution adapter.
