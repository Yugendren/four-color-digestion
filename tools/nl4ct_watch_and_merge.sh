#!/bin/bash
# Polls shard state files for a degree; once all are "completed": true, runs the merge
# step and drops a DONE marker. Meant to be launched detached (nohup ... & disown) so it
# survives independently of any single tool invocation.
set -uo pipefail
cd "$(dirname "$0")/.."

DEGREE=$1
SHARD_TOTAL=$2
RESULTS_DIR=results/nl4ct-differential
MARKER=$RESULTS_DIR/DONE_d${DEGREE}

while true; do
    all_done=1
    for i in $(seq 0 $((SHARD_TOTAL - 1))); do
        f=$RESULTS_DIR/report_d${DEGREE}_shard${i}of${SHARD_TOTAL}.state.json
        if [ ! -f "$f" ]; then
            all_done=0
            break
        fi
        completed=$(.venv/bin/python3 -c "import json; print(json.load(open('$f'))['completed'])" 2>/dev/null)
        if [ "$completed" != "True" ]; then
            all_done=0
            break
        fi
    done
    if [ "$all_done" -eq 1 ]; then
        echo "[watch d=$DEGREE] all $SHARD_TOTAL shards completed, merging..."
        .venv/bin/python3 tools/nl4ct_differential.py --degree "$DEGREE" --merge --shard-total "$SHARD_TOTAL"
        touch "$MARKER"
        echo "[watch d=$DEGREE] done, marker written to $MARKER"
        break
    fi
    sleep 60
done
