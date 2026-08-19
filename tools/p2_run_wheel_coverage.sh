#!/bin/bash
# Driver for P2 deliverable 1 (wheel-level coverage). Runs each hub degree d=7..11
# sequentially; within a degree, shards across all available cores (nl4ct_watch_and_merge
# pattern from the nl4ct-differential run, reused here for p2_wheel_coverage.py). Degrees
# run sequentially (not concurrently) because the total wall time is the same either way
# (sum of serial work / n_cores) but sequential keeps resource usage/debugging simpler.
# Meant to be launched detached: nohup tools/p2_run_wheel_coverage.sh > log_p2_wheel.txt 2>&1 &
set -uo pipefail
cd "$(dirname "$0")/.."

RESULTS_DIR=results/p2-coverage
mkdir -p "$RESULTS_DIR"

if [[ "$OSTYPE" == "darwin"* ]]; then
    N=$(sysctl -n hw.ncpu)
else
    N=$(nproc)
fi
# Leave a little headroom for the interactive session.
SHARDS=$((N > 2 ? N - 2 : 1))

for DEGREE in 7 8 9 10 11; do
    MARKER=$RESULTS_DIR/DONE_wheel_d${DEGREE}
    if [ -f "$MARKER" ]; then
        echo "[p2-wheel d=$DEGREE] already done, skipping"
        continue
    fi
    echo "[p2-wheel d=$DEGREE] starting with $SHARDS shards"
    pids=()
    for i in $(seq 0 $((SHARDS - 1))); do
        .venv/bin/python3 tools/p2_wheel_coverage.py --degree "$DEGREE" \
            --shard-index "$i" --shard-total "$SHARDS" --resume \
            --checkpoint-every 500 \
            >> "$RESULTS_DIR/log_wheel_d${DEGREE}_shard${i}.txt" 2>&1 &
        pids+=($!)
    done
    wait "${pids[@]}"
    echo "[p2-wheel d=$DEGREE] all $SHARDS shards finished, merging..."
    .venv/bin/python3 tools/p2_wheel_coverage.py --degree "$DEGREE" --merge --shard-total "$SHARDS"
    touch "$MARKER"
    echo "[p2-wheel d=$DEGREE] done, marker at $MARKER"
done
echo "[p2-wheel] ALL DEGREES DONE"
touch "$RESULTS_DIR/DONE_wheel_all"
