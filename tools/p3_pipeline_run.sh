#!/bin/bash
# tools/p3_pipeline_run.sh <pool-dir> <run-name>
#
# Full P3 prune-and-verify pipeline re-run against a candidate reduced pool, per
# 02-P3-DESIGN.md step 3 ("re-run pipeline with U \ B"). Regenerates EVERYTHING
# downstream of the pool from scratch (combined rules, wheels, cartwheels) --
# deliberately never reuses the master third_party/computer-checks/{combined_rules,
# wheels} artifacts, since those reflect the FULL 8,200-config pool, not U \ B. Ends
# with the three gluing checks (Lemma A.4/A.5/A.6, check_deg8/check_7triangle/
# check_deg7), asserts live (the build is CMAKE_BUILD_TYPE=Debug, no -DNDEBUG -- see
# third_party/computer-checks/build/CMakeCache.txt), and writes a PASS/FAIL verdict.
#
# <pool-dir> is a directory of *.conf files (typically symlinks into
# third_party/computer-checks/reducible-configurations/D) -- the candidate U \ B.
# <run-name> becomes the artifact directory results/p3/runs/<run-name>/.
#
# Usage (always launch detached -- this takes hours):
#   nohup tools/p3_pipeline_run.sh build/p3-pool-v1/D batch1 \
#     > results/p3/runs/batch1/driver.log 2>&1 & disown
#
# Resumable: coarse per-stage marker files (DONE_combine, DONE_enum_wheels,
# DONE_enum_cartwheels, DONE_checks) in the run directory let a killed/restarted run
# skip already-finished stages. Within enum_cartwheels (the longest stage, ~3-4h),
# per-wheel ".done" marker files (log/d<degree>/enum_d<degree>_<idx>.done) give
# finer-grained resume, mirroring third_party/computer-checks/enum_blocklog_d78.sh's
# resumability pattern.
#
# IMPORTANT correctness point (see 02-P3-DESIGN.md): wheel/cartwheel counts per degree
# are NOT hardcoded to the full-pool baseline (5439/6790/3285/626/8) -- they are
# measured after enum_wheels runs against THIS pool, since a smaller pool can change
# which wheels survive stage-1 pruning. Counts changing is expected and allowed; only
# the three gluing checks passing is a hard gate.

set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ $# -ne 2 ]; then
    echo "usage: $0 <pool-dir> <run-name>" >&2
    exit 2
fi
POOL_DIR_ARG="$1"
RUN_NAME="$2"
[ -d "$POOL_DIR_ARG" ] || { echo "pool dir not found: $POOL_DIR_ARG" >&2; exit 1; }
POOL_DIR="$(cd "$POOL_DIR_ARG" && pwd)"

CC="$ROOT/third_party/computer-checks"
BIN="$CC/build/src/main"
RULE_DIR="$CC/discharging-rules/R"
EMPTY_DIR="$CC/empty"
[ -x "$BIN" ] || { echo "binary not found/executable: $BIN" >&2; exit 1; }

RUN_DIR="$ROOT/results/p3/runs/$RUN_NAME"
WORK="$RUN_DIR/work"
LOG="$RUN_DIR/log"
mkdir -p "$WORK/combined_rules/all" "$WORK/combined_rules/non_blocked" "$WORK/wheels/zero" "$LOG"
for d in 7 8 9 10 11; do
    mkdir -p "$WORK/wheels/d$d" "$LOG/d$d"
done

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] [p3-pipeline $RUN_NAME] $1"; }

FAIL() {
    log "FAIL: $1"
    echo "FAIL: $1 (at $(ts))" > "$RUN_DIR/VERDICT.txt"
    exit 1
}

log "starting. pool=$POOL_DIR run_dir=$RUN_DIR binary=$BIN"

# --- Stage 0: record pool identity (checksum) ---
POOL_MANIFEST="$RUN_DIR/pool_manifest.sha256"
if [ ! -f "$POOL_MANIFEST" ]; then
    (cd "$POOL_DIR" && shasum -a 256 -- *.conf | sort) > "$POOL_MANIFEST"
fi
N_POOL=$(wc -l < "$POOL_MANIFEST" | tr -d ' ')
log "pool size = $N_POOL (full pool is 8200; manifest at $POOL_MANIFEST)"

