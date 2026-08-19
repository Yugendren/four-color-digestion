# FINALIZE.md — how to finish P2 coverage measurement from here

Written by the worker that set up the P2 background pipelines, at the point where it
was told to stand down (main session takes over from here). Everything below is
resumable / idempotent; nothing here requires re-deriving design decisions, only
running commands and merging.

## Status snapshot at handoff time (see actual current state, this will be stale)

Run `.venv/bin/python3 tools/p2_report.py` (prints to stdout; doesn't need any
merge step to give you an accurate PARTIAL picture) to get the live numbers. As of
writing this file:

- **Wheel-level (Part 1)**: d=7, d=8, d=9 fully merged and done (`results/p2-coverage/
  DONE_wheel_d7/d8/d9` markers exist, `summary_d{7,8,9}.json` + `wheel_survivors_d{7,8,9}.jsonl`
  are final). d=10 is ~85% through its 8 shards. d=11 has not started yet (the driver
  processes degrees strictly sequentially).
- **Cartwheel-level (Part 2)**: d=10 (626/626) and d=11 (8/8) are COMPLETE. d=7 is
  ~80% through 5439 wheels, d=8 ~85% through 6790 wheels. **d=9 was never launched at
  the cartwheel level** — this matches the literal scope of `01-PROBLEM-STATEMENT.md`'s
  deliverable 2 instructions (which explicitly named d=11, d=10, d=7, d=8 and never
  mentioned d=9 for the `--enum_cartwheels` re-run). Decide whether to add it (see
  "Optional: d=9 cartwheel-level" below) or explicitly note the omission as intentional
  in the final report — either is defensible, but the report should say which.

## 1. Everything is self-driving; just wait / check

Both long-running pipelines are detached, resumable, background processes already
running (launched via `nohup ... & disown`, NOT via any tool's background-task
tracking — they will keep running independently of this conversation/session, but you
must poll their output files yourself, e.g. via a `Bash` `until <marker exists>; do
sleep 30; done` loop with `run_in_background: true`, and expect that loop itself to
get killed after a while — just re-issue it, it's idempotent):

**Wheel-level driver** (PID likely still `tools/p2_run_wheel_coverage.sh`, check with
`ps aux | grep p2_run_wheel_coverage`):
```
cd /Users/yugendren/experiments/four_color_digestion
tail -f log_p2_wheel_coverage.txt          # progress log
ls results/p2-coverage/DONE_wheel_all      # exists once EVERYTHING (d7..d11) is done
```
If for some reason the driver process died, just re-launch it — it skips any degree
whose `DONE_wheel_d{d}` marker already exists, and each shard resumes from its own
`.state.json` via `--resume`:
```
nohup tools/p2_run_wheel_coverage.sh > log_p2_wheel_coverage.txt 2>&1 & disown
```

**Cartwheel-level drivers** (PIDs were 10047 for d7, 10341 for d8 at launch time —
check with `ps aux | grep main_blocklog` / `ps aux | grep enum_blocklog_d78`):
```
cd /Users/yugendren/experiments/four_color_digestion/third_party/computer-checks
ls wheels/zero_blocklog/d7_*.blocklog.tsv | wc -l   # vs 5439
ls wheels/zero_blocklog/d8_*.blocklog.tsv | wc -l   # vs 6790
tail -f log_blocklog/d7_driver.log
tail -f log_blocklog/d8_driver.log
```
If dead, re-launch (resumable — skips any idx whose `.blocklog.tsv` already exists,
even if 0 bytes):
```
cd /Users/yugendren/experiments/four_color_digestion/third_party/computer-checks
nohup ./enum_blocklog_d78.sh 7 5439 > log_blocklog/d7_driver.log 2>&1 & disown
nohup ./enum_blocklog_d78.sh 8 6790 > log_blocklog/d8_driver.log 2>&1 & disown
```

## 2. Merging (wheel-level only — cartwheel-level needs no merge step)

**Wheel-level**: the driver (`tools/p2_run_wheel_coverage.sh`) already calls
`tools/p2_wheel_coverage.py --degree {d} --merge --shard-total {N}` automatically once
all shards for a degree finish, producing `results/p2-coverage/wheel_survivors_d{d}.jsonl`
(merged) + `summary_d{d}.json`. You should NOT need to run the merge manually unless
the driver died mid-merge; if so:
```
.venv/bin/python3 tools/p2_wheel_coverage.py --degree {d} --merge --shard-total 8
```
(shard-total is 8 on this machine — `sysctl -n hw.ncpu` (10) minus 2, see the driver
script; if you re-shard with a different count you must merge with that same count).

**Cartwheel-level**: there is no merge step — `wheels/zero_blocklog/*.blocklog.tsv`
(one file per wheel, named `d{degree}_{idx}.blocklog.tsv`) IS the final data, already
in its final location. `tools/p2_report.py`'s `cartwheel_level_stats()` (in
`tools/p2_report.py`) reads directly from
`third_party/computer-checks/wheels/zero_blocklog/*.blocklog.tsv` — **this path was
double-checked and is correct** (i.e. if you were told the stats collector points at
the wrong directory, that has already been verified NOT to be the case: `CC / "wheels"
/ "zero_blocklog"` where `CC = ROOT / "third_party" / "computer-checks"` resolves to
exactly `third_party/computer-checks/wheels/zero_blocklog`, which is where
`enum_blocklog_d78.sh` / the manual d10/d11 validation runs actually wrote their
output — confirmed by successfully running `tools/p2_report.py` against it and getting
sane, non-zero numbers). If you DO hit an empty/wrong-directory symptom, check first
whether `third_party/computer-checks/wheels/zero_blocklog` actually exists and has
files (`ls | wc -l`) before assuming the Python side is broken.

