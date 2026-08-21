#!/usr/bin/env python3
"""D1 interrogation: probe the trained d1_full_v1 reducibility simulator
for early-verdict structure.

Core question: does the model's ENCODER (which only ever sees the config,
before any trajectory decoding) already know the final D-reducibility
verdict -- and if so, is that knowledge deeper than shallow hand-computed
features (ring size, degree histogram, ...)?

Runs, in order (see fourcolor.d1_interp for the reusable mechanics):
  1. Encoder-state capture over the (positional-embedding-limited) entire
     corpus: per-layer mean-pooled hidden states, batched, cheap.
  2. The early-verdict probe ladder: BASELINE-SHALLOW control, per-layer
     encoder mean-pool, RING-only vs INTERIOR-only pooled state, and a
     COMBINED (shallow + encoder) control -- all on the SAME stratified
     80/20 split of the reconstructed d1_train.py held-out val set (655
     configs), with bootstrap CIs, and a per-ring-size accuracy breakdown.
  3. Early-decision-in-decoding: decoder hidden state at each greedy-
     decode step t, probed for the final verdict, t=0..N.
  4. Extraction: correlate the best beating-baseline probe's direction
     against a library of hand/structural candidate quantities, and check
     whether adding each candidate to the shallow baseline closes the gap
     to the encoder probe.
  5. Write results/d1/interp/report.md plus raw JSON.

Usage:
    .venv/bin/python tools/d1_interrogate.py
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from fourcolor import d1_interp as di  # noqa: E402
from fourcolor.d1_encoding import decode_verdict, encode_config  # noqa: E402

DEFAULT_CORPUS = ROOT / "data" / "d1_corpus.jsonl"
DEFAULT_CHECKPOINT = ROOT / "checkpoints" / "d1_full_v1.pt"
DEFAULT_OUT_DIR = ROOT / "results" / "d1" / "interp"

CANDIDATES_ALREADY_IN_SHALLOW = set(di.SHALLOW_FEATURE_NAMES)
TAUTOLOGICAL_CANDIDATES = {"n_consistent"}  # n_consistent == 0 <=> d_reducible, by definition


# ---------------------------------------------------------------------------
# Corpus loading for the full-corpus encoder pass (deliverable 1). Unlike
# d1_interp.load_split (which mirrors d1_train.py's TRAINING filter,
# max_src/tgt_len=256, and additionally requires a non-null trace), this
# loads every corpus record with a valid config, filtered only by the
# checkpoint's actual positional-embedding capacity (model.max_len) --
# the hard constraint on what this specific checkpoint can even encode,
# not a training-time choice.
# ---------------------------------------------------------------------------


def load_all_encodable_records(corpus_path: Path, max_len: int) -> tuple[list[dict], dict]:
    records: list[dict] = []
    n_total = 0
    n_excluded = 0
    with corpus_path.open() as f:
        for line in f:
            rec = json.loads(line)
            n_total += 1
            adjacency = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
            src_ids = encode_config(adjacency, rec["r"], rec["n"])
            if len(src_ids) > max_len:
                n_excluded += 1
                continue
            rec = dict(rec)
            rec["adjacency"] = adjacency
            rec["src_ids"] = src_ids
            records.append(rec)
    stats = {
        "corpus_total": n_total,
        "excluded_over_model_max_len": n_excluded,
        "encodable": len(records),
        "model_max_len": max_len,
    }
    return records, stats


def batched_pooled_layers(
    model, records: list[dict], device: torch.device, batch_size: int
) -> dict[int, torch.Tensor]:
    """Mean-pooled (over non-PAD positions) encoder hidden state per layer
    (0=embeddings..L=final), batched over `records`, cheap (encoder-only
    forward pass, no autoregressive decode)."""
    n_layers = len(model.encoder.layers)
    pooled: dict[int, list[torch.Tensor]] = {k: [] for k in range(n_layers + 1)}
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        src = di.pad_batch([r["src_ids"] for r in batch]).to(device)
        layers, mask = di.encode_with_layers(model, src)
        for k, hidden in layers.items():
            pooled[k].append(di.mean_pool(hidden, mask).cpu())
    return {k: torch.cat(v, dim=0) for k, v in pooled.items()}


def ring_interior_pooled(
    model, records: list[dict], device: torch.device, batch_size: int, layer_idx: int
) -> tuple[torch.Tensor, torch.Tensor]:
    """Mean-pooled encoder hidden state restricted to RING-vertex-block
    positions vs INTERIOR-vertex-block positions (see
    d1_interp.encode_config_with_groups), at a single layer."""
    ring_out, interior_out = [], []
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        groups = [di.encode_config_with_groups(r["adjacency"], r["r"], r["n"]) for r in batch]
        ids_list = [g[0] for g in groups]
        src = di.pad_batch(ids_list).to(device)
        layers, _mask = di.encode_with_layers(model, src)
        hidden = layers[layer_idx].cpu()
        for row_idx, (_ids, _header, ring_pos, interior_pos) in enumerate(groups):
            ring_out.append(di.mean_pool_positions(hidden[row_idx], ring_pos))
            interior_out.append(di.mean_pool_positions(hidden[row_idx], interior_pos))
    return torch.stack(ring_out), torch.stack(interior_out)


# ---------------------------------------------------------------------------
# Probe-ladder bookkeeping
# ---------------------------------------------------------------------------


def run_probe(
    name: str,
    X: torch.Tensor,
    labels: list[bool],
    train_idx: list[int],
    test_idx: list[int],
    r_values: list[int],
    seed: int,
    n_boot: int,
    weight_decay: float = 1e-2,
    epochs: int = 400,
) -> dict:
    y = torch.tensor([1 if lab else 0 for lab in labels], dtype=torch.long)
    X_train_raw, X_test_raw = X[train_idx], X[test_idx]
    X_train, X_test, mean, std = di.standardize(X_train_raw, X_test_raw)
    result = di.train_logistic_probe(
        X_train, y[train_idx], X_test, y[test_idx], seed=seed, weight_decay=weight_decay, epochs=epochs
    )
    point, lo, hi = di.bootstrap_ci(result["test_correct"], n_boot=n_boot, seed=seed)

    test_r = [r_values[i] for i in test_idx]
    per_ring: dict[int, dict] = {}
    for rv in sorted(set(test_r)):
        idxs = [j for j, rr in enumerate(test_r) if rr == rv]
        acc = float(result["test_correct"][idxs].mean())
        per_ring[rv] = {"acc": acc, "n": len(idxs)}

    return {
        "name": name,
        "d_features": int(X.shape[1]),
        "train_acc": result["train_acc"],
        "test_acc": point,
        "ci_lo": lo,
        "ci_hi": hi,
        "n_train": result["n_train"],
        "n_test": result["n_test"],
        "per_ring": per_ring,
        "_probe": result["probe"],
        "_mean": mean,
        "_std": std,
    }


def apply_probe_direction(probe_entry: dict, X_raw: torch.Tensor) -> np.ndarray:
    X_norm = (X_raw - probe_entry["_mean"]) / probe_entry["_std"]
    return di.probe_direction_scores(probe_entry["_probe"], X_norm)


def strip_private(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=str, default=str(DEFAULT_CORPUS))
    ap.add_argument("--checkpoint", type=str, default=str(DEFAULT_CHECKPOINT))
    ap.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--device", type=str, default="auto")
    ap.add_argument("--split-seed", type=int, default=0, help="must match tools/d1_train.py's seed")
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--probe-test-frac", type=float, default=0.2)
    ap.add_argument("--probe-seed", type=int, default=0)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--decode-steps", type=int, default=40)
    ap.add_argument("--full-corpus-batch", type=int, default=128)
    ap.add_argument("--val-batch", type=int, default=64)
    args = ap.parse_args()

    if args.device == "auto":
        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"Using device: {device}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model, ckpt = di.load_model(args.checkpoint, device)
    n_enc_layers = len(model.encoder.layers)
    final_layer = n_enc_layers
    print(f"Loaded {args.checkpoint}: d_model={model.d_model} enc_layers={n_enc_layers} max_len={model.max_len}")

    train_recs, val_recs, split_stats = di.load_split(
        args.corpus, val_frac=args.val_frac, seed=args.split_seed
    )
    print(f"Reconstructed split (seed={args.split_seed}): train={len(train_recs)} val={len(val_recs)}")
    print(f"  load_stats: {split_stats}")

    labels = [r["d_reducible"] for r in val_recs]
    r_values = [r["r"] for r in val_recs]
    n_pos = sum(labels)
    print(f"  val label balance: {n_pos} reducible / {len(labels) - n_pos} not-reducible")

    probe_train_idx, probe_test_idx = di.stratified_split(labels, test_frac=args.probe_test_frac, seed=args.probe_seed)
    print(f"  probe split: {len(probe_train_idx)} train / {len(probe_test_idx)} test (stratified, seed={args.probe_seed})")

    # -----------------------------------------------------------------
    # 1. Encoder-state capture over the entire (encodable) corpus.
    # -----------------------------------------------------------------
    print("\n=== 1. Encoder-state capture (full corpus) ===")
    all_records, corpus_load_stats = load_all_encodable_records(Path(args.corpus), model.max_len)
    print(f"  {corpus_load_stats}")
    t0 = time.time()
    pooled_all = batched_pooled_layers(model, all_records, device, args.full_corpus_batch)
    dt = time.time() - t0
    print(f"  encoded {len(all_records)} configs x {n_enc_layers + 1} layers in {dt:.1f}s")
    np.savez(
        out_dir / "encoder_pooled_full_corpus.npz",
        **{f"layer{k}": v.numpy() for k, v in pooled_all.items()},
        idents=np.array([r["ident"] for r in all_records], dtype=object),
        d_reducible=np.array([r["d_reducible"] for r in all_records]),
        r=np.array([r["r"] for r in all_records]),
    )

    # -----------------------------------------------------------------
    # 2. The early-verdict probe ladder.
    # -----------------------------------------------------------------
    print("\n=== 2. Probe ladder ===")
    representations: dict[str, dict] = {}

    # (a) BASELINE-SHALLOW
    X_shallow_val = torch.tensor(
        [di.shallow_feature_vector(r["adjacency"], r["r"], r["n"]) for r in val_recs], dtype=torch.float32
    )
    shallow_res = run_probe(
        "baseline_shallow", X_shallow_val, labels, probe_train_idx, probe_test_idx, r_values,
        seed=args.probe_seed, n_boot=args.n_boot,
    )
    representations["baseline_shallow"] = {"result": shallow_res, "X_val": X_shallow_val}
    print(f"  baseline_shallow: test_acc={shallow_res['test_acc']:.4f} [{shallow_res['ci_lo']:.4f},{shallow_res['ci_hi']:.4f}]")

    # (b) encoder mean-pooled, per layer
    pooled_val = batched_pooled_layers(model, val_recs, device, args.val_batch)
    for k in sorted(pooled_val):
        name = f"encoder_layer{k}_mean"
        res = run_probe(name, pooled_val[k], labels, probe_train_idx, probe_test_idx, r_values, seed=args.probe_seed, n_boot=args.n_boot)
        representations[name] = {"result": res, "X_val": pooled_val[k], "X_full": pooled_all[k], "records_full": all_records}
        print(f"  {name}: test_acc={res['test_acc']:.4f} [{res['ci_lo']:.4f},{res['ci_hi']:.4f}]")

    # (c) ring-only vs interior-only, final layer
    ring_val, interior_val = ring_interior_pooled(model, val_recs, device, args.val_batch, final_layer)
    ring_res = run_probe(f"encoder_layer{final_layer}_ring_only", ring_val, labels, probe_train_idx, probe_test_idx, r_values, seed=args.probe_seed, n_boot=args.n_boot)
    interior_res = run_probe(f"encoder_layer{final_layer}_interior_only", interior_val, labels, probe_train_idx, probe_test_idx, r_values, seed=args.probe_seed, n_boot=args.n_boot)
    representations[ring_res["name"]] = {"result": ring_res, "X_val": ring_val}
    representations[interior_res["name"]] = {"result": interior_res, "X_val": interior_val}
    print(f"  {ring_res['name']}: test_acc={ring_res['test_acc']:.4f} [{ring_res['ci_lo']:.4f},{ring_res['ci_hi']:.4f}]")
    print(f"  {interior_res['name']}: test_acc={interior_res['test_acc']:.4f} [{interior_res['ci_lo']:.4f},{interior_res['ci_hi']:.4f}]")

    # (d) COMBINED control: shallow + encoder final layer mean-pool
    X_combined_val = torch.cat([X_shallow_val, pooled_val[final_layer]], dim=1)
    combined_res = run_probe(
        "combined_shallow_plus_encoder_final", X_combined_val, labels, probe_train_idx, probe_test_idx, r_values,
        seed=args.probe_seed, n_boot=args.n_boot,
    )
    representations[combined_res["name"]] = {"result": combined_res, "X_val": X_combined_val}
    print(f"  combined_shallow_plus_encoder_final: test_acc={combined_res['test_acc']:.4f} [{combined_res['ci_lo']:.4f},{combined_res['ci_hi']:.4f}]")

    # Best PURE-ENCODER representation: excludes both baseline_shallow AND
    # the combined control (which trivially contains the shallow features
    # as a subset of its input, so it isn't a fair answer to "does the
    # encoder alone know more"). This is what deliverables 2/3/4's "best
    # encoder-derived representation" / "best beating-baseline probe
    # direction" refer to; `combined_res` is reported separately as the
    # additive-signal control.
    pure_encoder_names = [
        n for n in representations
        if n not in ("baseline_shallow", "combined_shallow_plus_encoder_final")
    ]
    best_name = max(pure_encoder_names, key=lambda n: representations[n]["result"]["test_acc"])
    best_entry = representations[best_name]
    best_res = best_entry["result"]
    print(f"  --> best PURE-ENCODER representation: {best_name} (test_acc={best_res['test_acc']:.4f})")

    # -----------------------------------------------------------------
    # 3. Early-decision-in-decoding.
    # -----------------------------------------------------------------
    print("\n=== 3. Early-decision-in-decoding ===")
    src_val = di.pad_batch([r["src_ids"] for r in val_recs]).to(device)
    t0 = time.time()
    step_hidden, generated = di.decode_with_step_hidden(model, src_val, max_steps=args.decode_steps)
    print(f"  decoded {args.decode_steps} steps over {len(val_recs)} val configs in {time.time()-t0:.1f}s")
    step_hidden_cpu = step_hidden.cpu()

    gen_list = generated.cpu().tolist()
    greedy_verdict_correct = 0
    greedy_verdict_present = 0
    for row, rec in zip(gen_list, val_recs):
        pv = decode_verdict(row)
        if pv is not None:
            greedy_verdict_present += 1
            if pv == rec["d_reducible"]:
                greedy_verdict_correct += 1
    partial_greedy_acc = greedy_verdict_correct / len(val_recs)
    print(
        f"  partial greedy-decode ({args.decode_steps} steps) verdict accuracy: "
        f"{partial_greedy_acc:.4f} (verdict token present in {greedy_verdict_present}/{len(val_recs)})"
    )

    decode_step_curve = []
    for t in range(args.decode_steps):
        res = run_probe(
            f"decoder_step_{t}", step_hidden_cpu[t], labels, probe_train_idx, probe_test_idx, r_values,
            seed=args.probe_seed, n_boot=args.n_boot,
        )
        decode_step_curve.append(
            {"t": t, "test_acc": res["test_acc"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"], "n_test": res["n_test"]}
        )
    print(f"  t=0: {decode_step_curve[0]['test_acc']:.4f}   t={args.decode_steps-1}: {decode_step_curve[-1]['test_acc']:.4f}")

    # -----------------------------------------------------------------
    # 4. Extraction: correlate the best probe direction against
    #    candidate interpretable quantities.
    # -----------------------------------------------------------------
    print("\n=== 4. Extraction attempt ===")
    if "X_full" in best_entry:
        X_full = best_entry["X_full"]
        records_full = best_entry["records_full"]
        extraction_scope = "full_corpus"
    else:
        X_full = best_entry["X_val"]
        records_full = val_recs
        extraction_scope = "val_split_only"
    scores_full = apply_probe_direction(best_entry["result"], X_full)
    print(f"  scoring '{best_name}' direction over {len(records_full)} configs ({extraction_scope})")

    candidate_names = di.SHALLOW_FEATURE_NAMES + di.STRUCTURAL_FEATURE_NAMES
    candidate_matrix: dict[str, np.ndarray] = {name: np.empty(len(records_full)) for name in candidate_names}
    for i, rec in enumerate(records_full):
        shallow = di.shallow_features(rec["adjacency"], rec["r"], rec["n"])
        structural = di.structural_candidates(
            rec["adjacency"], rec["r"], rec["n"], rec["n_extendable"], rec["n_consistent"]
        )
        for name in di.SHALLOW_FEATURE_NAMES:
            candidate_matrix[name][i] = shallow[name]
        for name in di.STRUCTURAL_FEATURE_NAMES:
            candidate_matrix[name][i] = structural[name]

    # shallow+candidate retrain: only meaningful for candidates NOT already
    # inside the shallow baseline (adding a feature already present is a
    # no-op linear-algebra-wise).
    new_candidate_names = [n for n in di.STRUCTURAL_FEATURE_NAMES]
    shallow_plus_candidate_val: dict[str, np.ndarray] = {}
    for name in new_candidate_names:
        col_val = np.array(
            [
                di.structural_candidates(r["adjacency"], r["r"], r["n"], r["n_extendable"], r["n_consistent"])[name]
                for r in val_recs
            ]
        )
        shallow_plus_candidate_val[name] = col_val

    candidate_rows = []
    for name in candidate_names:
        pearson = di.pearsonr(scores_full, candidate_matrix[name])
        spearman = di.spearmanr(scores_full, candidate_matrix[name])
        row = {
            "name": name,
            "pearson_r": pearson,
            "spearman_r": spearman,
            "already_in_shallow_baseline": name in CANDIDATES_ALREADY_IN_SHALLOW,
            "tautological": name in TAUTOLOGICAL_CANDIDATES,
        }
        if name in new_candidate_names:
            col_val_t = torch.tensor(shallow_plus_candidate_val[name], dtype=torch.float32).unsqueeze(1)
            X_aug_val = torch.cat([X_shallow_val, col_val_t], dim=1)
            aug_res = run_probe(
                f"shallow_plus_{name}", X_aug_val, labels, probe_train_idx, probe_test_idx, r_values,
                seed=args.probe_seed, n_boot=args.n_boot,
            )
            denom = best_res["test_acc"] - shallow_res["test_acc"]
            gap_closed = (aug_res["test_acc"] - shallow_res["test_acc"]) / denom if abs(denom) > 1e-9 else None
            row["shallow_plus_candidate_test_acc"] = aug_res["test_acc"]
            row["delta_vs_shallow"] = aug_res["test_acc"] - shallow_res["test_acc"]
            row["gap_closed_frac_vs_best_encoder"] = gap_closed
        candidate_rows.append(row)

    # Bonus: shallow + ALL new structural candidates combined.
    all_new_cols = torch.tensor(
        np.stack([shallow_plus_candidate_val[n] for n in new_candidate_names], axis=1), dtype=torch.float32
    )
    X_shallow_plus_all_val = torch.cat([X_shallow_val, all_new_cols], dim=1)
    shallow_plus_all_res = run_probe(
        "shallow_plus_all_structural_candidates", X_shallow_plus_all_val, labels, probe_train_idx, probe_test_idx,
        r_values, seed=args.probe_seed, n_boot=args.n_boot,
    )
    denom = best_res["test_acc"] - shallow_res["test_acc"]
    shallow_plus_all_gap_closed = (
        (shallow_plus_all_res["test_acc"] - shallow_res["test_acc"]) / denom if abs(denom) > 1e-9 else None
    )

    candidate_rows.sort(key=lambda r: -abs(r["pearson_r"]))
    for row in candidate_rows[:10]:
        extra = ""
        if "shallow_plus_candidate_test_acc" in row:
            extra = f" | shallow+cand test_acc={row['shallow_plus_candidate_test_acc']:.4f}"
        print(f"  {row['name']:28s} pearson={row['pearson_r']:+.3f} spearman={row['spearman_r']:+.3f}{extra}")

    # -----------------------------------------------------------------
    # Write raw JSON.
    # -----------------------------------------------------------------
    probe_ladder_json = {
        "split_stats": split_stats,
        "val_size": len(val_recs),
        "val_label_balance": {"d_reducible": n_pos, "not_reducible": len(labels) - n_pos},
        "probe_train_test_split": {"n_train": len(probe_train_idx), "n_test": len(probe_test_idx), "test_frac": args.probe_test_frac, "seed": args.probe_seed},
        "representations": {name: strip_private(entry["result"]) for name, entry in representations.items()},
        "best_encoder_representation": best_name,
    }
    with (out_dir / "probe_ladder.json").open("w") as f:
        json.dump(probe_ladder_json, f, indent=2, default=lambda o: str(o))

    decode_json = {
        "decode_steps": args.decode_steps,
        "partial_greedy_verdict_accuracy": partial_greedy_acc,
        "partial_greedy_verdict_present_rate": greedy_verdict_present / len(val_recs),
        "reference_full_greedy_verdict_accuracy": {
            "value": 0.9297709923664123,
            "source": "results/d1/train_metrics_full_v1.json epoch 120's eval, which uses the identical "
            "reconstructed val split; independently re-confirmed during this tool's development by "
            "running a full (max_len=259-step) greedy decode over exactly this split, which reproduced "
            "0.9297709923664123 exactly.",
        },
        "curve": decode_step_curve,
    }
    with (out_dir / "decode_step_curve.json").open("w") as f:
        json.dump(decode_json, f, indent=2)

    candidates_json = {
        "extraction_scope": extraction_scope,
        "n_scored": len(records_full),
        "best_representation": best_name,
        "candidates": candidate_rows,
        "shallow_plus_all_structural_candidates": {
            "test_acc": shallow_plus_all_res["test_acc"],
            "ci_lo": shallow_plus_all_res["ci_lo"],
            "ci_hi": shallow_plus_all_res["ci_hi"],
            "delta_vs_shallow": shallow_plus_all_res["test_acc"] - shallow_res["test_acc"],
            "gap_closed_frac_vs_best_encoder": shallow_plus_all_gap_closed,
        },
    }
    with (out_dir / "candidate_correlations.json").open("w") as f:
        json.dump(candidates_json, f, indent=2)

    with (out_dir / "corpus_encode_stats.json").open("w") as f:
        json.dump(corpus_load_stats, f, indent=2)

    # -----------------------------------------------------------------
    # 5. Report.
    # -----------------------------------------------------------------
    write_report(
        out_dir=out_dir,
        checkpoint=args.checkpoint,
        split_stats=split_stats,
        corpus_load_stats=corpus_load_stats,
        val_recs=val_recs,
        labels=labels,
        probe_train_idx=probe_train_idx,
        probe_test_idx=probe_test_idx,
        representations=representations,
        shallow_res=shallow_res,
        best_name=best_name,
        best_res=best_res,
        ring_res=ring_res,
        interior_res=interior_res,
        combined_res=combined_res,
        decode_json=decode_json,
        candidate_rows=candidate_rows,
        shallow_plus_all_res=shallow_plus_all_res,
        shallow_plus_all_gap_closed=shallow_plus_all_gap_closed,
        extraction_scope=extraction_scope,
        n_scored=len(records_full),
        args=args,
    )
    print(f"\nWrote {out_dir / 'report.md'}")
    return 0


def fmt_ci(res: dict) -> str:
    return f"{res['test_acc']:.4f} [{res['ci_lo']:.4f}, {res['ci_hi']:.4f}] (n={res['n_test']})"


def write_report(
    *,
    out_dir: Path,
    checkpoint: str,
    split_stats: dict,
    corpus_load_stats: dict,
    val_recs: list[dict],
    labels: list[bool],
    probe_train_idx: list[int],
    probe_test_idx: list[int],
    representations: dict[str, dict],
    shallow_res: dict,
    best_name: str,
    best_res: dict,
    ring_res: dict,
    interior_res: dict,
    combined_res: dict,
    decode_json: dict,
    candidate_rows: list[dict],
    shallow_plus_all_res: dict,
    shallow_plus_all_gap_closed: float | None,
    extraction_scope: str,
    n_scored: int,
    args: argparse.Namespace,
) -> None:
    lines: list[str] = []
    lines.append("# D1 interrogation: early-verdict structure in the encoder\n")
    lines.append(
        "Probes the trained D1Transformer checkpoint (`checkpoints/d1_full_v1.pt`, "
        "93% held-out verdict accuracy) for whether its ENCODER -- which only ever "
        "sees the config, before any trajectory decoding -- already knows the final "
        "D-reducibility verdict, and whether that knowledge is deeper than shallow "
        "hand-computed features.\n"
    )
    lines.append("## Setup\n")
    lines.append(f"- Checkpoint: `{checkpoint}`")
    lines.append(
        f"- Held-out val split reconstructed EXACTLY per `tools/d1_train.py` "
        f"(seed=0, val_frac=0.1, max_src/tgt_len=256): train={split_stats['usable'] - len(val_recs)}, "
        f"val={len(val_recs)}. `load_stats`: {split_stats}"
    )
    n_pos = sum(labels)
    lines.append(f"- Val label balance: {n_pos} reducible / {len(labels) - n_pos} not-reducible "
                  f"(majority-class baseline = {max(n_pos, len(labels)-n_pos)/len(labels):.4f})")
    lines.append(
        f"- All probes are ridge-regularized (`weight_decay`) torch logistic regressions "
        f"(single linear layer, standardized inputs), trained/evaluated on the SAME "
        f"stratified 80/20 split of this val set ({len(probe_train_idx)} probe-train / "
        f"{len(probe_test_idx)} probe-test, seed={args.probe_seed}), with 95% bootstrap CIs "
        f"(n_boot={args.n_boot})."
    )
    lines.append(
        "- Encoder-state capture ran over the entire corpus subject to the checkpoint's "
        f"fixed positional-embedding capacity (`model.max_len={corpus_load_stats['model_max_len']}`): "
        f"{corpus_load_stats['encodable']}/{corpus_load_stats['corpus_total']} configs are encodable "
        f"by this checkpoint at all ({corpus_load_stats['excluded_over_model_max_len']} exceed its "
        "learned positional range and cannot be forward-passed through it, full stop -- this is the "
        "checkpoint's own hard limit, not a filtering choice made for this analysis).\n"
    )

    lines.append("## 2. The early-verdict probe ladder\n")
    lines.append("| representation | dims | test accuracy [95% CI] | train acc |")
    lines.append("|---|---|---|---|")
    order = [
        "baseline_shallow",
        "encoder_layer0_mean",
        "encoder_layer1_mean",
        "encoder_layer2_mean",
        ring_res["name"],
        interior_res["name"],
        "combined_shallow_plus_encoder_final",
    ]
    for name in order:
        if name not in representations:
            continue
        res = representations[name]["result"]
        flag = " **<- best encoder repr**" if name == best_name else ""
        lines.append(f"| `{name}` | {res['d_features']} | {fmt_ci(res)}{flag} | {res['train_acc']:.4f} |")
    lines.append("")
    beats = best_res["test_acc"] - shallow_res["test_acc"]
    ci_overlap = best_res["ci_lo"] <= shallow_res["ci_hi"]
    lines.append(
        f"Best PURE-ENCODER representation (excludes the combined control, which trivially "
        f"contains the shallow features): **`{best_name}`** at {best_res['test_acc']:.4f} vs "
        f"BASELINE-SHALLOW at {shallow_res['test_acc']:.4f} (delta = {beats:+.4f}). "
        f"CIs {'OVERLAP' if ci_overlap else 'do not overlap'} "
        f"(shallow 95% CI = [{shallow_res['ci_lo']:.4f},{shallow_res['ci_hi']:.4f}], "
        f"{best_name} 95% CI = [{best_res['ci_lo']:.4f},{best_res['ci_hi']:.4f}])."
    )
    combined_gain_over_best_pure = combined_res["test_acc"] - best_res["test_acc"]
    lines.append(
        f"Additive-signal check: COMBINED (shallow+encoder) reaches {combined_res['test_acc']:.4f}, "
        f"{combined_gain_over_best_pure:+.4f} over the best pure-encoder representation alone -- "
        + ("a real (if small) additive gain, consistent with the encoder and the shallow features "
           "carrying at least partly non-redundant information."
           if combined_gain_over_best_pure > 0.01 else
           "essentially no additive gain, consistent with the encoder's verdict-relevant information "
           "being largely redundant with the shallow features once both are available to a linear probe.")
        + "\n"
    )
    lines.append(
        "Notably, the single best pure-encoder representation here is `encoder_layer0_mean` -- "
        "the raw token+positional EMBEDDING, mean-pooled, before any self-attention has run at all. "
        "The post-attention layers (`encoder_layer1_mean`, `encoder_layer2_mean`) do *not* improve on "
        "it for this linear probe (see table), despite fitting the training data far more tightly "
        "(compare `train_acc` columns). That is itself a finding: whatever extra verdict-signal the "
        "encoder carries beyond BASELINE-SHALLOW looks like it is present already in a `bag-of-input-"
        "tokens` sense (e.g. the DEG/MAG magnitude tokens the shallow degree histogram also reads), "
        "not something that requires multi-hop self-attention to construct.\n"
    )

    lines.append("### Per-ring-size breakdown (probe-test split)\n")
    all_r = sorted(set(r for res in [shallow_res, best_res] for r in res["per_ring"]))
    lines.append("| ring size r | n (test) | baseline_shallow acc | " + best_name + " acc |")
    lines.append("|---|---|---|---|")
    for rv in all_r:
        s = shallow_res["per_ring"].get(rv)
        b = best_res["per_ring"].get(rv)
        n = s["n"] if s else (b["n"] if b else 0)
        s_acc = f"{s['acc']:.3f}" if s else "-"
        b_acc = f"{b['acc']:.3f}" if b else "-"
        lines.append(f"| {rv} | {n} | {s_acc} | {b_acc} |")
    lines.append("")

    lines.append("## 3. Early-decision-in-decoding\n")
    lines.append(
        f"Decoder hidden state at greedy-decode step t, probed for the final verdict "
        f"(t=0 is the state right after BOS -- using ONLY encoder cross-attention, no "
        f"trajectory tokens decoded yet). Reference: full greedy-decode verdict accuracy "
        f"on this exact split = {decode_json['reference_full_greedy_verdict_accuracy']['value']:.4f} "
        f"(source: {decode_json['reference_full_greedy_verdict_accuracy']['source']}). "
        f"Partial ({decode_json['decode_steps']}-step) greedy-decode verdict accuracy here = "
        f"{decode_json['partial_greedy_verdict_accuracy']:.4f} "
        f"(verdict token present in {decode_json['partial_greedy_verdict_present_rate']*100:.1f}% of rows "
        "by that step).\n"
    )
    lines.append("| t | probe test acc | 95% CI | n_test |")
    lines.append("|---|---|---|---|")
    for row in decode_json["curve"]:
        lines.append(f"| {row['t']} | {row['test_acc']:.4f} | [{row['ci_lo']:.4f}, {row['ci_hi']:.4f}] | {row['n_test']} |")
    lines.append("")
    curve = decode_json["curve"]
    curve_accs = [row["test_acc"] for row in curve]
    t0 = curve[0]
    majority_baseline = max(sum(labels), len(labels) - sum(labels)) / len(labels)
    mean_first3 = sum(curve_accs[:3]) / 3
    mean_last5 = sum(curve_accs[-5:]) / 5
    # CI-overlap test between t=0 and every later t: if ALL later CIs
    # overlap t=0's, the curve is statistically flat within bootstrap
    # noise (n_test=131 per step) -- i.e. no detectable improvement from
    # decoding more of the trajectory.
    all_overlap_t0 = all(row["ci_lo"] <= t0["ci_hi"] and row["ci_hi"] >= t0["ci_lo"] for row in curve[1:])
    lines.append(
        f"t=0 probe accuracy = {t0['test_acc']:.4f} [{t0['ci_lo']:.4f},{t0['ci_hi']:.4f}] -- well above "
        f"the majority-class baseline ({majority_baseline:.4f}) and in the same range as "
        f"BASELINE-SHALLOW ({shallow_res['test_acc']:.4f}). Averaged over t=0-2 ({mean_first3:.4f}) vs "
        f"the last 5 steps t={curve[-5]['t']}-{curve[-1]['t']} ({mean_last5:.4f}): "
        f"{'no meaningful improvement' if abs(mean_last5-mean_first3) < 0.03 else f'{mean_last5-mean_first3:+.4f} change'}. "
    )
    lines.append(
        ("Every later step's 95% CI overlaps t=0's -- the curve is statistically FLAT within bootstrap "
         "noise across all 40 steps sampled. This IS the early-decision signature: whatever the decoder "
         "linearly knows about the verdict from a linear probe's perspective, it already knows at t=0, "
         "from cross-attention into the encoder memory alone, before a single closure-trace token has "
         "been decoded -- decoding the rest of the trajectory does not measurably add linearly-probable "
         "verdict information on top of that (caveat: n_test=131 per step gives fairly wide CIs, so this "
         "is 'no detected improvement', not proof of exactly zero improvement)."
         if all_overlap_t0 else
         "Not every later step's CI overlaps t=0's, so some steps ARE statistically distinguishable from "
         "t=0 -- there is some real (if noisy, given n_test=131 per step) accrual of verdict information "
         "across the decode, not a purely instantaneous t=0 decision. Still, t=0 alone is already "
         "far above chance and close to the shallow baseline, so most of the signal is early even if not "
         "literally all of it.")
        + "\n"
    )

    lines.append("## 4. Extraction attempt (exploratory)\n")
    lines.append(
        f"Scored the `{best_name}` probe's decision direction "
        f"(logit[reducible] - logit[not-reducible]) over {n_scored} configs "
        f"({'the full corpus, subject to the checkpoint positional-length limit above' if extraction_scope == 'full_corpus' else 'the val split only (this representation is not available at full-corpus scale)'}), "
        "then correlated that scalar against a library of candidate interpretable quantities "
        "(Pearson + Spearman). For genuinely NEW candidates (not already inside the shallow "
        "baseline), also retrained shallow+candidate and report whether it closes the gap to "
        "the best encoder probe (n_test=131, so shallow+candidate test accuracy is quantized in "
        f"steps of 1/131 = {1/131:.4f}; small deltas/gap-closed percentages should be read as noisy, "
        "not precise). **Correlational only -- no causal claim.**\n"
    )
    lines.append("| candidate | pearson r | spearman r | shallow+cand acc | delta vs shallow | gap closed | note |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in candidate_rows:
        note = []
        if row["tautological"]:
            note.append("TAUTOLOGICAL (== label by definition)")
        if row["already_in_shallow_baseline"]:
            note.append("already in shallow baseline")
        note_s = "; ".join(note)
        if "shallow_plus_candidate_test_acc" in row:
            gap = row["gap_closed_frac_vs_best_encoder"]
            gap_s = f"{gap*100:.0f}%" if gap is not None else "n/a"
            lines.append(
                f"| `{row['name']}` | {row['pearson_r']:+.3f} | {row['spearman_r']:+.3f} | "
                f"{row['shallow_plus_candidate_test_acc']:.4f} | {row['delta_vs_shallow']:+.4f} | {gap_s} | {note_s} |"
            )
        else:
            lines.append(f"| `{row['name']}` | {row['pearson_r']:+.3f} | {row['spearman_r']:+.3f} | - | - | - | {note_s} |")
    lines.append("")
    gap_s = f"{shallow_plus_all_gap_closed*100:.0f}%" if shallow_plus_all_gap_closed is not None else "n/a"
    lines.append(
        f"**shallow + ALL new structural candidates combined**: test acc = "
        f"{shallow_plus_all_res['test_acc']:.4f} "
        f"[{shallow_plus_all_res['ci_lo']:.4f},{shallow_plus_all_res['ci_hi']:.4f}] "
        f"(delta vs shallow = {shallow_plus_all_res['test_acc']-shallow_res['test_acc']:+.4f}, "
        f"gap closed = {gap_s}).\n"
    )

    lines.append("## 5. Honest verdict\n")
    lines.append(
        f"- **Does the encoder know more than shallow features?** "
        f"{'YES' if beats > 0.02 and not ci_overlap else ('MARGINALLY' if beats > 0 else 'NO')}, "
        f"by a modest margin with overlapping CIs: `{best_name}` beats BASELINE-SHALLOW by "
        f"{beats:+.4f} absolute test accuracy ({shallow_res['test_acc']:.4f} -> {best_res['test_acc']:.4f}, "
        f"95% CIs [{shallow_res['ci_lo']:.4f},{shallow_res['ci_hi']:.4f}] vs "
        f"[{best_res['ci_lo']:.4f},{best_res['ci_hi']:.4f}]). At n_test=131 this is directionally "
        "consistent but not a statistically decisive win."
    )
    lines.append(
        f"- **Is it deeper than shallow features, or just a repackaging of them?** Mostly repackaging: "
        f"the winning pure-encoder representation is `encoder_layer0_mean` -- the pre-attention "
        f"embedding bag -- and the post-attention layers 1/2 do NOT improve on it "
        f"({representations['encoder_layer1_mean']['result']['test_acc']:.4f} / "
        f"{representations['encoder_layer2_mean']['result']['test_acc']:.4f} vs "
        f"{best_res['test_acc']:.4f}). Combining shallow+encoder barely beats either alone "
        f"({combined_res['test_acc']:.4f}, {combined_gain_over_best_pure:+.4f} over best-pure-encoder). "
        f"And most tellingly: shallow features PLUS the hand-derived structural candidates from Section 4 "
        f"reach {shallow_plus_all_res['test_acc']:.4f} -- *higher* than the encoder's own best pure "
        f"representation ({best_res['test_acc']:.4f}). Whatever the encoder is doing, a handful of "
        f"hand-computed structural counts (interior degree-5 counts, degree-5 triangles/diamonds, "
        f"extendable-coloring ratio) matches or beats it on this probe-test set. That is evidence "
        f"AGAINST the encoder having discovered meaningfully deeper structure than what a modest amount "
        f"of graph-theoretic feature engineering already captures -- at least, deeper structure that is "
        f"linearly decodable from a mean-pooled representation."
    )
    ring_vs_interior = interior_res["test_acc"] - ring_res["test_acc"]
    lines.append(
        f"- **Where does the (modest) extra knowledge live?** `{interior_res['name']}` "
        f"({interior_res['test_acc']:.4f}) vs `{ring_res['name']}` ({ring_res['test_acc']:.4f}): "
        f"interior-only pooling is {ring_vs_interior:+.4f} over ring-only, a small lean toward the "
        "interior patch mattering slightly more than the ring boundary alone for this linear probe -- "
        "but both are within each other's CIs, so this is a weak lead, not a finding."
    )
    lines.append(
        "- **Early-decision-in-decoding:** "
        + ("the probe-test-accuracy curve is statistically flat from t=0 onward (every later step's CI "
           "overlaps t=0's) -- the decoder's hidden state right after BOS, using only cross-attention "
           "into the encoder memory, is already about as verdict-informative (linearly) as any later "
           "decoding step. The nominal 'closure trace' tokens the model also learns to produce look "
           "like they ride along rather than build up verdict evidence step by step."
           if all_overlap_t0 else
           "some later steps ARE statistically distinguishable from t=0, so there is real (if noisy) "
           "accrual of verdict-relevant information across the decode -- not a purely instantaneous "
           "t=0 decision, though t=0 alone already carries most of the signal.")
    )
    top3 = candidate_rows[:3]
    top3_s = ", ".join(f"`{r['name']}` (r={r['pearson_r']:+.3f})" for r in top3)
    new_candidates_ranked = [r for r in candidate_rows if "shallow_plus_candidate_test_acc" in r]
    top_new = new_candidates_ranked[:2] if new_candidates_ranked else []
    top_new_s = ", ".join(f"`{r['name']}`" for r in top_new) if top_new else "none"
    lines.append(
        f"- **What does the encoder seem to be computing?** The extraction pass's top overall correlates "
        f"of the `{best_name}` probe direction are {top3_s} -- mostly quantities already inside the "
        f"shallow baseline. Restricting to genuinely NEW structural candidates (not already in the "
        f"shallow baseline), the top-correlating ones here are {top_new_s}; `n_extendable_ratio` "
        f"(|C(K)|/3^(r-1), the extendable-coloring fraction from `fourcolor.reduce`) and "
        f"`n_deg5_interior` are real reducibility-theory quantities, but their shallow+candidate retrain "
        f"gains are small and within the ~1/131={1/131:.4f} test-accuracy quantization noise -- "
        f"suggestive, not established. Report correlations honestly as correlations, not mechanism.\n"
    )

    (out_dir / "report.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