# --- Stage 1: combine_rules, both passes (Lemma A.1 / A.2) ---
if [ ! -f "$RUN_DIR/DONE_combine" ]; then
    log "stage 1: combine_rules"
    "$BIN" --combine_rules -R "$RULE_DIR" -C "$EMPTY_DIR" -o "$WORK/combined_rules/all" \
        > "$LOG/combine_all.log" 2>&1
    rc_all=$?
    "$BIN" --combine_rules -R "$RULE_DIR" -C "$POOL_DIR" -o "$WORK/combined_rules/non_blocked" \
        > "$LOG/combine_non_blocked.log" 2>&1
    rc_nb=$?
    [ $rc_all -eq 0 ] || FAIL "combine_rules --confdir empty exited $rc_all (see $LOG/combine_all.log)"
    [ $rc_nb -eq 0 ] || FAIL "combine_rules --confdir pool exited $rc_nb (see $LOG/combine_non_blocked.log)"
    touch "$RUN_DIR/DONE_combine"
else
    log "stage 1 already done, skipping"
fi
N_ALL=$(ls "$WORK/combined_rules/all"/*.combined_rule 2>/dev/null | wc -l | tr -d ' ')
N_NB=$(ls "$WORK/combined_rules/non_blocked"/*.combined_rule 2>/dev/null | wc -l | tr -d ' ')
log "combined_rules: all=$N_ALL non_blocked=$N_NB (full-pool reference: 1832/671; may legitimately differ)"

# --- Stage 2: enum_wheels d7..11 (parallel, one process per degree; 5 <= ncpu always) ---
if [ ! -f "$RUN_DIR/DONE_enum_wheels" ]; then
    log "stage 2: enum_wheels d7..11"
    pids=()
    for d in 7 8 9 10 11; do
        "$BIN" --enum_wheels -d "$d" -R "$RULE_DIR" -C "$POOL_DIR" \
            -S "$WORK/combined_rules/non_blocked" -o "$WORK/wheels/d$d" \
            > "$LOG/enum_wheels_d$d.log" 2>&1 &
        pids+=($!)
    done
    fail=0
    for pid in "${pids[@]}"; do
        wait "$pid" || fail=1
    done
    [ $fail -eq 0 ] || FAIL "enum_wheels: one or more degree processes exited non-zero (see $LOG/enum_wheels_d*.log)"
    touch "$RUN_DIR/DONE_enum_wheels"
else
    log "stage 2 already done, skipping"
fi

declare -A NWHEEL
for d in 7 8 9 10 11; do
    NWHEEL[$d]=$(ls "$WORK/wheels/d$d"/*.cartwheel 2>/dev/null | wc -l | tr -d ' ')
    log "wheels d$d: ${NWHEEL[$d]} (full-pool reference: 5439/6790/3285/626/8 resp.; may legitimately differ)"
done

# --- Stage 3: enum_cartwheels, all five degrees, throttled parallel across wheel files ---
if [ ! -f "$RUN_DIR/DONE_enum_cartwheels" ]; then
    log "stage 3: enum_cartwheels"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        MAX_JOBS=$(sysctl -n hw.ncpu)
    else
        MAX_JOBS=$(nproc)
    fi
    CHECK_INTERVAL=2
    for d in 7 8 9 10 11; do
        n=${NWHEEL[$d]}
        log "  degree $d: $n wheels"
        for idx in $(seq 0 $((n - 1))); do
            marker="$LOG/d$d/enum_d${d}_${idx}.done"
            if [ -f "$marker" ]; then
                continue
            fi
            while [ "$(jobs -p | wc -l)" -ge "$MAX_JOBS" ]; do
                sleep "$CHECK_INTERVAL"
            done
            wheel="$WORK/wheels/d$d/d${d}_${idx}.cartwheel"
            (
                "$BIN" --enum_cartwheels -w "$wheel" -C "$POOL_DIR" -R "$RULE_DIR" \
                    -S "$WORK/combined_rules/non_blocked" -o "$WORK/wheels/zero" \
                    > "$LOG/d$d/enum_d${d}_${idx}.log" 2>&1
                rc=$?
                if [ $rc -eq 0 ]; then
                    touch "$marker"
                else
                    echo "FAILED rc=$rc" > "$LOG/d$d/enum_d${d}_${idx}.FAILED"
                fi
            ) &
        done
        wait
    done
    if ls "$LOG"/d*/*.FAILED > /dev/null 2>&1; then
        FAIL "enum_cartwheels: one or more per-wheel jobs failed (see $LOG/d*/*.FAILED)"
    fi
    touch "$RUN_DIR/DONE_enum_cartwheels"
else
    log "stage 3 already done, skipping"
fi

N_ZERO=$(ls "$WORK/wheels/zero"/*.cartwheel 2>/dev/null | wc -l | tr -d ' ')
log "bad cartwheels total (all degrees, merged): $N_ZERO (full-pool reference: 10094; may legitimately differ)"

# --- Stage 4: the three gluing checks (Lemma A.4/A.5/A.6) -- MUST pass, asserts live ---
if [ ! -f "$RUN_DIR/DONE_checks" ]; then
    log "stage 4: gluing checks"
    "$BIN" --check_deg8 -W "$WORK/wheels/zero" -C "$POOL_DIR" > "$LOG/check_deg8.log" 2>&1
    rc_deg8=$?
    "$BIN" --check_7triangle -W "$WORK/wheels/zero" -C "$POOL_DIR" > "$LOG/check_7triangle.log" 2>&1
    rc_7tri=$?
    "$BIN" --check_deg7 -W "$WORK/wheels/zero" -C "$POOL_DIR" > "$LOG/check_deg7.log" 2>&1
    rc_deg7=$?
    ok=1
    { [ $rc_deg8 -eq 0 ] && grep -q "Finished checking degree 8" "$LOG/check_deg8.log"; } \
        || { log "check_deg8 FAILED rc=$rc_deg8"; ok=0; }
    { [ $rc_7tri -eq 0 ] && grep -q "Finished checking 7-triangles" "$LOG/check_7triangle.log"; } \
        || { log "check_7triangle FAILED rc=$rc_7tri"; ok=0; }
    { [ $rc_deg7 -eq 0 ] && grep -q "Finished checking degree 7" "$LOG/check_deg7.log"; } \
        || { log "check_deg7 FAILED rc=$rc_deg7"; ok=0; }
    if [ $ok -ne 1 ]; then
        FAIL "one or more gluing checks failed (see $LOG/check_*.log); exit codes: deg8=$rc_deg8 7triangle=$rc_7tri deg7=$rc_deg7"
    fi
    touch "$RUN_DIR/DONE_checks"
else
    log "stage 4 already done, skipping"
fi

# --- Checksums + counts + verdict ---
CHECKSUM_FILE="$RUN_DIR/checksums.sha256"
{
    (cd "$WORK/combined_rules/non_blocked" && shasum -a 256 -- *.combined_rule 2>/dev/null | sort)
    for d in 7 8 9 10 11; do
        (cd "$WORK/wheels/d$d" && shasum -a 256 -- *.cartwheel 2>/dev/null | sort)
    done
    (cd "$WORK/wheels/zero" && shasum -a 256 -- *.cartwheel 2>/dev/null | sort)
} > "$CHECKSUM_FILE"

COUNTS_FILE="$RUN_DIR/counts.json"
python3 - "$COUNTS_FILE" "$N_POOL" "$N_ALL" "$N_NB" "$N_ZERO" \
    "${NWHEEL[7]}" "${NWHEEL[8]}" "${NWHEEL[9]}" "${NWHEEL[10]}" "${NWHEEL[11]}" <<'PYEOF'
import json
import sys

out, n_pool, n_all, n_nb, n_zero, w7, w8, w9, w10, w11 = sys.argv[1:11]
json.dump(
    {
        "n_pool": int(n_pool),
        "n_combined_all": int(n_all),
        "n_combined_non_blocked": int(n_nb),
        "n_wheels": {"d7": int(w7), "d8": int(w8), "d9": int(w9), "d10": int(w10), "d11": int(w11)},
        "n_bad_cartwheels_total": int(n_zero),
    },
    open(out, "w"),
    indent=2,
)
PYEOF

echo "PASS (at $(ts))" > "$RUN_DIR/VERDICT.txt"
log "PASS. Verdict: $RUN_DIR/VERDICT.txt  Counts: $COUNTS_FILE  Checksums: $CHECKSUM_FILE"