## 3. Once everything is `complete`

```
cd /Users/yugendren/experiments/four_color_digestion
.venv/bin/python3 tools/p2_report.py > results/p2-coverage/report.md
```
This regenerates `results/p2-coverage/report.md` (already present from a PARTIAL run at
handoff time — re-run this to get the final version) plus JSON sidecars
`results/p2-coverage/wheel_level_stats.json` and `cartwheel_level_stats.json`. The
report's "Tractability verdict" section (`_tractability_verdict()` in
`tools/p2_report.py`) is generated dynamically from the actual numbers, including a
"PARTIAL data" caveat sentence that will automatically disappear once both parts report
`status: complete` — no manual editing needed, just re-run.

**Important finding already visible in the partial data, worth preserving in the final
narrative**: wheel-level column reduction is dramatic (~61 distinct blocker configs out
of 8,200, i.e. >99% reduction) but cartwheel-level column reduction is NOT (already
6,415/8,200 ≈ 78% of the pool implicated, as a LOWER bound, from d7/d8 partial + d10/d11
complete) — this is a genuinely different and less optimistic result than the wheel-
level number alone would suggest, and than `01-PROBLEM-STATEMENT.md`'s
resource-realities section seemed to expect ("likely far below 8,200"). Don't let the
wheel-level number carry the whole tractability story; both levels need to be reported,
and the cartwheel-level number is probably the more decision-relevant one for P3 since
that's the level the real proof's search actually operates at.

Also worth flagging honestly: the cartwheel-level C++ patch logs only the FIRST
matching config per blocking event (mirroring the original short-circuit boolean
check), not full attribution like the wheel-level Python code does. So (a) the
cartwheel-level "distinct blocker" count is a lower bound, not exact, and (b) there is
currently NO measurement of true row-sparsity (avg blockers per event) at the
cartwheel level — the "1.0" you'll see in the table is an artifact of first-match-only
logging, not a real sparsity measurement. `tools/p2_report.py`'s tractability verdict
already says this explicitly; don't let it get edited into a false "sparse, 1.0
avg" claim.

## 4. Optional: full cartwheel-level attribution (if the exact column/sparsity numbers
   matter for the final P3 tractability claim, not just a lower bound)

A follow-up patch of the same shape as `results/p2-coverage/cxx_patch.diff` could change
`blocked_by_reducible_configuration`'s `matched_names` collection (in
`pseudo_configuration.cpp`, already has the plumbing) to gather ALL matches instead of
stopping at the first — this is a small additional diff, NOT a redesign, since the
out-parameter machinery already exists; only `contain_conf`'s inner loop needs to keep
scanning instead of returning early when `matched_name != nullptr`. Given the cost
already observed (full d10+d11 cartwheel-level took a few minutes; d7/d8 first-match
logging is taking ~30-40 min combined), full attribution would cost more (no early
exit) but is very likely still tractable within an hour or two — worth doing if the
"78%" lower bound needs to become an exact figure for the final report. Not started;
flagging as a clearly-scoped next step rather than doing it, since it changes the
already-validated and already-running C++ patch.

## 5. Optional: d=9 cartwheel-level

Not launched (see status note above). If wanted:
```
cd /Users/yugendren/experiments/four_color_digestion/third_party/computer-checks
nohup ./enum_blocklog_d78.sh 9 3285 > log_blocklog/d9_driver.log 2>&1 & disown
```
(the driver script is generically parameterized by degree/count despite its `_d78`
name — it was named for the two degrees the original spec called out, but works for
any degree given `wheels/d{degree}/*.cartwheel` exists, which it does for d9).

## 6. Tests / `make test`

`tests/test_nl4ct.py::TestBlockingAttribution` (the new P2 deliverable-4 differential
tests) were run standalone and passed (16/16 tests in `tests.test_nl4ct`, ~153s). The
FULL `make test` (all three test files: `test_nl4ct.py`, `test_conf_parser.py`,
`test_reduce.py`) was NOT re-run after this point in favor of not competing for CPU
with the background coverage/blocklog runs — `test_conf_parser.py` and `test_reduce.py`
were not touched by this work and should be unaffected, but re-run `make test` once
before the final commit to confirm the full suite is still green, per the original task
's acceptance gate.

## 7. Final commit

The task's specified final commit message (once report.md reflects complete data and
`make test` is green) is:
```
P2 coverage measurement: wheel- and cartwheel-level blocking attribution

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Pf3nH15FoWpvvUnkYiDboB
```
An intermediate commit (uncommitted code/tooling/tests/partial results, everything
needed to resume/finish) was already made before this handoff — see `git log` — so the
final commit should be a NEW commit on top of it (per repo convention: never amend),
containing the final `report.md`, final `wheel_survivors_d*.jsonl` / `summary_d*.json`,
and whatever cartwheel-level completion state exists at that time. The nested git repo
at `third_party/computer-checks` (the C++ patch) is intentionally NOT part of any outer
commit — it's a separate, already-clean-before-our-edits nested repository; the
reproducible artifact for the outer repo is `results/p2-coverage/cxx_patch.diff`
(229 lines) plus the `.orig` backups left next to every patched file under
`third_party/computer-checks/src/*.orig`.
