# Full Golden Dragon Alloy — optional private local knowledge

The public Golden Dragon repository intentionally does NOT include private owner
memory. The full skill, its runtime files, historical memory, and the live learning
snapshots are stored in the owner's PRIVATE GitHub repository:

https://github.com/kosif199022-jpg/golden-dragon-alloy-private

To use the private full knowledge in the desktop application's Knowledge panel,
clone this repository into a local directory and set:

    GOLDEN_DRAGON_ALLOY_HOME = path/to/golden-dragon-alloy

By default, the bridge checks the owner's home/golden-dragon-alloy folder.
If available, the app searches the private 26,363-unit FTS database in
read-only mode, exposing ONLY active, non-memory records. Without this folder,
the app continues using its existing bundled 16,315-record knowledge database.

Private historical memory (163 units), and future lessons, remain available
from the private skill's own command-line interface:

    python -X utf8 alloy.py memory stats
    python -X utf8 alloy.py memory recall "السؤال"
    python -X utf8 alloy.py memory remember "تعلم جديد"
    python -X utf8 alloy.py learn "درس جديد"
    python -X utf8 alloy.py memory snapshot
    python -X utf8 alloy.py memory sync --push

The private memory only synchronizes when explicitly requested; the sync
operation refuses to push to a public GitHub remote. Nothing in the public
repository or the desktop app copies the private DB, chats, or learning files.

This integration does not install or overwrite any existing skill on the
owner's PC. The original complete .skill archive is preserved on the PC.
