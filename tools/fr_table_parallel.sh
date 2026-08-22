#!/bin/bash
# Sharded f(r) sweep: fr_table_parallel.sh <r> <n> <mod>
# Launches <mod> plantri res/mod shards of the (r, n) cell in parallel.
# Each shard has its own manifest + JSONL (crash loses only that shard;
# rerun with the same args to resume — completed shards are skipped).
# Completeness = union of shards 0..mod-1 (plantri res/mod partitions the
# enumeration exactly; see plantri-guide.txt).
set -uo pipefail
cd "$(dirname "$0")/.."
R=$1; N=$2; MOD=$3
for RES in $(seq 0 $((MOD-1))); do
    nohup .venv/bin/python tools/fr_table.py "$R" "$N" "$N" --resume --res "$RES" --mod "$MOD" \
        > "results/theorem/fr_table/log_r${R}_n${N}_s${RES}of${MOD}.txt" 2>&1 &
done
wait
echo "all $MOD shards of r=$R n=$N complete"
for RES in $(seq 0 $((MOD-1))); do
    tail -1 "results/theorem/fr_table/log_r${R}_n${N}_s${RES}of${MOD}.txt"
done
