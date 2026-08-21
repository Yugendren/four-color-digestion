#!/usr/bin/env python3
"""Seed replication for the ring-10 boundary result: does
control_encoder_summary (D1v2VerdictOnlyModel's frozen encoder, mean-pool
summary, probed with a linear ridge classifier) beat shallow hand-computed
features specifically on BOUNDARY configurations, ACROSS training seeds --
not just the one seed (0) results/d1v2/v2run/interrogation.json reports
(control_encoder_summary boundary_acc=0.9048 [0.7619,1.0000] vs shallow
boundary_acc=0.5238 [0.3321,0.7143], non-overlapping 95% CIs)?

This is the mechanism-contingency guard: `--seed` in tools/d1v2_train.py
drives BOTH the model's weight init/minibatch order AND (via
stratified_split) which configs land in train vs val, so a seed-0-only
result could in principle be an artifact of one lucky split+init rather
than a property of the representation. Re-running end to end (retrain +
reprobe) at seeds 1, 2, 3 is the direct test.

Only the CONTROL model is retrained (fast: ~26 epochs x ~5.5s at ring 10,
~2-3 min/seed on this machine's MPS backend) -- the dynamics model isn't
needed for this probe ladder. Each seed's own train/val split is
reconstructed from that seed's own control_metrics.json hyperparameters
(mirroring tools/d1v2_interrogate.py's load_ring_split, but keyed off
control_metrics.json instead of dynamics_metrics.json since there is no
dynamics run here) and verified against that file's own recorded split
sizes via tools.d1v2_interrogate.verify_split_against_metrics -- same
loud-on-mismatch guard as the original interrogation.

Probe ladder per seed (reusing tools/d1v2_interrogate.py's run_probe,
shallow_plus_structural_vector, control_encoder_summary verbatim): shallow,
shallow_plus_structural, control_encoder_summary. Same probe methodology as
the original interrogation (stratified 80/20 probe-train/probe-test split
of that seed's val set, probe_seed=0, n_boot=2000 bootstrap CI), varying
only the OUTER training seed (which determines the val set contents and the
control model's weights).

Seed 0 reuses the existing results/d1v2/r10v2 control_best.pt/
control_metrics.json (already trained) rather than retraining, so its
numbers are directly comparable to (and should reproduce) v2run's.

Usage:
    .venv/bin/python results/d1v2/replication/collect_seed_replication.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import torch  # noqa: E402

from fourcolor import d1_interp as di  # noqa: E402

import d1v2_interrogate as interro  # noqa: E402
import d1v2_train as dt  # noqa: E402

RING = 10
SEEDS = [0, 1, 2, 3]
DATA_DIR = ROOT / "data" / "v2"
RESULTS_DIR = ROOT / "results" / "d1v2"
OUT_DIR = RESULTS_DIR / "replication"
PROBE_SEED = 0
PROBE_TEST_FRAC = 0.2
N_BOOT = 2000
PROBE_NAMES = ["shallow", "shallow_plus_structural", "control_encoder_summary"]


def ring_dir_for_seed(seed: int) -> Path:
    # seed 0's control model already exists from the original --model both
    # run at results/d1v2/r10v2; new seeds get their own out-dir.
    return RESULTS_DIR / "r10v2" if seed == 0 else RESULTS_DIR / f"r10s{seed}"


def train_control_if_needed(seed: int, device: str) -> None:
    out_dir = ring_dir_for_seed(seed)
    ckpt = out_dir / "control_best.pt"
    metrics_path = out_dir / "control_metrics.json"
    if ckpt.exists() and metrics_path.exists():
        print(f"[seed {seed}] control model already present at {out_dir}, skipping training")
        return
    cmd = [
        sys.executable, str(ROOT / "tools" / "d1v2_train.py"),
        "--ring", str(RING), "--model", "control",
        "--seed", str(seed), "--out-dir", str(out_dir),
        "--device", device,
    ]
    print(f"[seed {seed}] training control model: {' '.join(cmd)}")
    t0 = time.time()
    log_path = OUT_DIR / f"train_seed{seed}.log"
    with log_path.open("w") as logf:
        subprocess.run(cmd, check=True, cwd=ROOT, stdout=logf, stderr=subprocess.STDOUT)
    print(f"[seed {seed}] done in {time.time()-t0:.1f}s (log: {log_path})")


def probe_one_seed(seed: int, device: torch.device) -> dict:
    out_dir = ring_dir_for_seed(seed)
    ctrl_metrics = json.loads((out_dir / "control_metrics.json").read_text())
    hp = ctrl_metrics["hyperparameters"]
    assert hp["seed"] == seed, f"control_metrics.json seed {hp['seed']} != requested {seed}"

    records = dt.load_records(DATA_DIR, RING)
    for rec in records:
        rec["adjacency"] = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
    train_idx, val_idx = dt.stratified_split(records, hp["val_frac"], hp["seed"], hp["stratify"])
    expected = {
        "train_size": ctrl_metrics["train_size"],
        "val_size": ctrl_metrics["val_size"],
        "val_boundary_size": ctrl_metrics["val_boundary_size"],
        "train_boundary_size": ctrl_metrics["train_boundary_size"],
    }
    interro.verify_split_against_metrics(records, train_idx, val_idx, expected)

    val_records = [records[i] for i in val_idx]
    labels = [r["d_reducible"] for r in val_records]
    boundary_flags = [bool(r["boundary"]) for r in val_records]

    probe_train_idx, probe_test_idx = di.stratified_split(labels, test_frac=PROBE_TEST_FRAC, seed=PROBE_SEED)

    control_model, _ckpt = interro.load_control_model(out_dir / "control_best.pt", device)

    X_shallow = torch.tensor(
        [di.shallow_feature_vector(r["adjacency"], r["r"], r["n"]) for r in val_records], dtype=torch.float32
    )
    X_struct = torch.tensor(
        [interro.shallow_plus_structural_vector(r) for r in val_records], dtype=torch.float32
    )
    ctrl_summary = interro.control_encoder_summary(control_model, val_records, device)

    feature_matrices = {
        "shallow": X_shallow,
        "shallow_plus_structural": X_struct,
        "control_encoder_summary": ctrl_summary,
    }

    probe_results = {
        name: interro.run_probe(
            name, feature_matrices[name], labels, boundary_flags,
            probe_train_idx, probe_test_idx, seed=PROBE_SEED, n_boot=N_BOOT,
        )
        for name in PROBE_NAMES
    }

    return {
        "seed": seed,
        "ring_dir": str(out_dir),
        "val_size": len(val_records),
        "val_boundary_size": sum(boundary_flags),
        "probe_split": {"n_train": len(probe_train_idx), "n_test": len(probe_test_idx), "test_frac": PROBE_TEST_FRAC},
        "probe_results": probe_results,
    }


def main() -> int:
    device_str = "mps" if torch.backends.mps.is_available() else "cpu"
    device = torch.device(device_str)
    print(f"Using device: {device}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for seed in SEEDS:
        if seed != 0:
            train_control_if_needed(seed, device_str)

    seed_results = {}
    for seed in SEEDS:
        print(f"\n=== seed {seed} ===")
        res = probe_one_seed(seed, device)
        seed_results[seed] = res
        for name in PROBE_NAMES:
            r = res["probe_results"][name]
            print(f"  {name:28s} overall={r['overall_acc']:.4f}  boundary={r['boundary_acc']}")

    out_json = OUT_DIR / "seed_replication.json"
    with out_json.open("w") as f:
        json.dump(seed_results, f, indent=2, default=lambda o: str(o))
    print(f"\nWrote {out_json}")

    # Decision rule reused verbatim from tools/d1v2_interrogate.py: does
    # control_encoder_summary's boundary CI clear shallow's (non-overlapping,
    # correct direction) at each seed?
    lines = ["seed | shallow boundary_acc [CI] (n) | control_encoder_summary boundary_acc [CI] (n) | beats shallow (non-overlapping CI)?"]
    lines.append("---|---|---|---")
    for seed in SEEDS:
        res = seed_results[seed]
        sh = res["probe_results"]["shallow"]
        ce = res["probe_results"]["control_encoder_summary"]
        beats = "n/a"
        if sh["boundary_acc"] is not None and ce["boundary_acc"] is not None:
            beats = "YES" if interro.ci_non_overlap_and_higher(
                (ce["boundary_acc"], ce["boundary_ci_lo"], ce["boundary_ci_hi"]),
                (sh["boundary_acc"], sh["boundary_ci_lo"], sh["boundary_ci_hi"]),
            ) else "no"
        lines.append(
            f"{seed} | "
            f"{interro.fmt_ci(sh['boundary_acc'], sh['boundary_ci_lo'], sh['boundary_ci_hi'], sh['n_test_boundary'])} | "
            f"{interro.fmt_ci(ce['boundary_acc'], ce['boundary_ci_lo'], ce['boundary_ci_hi'], ce['n_test_boundary'])} | "
            f"{beats}"
        )
    summary_txt = "\n".join(lines)
    print("\n" + summary_txt)
    (OUT_DIR / "seed_replication_summary.txt").write_text(summary_txt + "\n")
    print(f"Wrote {OUT_DIR / 'seed_replication_summary.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
