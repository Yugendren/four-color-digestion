#!/bin/bash
# tools/lp_rerun_failed_wheels.sh
#
# Re-run `--enum_cartwheels` for the wheels whose S1 (ring<=14 pool) job ABORTED on an
# assert, using an NDEBUG (Release) build so the asserts are compiled out and the
# offending fully-refined cartwheels are written to disk instead of killing the process.
#
# Those cartwheels are the leaves of the refinement search; each one yields a LINEAR
# necessary constraint on the rule-amount vector x (see tools/lp_discharge.py and
# results/steinberger/LP-SCHEMA-RESULT.md). Nothing here is used as a *proof* that the
# pipeline passes -- only as a source of valid constraint rows.
#
# Idempotent/resumable via per-wheel .done markers, like tools/p3_pipeline_run.sh.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CC="$ROOT/third_party/computer-checks"
BIN="${LP_BIN:-$CC/build-ndebug/src/main}"
RUN_DIR="$ROOT/results/p3/runs/steinberger-s1"
POOL_DIR="$ROOT/build/steinberger-pool-r14/D"
RULE_DIR="$CC/discharging-rules/R"
WORK="$RUN_DIR/work"
OUT="$WORK/wheels/zero_ndebug"
LOG="$RUN_DIR/log_ndebug"

[ -x "$BIN" ] || { echo "binary not found: $BIN" >&2; exit 1; }
mkdir -p "$OUT" "$LOG"

MAX_JOBS="${LP_JOBS:-8}"
ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
echo "[$(ts)] start; bin=$BIN jobs=$MAX_JOBS out=$OUT"

# The failed wheels, as "<degree> <index>" pairs, read from the S1 .FAILED markers.
JOBLIST="$LOG/joblist.txt"
: > "$JOBLIST"
for d in 7 8 9 10 11; do
    for f in "$RUN_DIR/log/d$d"/*.FAILED; do
        [ -e "$f" ] || continue
        b="$(basename "$f" .FAILED)"      # enum_d<deg>_<idx>
        echo "$d ${b##*_}" >> "$JOBLIST"
    done
done
echo "[$(ts)] $(wc -l < "$JOBLIST" | tr -d ' ') aborted wheels to re-run"

while read -r d idx; do
    marker="$LOG/d${d}_${idx}.done"
    [ -f "$marker" ] && continue
    while [ "$(jobs -p | wc -l)" -ge "$MAX_JOBS" ]; do sleep 2; done
    wheel="$WORK/wheels/d$d/d${d}_${idx}.cartwheel"
    (
        "$BIN" --enum_cartwheels -w "$wheel" -C "$POOL_DIR" -R "$RULE_DIR" \
            -S "$WORK/combined_rules/non_blocked" -o "$OUT" \
            > "$LOG/d${d}_${idx}.log" 2>&1 \
            && touch "$marker" || echo "rc=$?" > "$LOG/d${d}_${idx}.FAILED"
    ) &
done < "$JOBLIST"
wait

n_done=$(ls "$LOG"/*.done 2>/dev/null | wc -l | tr -d ' ')
n_fail=$(ls "$LOG"/*.FAILED 2>/dev/null | wc -l | tr -d ' ')
n_cw=$(find "$OUT" -name '*.cartwheel' | wc -l | tr -d ' ')
echo "[$(ts)] done: $n_done ok, $n_fail failed, $n_cw cartwheels written"
