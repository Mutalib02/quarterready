# recorded/ – Claude output recorded via Claude Code

**Claude output recorded via Claude Code today (2026-11-04) – live API mode needs a funded key.**

These files are replay responses in the same hash-keyed format as `cache/`, but they were *not*
produced by a live API call. The API key had no credit, so each request the app would have sent
was written out (`scripts/claude_code_recorder.py run`) and answered by Claude (claude-sonnet-5-5)
running inside Claude Code, who read the redacted request and wrote the response the model would
give (`scripts/claude_code_recorder.py apply`). 39 responses cover one full morning briefing on
the standard synthetic data:

- 1 + 1 + 1 + 1 + 1 = 5 agent turns (tool selection, queueing, final to-do list)
- 10 lead assessments, 5 sentiment checks
- 7 categorisation batches covering all 304 rows of Dave's Q2 CSV
- 7 lead replies, 3 quote wordings, 1 records chase, 1 retention message

How honest is it?

- The judgements are mine, made from the redacted request only. `data/labelled_*.csv` was not
  opened until after every answer was recorded.
- Per-merchant decisions were typed into a lookup table and applied to rows by regex to save
  typing. The table is a record of those decisions; it is not the local rule engine.
- This is **not** a blind test: the same session wrote the generator and knew the trap list in
  CLAUDE.md §5. Treat the evaluation numbers as indicative only.
- Replay is exact-match: changing a prompt, the data or the tools changes the request hash, and
  the Recorded engine will then say "Not in the recorded set". `tests/test_recorded.py` guards this.

To get real API output, fund a key and use Live mode, then commit `cache/*.json`.
