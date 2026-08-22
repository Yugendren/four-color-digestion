#!/bin/bash
# Bootstrap the four_color_digestion compute stack on a fresh Linux server
# (e.g. the RTX 3060 box — GPU not required for the enumeration workload).
#
# Usage, from the Mac:
#   1. rsync the repo skeleton (code + pinned sources, NOT bulky results/data):
#        rsync -av --exclude '.venv' --exclude 'data/' --exclude 'results/' \
#              --exclude 'build/' --exclude 'checkpoints/' \
#              /Users/yugendren/experiments/four_color_digestion/  <host>:~/four_color_digestion/
#   2. ssh <host> 'bash ~/four_color_digestion/tools/bootstrap_server.sh'
#   3. run cells remotely, e.g.:
#        ssh <host> 'cd ~/four_color_digestion && nohup .venv/bin/python tools/fr_table.py 13 20 20 > results/theorem/fr_table/log_r13_n20.txt 2>&1 & disown'
#   4. rsync results back:
#        rsync -av <host>:~/four_color_digestion/results/theorem/fr_table/ results/theorem/fr_table/
set -euo pipefail
cd "$(dirname "$0")/.."

# Python env (needs python3.10+; prefers 3.12)
PY=$(command -v python3.12 || command -v python3)
$PY -m venv .venv
.venv/bin/pip -q install numpy networkx

# plantri build (pure C, no deps)
cd third_party/plantri
if [ ! -x plantri55/plantri ]; then
    tar xzf archive.tar.gz
    (cd plantri55 && cc -O3 -w -o plantri plantri.c)
fi
cd ../..
mkdir -p results/theorem/fr_table data build

# smoke: checker on a tiny enumeration cell (r=8 n=9, one config, ~2s)
.venv/bin/python tools/fr_table.py 8 9 9 --resume
echo "BOOTSTRAP OK: $(hostname), $($PY --version), plantri $(third_party/plantri/plantri55/plantri 2>&1 | head -c 40)"
