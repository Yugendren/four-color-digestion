#!/usr/bin/env python3
"""Error-set digestion for the ring-10 boundary result: which specific
BOUNDARY val configs does the `control_encoder_summary` probe classify
CORRECTLY that the `shallow_plus_structural` probe gets WRONG (the
"learned encoder" named in results/d1v2/v2run/interrogation.json's
headline comparison -- control_encoder_summary boundary_acc=0.9048 vs
shallow_plus_structural boundary_acc=0.7619, same probe-test split)?

Reconstructs the EXACT seed-0 probe split tools/d1v2_interrogate.py used
to produce results/d1v2/v2run/interrogation.json (results_dir=results/
d1v2/v2run, whose r10/ symlinks to r10v2/ -- verified against that run's
recorded split sizes exactly as tools/d1v2_interrogate.py itself does),
re-trains the two probes (same seed=0, weight_decay, epochs -- torch is
deterministic given a fixed seed and these are full-batch Adam runs) to
recover PER-EXAMPLE test_correct arrays (which run_probe's return value
discards after computing summary stats), then partitions the 21 boundary
configs in the probe-test split into:
    encoder_right_struct_wrong  (the case of interest)
    both_right
    both_wrong
    struct_right_encoder_wrong  (for completeness)

For every config in encoder_right_struct_wrong, plus 2-3 both_right and
2-3 both_wrong for contrast, dumps full record data (ident, n, adjacency,
degree sequence, n_extendable, n_consistent, rounds, set_trace) into
results/d1v2/digestion/cases.md, plus a feature-mean comparison table
(the full STRUCTURAL_FEATURE_NAMES library minus n_consistent, matching
tools/d1v2_interrogate.py's STRUCTURAL_CANDIDATE_NAMES, plus trace-shape
stats: rounds, monotonicity of survivor-count decay, first-round drop
ratio) for encoder_right_struct_wrong vs the rest of boundary (both the
val-boundary population and the full corpus boundary population, for
more statistical power).

Pure evidence collection -- no interpretation of WHY these features
differ, just the numbers, per the task's explicit instruction.

Usage:
    .venv/bin/python results/d1v2/digestion/find_error_set.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import torch  # noqa: E402

from fourcolor import d1_interp as di  # noqa: E402

import d1v2_interrogate as interro  # noqa: E402
import d1v2_train as dt  # noqa: E402

RING = 10
DATA_DIR = ROOT / "data" / "v2"
RESULTS_DIR = ROOT / "results" / "d1v2" / "v2run"  # r10/ symlinks to r10v2/
OUT_DIR = ROOT / "results" / "d1v2" / "digestion"
PROBE_SEED = 0
PROBE_TEST_FRAC = 0.2

STRUCTURAL_NAMES = interro.STRUCTURAL_CANDIDATE_NAMES  # v1 structural library minus n_consistent


def probe_test_correct(X: torch.Tensor, labels: list[bool], train_idx, test_idx, seed: int = 0):
    """Exactly run_probe's internal steps, but returns the per-example
    test_correct array (aligned with test_idx's order) instead of
    discarding it after computing summary stats."""
    y = torch.tensor([1 if lab else 0 for lab in labels], dtype=torch.long)
    X_train_raw, X_test_raw = X[train_idx], X[test_idx]
    X_train, X_test, _mean, _std = di.standardize(X_train_raw, X_test_raw)
    result = di.train_logistic_probe(X_train, y[train_idx], X_test, y[test_idx], seed=seed)
    return result["test_correct"], result["test_pred"]


def degree_sequence(adjacency: dict[int, list[int]], n: int) -> list[int]:
    return [len(adjacency[v]) for v in range(1, n + 1)]


def trace_shape_stats(rec: dict) -> dict:
    counts = [len(s) for s in rec["set_trace"]]
    monotonic = all(counts[i] >= counts[i + 1] for i in range(len(counts) - 1))
    first_drop_ratio = (counts[0] - counts[1]) / counts[0] if len(counts) >= 2 and counts[0] > 0 else None
    return {
        "rounds": rec["rounds"],
        "survivor_counts": counts,
        "monotonic_nonincreasing": monotonic,
        "first_round_drop_ratio": first_drop_ratio,
        "final_survivors": counts[-1],
    }


def dump_case(rec: dict, label: str) -> list[str]:
    lines = [f"### {label}: ident={rec['ident']}\n"]
    struct = di.structural_candidates(rec["adjacency"], rec["r"], rec["n"], rec["n_extendable"], rec["n_consistent"])
    ts = trace_shape_stats(rec)
    lines.append(f"- n={rec['n']}, r={rec['r']}, d_reducible={rec['d_reducible']}, boundary={rec['boundary']}")
    lines.append(f"- source={rec['source']}, canonical_key={rec['canonical_key']}")
    lines.append(f"- n_extendable={rec['n_extendable']}, n_consistent={rec['n_consistent']}")
    lines.append(f"- degree sequence (v=1..n): {degree_sequence(rec['adjacency'], rec['n'])}")
    lines.append("- adjacency:")
    lines.append("  ```")
    for v in range(1, rec["n"] + 1):
        lines.append(f"  {v}: {rec['adjacency'][v]}")
    lines.append("  ```")
    lines.append(f"- structural candidates: {json.dumps(struct)}")
    lines.append(
        f"- trace shape: rounds={ts['rounds']}, survivor_counts={ts['survivor_counts']}, "
        f"monotonic_nonincreasing={ts['monotonic_nonincreasing']}, "
        f"first_round_drop_ratio={ts['first_round_drop_ratio']}, final_survivors={ts['final_survivors']}"
    )
    lines.append(
        "- set_trace (full raw per-round surviving-code-index lists, up to thousands of ints "
        "each round -- NOT reproduced here since it isn't human-legible as raw integers; the "
        "survivor_counts trajectory above IS the human-legible summary of it, and the full "
        f"raw list is retrievable by ident from `data/v2/traces_r10.jsonl` (ident={rec['ident']}) "
        "or `results/d1v2/digestion/error_set.json`)"
    )
    lines.append("")
    return lines


def feature_means(records: list[dict]) -> dict:
    if not records:
        return {}
    out = {}
    for name in STRUCTURAL_NAMES:
        vals = [
            di.structural_candidates(r["adjacency"], r["r"], r["n"], r["n_extendable"], r["n_consistent"])[name]
            for r in records
        ]
        out[name] = sum(vals) / len(vals)
    trace_stats = [trace_shape_stats(r) for r in records]
    out["rounds"] = sum(t["rounds"] for t in trace_stats) / len(trace_stats)
    out["monotonic_nonincreasing_frac"] = sum(t["monotonic_nonincreasing"] for t in trace_stats) / len(trace_stats)
    drop_ratios = [t["first_round_drop_ratio"] for t in trace_stats if t["first_round_drop_ratio"] is not None]
    out["first_round_drop_ratio"] = sum(drop_ratios) / len(drop_ratios) if drop_ratios else None
    out["final_survivors"] = sum(t["final_survivors"] for t in trace_stats) / len(trace_stats)
    out["n"] = len(records)
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    device = torch.device("cpu")

    split = interro.load_ring_split(RING, DATA_DIR, RESULTS_DIR)
    records, val_idx = split["records"], split["val_idx"]
    val_records = [records[i] for i in val_idx]
    labels = [r["d_reducible"] for r in val_records]
    boundary_flags = [bool(r["boundary"]) for r in val_records]

    probe_train_idx, probe_test_idx = di.stratified_split(labels, test_frac=PROBE_TEST_FRAC, seed=PROBE_SEED)

    control_model, _ = interro.load_control_model(RESULTS_DIR / "r10" / "control_best.pt", device)
    X_struct = torch.tensor(
        [interro.shallow_plus_structural_vector(r) for r in val_records], dtype=torch.float32
    )
    ctrl_summary = interro.control_encoder_summary(control_model, val_records, device)

    ctrl_correct, ctrl_pred = probe_test_correct(ctrl_summary, labels, probe_train_idx, probe_test_idx, seed=PROBE_SEED)
    struct_correct, struct_pred = probe_test_correct(X_struct, labels, probe_train_idx, probe_test_idx, seed=PROBE_SEED)

    # Sanity check against the recorded interrogation.json boundary_acc
    # (n_test_boundary should be 21, boundary_acc 0.9047619.../0.7619...).
    boundary_positions = [j for j, i in enumerate(probe_test_idx) if boundary_flags[i]]
    n_test_boundary = len(boundary_positions)
    ctrl_boundary_acc = ctrl_correct[boundary_positions].mean() if boundary_positions else None
    struct_boundary_acc = struct_correct[boundary_positions].mean() if boundary_positions else None
    print(f"n_test_boundary={n_test_boundary}  control_encoder_summary boundary_acc={ctrl_boundary_acc}  "
          f"shallow_plus_structural boundary_acc={struct_boundary_acc}")
    assert n_test_boundary == 21, f"expected 21 boundary test examples per v2run/interrogation.json, got {n_test_boundary}"

    groups = {"encoder_right_struct_wrong": [], "struct_right_encoder_wrong": [], "both_right": [], "both_wrong": []}
    for j in boundary_positions:
        val_idx_pos = probe_test_idx[j]
        rec = val_records[val_idx_pos]
        c_ok, s_ok = bool(ctrl_correct[j]), bool(struct_correct[j])
        if c_ok and not s_ok:
            groups["encoder_right_struct_wrong"].append(rec)
        elif s_ok and not c_ok:
            groups["struct_right_encoder_wrong"].append(rec)
        elif c_ok and s_ok:
            groups["both_right"].append(rec)
        else:
            groups["both_wrong"].append(rec)

    for name, recs in groups.items():
        print(f"{name}: n={len(recs)}  idents={[r['ident'] for r in recs]}")

    # ---- cases.md ----
    lines = ["# Ring-10 boundary error-set digestion: control_encoder_summary vs shallow_plus_structural\n"]
    lines.append(
        "Same seed-0 probe split as `results/d1v2/v2run/interrogation.json` "
        "(reconstructed via `tools/d1v2_interrogate.py`'s own `load_ring_split`, "
        "verified against its recorded split sizes; probe-test split stratified-by-"
        "label seed=0, test_frac=0.2). 21 of the probe-test split's 98 examples are "
        "boundary=True.\n"
    )
    lines.append(
        f"- `control_encoder_summary` probe boundary accuracy: {ctrl_boundary_acc:.4f} "
        f"({int(ctrl_correct[boundary_positions].sum())}/{n_test_boundary})\n"
        f"- `shallow_plus_structural` probe boundary accuracy: {struct_boundary_acc:.4f} "
        f"({int(struct_correct[boundary_positions].sum())}/{n_test_boundary})\n"
    )
    lines.append("## Confusion breakdown (boundary probe-test examples, n=21)\n")
    lines.append("| group | n | idents |")
    lines.append("|---|---|---|")
    for name, recs in groups.items():
        lines.append(f"| `{name}` | {len(recs)} | {', '.join(str(r['ident']) for r in recs)} |")
    lines.append("")

    lines.append(
        "## encoder_right_struct_wrong: full case dumps\n\n"
        "The configs `control_encoder_summary`'s probe gets right and "
        "`shallow_plus_structural`'s probe gets wrong -- the target set.\n"
    )
    for rec in groups["encoder_right_struct_wrong"]:
        lines.extend(dump_case(rec, "encoder_right_struct_wrong"))

    lines.append(f"## Contrast: both_right (showing up to 3 of {len(groups['both_right'])})\n")
    for rec in groups["both_right"][:3]:
        lines.extend(dump_case(rec, "both_right"))

    lines.append(f"## Contrast: both_wrong (showing up to 3 of {len(groups['both_wrong'])})\n")
    for rec in groups["both_wrong"][:3]:
        lines.extend(dump_case(rec, "both_wrong"))

    if groups["struct_right_encoder_wrong"]:
        lines.append(f"## For completeness: struct_right_encoder_wrong (n={len(groups['struct_right_encoder_wrong'])})\n")
        for rec in groups["struct_right_encoder_wrong"]:
            lines.extend(dump_case(rec, "struct_right_encoder_wrong"))

    # ---- feature comparison table ----
    error_set = groups["encoder_right_struct_wrong"]
    error_idents = {r["ident"] for r in error_set}
    val_boundary_records = [r for r in val_records if r["boundary"]]
    rest_val_boundary = [r for r in val_boundary_records if r["ident"] not in error_idents]
    full_boundary_records = [r for r in records if r["boundary"] and r["ident"] not in error_idents]

    means_error = feature_means(error_set)
    means_rest_val_boundary = feature_means(rest_val_boundary)
    means_rest_full_boundary = feature_means(full_boundary_records)

    lines.append("## Feature means: encoder_right_struct_wrong vs rest of boundary\n")
    lines.append(
        f"encoder_right_struct_wrong: n={means_error.get('n', 0)}. "
        f"Rest of VAL boundary (val boundary set minus this group): n={means_rest_val_boundary.get('n', 0)}. "
        f"Rest of FULL CORPUS boundary (all 776 boundary configs minus this group): "
        f"n={means_rest_full_boundary.get('n', 0)}.\n"
    )
    feature_order = STRUCTURAL_NAMES + [
        "rounds", "monotonic_nonincreasing_frac", "first_round_drop_ratio", "final_survivors",
    ]
    lines.append("| feature | encoder_right_struct_wrong mean | rest-of-val-boundary mean | rest-of-full-corpus-boundary mean |")
    lines.append("|---|---|---|---|")
    for feat in feature_order:
        a = means_error.get(feat)
        b = means_rest_val_boundary.get(feat)
        c = means_rest_full_boundary.get(feat)

        def fmt(v):
            if v is None:
                return "n/a"
            return f"{v:.4f}"

        lines.append(f"| `{feat}` | {fmt(a)} | {fmt(b)} | {fmt(c)} |")
    lines.append("")

    lines.append(
        "## Full raw records (including complete per-round `set_trace` code-index lists)\n\n"
        "The exact configs dumped in summary form above, with EVERY field (including the full "
        "raw `set_trace`, omitted above for readability), are in "
        "`results/d1v2/digestion/error_set_full.json`, keyed by `ident`.\n"
    )

    (OUT_DIR / "cases.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {OUT_DIR / 'cases.md'}")

    # ---- raw json for reproducibility ----
    raw = {
        "n_test_boundary": n_test_boundary,
        "control_encoder_summary_boundary_acc": float(ctrl_boundary_acc),
        "shallow_plus_structural_boundary_acc": float(struct_boundary_acc),
        "groups": {name: [r["ident"] for r in recs] for name, recs in groups.items()},
        "feature_means": {
            "encoder_right_struct_wrong": means_error,
            "rest_of_val_boundary": means_rest_val_boundary,
            "rest_of_full_corpus_boundary": means_rest_full_boundary,
        },
    }
    with (OUT_DIR / "error_set.json").open("w") as f:
        json.dump(raw, f, indent=2, default=str)
    print(f"Wrote {OUT_DIR / 'error_set.json'}")

    dumped_records = (
        groups["encoder_right_struct_wrong"]
        + groups["both_right"][:3]
        + groups["both_wrong"][:3]
        + groups["struct_right_encoder_wrong"]
    )
    full_dump = {rec["ident"]: rec for rec in dumped_records}
    with (OUT_DIR / "error_set_full.json").open("w") as f:
        json.dump(full_dump, f, indent=2, default=str)
    print(f"Wrote {OUT_DIR / 'error_set_full.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
