# White Bird-inspired orchestration V50

Native SQLite queue, no dependency on WhiteBird.exe. Commands:
- python rose.py white-native status
- python rose.py white-native enqueue job.json --approve-write
- python rose.py white-native work-one --approve-write
- python rose.py white-native result JOB_ID
- python rose.py white-native recover --approve-write
- python rose.py white-native verify-outputs files.json
- python rose.py white-native check-pairs events.json
- python rose.py white-native compare scores.json

Optional --queue-db isolates a queue. Job JSON: {"op":"motion-ease","params":{"name":"linear","samples":3}}. Five allowlisted pure operations (motion-ease, motion-beats, decision-matrix, plan-gaps, agent-rigor). No shell, network, model launch or file-writing jobs. Each explicit work-one runs one job, persists the result, and returns. Recover requeues expired five-minute leases, with fencing and at most three claims. No daemon or automatic background monitoring. Verify-outputs accepts {"workspace":"local folder","files":["relative.txt"]}, trusted workspace only. Comparison ranks supplied scores, not actual models. Test: python -m unittest -v test_white_native_v50 test_golden_native_v49.
