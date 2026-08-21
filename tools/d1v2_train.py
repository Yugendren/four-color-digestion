#!/usr/bin/env python3
"""Train the D1-v2 ring specialist: encoder + iterated-map dynamics head
(D1v2DynamicsModel) predicting the full per-round survivor-code bitmap and
final verdict, teacher-forced on data/v2/traces_r{ring}.jsonl. Also trains
the CONTROL (D1v2VerdictOnlyModel: same encoder, verdict head only, no
dynamics supervision) on the same split/budget, so the two models'
held-out metrics isolate what dynamics supervision buys over a plain
classifier. Generic over ring size via --ring (paths derive from it: data/
v2/traces_r{ring}.jsonl, data/v2/code_index_r{ring}.json) -- same script
serves r=8 now and r=9/10 later once their corpora are ready.

No scheduled sampling: training uses plain teacher forcing throughout
(the TRUE previous-round bitmap is always fed to the dynamics head during
training; see D1v2DynamicsModel.forward's mode="teacher_force"). At this
corpus size (~1-2k configs, <=9 rounds) scheduled sampling adds a second
hyperparameter (a decay schedule) to tune blind; plain teacher forcing is
the simpler default and free-running fidelity is instead measured
end-to-end at EVAL time every epoch (see `evaluate_dynamics`), which is
the metric that actually matters for the deployment use case (rollout
without access to ground truth).

Train/val split is STRATIFIED by the `boundary` flag (near-boundary hard
cases -- see tools/d1v2_datagen.py module docstring), not plain random:
boundary configs are a small minority of the corpus (16/1162 at r=8), and
free-running verdict accuracy on boundary=true configs is the headline
metric this whole task is about, so a plain random split risks stranding
too few (or zero) boundary examples in the val set to measure it
meaningfully. `--no-stratify` reverts to a plain random split.

Usage:
    .venv/bin/python tools/d1v2_train.py --ring 8 --model both \
        --out-dir results/d1v2/r8
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import torch  # noqa: E402
from torch import nn  # noqa: E402
from torch.nn.utils.rnn import pad_sequence  # noqa: E402

from fourcolor.d1_encoding import PAD_ID, encode_config  # noqa: E402
from fourcolor.d1v2_model import (  # noqa: E402
    D1v2DynamicsModel,
    D1v2VerdictOnlyModel,
    count_parameters,
)

DEFAULT_DATA_DIR = ROOT / "data" / "v2"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def traces_path(data_dir: Path, ring: int) -> Path:
    return data_dir / f"traces_r{ring}.jsonl"


def code_index_path(data_dir: Path, ring: int) -> Path:
    return data_dir / f"code_index_r{ring}.json"


def load_code_index(data_dir: Path, ring: int) -> int:
    """Returns n_codes for this ring."""
    d = json.loads(code_index_path(data_dir, ring).read_text())
    assert d["r"] == ring
    return d["n_codes"]


def load_records(data_dir: Path, ring: int) -> list[dict]:
    """Loads traces_r{ring}.jsonl into a list of dicts with pre-encoded
    `src_ids` (token id list) added; `adjacency` keys coerced to int."""
    records = []
    path = traces_path(data_dir, ring)
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            adjacency = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
            rec["src_ids"] = encode_config(adjacency, rec["r"], rec["n"])
            records.append(rec)
    return records


def stratified_split(
    records: list[dict], val_frac: float, seed: int, stratify: bool
) -> tuple[list[int], list[int]]:
    """Returns (train_idx, val_idx). If `stratify`, boundary=true and
    boundary=false configs are shuffled and split separately so both
    strata are proportionally represented in val (see module docstring
    for why this matters at this corpus's boundary-set size)."""
    rng = random.Random(seed)
    n = len(records)
    if not stratify:
        idx = list(range(n))
        rng.shuffle(idx)
        n_val = max(1, int(round(n * val_frac)))
        return idx[n_val:], idx[:n_val]

    boundary_idx = [i for i, r in enumerate(records) if r["boundary"]]
    other_idx = [i for i, r in enumerate(records) if not r["boundary"]]
    rng.shuffle(boundary_idx)
    rng.shuffle(other_idx)

    n_val_b = max(1, int(round(len(boundary_idx) * val_frac))) if boundary_idx else 0
    n_val_o = max(1, int(round(len(other_idx) * val_frac))) if other_idx else 0

    val_idx = boundary_idx[:n_val_b] + other_idx[:n_val_o]
    train_idx = boundary_idx[n_val_b:] + other_idx[n_val_o:]
    rng.shuffle(val_idx)
    rng.shuffle(train_idx)
    return train_idx, val_idx


def pad_src_batch(src_id_lists: list[list[int]]) -> torch.Tensor:
    tensors = [torch.tensor(ids, dtype=torch.long) for ids in src_id_lists]
    return pad_sequence(tensors, batch_first=True, padding_value=PAD_ID)


def build_batch_bitmaps(
    records_subset: list[dict], n_codes: int
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Builds the per-round survivor bitmap batch for a list of records.

    Returns:
        true_bitmaps: (B, T, n_codes) float, T = max(rounds)+1 over this
            subset. Rounds beyond an example's own `rounds` are zero-filled
            (never used for anything but the padded slot of a GRU step --
            excluded from loss and metrics via `round_mask`, and never
            read for verdict since that's gathered at each example's own
            `round_idx`).
        round_mask: (B, T) bool, True at valid (t <= rounds_i) round slots.
        round_idx: (B,) int64, each example's own final round index
            (== its `rounds` field) -- set_trace has `rounds+1` entries,
            0-indexed, so this is directly the last valid index.
        verdict: (B,) float 0/1, d_reducible label.
    """
    B = len(records_subset)
    T = max(r["rounds"] for r in records_subset) + 1
    true_bitmaps = torch.zeros(B, T, n_codes, dtype=torch.float32)
    round_mask = torch.zeros(B, T, dtype=torch.bool)
    round_idx = torch.zeros(B, dtype=torch.long)
    verdict = torch.zeros(B, dtype=torch.float32)
    for i, rec in enumerate(records_subset):
        rounds = rec["rounds"]
        set_trace = rec["set_trace"]
        assert len(set_trace) == rounds + 1
        for t, codes in enumerate(set_trace):
            if codes:
                true_bitmaps[i, t, codes] = 1.0
        round_mask[i, : rounds + 1] = True
        round_idx[i] = rounds
        verdict[i] = 1.0 if rec["d_reducible"] else 0.0
    return true_bitmaps, round_mask, round_idx, verdict


# ---------------------------------------------------------------------------
# Loss / metrics (pure functions, unit-testable without a model)
# ---------------------------------------------------------------------------


def masked_state_bce(
    logits: torch.Tensor, true_bitmaps: torch.Tensor, round_mask: torch.Tensor
) -> torch.Tensor:
    """logits/true_bitmaps: (B,T,n_codes); round_mask: (B,T). Per-round
    BCE averaged over codes first (so rounds don't get weighted by
    n_codes, which is constant, but this keeps the reduction order
    explicit/interrogatable), then masked-averaged over (B,T)."""
    per_round = nn.functional.binary_cross_entropy_with_logits(
        logits, true_bitmaps, reduction="none"
    ).mean(dim=-1)  # (B,T)
    mask = round_mask.to(per_round.dtype)
    denom = mask.sum().clamp(min=1.0)
    return (per_round * mask).sum() / denom


def micro_confusion(
    pred_bool: torch.Tensor, true_bool: torch.Tensor, mask: torch.Tensor
) -> tuple[int, int, int]:
    """pred_bool/true_bool: (..., n_codes) bool; mask: (...) bool
    broadcastable to the leading dims. Returns (tp, fp, fn) micro-summed
    over every unmasked (example, round, code) triple."""
    mask3 = mask.unsqueeze(-1)
    tp = int((pred_bool & true_bool & mask3).sum().item())
    fp = int((pred_bool & ~true_bool & mask3).sum().item())
    fn = int((~pred_bool & true_bool & mask3).sum().item())
    return tp, fp, fn


def f1_from_confusion(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def per_round_f1(
    logits: torch.Tensor, true_bitmaps: torch.Tensor, round_mask: torch.Tensor, threshold: float = 0.5
) -> list[dict]:
    """Returns a list (len T) of {"round": t, "support": n_examples, **f1_from_confusion}
    for each round slot present in this batch."""
    pred_bool = torch.sigmoid(logits) >= threshold
    true_bool = true_bitmaps >= 0.5
    out = []
    T = logits.size(1)
    for t in range(T):
        support = int(round_mask[:, t].sum().item())
        tp, fp, fn = micro_confusion(pred_bool[:, t, :], true_bool[:, t, :], round_mask[:, t])
        out.append({"round": t, "support": support, **f1_from_confusion(tp, fp, fn)})
    return out


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------


@torch.no_grad()
def evaluate_dynamics(
    model: D1v2DynamicsModel,
    val_records: list[dict],
    n_codes: int,
    device: torch.device,
    threshold: float = 0.5,
) -> dict:
    model.eval()
    src = pad_src_batch([r["src_ids"] for r in val_records]).to(device)
    true_bitmaps, round_mask, round_idx, verdict = build_batch_bitmaps(val_records, n_codes)
    true_bitmaps, round_mask = true_bitmaps.to(device), round_mask.to(device)
    round_idx, verdict = round_idx.to(device), verdict.to(device)
    boundary_mask = torch.tensor([bool(r["boundary"]) for r in val_records], device=device)
    n_rounds = true_bitmaps.size(1) - 1

    # Teacher-forced pass: state-bitmap F1 per round + teacher-forced verdict.
    tf_logits, tf_hidden = model(src, true_bitmaps=true_bitmaps, mode="teacher_force")
    tf_state_loss = masked_state_bce(tf_logits, true_bitmaps, round_mask).item()
    tf_round_f1 = per_round_f1(tf_logits, true_bitmaps, round_mask, threshold)
    tf_verdict_logits = model.verdict_logits(tf_hidden, round_idx)
    tf_verdict_pred = (torch.sigmoid(tf_verdict_logits) >= 0.5)
    tf_verdict_correct = (tf_verdict_pred == (verdict >= 0.5))
    verdict_accuracy_teacher_forced = tf_verdict_correct.float().mean().item()

    # Free-running pass: feed the model's own thresholded predictions
    # forward instead of ground truth; same round count as this val batch's
    # teacher-forced pass so the two are directly comparable round-by-round.
    fr_logits, fr_hidden = model(src, n_rounds=n_rounds, mode="free_run", threshold=threshold)
    fr_round_f1 = per_round_f1(fr_logits, true_bitmaps, round_mask, threshold)
    fr_verdict_logits = model.verdict_logits(fr_hidden, round_idx)
    fr_verdict_pred = (torch.sigmoid(fr_verdict_logits) >= 0.5)
    fr_verdict_correct = (fr_verdict_pred == (verdict >= 0.5))
    verdict_accuracy_free_running = fr_verdict_correct.float().mean().item()

    n_boundary = int(boundary_mask.sum().item())
    if n_boundary > 0:
        verdict_accuracy_free_running_boundary = (
            fr_verdict_correct[boundary_mask].float().mean().item()
        )
    else:
        verdict_accuracy_free_running_boundary = None

    return {
        "n_val": len(val_records),
        "n_val_boundary": n_boundary,
        "round0_f1": tf_round_f1[0]["f1"],
        "teacher_forced_state_loss": tf_state_loss,
        "teacher_forced_per_round_f1": tf_round_f1,
        "free_running_per_round_f1": fr_round_f1,
        "verdict_accuracy_teacher_forced": verdict_accuracy_teacher_forced,
        "verdict_accuracy_free_running": verdict_accuracy_free_running,
        "verdict_accuracy_free_running_boundary": verdict_accuracy_free_running_boundary,
    }


@torch.no_grad()
def evaluate_control(
    model: D1v2VerdictOnlyModel, val_records: list[dict], device: torch.device
) -> dict:
    model.eval()
    src = pad_src_batch([r["src_ids"] for r in val_records]).to(device)
    verdict = torch.tensor([1.0 if r["d_reducible"] else 0.0 for r in val_records], device=device)
    boundary_mask = torch.tensor([bool(r["boundary"]) for r in val_records], device=device)

    logits = model(src)
    pred = torch.sigmoid(logits) >= 0.5
    correct = pred == (verdict >= 0.5)
    verdict_accuracy = correct.float().mean().item()

    n_boundary = int(boundary_mask.sum().item())
    verdict_accuracy_boundary = (
        correct[boundary_mask].float().mean().item() if n_boundary > 0 else None
    )
    return {
        "n_val": len(val_records),
        "n_val_boundary": n_boundary,
        "verdict_accuracy": verdict_accuracy,
        "verdict_accuracy_boundary": verdict_accuracy_boundary,
    }


# ---------------------------------------------------------------------------
# Train loops
# ---------------------------------------------------------------------------


def make_device(name: str) -> torch.device:
    if name == "auto":
        return torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    return torch.device(name)


def train_dynamics(args, records, train_idx, val_idx, n_codes, max_len, device) -> dict:
    train_records = [records[i] for i in train_idx]
    val_records = [records[i] for i in val_idx]

    model = D1v2DynamicsModel(
        n_codes=n_codes,
        d_model=args.d_model,
        nhead=args.nhead,
        dim_feedforward=args.dim_feedforward,
        max_len=max_len,
        num_encoder_layers=args.encoder_layers,
    ).to(device)
    n_params = count_parameters(model)
    print(f"[dynamics] parameters: {n_params:,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.max_epochs)

    metrics = {
        "model": "dynamics",
        "ring": args.ring,
        "n_codes": n_codes,
        "hyperparameters": {k: v for k, v in vars(args).items()},
        "device": str(device),
        "param_count": n_params,
        "train_size": len(train_records),
        "val_size": len(val_records),
        "val_boundary_size": sum(1 for r in val_records if r["boundary"]),
        "train_boundary_size": sum(1 for r in train_records if r["boundary"]),
        "epochs": [],
        "best_epoch": None,
        "best_verdict_accuracy_free_running": -1.0,
    }

    rng = random.Random(args.seed)
    best_metric = -1.0
    best_epoch = 0
    epochs_since_improve = 0
    ckpt_best = Path(args.out_dir) / "dynamics_best.pt"
    ckpt_last = Path(args.out_dir) / "dynamics_last.pt"
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    train_start = time.time()
    for epoch in range(1, args.max_epochs + 1):
        model.train()
        perm = list(range(len(train_records)))
        rng.shuffle(perm)
        total_loss = 0.0
        total_state_loss = 0.0
        total_verdict_loss = 0.0
        n_batches = 0
        epoch_start = time.time()
        for i in range(0, len(perm), args.batch_size):
            batch_idx = perm[i : i + args.batch_size]
            batch_records = [train_records[j] for j in batch_idx]
            src = pad_src_batch([r["src_ids"] for r in batch_records]).to(device)
            true_bitmaps, round_mask, round_idx, verdict = build_batch_bitmaps(batch_records, n_codes)
            true_bitmaps, round_mask = true_bitmaps.to(device), round_mask.to(device)
            round_idx, verdict = round_idx.to(device), verdict.to(device)

            logits, hiddens = model(src, true_bitmaps=true_bitmaps, mode="teacher_force")
            state_loss = masked_state_bce(logits, true_bitmaps, round_mask)
            verdict_logits = model.verdict_logits(hiddens, round_idx)
            verdict_loss = nn.functional.binary_cross_entropy_with_logits(verdict_logits, verdict)
            loss = args.state_loss_weight * state_loss + args.verdict_loss_weight * verdict_loss

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optimizer.step()

            total_loss += loss.item()
            total_state_loss += state_loss.item()
            total_verdict_loss += verdict_loss.item()
            n_batches += 1
        scheduler.step()

        eval_metrics = evaluate_dynamics(model, val_records, n_codes, device)
        epoch_time = time.time() - epoch_start
        monitored = eval_metrics["verdict_accuracy_free_running"]
        improved = monitored > best_metric
        if improved:
            best_metric = monitored
            best_epoch = epoch
            epochs_since_improve = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "hyperparameters": vars(args),
                    "epoch": epoch,
                    "n_codes": n_codes,
                    "max_len": max_len,
                },
                ckpt_best,
            )
        else:
            epochs_since_improve += 1

        boundary_acc = eval_metrics["verdict_accuracy_free_running_boundary"]
        boundary_str = f"{boundary_acc:.4f}" if boundary_acc is not None else "n/a"
        print(
            f"[dynamics] epoch {epoch:3d}/{args.max_epochs}  loss={total_loss/max(1,n_batches):.4f} "
            f"(state={total_state_loss/max(1,n_batches):.4f} verdict={total_verdict_loss/max(1,n_batches):.4f})  "
            f"round0_f1={eval_metrics['round0_f1']:.4f}  "
            f"verdict_acc_tf={eval_metrics['verdict_accuracy_teacher_forced']:.4f}  "
            f"verdict_acc_fr={eval_metrics['verdict_accuracy_free_running']:.4f}  "
            f"verdict_acc_fr_boundary={boundary_str}  "
            f"time={epoch_time:.1f}s{'  *best*' if improved else ''}",
            flush=True,
        )
        metrics["epochs"].append(
            {
                "epoch": epoch,
                "train_loss": total_loss / max(1, n_batches),
                "train_state_loss": total_state_loss / max(1, n_batches),
                "train_verdict_loss": total_verdict_loss / max(1, n_batches),
                "n_batches": n_batches,
                "epoch_time_sec": epoch_time,
                **eval_metrics,
            }
        )

        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "hyperparameters": vars(args),
                "epoch": epoch,
                "n_codes": n_codes,
                "max_len": max_len,
            },
            ckpt_last,
        )

        if epochs_since_improve >= args.patience:
            print(
                f"[dynamics] early stop at epoch {epoch}: no improvement in "
                f"free-running verdict accuracy for {args.patience} epochs "
                f"(best={best_metric:.4f} at epoch {best_epoch})"
            )
            break

    metrics["best_epoch"] = best_epoch
    metrics["best_verdict_accuracy_free_running"] = best_metric
    metrics["total_train_time_sec"] = time.time() - train_start
    metrics["final_eval"] = metrics["epochs"][-1] if metrics["epochs"] else None
    return metrics


def train_control(args, records, train_idx, val_idx, max_len, device) -> dict:
    train_records = [records[i] for i in train_idx]
    val_records = [records[i] for i in val_idx]

    model = D1v2VerdictOnlyModel(
        d_model=args.d_model,
        nhead=args.nhead,
        dim_feedforward=args.dim_feedforward,
        max_len=max_len,
        num_encoder_layers=args.encoder_layers,
    ).to(device)
    n_params = count_parameters(model)
    print(f"[control] parameters: {n_params:,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.max_epochs)

    metrics = {
        "model": "control_verdict_only",
        "ring": args.ring,
        "hyperparameters": {k: v for k, v in vars(args).items()},
        "device": str(device),
        "param_count": n_params,
        "train_size": len(train_records),
        "val_size": len(val_records),
        "val_boundary_size": sum(1 for r in val_records if r["boundary"]),
        "train_boundary_size": sum(1 for r in train_records if r["boundary"]),
        "epochs": [],
        "best_epoch": None,
        "best_verdict_accuracy": -1.0,
    }

    rng = random.Random(args.seed)
    best_metric = -1.0
    best_epoch = 0
    epochs_since_improve = 0
    ckpt_best = Path(args.out_dir) / "control_best.pt"
    ckpt_last = Path(args.out_dir) / "control_last.pt"
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    train_start = time.time()
    for epoch in range(1, args.max_epochs + 1):
        model.train()
        perm = list(range(len(train_records)))
        rng.shuffle(perm)
        total_loss = 0.0
        n_batches = 0
        epoch_start = time.time()
        for i in range(0, len(perm), args.batch_size):
            batch_idx = perm[i : i + args.batch_size]
            batch_records = [train_records[j] for j in batch_idx]
            src = pad_src_batch([r["src_ids"] for r in batch_records]).to(device)
            verdict = torch.tensor(
                [1.0 if r["d_reducible"] else 0.0 for r in batch_records], device=device
            )

            logits = model(src)
            loss = nn.functional.binary_cross_entropy_with_logits(logits, verdict)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optimizer.step()

            total_loss += loss.item()
            n_batches += 1
        scheduler.step()

        eval_metrics = evaluate_control(model, val_records, device)
        epoch_time = time.time() - epoch_start
        monitored = eval_metrics["verdict_accuracy"]
        improved = monitored > best_metric
        if improved:
            best_metric = monitored
            best_epoch = epoch
            epochs_since_improve = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "hyperparameters": vars(args),
                    "epoch": epoch,
                    "max_len": max_len,
                },
                ckpt_best,
            )
        else:
            epochs_since_improve += 1

        boundary_acc = eval_metrics["verdict_accuracy_boundary"]
        boundary_str = f"{boundary_acc:.4f}" if boundary_acc is not None else "n/a"
        print(
            f"[control]  epoch {epoch:3d}/{args.max_epochs}  loss={total_loss/max(1,n_batches):.4f}  "
            f"verdict_acc={eval_metrics['verdict_accuracy']:.4f}  "
            f"verdict_acc_boundary={boundary_str}  "
            f"time={epoch_time:.1f}s{'  *best*' if improved else ''}",
            flush=True,
        )
        metrics["epochs"].append(
            {
                "epoch": epoch,
                "train_loss": total_loss / max(1, n_batches),
                "n_batches": n_batches,
                "epoch_time_sec": epoch_time,
                **eval_metrics,
            }
        )

        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "hyperparameters": vars(args),
                "epoch": epoch,
                "max_len": max_len,
            },
            ckpt_last,
        )

        if epochs_since_improve >= args.patience:
            print(
                f"[control] early stop at epoch {epoch}: no improvement in "
                f"verdict accuracy for {args.patience} epochs "
                f"(best={best_metric:.4f} at epoch {best_epoch})"
            )
            break

    metrics["best_epoch"] = best_epoch
    metrics["best_verdict_accuracy"] = best_metric
    metrics["total_train_time_sec"] = time.time() - train_start
    metrics["final_eval"] = metrics["epochs"][-1] if metrics["epochs"] else None
    return metrics


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ring", type=int, default=8)
    ap.add_argument("--data-dir", type=str, default=str(DEFAULT_DATA_DIR))
    ap.add_argument("--out-dir", type=str, default="")
    ap.add_argument("--model", type=str, choices=["dynamics", "control", "both"], default="both")
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--stratify", action="store_true", default=True)
    ap.add_argument("--no-stratify", dest="stratify", action="store_false")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--max-epochs", type=int, default=150)
    ap.add_argument("--patience", type=int, default=20)
    ap.add_argument("--d-model", type=int, default=256)
    ap.add_argument("--nhead", type=int, default=4)
    ap.add_argument("--dim-feedforward", type=int, default=0, help="0 = 2*d_model")
    ap.add_argument("--encoder-layers", type=int, default=2)
    ap.add_argument("--state-loss-weight", type=float, default=1.0)
    ap.add_argument("--verdict-loss-weight", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", type=str, default="auto")
    ap.add_argument("--grad-clip", type=float, default=1.0)
    args = ap.parse_args()

    if not args.dim_feedforward:
        args.dim_feedforward = 2 * args.d_model
    if not args.out_dir:
        args.out_dir = str(ROOT / "results" / "d1v2" / f"r{args.ring}")

    torch.manual_seed(args.seed)
    random.seed(args.seed)

    device = make_device(args.device)
    print(f"Using device: {device}")

    data_dir = Path(args.data_dir)
    n_codes = load_code_index(data_dir, args.ring)
    t0 = time.time()
    records = load_records(data_dir, args.ring)
    max_len = max(len(r["src_ids"]) for r in records) + 4 if records else 32
    print(
        f"Loaded {len(records)} configs for ring {args.ring} "
        f"({n_codes} codes, max src len {max_len}) in {time.time()-t0:.1f}s"
    )

    train_idx, val_idx = stratified_split(records, args.val_frac, args.seed, args.stratify)
    n_boundary_total = sum(1 for r in records if r["boundary"])
    print(
        f"Train: {len(train_idx)}  Val: {len(val_idx)}  "
        f"(boundary total {n_boundary_total}, stratify={args.stratify})"
    )

    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    combined = {
        "ring": args.ring,
        "n_configs": len(records),
        "n_codes": n_codes,
        "n_boundary_total": n_boundary_total,
        "train_size": len(train_idx),
        "val_size": len(val_idx),
    }

    if args.model in ("dynamics", "both"):
        dyn_metrics = train_dynamics(args, records, train_idx, val_idx, n_codes, max_len, device)
        out_path = Path(args.out_dir) / "dynamics_metrics.json"
        with out_path.open("w") as f:
            json.dump(dyn_metrics, f, indent=2)
        print(f"Wrote {out_path}")
        combined["dynamics"] = {
            "best_epoch": dyn_metrics["best_epoch"],
            "best_verdict_accuracy_free_running": dyn_metrics["best_verdict_accuracy_free_running"],
        }

    if args.model in ("control", "both"):
        ctrl_metrics = train_control(args, records, train_idx, val_idx, max_len, device)
        out_path = Path(args.out_dir) / "control_metrics.json"
        with out_path.open("w") as f:
            json.dump(ctrl_metrics, f, indent=2)
        print(f"Wrote {out_path}")
        combined["control"] = {
            "best_epoch": ctrl_metrics["best_epoch"],
            "best_verdict_accuracy": ctrl_metrics["best_verdict_accuracy"],
        }

    summary_path = Path(args.out_dir) / "summary.json"
    with summary_path.open("w") as f:
        json.dump(combined, f, indent=2)
    print(f"Wrote {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
