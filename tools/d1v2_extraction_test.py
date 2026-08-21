#!/usr/bin/env python3
"""Extraction gap test: do hand-coded ARRANGEMENT features (degree-5 subgraph
geometry, src/fourcolor/d1_features.py) close the encoder-vs-structural gap on
ring-10 boundary configs, across seeds 0-3?

Pre-registered readout:
  (a) CLOSED if shallow+structural+arrangement boundary accuracy >= the
      control-encoder probe's at >= 3/4 seeds (point estimates);
  (b) decisive if the augmented probe beats plain shallow with non-overlapping
      CIs wherever the encoder does (seeds 0 and 3).
Also checks the 4 seed-0 'encoder_right_struct_wrong' configs individually.
"""

import importlib.util
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from fourcolor import d1_interp as di  # noqa: E402
from fourcolor import d1_features as df  # noqa: E402
import d1v2_train as dt  # noqa: E402
import d1v2_interrogate as interro  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "collect_seed_replication",
    ROOT / "results" / "d1v2" / "replication" / "collect_seed_replication.py")
csr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csr)

RING = 10
DATA_DIR = ROOT / "data" / "v2"
PROBE_SEED = 0
PROBE_TEST_FRAC = 0.2
N_BOOT = 2000
OUT = ROOT / "results" / "d1v2" / "extraction"


def probe_one_seed(seed: int, device: torch.device) -> dict:
    out_dir = csr.ring_dir_for_seed(seed)
    ctrl_metrics = json.loads((out_dir / "control_metrics.json").read_text())
    hp = ctrl_metrics["hyperparameters"]

    records = dt.load_records(DATA_DIR, RING)
    for rec in records:
        rec["adjacency"] = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
    train_idx, val_idx = dt.stratified_split(records, hp["val_frac"], hp["seed"], hp["stratify"])
    val_records = [records[i] for i in val_idx]
    labels = [r["d_reducible"] for r in val_records]
    boundary_flags = [bool(r["boundary"]) for r in val_records]
    probe_train_idx, probe_test_idx = di.stratified_split(
        labels, test_frac=PROBE_TEST_FRAC, seed=PROBE_SEED)

    control_model, _ = interro.load_control_model(out_dir / "control_best.pt", device)

    X_struct = torch.tensor(
        [interro.shallow_plus_structural_vector(r) for r in val_records],
        dtype=torch.float32)
    X_arr = torch.tensor(
        [df.arrangement_feature_vector(r["adjacency"], r["r"], r["n"])
         for r in val_records], dtype=torch.float32)
    X_aug = torch.cat([X_struct, X_arr], dim=1)
    ctrl_summary = interro.control_encoder_summary(control_model, val_records, device)

    mats = {
        "shallow": torch.tensor(
            [di.shallow_feature_vector(r["adjacency"], r["r"], r["n"])
             for r in val_records], dtype=torch.float32),
        "shallow_plus_structural": X_struct,
        "struct_plus_arrangement": X_aug,
        "control_encoder_summary": ctrl_summary,
    }
    res = {name: interro.run_probe(
        name, mats[name], labels, boundary_flags,
        probe_train_idx, probe_test_idx, seed=PROBE_SEED, n_boot=N_BOOT)
        for name in mats}

    # per-config predictions for the augmented probe on seed-0 error set
    per_config = {}
    if seed == 0:
        err = json.loads((ROOT / "results" / "d1v2" / "digestion" / "error_set.json").read_text())
        target = set(err.get("encoder_right_struct_wrong", []))
        if target:
            preds = interro.probe_predictions(
                mats["struct_plus_arrangement"], labels,
                probe_train_idx, probe_test_idx, seed=PROBE_SEED) \
                if hasattr(interro, "probe_predictions") else None
            if preds is not None:
                for i in probe_test_idx:
                    ident = val_records[i]["ident"]
                    if ident in target:
                        per_config[ident] = {
                            "true": labels[i], "aug_pred": bool(preds[i])}
    return {"seed": seed, "probe_results": res, "error_set_check": per_config}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cpu")
    all_res = [probe_one_seed(s, device) for s in (0, 1, 2, 3)]

    closed_votes = 0
    lines = ["# Extraction gap test (arrangement features)\n"]
    for res in all_res:
        pr = res["probe_results"]
        enc_b = pr["control_encoder_summary"]["boundary_acc"]
        aug_b = pr["struct_plus_arrangement"]["boundary_acc"]
        closed_votes += aug_b >= enc_b
        lines.append(f"\n## seed {res['seed']}\n")
        for name, v in pr.items():
            lines.append(
                f"- {name}: overall {v['overall_acc']:.3f} "
                f"[{v['overall_ci_lo']:.3f},{v['overall_ci_hi']:.3f}]  "
                f"boundary {v['boundary_acc']:.3f} "
                f"[{v['boundary_ci_lo']:.3f},{v['boundary_ci_hi']:.3f}] "
                f"(n={v['n_test_boundary']})")
        if res["error_set_check"]:
            lines.append(f"- error-set check: {json.dumps(res['error_set_check'])}")

    verdict = "CLOSED" if closed_votes >= 3 else "NOT CLOSED"
    lines.append(f"\n## Verdict: {verdict} ({closed_votes}/4 seeds with "
                 "augmented >= encoder on boundary)\n")
    (OUT / "report.md").write_text("\n".join(lines))
    json.dump([{**r, "probe_results": {k: v for k, v in r["probe_results"].items()}}
               for r in all_res], open(OUT / "results.json", "w"), indent=1, default=str)
    print("\n".join(lines[-6:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
