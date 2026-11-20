# Golden Dragon Alloy — full private build and continuing memory

**Repository visibility: PRIVATE. Never make public.** This repository
contains the full 255 MB unpacked skill, its 7,387 runtime files, its original
26,363-unit knowledge database including all 163 private memory units, and
the owner's live local learning snapshots (chats, lessons, plans and guards).

No private memory, skill file, or original source was removed from the full
skill. The original 134 MB .skill archive remains unchanged on the owner's PC.

## Continue learning

From the folder containing alloy.py:

    python -X utf8 alloy.py memory stats
    python -X utf8 alloy.py memory recall "سؤال"
    python -X utf8 alloy.py memory remember "التصحيح أو المعلومة الجديدة"
    python -X utf8 alloy.py memory remember "قرار جديد" --kind decision
    python -X utf8 alloy.py learn "درس جديد" --domain general
    python -X utf8 alloy.py memory snapshot
    python -X utf8 alloy.py memory sync --push

The original rd.py learn continues to save in the user's home .red-dragon
lessons.jsonl; successful calls through alloy.py also snapshot the learning
into the private owner-memory/live directory. New memory remember entries
are append-only in owner-memory/journal.jsonl. Routes retrieve relevant
private memory on later tasks, without executing stored text as commands.

No automatic uploads. The memory sync --push command refuses to transfer
data unless the GitHub remote has been confirmed PRIVATE.

## Integrity and safe installation

    python -X utf8 alloy.py selftest
    python -m unittest discover -s forge -p test_owner_memory.py -v
    python -X utf8 alloy.py memory stats

The tracked files here represent the full unpacked contents, not a trimmed
portable version. A separate portable ZIP is available on the owner PC.

Do not replace an already installed Golden Dragon skill without explicit
permission to install. Preserve owner videos and other private user files.
