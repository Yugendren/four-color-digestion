#!/usr/bin/env python3
"""Exact differential: enumerate all hub-degree-d wheels, apply the (Python-reimplemented)
stage-1 discharging prune (charge_bound >= 0, then reducible-configuration blocking), and
compare the resulting "possible bad wheel" set against the C++ ground truth under
``third_party/computer-checks/wheels/d{d}/*.cartwheel``.

Usage:
    tools/nl4ct_differential.py --degree 7 [--limit N] [--checkpoint-every 5000]
                                 [--out results/nl4ct-differential/report_d7.json]

Designed to be run as a long-lived background process for d=10/d=11 (millions of
candidates): progress is checkpointed to the output JSON periodically so it can be
inspected (or the process killed and the partial result kept) without losing work.
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


def run(degree: int, limit: int | None, checkpoint_every: int, out_path: Path) -> None:
    t_start = time.time()
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
    false_positive_examples: list[dict] = []  # predicted bad, not in ground truth
    false_negative_seen_not_bad: list[dict] = []  # in ground truth but WE didn't predict bad (should be empty if correct)

    def write_checkpoint(i: int, completed: bool) -> None:
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
            "elapsed_seconds": time.time() - t_start,
        }
        if completed:
            report["exact_match"] = (false_pos == [] and false_neg == [])
            report["n_false_positive"] = len(false_pos)
            report["n_false_negative"] = len(false_neg)
            report["false_positive_examples"] = [list(s) for s in false_pos[:50]]
            report["false_negative_examples"] = [list(s) for s in false_neg[:50]]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2))

    for i, seq in enumerate(seqs[:total]):
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
                f"{len(predicted_bad)} predicted bad, elapsed {time.time() - t_start:.0f}s",
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
    args = ap.parse_args()
    out = args.out or (ROOT / "results" / "nl4ct-differential" / f"report_d{args.degree}.json")
    run(args.degree, args.limit, args.checkpoint_every, out)


if __name__ == "__main__":
    main()
