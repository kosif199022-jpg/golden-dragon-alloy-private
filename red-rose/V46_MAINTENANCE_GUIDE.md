# V46 — Red Rose speed and bounded self-maintenance

## Native changes
- Readiness counts use one catalogue snapshot, one status snapshot and one dependency result per distinct requirement set. The public single-op readiness still checks fresh state.
- Media integrity hashing streams 1 MiB chunks; full ffprobe and decode gates remain.
- The native `maintain` CLI offers audit, test, benchmark and approved repair. The only currently auto-repairable code regression is the exact legacy whole-video hash allocation. Unknown defects must not be labelled repaired.

## Run
From red-rose:
```bash
python rose.py maintain audit
python rose_maintenance.py benchmark
python rose_maintenance.py test --timeout 180
python rose.py maintain repair
python rose.py maintain repair --approve-write
```
The standalone command avoids loading the full CLI for audit. Test subprocesses have deadlines and a temporary RED_ROSE_DB. Repair candidates run in an overlay; failed or changed candidates are rejected. No owner memory, secrets, remote code, package install, upload, auto-push, or model retraining. Run repair only when no other process is editing the skill.

## Continuous improvement protocol (agent, each authorized development task)
1. Fast lane: audit once, reuse verified capabilities and cached readiness; avoid loading all reference archives. Slow lane only for unknown defects, quality failures, or risk. Capture evidence and reproduce the actual failure.
2. Diagnose with minimal fixtures and timing; compare baseline, candidate, and held-out case. Use median and same machine/settings; no performance claims from one run.
3. Prefer native targeted code. For media: validate encoder on device, bound retries and timeouts; keep quality and exact Arabic text; cache static assets by source/settings hashes; resume missing segments; independent continuity, audio and decode checks. These are next implementation targets, not all shipped by V46.
4. Add a negative regression test. Run targeted and full suite in isolated environment. Reject degradation, untested work, unknown dependencies, and unauthorized writes. Agent must not weaken QA to improve speed.
5. Propose a small branch/PR, preserve history and prior source. Update DISCOVERIES and provenance from verified results only. No automatic main merge without authorization and green checks.
6. For approved safe known regressions, native repair applies only exact tested candidate; repeated run is idempotent. For new defects, authorized coding agent proposes a patch and adds reviewed deterministic repair rules if appropriate. Do not claim autonomous general AI code generation without a configured agent.
7. Keep personal memory local and record only verified lessons with existing approval rules.

## Attachment distillation (reviewed source examples; no archive runtime dependency)
- Cinema C V31: bounded commands, socket timeouts, retry limits. V34: encoder probe/cache, compatible output and recovery.
- Maven Toon: cached set bake, bounded workers and resumable segment rendering; doctor/QA.
- Maven 3D: deterministic seek, partial re-render. Kitten Rescue (two archives): frame-range export, deterministic seek, streamed ffmpeg.
- Remotion: smallest frame-dependent component, RTL word animation, preserve connected Arabic letters.
- Faceless Shorts: end-to-end self-test; Living Site: independent cut/continuity gates.
- Thinking, Fast and Slow (Daniel Kahneman): automatic vs deliberate work, escalate when uncertainty/error risk is high; engineering analogy, not a trained cognitive model.

## Evidence status
Source reviewed; benchmark and CI results must be recorded from the exact commit before claiming a measured speedup or merging. No claim that full media rendering is faster.
