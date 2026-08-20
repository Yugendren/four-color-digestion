#!/usr/bin/env python3
"""Train D1Transformer on the D1 corpus: canonical config encoding ->
process-supervised closure-trace + verdict tokens (teacher forcing),
evaluated by exact sequence match and verdict-only accuracy (greedy
decode). Mirrors the training-loop structure of
/Users/yugendren/experiments/zeta_map_interp/tools/train.py (attribution
comment in src/fourcolor/d1_model.py covers the architecture; this script
is adapted independently for D1's variable-length batched sequences,
since the zeta-map task used fixed-length sequences and did not need
dynamic padding).

Usage (staging / smoke):
    .venv/bin/python tools/d1_train.py --limit 500 --epochs 3 \
        --tag smoke --metrics-out results/d1/smoke.json

Saves:
    checkpoints/d1_model.pt      -- model state_dict + hyperparameters
    <--metrics-out>               -- per-epoch loss/eval + hyperparameters
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import torch  # noqa: E402
from torch import nn  # noqa: E402
from torch.nn.utils.rnn import pad_sequence  # noqa: E402

from fourcolor.d1_encoding import (  # noqa: E402
    PAD_ID,
    decode_verdict,
    encode_config,
    encode_trace,
)
from fourcolor.d1_model import D1Transformer, count_parameters  # noqa: E402

DEFAULT_CORPUS = ROOT / "data" / "d1_corpus.jsonl"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def load_examples(
    corpus_path: Path, max_src_len: int, max_tgt_len: int
) -> tuple[list[list[int]], list[list[int]], list[bool], dict]:
    """Load process-supervision examples (records with a non-null trace).
    Returns (src_id_lists, tgt_id_lists, d_reducible_flags, load_stats)."""
    src_list, tgt_list, verdicts = [], [], []
    n_total = 0
    n_no_trace = 0
    n_too_long = 0
    with corpus_path.open() as f:
        for line in f:
            rec = json.loads(line)
            n_total += 1
            if rec["trace"] is None:
                n_no_trace += 1
                continue
            adjacency = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
            src_ids = encode_config(adjacency, rec["r"], rec["n"])
            tgt_ids = encode_trace(rec["trace"], rec["d_reducible"])
            if len(src_ids) > max_src_len or len(tgt_ids) > max_tgt_len:
                n_too_long += 1
                continue
            src_list.append(src_ids)
            tgt_list.append(tgt_ids)
            verdicts.append(rec["d_reducible"])
    stats = {
        "corpus_total": n_total,
        "no_trace_excluded": n_no_trace,
        "too_long_excluded": n_too_long,
        "usable": len(src_list),
    }
    return src_list, tgt_list, verdicts, stats


def pad_batch(id_lists: list[list[int]]) -> torch.Tensor:
    tensors = [torch.tensor(ids, dtype=torch.long) for ids in id_lists]
    return pad_sequence(tensors, batch_first=True, padding_value=PAD_ID)


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------


@torch.no_grad()
def evaluate(
    model: D1Transformer,
    src_ids: torch.Tensor,
    tgt_id_lists: list[list[int]],
    device: torch.device,
    batch_size: int,
    max_len: int,
) -> dict:
    model.eval()
    n = len(tgt_id_lists)
    exact = 0
    verdict_correct = 0
    verdict_present = 0
    for i in range(0, n, batch_size):
        batch_src = src_ids[i : i + batch_size].to(device)
        gen = model.greedy_decode(batch_src, max_len=max_len).cpu().tolist()
        for row, expected in zip(gen, tgt_id_lists[i : i + batch_size]):
            # Trim trailing PAD for exact-match comparison against the
            # (already EOS-terminated) expected sequence.
            trimmed = row[: row.index(0)] if 0 in row else row  # 0 == PAD_ID
            if trimmed == expected:
                exact += 1
            pred_v = decode_verdict(row)
            true_v = decode_verdict(expected)
            if pred_v is not None:
                verdict_present += 1
                if pred_v == true_v:
                    verdict_correct += 1
    return {
        "exact_match": exact / n if n else 0.0,
        "verdict_accuracy": verdict_correct / n if n else 0.0,
        "verdict_present_rate": verdict_present / n if n else 0.0,
        "n_eval": n,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=str, default=str(DEFAULT_CORPUS))
    ap.add_argument("--limit", type=int, default=0, help="subsample corpus to this many usable examples (0 = all)")
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--max-src-len", type=int, default=256)
    ap.add_argument("--max-tgt-len", type=int, default=256)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--eval-batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--d-model", type=int, default=192)
    ap.add_argument("--nhead", type=int, default=4)
    ap.add_argument("--dim-feedforward", type=int, default=384)
    ap.add_argument("--encoder-layers", type=int, default=2)
    ap.add_argument("--decoder-layers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", type=str, default="auto")
    ap.add_argument("--grad-clip", type=float, default=1.0)
    ap.add_argument("--checkpoint-out", type=str, default=str(ROOT / "checkpoints" / "d1_model.pt"))
    ap.add_argument("--metrics-out", type=str, default=str(ROOT / "results" / "d1" / "train_metrics.json"))
    ap.add_argument("--tag", type=str, default="")
    ap.add_argument("--time-budget-sec", type=float, default=0.0, help="if >0, stop after roughly this many seconds (smoke-run budget)")
    args = ap.parse_args()

    torch.manual_seed(args.seed)

    if args.device == "auto":
        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"Using device: {device}")

    t0 = time.time()
    src_list, tgt_list, verdicts, load_stats = load_examples(
        Path(args.corpus), args.max_src_len, args.max_tgt_len
    )
    print(f"Loaded {load_stats['usable']} usable examples in {time.time()-t0:.1f}s: {load_stats}")

    import random

    rng = random.Random(args.seed)
    idx = list(range(len(src_list)))
    rng.shuffle(idx)
    if args.limit and args.limit < len(idx):
        idx = idx[: args.limit]
        print(f"Subsampled to {len(idx)} examples")

    n_val = max(1, int(len(idx) * args.val_frac))
    val_idx, train_idx = idx[:n_val], idx[n_val:]
    print(f"Train: {len(train_idx)}  Val: {len(val_idx)}")

    train_src = [src_list[i] for i in train_idx]
    train_tgt = [tgt_list[i] for i in train_idx]
    val_src_ids = pad_batch([src_list[i] for i in val_idx])
    val_tgt = [tgt_list[i] for i in val_idx]

    max_len_needed = max(len(t) for t in tgt_list) if tgt_list else 8
    max_len_needed = max(max_len_needed, max(len(s) for s in src_list) if src_list else 8)

    model = D1Transformer(
        d_model=args.d_model,
        nhead=args.nhead,
        dim_feedforward=args.dim_feedforward,
        max_len=max_len_needed + 4,
        num_encoder_layers=args.encoder_layers,
        num_decoder_layers=args.decoder_layers,
    ).to(device)
    n_params = count_parameters(model)
    print(f"Model parameters: {n_params:,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)

    metrics = {
        "hyperparameters": vars(args),
        "device": str(device),
        "param_count": n_params,
        "train_size": len(train_idx),
        "val_size": len(val_idx),
        "load_stats": load_stats,
        "epochs": [],
    }

    train_start = time.time()
    stop_early = False
    for epoch in range(1, args.epochs + 1):
        if stop_early:
            break
        model.train()
        epoch_start = time.time()
        perm = list(range(len(train_src)))
        rng.shuffle(perm)
        total_loss = 0.0
        n_batches = 0
        for i in range(0, len(perm), args.batch_size):
            batch_idx = perm[i : i + args.batch_size]
            src = pad_batch([train_src[j] for j in batch_idx]).to(device)
            tgt = pad_batch([train_tgt[j] for j in batch_idx]).to(device)
            tgt_in = tgt[:, :-1]
            labels = tgt[:, 1:]

            logits = model(src, tgt_in)
            loss = nn.functional.cross_entropy(
                logits.reshape(-1, logits.size(-1)), labels.reshape(-1), ignore_index=PAD_ID
            )
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optimizer.step()

            total_loss += loss.item()
            n_batches += 1

            if args.time_budget_sec and (time.time() - train_start) > args.time_budget_sec:
                print(f"Time budget {args.time_budget_sec}s reached; stopping training loop.")
                stop_early = True
                break

        avg_loss = total_loss / max(1, n_batches)
        eval_metrics = evaluate(
            model, val_src_ids, val_tgt, device, args.eval_batch_size, max_len_needed + 4
        )
        epoch_time = time.time() - epoch_start
        print(
            f"Epoch {epoch:3d}/{args.epochs}  loss={avg_loss:.4f}  "
            f"exact_match={eval_metrics['exact_match']:.4f}  "
            f"verdict_acc={eval_metrics['verdict_accuracy']:.4f}  time={epoch_time:.1f}s"
        )
        metrics["epochs"].append(
            {
                "epoch": epoch,
                "train_loss": avg_loss,
                "n_batches": n_batches,
                **eval_metrics,
                "epoch_time_sec": epoch_time,
            }
        )

        ckpt_path = Path(args.checkpoint_out)
        ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "hyperparameters": vars(args),
                "epoch": epoch,
                "max_len": max_len_needed + 4,
            },
            ckpt_path,
        )

    total_train_time = time.time() - train_start
    metrics["total_train_time_sec"] = total_train_time
    metrics["final_eval"] = metrics["epochs"][-1] if metrics["epochs"] else None
    metrics["note"] = args.tag

    metrics_path = Path(args.metrics_out)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Wrote {metrics_path} (total train time {total_train_time:.1f}s)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
