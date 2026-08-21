#!/usr/bin/env python3
"""D1-v2 data layer: full per-round survivor-SET traces (not count buckets)
for small-ring configurations (r = 8, 9, 10), plus near-boundary corpus
enrichment.

Why: the v1 D1 cycle (results/d1/interp/report.md) trained on the COUNT
trace only (|C_i| per round). The interrogation found the model's encoder
mostly repackages shallow structural features rather than tracking closure
dynamics -- unsurprising, since a scalar count per round throws away exactly
the information (WHICH codes survive, and how the survivor set contracts)
that the closure process actually operates on. v2 exposes the full survivor
SET per round so a per-ring specialist model can be trained to predict/track
set membership, not just its cardinality.

Two input streams, both re-checked with fourcolor.reduce.check(record_sets=
True) so every v2 record's set_trace is self-consistent with its own
n_extendable/n_consistent/d_reducible/rounds (not copied from upstream
sources that may have used a different checker invocation):

  (a) corpus: every ring-{8,9,10} record already in data/d1_corpus.jsonl
      (rsst633 + steinberger2822 + prior plantri search hits + nl4ct pool,
      deduplicated -- see tools/d1_assemble.py). Fast (thousands of configs,
      each check() call is milliseconds at r<=10).

  (b) plantri_new: fresh plantri disk-triangulation search at n=18 -- one
      ring size beyond anything in the existing corpus (data/configs_r{8,9,
      10}_n*.jsonl top out at n=17; see results/datagen-d1b-log.txt). Full
      exhaustive n=18 search is too slow to run inline (measured: ~33s CPU
      per 1/200th "res/mod" split-shard, independent of ring size -- plantri
      balances the search tree by CPU cost, not by output count -- so a full
      unsplit run is >~1-3 hours per ring). We use plantri's built-in
      `res/mod` orbit-splitting instead of truncating mid-stream: each
      attempted residue always runs to completion (never a partially-read
      pipe), residues are visited in a fixed pseudo-random order (not a
      contiguous prefix) so a capped run still samples spread across the
      whole n=18 search space, and a wall-clock budget per (r, n) job stops
      the run cleanly between residues with a resumable checkpoint
      (data/v2/plantri_r{r}_n{n}.state.json + .jsonl, --resume picks up the
      unattempted residues next time).

Near-boundary enrichment: every record (both streams) gets a `boundary`
flag -- non-reducible configs with a small nonzero consistent set
(0 < n_consistent <= 50), or reducible configs whose closure took >= 6
rounds. These are the hard cases v1's count-bucket supervision blurred
together with everything else.

Code index maps (data/v2/code_index_r{r}.json): set_trace entries are
lists of INDICES into this per-ring sorted-canonical-code list (not raw
ternary codes), so downstream models see a small, dense, ring-local
vocabulary. Built once per ring, deterministically (sorted output of
fourcolor.reduce.canonical_codes(r)), and reused as long as they exist,
so different pipeline stages always agree on the mapping.

Usage:
    .venv/bin/python tools/d1v2_datagen.py code-index
    .venv/bin/python tools/d1v2_datagen.py corpus
    .venv/bin/python tools/d1v2_datagen.py plantri --rings 8 9 10 --resume
    .venv/bin/python tools/d1v2_datagen.py merge
    .venv/bin/python tools/d1v2_datagen.py all      # code-index + corpus + merge
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from fourcolor.canonical import canonical_key          # noqa: E402
from fourcolor.conf_parser import Configuration         # noqa: E402
from fourcolor.reduce import canonical_codes, check      # noqa: E402
import datagen as _datagen                               # noqa: E402

RINGS = (8, 9, 10)
V2_DIR = ROOT / "data" / "v2"
CORPUS_PATH = ROOT / "data" / "d1_corpus.jsonl"

BOUNDARY_CONSISTENT_MAX = 50   # non-reducible AND 0 < n_consistent <= this
BOUNDARY_ROUNDS_MIN = 6        # reducible AND rounds >= this

PLANTRI_N = 18                  # single new n level, beyond existing corpus (max n=17)
PLANTRI_MOD = 200               # res/mod split count
PLANTRI_BUDGET_SECONDS = 1700   # per (r, n) job wall-clock cap (~30 min headroom)


# ---------------------------------------------------------------------------
# Code index maps
# ---------------------------------------------------------------------------

def code_index_path(r: int) -> Path:
    return V2_DIR / f"code_index_r{r}.json"


def build_code_index(r: int) -> list[int]:
    return sorted(canonical_codes(r))


def write_code_index(r: int) -> list[int]:
    codes = build_code_index(r)
    V2_DIR.mkdir(parents=True, exist_ok=True)
    code_index_path(r).write_text(
        json.dumps({"r": r, "n_codes": len(codes), "codes": codes})
    )
    return codes


def load_or_build_code_index(r: int) -> tuple[list[int], dict[int, int]]:
    path = code_index_path(r)
    if path.exists():
        codes = json.loads(path.read_text())["codes"]
    else:
        codes = write_code_index(r)
    return codes, {c: i for i, c in enumerate(codes)}


def cmd_code_index(rings: list[int]) -> None:
    for r in rings:
        codes = write_code_index(r)
        print(f"r={r}: {len(codes)} canonical codes -> {code_index_path(r)}")


# ---------------------------------------------------------------------------
# Shared record construction
# ---------------------------------------------------------------------------

def boundary_flag(d_reducible: bool, n_consistent: int, rounds: int) -> bool:
    """Near-boundary/hard-case flag (see module docstring)."""
    if not d_reducible and 0 < n_consistent <= BOUNDARY_CONSISTENT_MAX:
        return True
    if d_reducible and rounds >= BOUNDARY_ROUNDS_MIN:
        return True
    return False


def encode_set_trace(set_trace: list[list[int]], code_to_idx: dict[int, int]) -> list[list[int]]:
    return [[code_to_idx[c] for c in round_codes] for round_codes in set_trace]


def make_v2_record(ident: str, n: int, r: int, adjacency: dict[int, list[int]],
                   res, code_to_idx: dict[int, int], source: str) -> dict:
    return {
        "ident": ident,
        "source": source,
        "n": n,
        "r": r,
        "adjacency": {str(v): nbrs for v, nbrs in adjacency.items()},
        "d_reducible": res.d_reducible,
        "n_extendable": res.n_extendable,
        "n_consistent": res.n_consistent,
        "rounds": res.rounds,
        "set_trace": encode_set_trace(res.set_trace, code_to_idx),
        "boundary": boundary_flag(res.d_reducible, res.n_consistent, res.rounds),
    }


# ---------------------------------------------------------------------------
# (a) Corpus-derived part
# ---------------------------------------------------------------------------

def corpus_checkpoint_path(r: int) -> Path:
    return V2_DIR / f"corpus_r{r}.jsonl"


def cmd_corpus(rings: list[int]) -> None:
    V2_DIR.mkdir(parents=True, exist_ok=True)
    by_ring: dict[int, list[dict]] = {r: [] for r in rings}
    with CORPUS_PATH.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec["r"] in by_ring:
                by_ring[rec["r"]].append(rec)

    for r in rings:
        codes, code_to_idx = load_or_build_code_index(r)
        recs = by_ring[r]
        out_path = corpus_checkpoint_path(r)
        n_boundary = 0
        n_mismatch = 0
        mismatches: list[str] = []
        t0 = time.time()
        with out_path.open("w") as f:
            for rec in recs:
                adjacency = {int(v): nb for v, nb in rec["adjacency"].items()}
                cfg = Configuration(rec["ident"], rec["n"], r, -1, -1, [], adjacency, [])
                res = check(cfg, record_sets=True)
                if (
                    res.n_extendable != rec.get("n_extendable")
                    or res.n_consistent != rec.get("n_consistent")
                    or res.d_reducible != rec.get("d_reducible")
                ):
                    n_mismatch += 1
                    if len(mismatches) < 10:
                        mismatches.append(rec["ident"])
                v2rec = make_v2_record(rec["ident"], rec["n"], r, adjacency, res,
                                       code_to_idx, source=f"corpus:{rec.get('source')}")
                if v2rec["boundary"]:
                    n_boundary += 1
                f.write(json.dumps(v2rec) + "\n")
        dt = time.time() - t0
        print(
            f"r={r}: corpus part {len(recs)} configs, {n_boundary} boundary, "
            f"{n_mismatch} verdict/count mismatches vs stored corpus record "
            f"(examples: {mismatches}) in {dt:.1f}s -> {out_path}"
        )


# ---------------------------------------------------------------------------
# (b) New plantri generation at n=18, res/mod split + wall-clock budget
# ---------------------------------------------------------------------------

def plantri_jsonl_path(r: int, n: int) -> Path:
    return V2_DIR / f"plantri_r{r}_n{n}.jsonl"


def plantri_state_path(r: int, n: int) -> Path:
    return V2_DIR / f"plantri_r{r}_n{n}.state.json"


def _residue_order(r: int, n: int, mod: int) -> list[int]:
    """Fixed pseudo-random visiting order over residues 0..mod-1 -- spreads
    a time-capped run across the whole search space instead of a
    contiguous, potentially-biased prefix. Deterministic given (r, n, mod)
    so repeated/resumed runs agree on the order."""
    order = list(range(mod))
    random.Random(f"{r}-{n}-{mod}").shuffle(order)
    return order


def run_plantri_job(r: int, n: int, mod: int, budget_seconds: float, resume: bool) -> None:
    V2_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = plantri_jsonl_path(r, n)
    state_path = plantri_state_path(r, n)
    codes, code_to_idx = load_or_build_code_index(r)

    done_residues: set[int] = set()
    prior_triangulations = 0
    prior_kept = 0
    if resume and state_path.exists():
        state = json.loads(state_path.read_text())
        assert state["r"] == r and state["n"] == n and state["mod"] == mod, (
            f"checkpoint mismatch for r={r} n={n} mod={mod}: {state}"
        )
        done_residues = set(state["done_residues"])
        prior_triangulations = state["triangulations_seen_total"]
        prior_kept = state["configs_kept_total"]
        print(
            f"[r={r} n={n}] resuming: {len(done_residues)}/{mod} residues already done "
            f"({prior_kept} configs kept so far)"
        )
        jf = jsonl_path.open("a")
    else:
        jsonl_path.write_text("")
        jf = jsonl_path.open("a")

    order = _residue_order(r, n, mod)
    remaining = [x for x in order if x not in done_residues]
    if not remaining:
        jf.close()
        print(f"[r={r} n={n}] already complete ({mod}/{mod} residues)")
        return

    triangulations_this_run = 0
    kept_this_run = 0
    t_start = time.time()

    for res_idx in remaining:
        if time.time() - t_start > budget_seconds:
            break
        t0 = time.time()
        proc = subprocess.run(
            [str(_datagen.PLANTRI), f"-P{r}", "-c3", "-a", str(n), f"{res_idx}/{mod}"],
            capture_output=True, text=True,
        )
        lines = [l for l in proc.stdout.splitlines() if l and l[0].isdigit()]
        triangulations_this_run += len(lines)
        kept_here = 0
        for k, line in enumerate(lines):
            adj = _datagen.parse_ascii_line(line)
            ring = _datagen.trace_outer_face(adj)
            if ring is None or len(ring) != r:
                continue
            cfg = _datagen.to_configuration(adj, ring, f"gen-r{r}-n{n}-res{res_idx}-{k}")
            if cfg is None:
                continue
            res = check(cfg, record_sets=True)
            v2rec = make_v2_record(cfg.ident, n, r, cfg.adjacency, res, code_to_idx,
                                   source="plantri_new")
            jf.write(json.dumps(v2rec) + "\n")
            jf.flush()
            kept_here += 1
        kept_this_run += kept_here
        done_residues.add(res_idx)
        dt = time.time() - t0

        state = {
            "r": r, "n": n, "mod": mod, "budget_seconds": budget_seconds,
            "done_residues": sorted(done_residues),
            "n_residues_done": len(done_residues),
            "n_residues_total": mod,
            "triangulations_seen_total": prior_triangulations + triangulations_this_run,
            "configs_kept_total": prior_kept + kept_this_run,
            "complete": len(done_residues) == mod,
            "last_updated": time.time(),
        }
        state_path.write_text(json.dumps(state, indent=2))
        print(
            f"[r={r} n={n}] residue {res_idx}/{mod} done in {dt:.1f}s: "
            f"{len(lines)} triangulations, {kept_here} kept "
            f"({len(done_residues)}/{mod} residues, elapsed {time.time() - t_start:.0f}s)",
            flush=True,
        )

    jf.close()
    complete = len(done_residues) == mod
    status = "COMPLETE" if complete else "PARTIAL (budget exhausted, resumable)"
    print(
        f"[r={r} n={n}] stopped after {len(done_residues)}/{mod} residues: {status}, "
        f"{prior_kept + kept_this_run} configs kept total -> {jsonl_path}"
    )


def cmd_plantri(rings: list[int], n: int, mod: int, budget: float, resume: bool) -> None:
    for r in rings:
        run_plantri_job(r, n, mod, budget, resume)


# ---------------------------------------------------------------------------
# Merge: corpus + all plantri_new checkpoints -> data/v2/traces_r{r}.jsonl
# ---------------------------------------------------------------------------

def traces_path(r: int) -> Path:
    return V2_DIR / f"traces_r{r}.jsonl"


def cmd_merge(rings: list[int]) -> None:
    for r in rings:
        parts: list[Path] = []
        corpus_p = corpus_checkpoint_path(r)
        if corpus_p.exists():
            parts.append(corpus_p)
        parts.extend(sorted(V2_DIR.glob(f"plantri_r{r}_n*.jsonl")))

        seen: dict[str, dict] = {}
        collisions = 0
        n_read = 0
        for p in parts:
            with p.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    n_read += 1
                    adjacency = {int(v): nb for v, nb in rec["adjacency"].items()}
                    key = canonical_key(adjacency, rec["r"], rec["n"])
                    if key in seen:
                        collisions += 1
                        continue
                    rec = dict(rec)
                    rec["canonical_key"] = key
                    seen[key] = rec

        out_path = traces_path(r)
        with out_path.open("w") as f:
            for rec in seen.values():
                f.write(json.dumps(rec) + "\n")

        n_boundary = sum(1 for rec in seen.values() if rec["boundary"])
        n_reducible = sum(1 for rec in seen.values() if rec["d_reducible"])
        print(
            f"r={r}: merged {n_read} raw records from {len(parts)} part file(s) -> "
            f"{len(seen)} unique ({collisions} dedup collisions); "
            f"{n_reducible}/{len(seen)} d_reducible, {n_boundary} boundary "
            f"-> {out_path}"
        )


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_rings(p):
        p.add_argument("--rings", type=int, nargs="+", default=list(RINGS))

    add_rings(sub.add_parser("code-index"))
    add_rings(sub.add_parser("corpus"))

    p_plantri = sub.add_parser("plantri")
    add_rings(p_plantri)
    p_plantri.add_argument("--n", type=int, default=PLANTRI_N)
    p_plantri.add_argument("--mod", type=int, default=PLANTRI_MOD)
    p_plantri.add_argument("--budget", type=float, default=PLANTRI_BUDGET_SECONDS)
    p_plantri.add_argument("--resume", action="store_true", default=True)
    p_plantri.add_argument("--no-resume", dest="resume", action="store_false")

    add_rings(sub.add_parser("merge"))
    add_rings(sub.add_parser("all"))

    args = ap.parse_args()
    rings = args.rings

    if args.cmd == "code-index":
        cmd_code_index(rings)
    elif args.cmd == "corpus":
        cmd_corpus(rings)
    elif args.cmd == "plantri":
        cmd_plantri(rings, args.n, args.mod, args.budget, args.resume)
    elif args.cmd == "merge":
        cmd_merge(rings)
    elif args.cmd == "all":
        cmd_code_index(rings)
        cmd_corpus(rings)
        cmd_merge(rings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
