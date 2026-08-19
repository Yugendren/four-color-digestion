#!/usr/bin/env python3
"""P2 (deliverable 1): wheel-level blocking-attribution coverage matrix.

For each hub degree d in 7..11, enumerate every wheel candidate (same enumeration as
tools/nl4ct_differential.py: ``fourcolor.nl4ct.enum_wheel_degree_sequences``), keep the
"charge survivors" (``charge_bound(x0) >= 0``), and for each of those compute the FULL
blocking attribution (``fourcolor.nl4ct.wheel_block_attribution``): per
representative-degree concretization (always exactly 1 at this stage, see
``WheelBlockAttribution`` docstring), the set of SOURCE ``.conf`` file names whose
contain-check succeeds. This is the "coverage matrix" P3's set-cover MILP will be built
from: a wheel is blocked by a chosen subset U' of source files iff every concretization
retains >= 1 member of U' in its blocker set.

One JSONL record per charge survivor is appended to
``results/p2-coverage/wheel_survivors_d{d}.jsonl`` as it is computed (so partial
progress is never lost), plus a periodic JSON checkpoint/state sidecar
(``*.state.json``) recording how many candidates of this shard have been processed, for
``--resume``. Sharding (``--shard-index``/``--shard-total``) and ``--merge`` mirror
tools/nl4ct_differential.py exactly.

Usage:
    tools/p2_wheel_coverage.py --degree 7 --shard-index 0 --shard-total 10 --resume
    tools/p2_wheel_coverage.py --degree 7 --merge --shard-total 10
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor import nl4ct as m  # noqa: E402

RESULTS_DIR = ROOT / "results" / "p2-coverage"


def _jsonl_path(degree: int, shard_index: int | None, shard_total: int | None) -> Path:
    if shard_index is None:
        return RESULTS_DIR / f"wheel_survivors_d{degree}.jsonl"
    return RESULTS_DIR / f"wheel_survivors_d{degree}_shard{shard_index}of{shard_total}.jsonl"


def _state_path(jsonl_path: Path) -> Path:
    return jsonl_path.with_suffix(".state.json")


def run(
    degree: int,
    limit: int | None,
    checkpoint_every: int,
    resume: bool,
    shard_index: int | None,
    shard_total: int | None,
) -> None:
    t_start = time.time()
    prior_elapsed = 0.0
    rules = m.load_rules(m.default_rule_dir())
    combined = m.load_combined_rules(m.default_combined_rule_dir(blocked=False), len(rules))
    confs_named = m.load_configurations_with_source(m.default_conf_dir())

    all_seqs = list(m.enum_wheel_degree_sequences(degree))
    if shard_index is not None:
        seqs = all_seqs[shard_index::shard_total]
        shard_label = f" shard {shard_index}/{shard_total}"
    else:
        seqs = all_seqs
        shard_label = ""
    total = len(seqs) if limit is None else min(limit, len(seqs))

    jsonl_path = _jsonl_path(degree, shard_index, shard_total)
    state_path = _state_path(jsonl_path)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    n_charge_survivors = 0
    n_blocked = 0
    start_i = 0
    mode = "a"

    if resume and state_path.exists():
        state = json.loads(state_path.read_text())
        assert state["degree"] == degree
        assert state["n_candidates_total"] == len(seqs), "candidate enumeration changed since checkpoint"
        start_i = state["n_candidates_processed"]
        n_charge_survivors = state["n_charge_bound_survivors_so_far"]
        n_blocked = state["n_blocked_so_far"]
        prior_elapsed = state.get("elapsed_seconds", 0.0)
        print(f"[d={degree}{shard_label}] resuming from checkpoint at {start_i}/{total} "
              f"(prior elapsed {prior_elapsed:.0f}s)", flush=True)
    else:
        # Fresh start: truncate the JSONL (avoid duplicate records on a non-resumed rerun).
        jsonl_path.write_text("")

    jf = jsonl_path.open(mode, buffering=1)

    def write_state(i: int, completed: bool) -> None:
        elapsed = prior_elapsed + (time.time() - t_start)
        state = {
            "degree": degree,
            "shard_index": shard_index,
            "shard_total": shard_total,
            "n_candidates_total": len(seqs),
            "n_candidates_processed": i,
            "n_charge_bound_survivors_so_far": n_charge_survivors,
            "n_blocked_so_far": n_blocked,
            "completed": completed,
            "elapsed_seconds": elapsed,
        }
        state_path.write_text(json.dumps(state, indent=2))

    for i, seq in enumerate(seqs[start_i:total], start=start_i):
        w = m.generate_cartwheel(degree, seq)
        cb = m.charge_bound(w, rules, combined)
        if cb >= 0:
            n_charge_survivors += 1
            att = m.wheel_block_attribution(w, confs_named)
            if att.blocked:
                n_blocked += 1
            record = {
                "degree": degree,
                "seq": list(seq),
                "charge_bound": cb,
                "n_concretizations": att.n_concretizations,
                "blocked": att.blocked,
                "blockers_per_concretization": [sorted(s) for s in att.per_concretization],
            }
            jf.write(json.dumps(record) + "\n")
        if (i + 1) % checkpoint_every == 0:
            write_state(i + 1, completed=False)
            print(
                f"[d={degree}{shard_label}] {i + 1}/{total} candidates, "
                f"{n_charge_survivors} charge-bound survivors, {n_blocked} blocked, "
                f"elapsed {prior_elapsed + time.time() - t_start:.0f}s",
                flush=True,
            )

    completed = total == len(seqs)
    write_state(total, completed=completed)
    jf.close()
    print(f"[d={degree}{shard_label}] done. completed_full_enum={completed}. See {jsonl_path}")


def merge(degree: int, shard_total: int) -> None:
    """Concatenate shard JSONLs into the final wheel_survivors_d{d}.jsonl and write a
    summary sidecar."""
    out_path = _jsonl_path(degree, None, None)
    n_candidates_total = 0
    n_charge_survivors = 0
    n_blocked = 0
    elapsed_max = 0.0
    n_lines = 0
    with out_path.open("w") as out_f:
        for i in range(shard_total):
            shard_jsonl = _jsonl_path(degree, i, shard_total)
            state = json.loads(_state_path(shard_jsonl).read_text())
            assert state["completed"], f"shard {i}/{shard_total} not completed yet"
            n_candidates_total += state["n_candidates_total"]
            n_charge_survivors += state["n_charge_bound_survivors_so_far"]
            n_blocked += state["n_blocked_so_far"]
            elapsed_max = max(elapsed_max, state["elapsed_seconds"])
            with shard_jsonl.open() as sf:
                for line in sf:
                    line = line.rstrip("\n")
                    if not line:
                        continue
                    out_f.write(line + "\n")
                    n_lines += 1

    all_seqs_count = len(list(m.enum_wheel_degree_sequences(degree)))
    assert n_candidates_total == all_seqs_count, (
        f"shard candidate counts sum to {n_candidates_total}, expected {all_seqs_count}"
    )
    assert n_lines == n_charge_survivors, (n_lines, n_charge_survivors)

    summary = {
        "degree": degree,
        "n_candidates_total": n_candidates_total,
        "n_charge_bound_survivors": n_charge_survivors,
        "n_blocked": n_blocked,
        "n_shards": shard_total,
        "elapsed_seconds_wall_estimate": elapsed_max,
        "jsonl": str(out_path.relative_to(ROOT)),
    }
    summary_path = RESULTS_DIR / f"summary_d{degree}.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"[d={degree}] merged {shard_total} shards -> {out_path}")
    print(json.dumps(summary, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--degree", type=int, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--checkpoint-every", type=int, default=1000)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--shard-index", type=int, default=None)
    ap.add_argument("--shard-total", type=int, default=None)
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()

    if args.merge:
        assert args.shard_total, "--merge requires --shard-total"
        merge(args.degree, args.shard_total)
        return

    if (args.shard_index is None) != (args.shard_total is None):
        raise SystemExit("--shard-index and --shard-total must be given together")

    run(args.degree, args.limit, args.checkpoint_every, args.resume, args.shard_index, args.shard_total)


if __name__ == "__main__":
    main()
