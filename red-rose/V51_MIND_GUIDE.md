# V51 adaptive mind

Use mind plan for substantial or uncertain tasks; do not invoke all 44 methods on every request. For routine tasks the existing fast path remains. Pass JSON containing request and optionally impact/uncertainty (0..3), constraints, unknowns, deliverable, done_when, external and irreversible flags. The underlying router is unchanged. The new gate never grants execution permission. Use mind gate to hash trusted workspace evidence and check supplied stage and constraint outcomes; hashes establish integrity, not semantic correctness. Use mind learn with explicit approval to store reproduced correction proposals with matching evidence hashes; this is a local candidate ledger, not accepted memory or automatic code modification. Use existing owner-authorized learning.record for accepted memory. All claims must be independently checked. No change to model weights or autonomous training.

Commands: python rose.py mind status; python rose.py mind plan INPUT.json; python rose.py mind gate INPUT.json; python rose.py mind learn INPUT.json --approve-write; python rose.py mind lessons. Optional --mind-db isolates local candidate storage.

Validation: python -m unittest -v test_mind_v51 test_white_native_v50 test_golden_native_v49. Existing routing failures are not changed or waived.
