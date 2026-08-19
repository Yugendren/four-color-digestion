#!/usr/bin/env python3
"""Exact differential: enumerate all hub-degree-d wheels, apply the (Python-reimplemented)
stage-1 discharging prune (charge_bound >= 0, then reducible-configuration blocking), and
compare the resulting "possible bad wheel" set against the C++ ground truth under
``third_party/computer-checks/wheels/d{d}/*.cartwheel``.

Usage:
    tools/nl4ct_differential.py --degree 7 [--limit N] [--checkpoint-every 5000]
                                 [--out results/nl4ct-differential/report_d7.json] [--resume]

Designed to be run as a long-lived process for d=10/d=11 (hundreds of thousands to
millions of candidates): progress is checkpointed periodically to both a human-readable
report JSON and a sidecar ``*.state.json`` (which additionally carries the full
predicted-bad list so a run can be resumed with ``--resume`` after being interrupted,
e.g. by a host/session time limit) without losing work.
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


def _state_path(out_path: Path) -> Path:
    return out_path.with_suffix("").with_suffix(".state.json")


def run(degree: int, limit: int | None, checkpoint_every: int, out_path: Path, resume: bool) -> None:
    t_start = time.time()
    prior_elapsed = 0.0
    rules = m.load_rules(m.default_rule_dir())
    combined = m.load_combined_rules(m.default_combined_rule_dir(blocked=False), len(rules))
    confs = m.load_configurations(m.default_conf_dir())

    truth_wheels = m.load_cartwheels(m.default_wheel_dir(degree))
    truth_set = {m.spoke_degree_sequence(w) for w in truth_wheels}
    assert len(truth_set) == len(truth_wheels), "ground-truth wheel files are not distinct necklaces"

    seqs = list(m.enum_wheel_degree_sequences(degree))
    total = len(seqs) if limit is None else min(limit, len(seqs))

    n_charge_survivors = 0
    n_blocked = 0
    predicted_bad: list[tuple[int, ...]] = []
    start_i = 0

    state_path = _state_path(out_path)
    if resume and state_path.exists():
        state = json.loads(state_path.read_text())
        assert state["degree"] == degree
        assert state["n_candidates_total"] == len(seqs), "candidate enumeration changed since checkpoint"
        start_i = state["n_candidates_processed"]
        n_charge_survivors = state["n_charge_bound_survivors_so_far"]
        n_blocked = state["n_blocked_so_far"]
        predicted_bad = [tuple(s) for s in state["predicted_bad"]]
        prior_elapsed = state.get("elapsed_seconds", 0.0)
        print(f"[d={degree}] resuming from checkpoint at {start_i}/{total} "
              f"(prior elapsed {prior_elapsed:.0f}s)", flush=True)

    def write_checkpoint(i: int, completed: bool) -> None:
        elapsed = prior_elapsed + (time.time() - t_start)
        predicted_set = set(predicted_bad)
        false_pos = sorted(predicted_set - truth_set)
        false_neg = sorted(truth_set - predicted_set) if completed else []
        report = {
            "degree": degree,
            "n_base_rules": len(rules),
            "n_combined_rules_non_blocked": len(combined),
            "n_confs_expanded": len(confs),
            "n_candidates_total": len(seqs),
            "n_candidates_processed": i,
            "n_charge_bound_survivors_so_far": n_charge_survivors,
            "n_blocked_so_far": n_blocked,
            "n_predicted_bad_so_far": len(predicted_bad),
            "n_ground_truth_bad": len(truth_set),
            "completed": completed,
            "elapsed_seconds": elapsed,
        }
        if completed:
            report["exact_match"] = (false_pos == [] and false_neg == [])
            report["n_false_positive"] = len(false_pos)
            report["n_false_negative"] = len(false_neg)
            report["false_positive_examples"] = [list(s) for s in false_pos[:50]]
            report["false_negative_examples"] = [list(s) for s in false_neg[:50]]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2))
        # Sidecar resumable state (not meant to be human-facing; carries the full list).
        state = dict(report)
        state["predicted_bad"] = [list(s) for s in predicted_bad]
        state_path.write_text(json.dumps(state))

    for i, seq in enumerate(seqs[start_i:total], start=start_i):
        w = m.generate_cartwheel(degree, seq)
        cb = m.charge_bound(w, rules, combined)
        if cb >= 0:
            n_charge_survivors += 1
            if m.wheel_is_blocked(w, confs):
                n_blocked += 1
            else:
                predicted_bad.append(seq)
        if (i + 1) % checkpoint_every == 0:
            write_checkpoint(i + 1, completed=False)
            print(
                f"[d={degree}] {i + 1}/{total} candidates, "
                f"{n_charge_survivors} charge-bound survivors, {n_blocked} blocked, "
                f"{len(predicted_bad)} predicted bad, elapsed {prior_elapsed + time.time() - t_start:.0f}s",
                flush=True,
            )

    completed = total == len(seqs)
    write_checkpoint(total, completed=completed)
    print(f"[d={degree}] done. completed_full_enum={completed}. See {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--degree", type=int, required=True)
    ap.add_argument("--limit", type=int, default=None, help="only process the first N candidates (for smoke testing)")
    ap.add_argument("--checkpoint-every", type=int, default=5000)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--resume", action="store_true", help="resume from the sidecar *.state.json if present")
    args = ap.parse_args()
    out = args.out or (ROOT / "results" / "nl4ct-differential" / f"report_d{args.degree}.json")
    run(args.degree, args.limit, args.checkpoint_every, out, args.resume)


if __name__ == "__main__":
    main()
