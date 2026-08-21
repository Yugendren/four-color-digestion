"""Interpretability harness for D1Transformer (the D1 reducibility
simulator): activation capture, linear probes, shallow/structural
candidate features, and the machinery `tools/d1_interrogate.py` needs to
ask "does the encoder already know the verdict, and is that knowledge
deeper than shallow features?"

Mechanics (hook-based activation capture, torch logistic probes,
stratified split, bootstrap CI) are adapted, with attribution, from the
zeta-map interpretability template:
    /Users/yugendren/experiments/zeta_map_interp/src/zetamap/interp.py
Copied and re-derived rather than imported across repos (no cross-repo
dependency). Two structural differences from that template drove the
adaptation, not a verbatim copy:
  * D1Transformer has 1-4 encoder/decoder layers (not fixed at 1), so
    activation capture here uses plain `register_forward_hook` on each
    `nn.TransformerEncoderLayer` / the `nn.TransformerDecoder` module
    rather than the MPS-safe `_sa_block`/`_mha_block` monkeypatch the
    template needed for per-head ATTENTION WEIGHTS specifically (that
    trick works around torch's fused-attention fast path suppressing
    `need_weights`; it isn't needed here because this task only needs
    hidden states, which forward hooks already see un-suppressed).
  * D1's target task is a held-out VERDICT probe (binary), not a
    per-token level probe, and adds a shallow/structural hand-features
    baseline the zeta-map task had no analogue of (zeta levels have no
    "shallow feature" competitor).

No sklearn/scipy is installed in this repo's .venv (see pyproject.toml:
only numpy + networkx), so probes are a from-scratch torch logistic
regression (linear layer + softmax cross-entropy + weight-decay ridge
penalty, exactly as the zeta-map template's `train_linear_probe`) and
correlation is a from-scratch numpy Pearson/Spearman (Spearman via
argsort-based ranks with average-rank tie handling).
"""

from __future__ import annotations

import contextlib
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .canonical import canonical_labeling
from .d1_encoding import BOS_ID, PAD_ID, STOI, decode_verdict, encode_config, encode_trace
from .d1_model import D1Transformer

# ---------------------------------------------------------------------------
# Corpus / held-out split (reproduces tools/d1_train.py's load_examples +
# main()'s shuffle/split EXACTLY, so the "val" records returned here are
# precisely the examples the d1_full_v1 checkpoint never trained on).
# ---------------------------------------------------------------------------


def load_split(
    corpus_path: str | Path,
    val_frac: float = 0.1,
    seed: int = 0,
    max_src_len: int = 256,
    max_tgt_len: int = 256,
) -> tuple[list[dict], list[dict], dict]:
    """Reproduce tools/d1_train.py's train/val split. Returns (train_records,
    val_records, load_stats); each record is the corpus's parsed dict plus
    int-keyed 'adjacency', and precomputed 'src_ids'/'tgt_ids'."""
    records: list[dict] = []
    n_total = n_no_trace = n_too_long = 0
    with Path(corpus_path).open() as f:
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
            rec = dict(rec)
            rec["adjacency"] = adjacency
            rec["src_ids"] = src_ids
            rec["tgt_ids"] = tgt_ids
            records.append(rec)

    load_stats = {
        "corpus_total": n_total,
        "no_trace_excluded": n_no_trace,
        "too_long_excluded": n_too_long,
        "usable": len(records),
    }

    rng = random.Random(seed)
    idx = list(range(len(records)))
    rng.shuffle(idx)
    n_val = max(1, int(len(idx) * val_frac))
    val_idx, train_idx = idx[:n_val], idx[n_val:]
    train_records = [records[i] for i in train_idx]
    val_records = [records[i] for i in val_idx]
    return train_records, val_records, load_stats


def load_model(checkpoint_path: str | Path, device: torch.device) -> tuple[D1Transformer, dict]:
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    hp = ckpt["hyperparameters"]
    model = D1Transformer(
        d_model=hp.get("d_model", 192),
        nhead=hp.get("nhead", 4),
        dim_feedforward=hp.get("dim_feedforward", 384),
        max_len=ckpt.get("max_len", 259),
        num_encoder_layers=hp.get("encoder_layers", 2),
        num_decoder_layers=hp.get("decoder_layers", 2),
    ).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model, ckpt


def pad_batch(id_lists: list[list[int]]) -> torch.Tensor:
    tensors = [torch.tensor(ids, dtype=torch.long) for ids in id_lists]
    return nn.utils.rnn.pad_sequence(tensors, batch_first=True, padding_value=PAD_ID)


# ---------------------------------------------------------------------------
# Encoder-state capture (deliverable 1): forward hooks on each encoder
# layer, "layer 0" = raw token+positional embeddings (the state that
# exists before ANY self-attention has run -- i.e. before the encoder has
# looked at the config as a whole at all).
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _capture_encoder_layer_outputs(model: D1Transformer):
    outputs: list[torch.Tensor | None] = [None] * len(model.encoder.layers)

    def make_hook(i: int):
        def hook(module, inputs, output):
            outputs[i] = output

        return hook

    handles = [layer.register_forward_hook(make_hook(i)) for i, layer in enumerate(model.encoder.layers)]
    try:
        yield outputs
    finally:
        for h in handles:
            h.remove()


@torch.no_grad()
def encode_with_layers(
    model: D1Transformer, src_ids: torch.Tensor
) -> tuple[dict[int, torch.Tensor], torch.Tensor]:
    """Per-layer encoder hidden states for a padded batch of src_ids.

    Returns (layers, padding_mask) where layers[0] is the pre-encoder
    embedding (B, S, D), layers[1..L] are each encoder layer's output
    (B, S, D) (layers[L] == the final memory the decoder cross-attends
    to, since D1Transformer's nn.TransformerEncoder has no final norm),
    and padding_mask is (B, S) True at PAD positions."""
    model.eval()
    padding_mask = src_ids == model.pad_id
    embeds = model._embed(src_ids)
    with _capture_encoder_layer_outputs(model) as layer_outs:
        model.encoder(embeds, src_key_padding_mask=padding_mask)
    layers = {0: embeds.detach()}
    for i, out in enumerate(layer_outs, start=1):
        assert out is not None, f"encoder layer {i} hook never fired"
        layers[i] = out.detach()
    return layers, padding_mask


def mean_pool(hidden: torch.Tensor, padding_mask: torch.Tensor) -> torch.Tensor:
    """Mean over non-PAD positions. hidden: (B, S, D); padding_mask: (B, S)
    True at PAD. Returns (B, D)."""
    keep = (~padding_mask).unsqueeze(-1).to(hidden.dtype)
    summed = (hidden * keep).sum(dim=1)
    counts = keep.sum(dim=1).clamp_min(1.0)
    return summed / counts


def mean_pool_positions(hidden_row: torch.Tensor, positions: list[int]) -> torch.Tensor:
    """Mean of hidden_row (S, D) over a subset of positions. Zero vector
    (with the same D) if positions is empty (e.g. a ring-only config with
    no interior vertices)."""
    if not positions:
        return torch.zeros(hidden_row.size(-1), dtype=hidden_row.dtype)
    return hidden_row[positions, :].mean(dim=0)


# ---------------------------------------------------------------------------
# Encoder input position groups: which token positions belong to a RING
# vertex's block vs an INTERIOR vertex's block. Deliberately re-derives
# encode_config's exact token layout (see d1_encoding.encode_config)
# rather than importing its private helpers, so the position bookkeeping
# is self-contained; test_d1_interp.py asserts token-for-token equality
# with d1_encoding.encode_config on sample configs to guard against drift.
# ---------------------------------------------------------------------------


def _mag_id_local(value: int, mag_cap: int) -> int:
    clamped = max(0, min(value, mag_cap))
    return STOI[f"MAG_{clamped}"]


def encode_config_with_groups(
    adjacency: dict[int, list[int]], r: int, n: int, mag_cap: int = 31
) -> tuple[list[int], list[int], list[int], list[int]]:
    """Like d1_encoding.encode_config, but also returns (header_pos,
    ring_pos, interior_pos): the token positions belonging to the "RING
    MAG(r) N MAG(n)" header, to ring-vertex (v<=r) blocks, and to
    interior-vertex (v>r) blocks respectively."""
    label, _start, direction = canonical_labeling(adjacency, r, n)
    inv = {new: old for old, new in label.items()}

    ids: list[int] = [STOI["RING"], _mag_id_local(r, mag_cap), STOI["N"], _mag_id_local(n, mag_cap)]
    header_pos = list(range(len(ids)))
    ring_pos: list[int] = []
    interior_pos: list[int] = []
    for new_v in range(1, n + 1):
        start = len(ids)
        old_v = inv[new_v]
        nbrs = adjacency[old_v]
        if direction == -1:
            nbrs = list(reversed(nbrs))
        new_nbrs = [label[u] for u in nbrs]
        if new_nbrs:
            k = new_nbrs.index(min(new_nbrs))
            new_nbrs = new_nbrs[k:] + new_nbrs[:k]
        ids.append(STOI["V"])
        ids.append(STOI["DEG"])
        ids.append(_mag_id_local(len(new_nbrs), mag_cap))
        for u in new_nbrs:
            offset = u - new_v
            ids.append(STOI["SIGN_POS"] if offset >= 0 else STOI["SIGN_NEG"])
            ids.append(_mag_id_local(abs(offset), mag_cap))
        end = len(ids)
        (ring_pos if new_v <= r else interior_pos).extend(range(start, end))
    return ids, header_pos, ring_pos, interior_pos


# ---------------------------------------------------------------------------
# Shallow (hand-computed) features -- the BASELINE-SHALLOW control.
# ---------------------------------------------------------------------------

_DEGREE_BINS = list(range(3, 12))  # deg_3 .. deg_11, plus an overflow deg_12p bin

SHALLOW_FEATURE_NAMES: list[str] = (
    ["r", "n", "n_interior", "mean_interior_degree", "min_interior_degree", "max_interior_degree"]
    + [f"deg_{d}" for d in _DEGREE_BINS]
    + ["deg_12p"]
)


def shallow_features(adjacency: dict[int, list[int]], r: int, n: int) -> dict[str, float]:
    """Hand-computed shallow features: ring size, n, interior vertex count,
    full-graph degree histogram, mean/min/max interior degree. Rotation/
    reflection invariant by construction (no canonicalization needed)."""
    degrees = {v: len(nbrs) for v, nbrs in adjacency.items()}
    interior = list(range(r + 1, n + 1))
    interior_degrees = [degrees[v] for v in interior] if interior else [0]

    hist = {f"deg_{d}": 0 for d in _DEGREE_BINS}
    hist["deg_12p"] = 0
    for d in degrees.values():
        if d < _DEGREE_BINS[0]:
            key = f"deg_{_DEGREE_BINS[0]}"
        elif d > _DEGREE_BINS[-1]:
            key = "deg_12p"
        else:
            key = f"deg_{d}"
        hist[key] += 1

    feats = {
        "r": float(r),
        "n": float(n),
        "n_interior": float(len(interior)),
        "mean_interior_degree": float(sum(interior_degrees) / len(interior_degrees)),
        "min_interior_degree": float(min(interior_degrees)),
        "max_interior_degree": float(max(interior_degrees)),
    }
    feats.update({k: float(v) for k, v in hist.items()})
    return feats


def shallow_feature_vector(adjacency: dict[int, list[int]], r: int, n: int) -> list[float]:
    feats = shallow_features(adjacency, r, n)
    return [feats[name] for name in SHALLOW_FEATURE_NAMES]


# ---------------------------------------------------------------------------
# Structural candidate features (deliverable 4's extraction library).
# ---------------------------------------------------------------------------

STRUCTURAL_FEATURE_NAMES = [
    "n_deg5_interior",
    "n_deg5_total",
    "max_run_deg5_ring",
    "max_run_const_degree_ring",
    "n_triangles_deg5",
    "n_diamonds_deg5",
    "n_extendable",
    "n_extendable_ratio",
    "n_consistent",
]


def _max_cyclic_run_true(vals: list[bool]) -> int:
    r = len(vals)
    if r == 0:
        return 0
    if all(vals):
        return r
    start = next(i for i, v in enumerate(vals) if not v)
    rotated = vals[start:] + vals[:start]
    best = cur = 0
    for v in rotated:
        if v:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _max_cyclic_const_run(vals: list[int]) -> int:
    r = len(vals)
    if r == 0:
        return 0
    if len(set(vals)) == 1:
        return r
    start = 0
    for i in range(r):
        if vals[i] != vals[(i - 1) % r]:
            start = i
            break
    rotated = vals[start:] + vals[:start]
    best = cur = 1
    for i in range(1, len(rotated)):
        if rotated[i] == rotated[i - 1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def _all_triangles(adjacency: dict[int, list[int]]) -> set[tuple[int, int, int]]:
    tris: set[tuple[int, int, int]] = set()
    for u, nbrs_u in adjacency.items():
        set_u = set(nbrs_u)
        for v in set_u:
            if v <= u:
                continue
            common = set_u & set(adjacency[v])
            for w in common:
                if w > v:
                    tris.add((u, v, w))
    return tris


def _diamonds_deg5_count(adjacency: dict[int, list[int]], deg5: set[int]) -> int:
    """Count of Birkhoff-diamond-like structures: an edge (u,v) with both
    endpoints degree-5, shared by >=2 triangles whose apex vertices are
    ALSO degree-5 (each such pair of apexes {w1,w2} is one diamond)."""
    count = 0
    seen_edges: set[tuple[int, int]] = set()
    for u, nbrs in adjacency.items():
        for v in nbrs:
            if v <= u or (u, v) in seen_edges:
                continue
            seen_edges.add((u, v))
            if u not in deg5 or v not in deg5:
                continue
            common = [w for w in adjacency[u] if w in adjacency[v] and w in deg5]
            k = len(common)
            count += k * (k - 1) // 2
    return count


def structural_candidates(
    adjacency: dict[int, list[int]], r: int, n: int, n_extendable: int, n_consistent: int
) -> dict[str, float]:
    """Exploratory candidate quantities for deliverable 4's correlation
    ranking. n_extendable/n_consistent are taken from the corpus record
    (already computed by fourcolor.reduce; see that module's docstring),
    not recomputed here."""
    degrees = {v: len(nbrs) for v, nbrs in adjacency.items()}
    deg5 = {v for v, d in degrees.items() if d == 5}
    n_deg5_interior = sum(1 for v in range(r + 1, n + 1) if degrees.get(v) == 5)
    n_deg5_total = len(deg5)

    ring_degrees = [degrees[v] for v in range(1, r + 1)]
    max_run_deg5_ring = _max_cyclic_run_true([d == 5 for d in ring_degrees])
    max_run_const_degree_ring = _max_cyclic_const_run(ring_degrees)

    triangles = _all_triangles(adjacency)
    n_triangles_deg5 = sum(1 for (a, b, c) in triangles if a in deg5 and b in deg5 and c in deg5)
    n_diamonds_deg5 = _diamonds_deg5_count(adjacency, deg5)

    ratio = n_extendable / (3 ** (r - 1)) if r >= 1 else 0.0

    return {
        "n_deg5_interior": float(n_deg5_interior),
        "n_deg5_total": float(n_deg5_total),
        "max_run_deg5_ring": float(max_run_deg5_ring),
        "max_run_const_degree_ring": float(max_run_const_degree_ring),
        "n_triangles_deg5": float(n_triangles_deg5),
        "n_diamonds_deg5": float(n_diamonds_deg5),
        "n_extendable": float(n_extendable),
        "n_extendable_ratio": float(ratio),
        "n_consistent": float(n_consistent),
    }


# ---------------------------------------------------------------------------
# Probe pipeline: stratified split, standardization, torch logistic probe,
# bootstrap CI. All ridge-regularized (weight_decay), all binary
# (verdict = d_reducible).
# ---------------------------------------------------------------------------


def stratified_split(labels: list[bool], test_frac: float = 0.2, seed: int = 0) -> tuple[list[int], list[int]]:
    """Index split stratified by (boolean) label, shuffled with `seed`."""
    rng = random.Random(seed)
    pos = [i for i, lab in enumerate(labels) if lab]
    neg = [i for i, lab in enumerate(labels) if not lab]
    rng.shuffle(pos)
    rng.shuffle(neg)
    n_test_pos = max(1, int(round(len(pos) * test_frac)))
    n_test_neg = max(1, int(round(len(neg) * test_frac)))
    test_idx = pos[:n_test_pos] + neg[:n_test_neg]
    train_idx = pos[n_test_pos:] + neg[n_test_neg:]
    rng.shuffle(train_idx)
    rng.shuffle(test_idx)
    return train_idx, test_idx


def standardize(
    X_train: torch.Tensor, X_test: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    mean = X_train.mean(dim=0, keepdim=True)
    std = X_train.std(dim=0, keepdim=True).clamp_min(1e-6)
    return (X_train - mean) / std, (X_test - mean) / std, mean.squeeze(0), std.squeeze(0)


def train_logistic_probe(
    X_train: torch.Tensor,
    y_train: torch.Tensor,
    X_test: torch.Tensor,
    y_test: torch.Tensor,
    epochs: int = 400,
    lr: float = 0.05,
    weight_decay: float = 1e-2,
    seed: int = 0,
) -> dict:
    """Ridge-regularized (weight_decay = L2) binary logistic probe: a
    single linear layer (d -> 2) trained full-batch with Adam + softmax
    cross-entropy, exactly the zeta-map interp template's
    `train_linear_probe` specialized to num_classes=2 (kept as a from-
    scratch torch implementation since no sklearn is installed here)."""
    torch.manual_seed(seed)
    X_train = X_train.detach().float()
    X_test = X_test.detach().float()
    d = X_train.shape[1]
    probe = nn.Linear(d, 2)
    opt = torch.optim.Adam(probe.parameters(), lr=lr, weight_decay=weight_decay)
    for _ in range(epochs):
        opt.zero_grad()
        logits = probe(X_train)
        loss = nn.functional.cross_entropy(logits, y_train)
        loss.backward()
        opt.step()
    with torch.no_grad():
        train_pred = probe(X_train).argmax(dim=-1)
        test_logits = probe(X_test)
        test_pred = test_logits.argmax(dim=-1)
        train_correct = (train_pred == y_train).float()
        test_correct = (test_pred == y_test).float()
    return {
        "probe": probe,
        "train_acc": train_correct.mean().item(),
        "test_acc": test_correct.mean().item(),
        "test_correct": test_correct.numpy(),
        "test_pred": test_pred.numpy(),
        "test_logits": test_logits.detach(),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
    }


def bootstrap_ci(
    correct: np.ndarray, n_boot: int = 2000, seed: int = 0, alpha: float = 0.05
) -> tuple[float, float, float]:
    """(point_estimate, lo, hi) 95%-by-default bootstrap CI on a 0/1
    correctness array's mean (accuracy)."""
    rng = np.random.RandomState(seed)
    n = len(correct)
    if n == 0:
        return 0.0, 0.0, 0.0
    boot = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.randint(0, n, n)
        boot[b] = correct[idx].mean()
    lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(correct.mean()), float(lo), float(hi)


# ---------------------------------------------------------------------------
# Correlation (no scipy available): Pearson + Spearman from scratch.
# ---------------------------------------------------------------------------


def _rankdata(x: np.ndarray) -> np.ndarray:
    """Average-rank ranking (ties get the mean of their tied rank range),
    scipy.stats.rankdata's default behavior, reimplemented since scipy is
    not installed in this repo's .venv."""
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=np.float64)
    sorted_x = x[order]
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and sorted_x[j + 1] == sorted_x[i]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        ranks[order[i : j + 1]] = avg_rank
        i = j + 1
    return ranks


def pearsonr(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xc = x - x.mean()
    yc = y - y.mean()
    denom = np.sqrt((xc**2).sum()) * np.sqrt((yc**2).sum())
    if denom == 0:
        return 0.0
    return float((xc * yc).sum() / denom)


def spearmanr(x: np.ndarray, y: np.ndarray) -> float:
    return pearsonr(_rankdata(np.asarray(x)), _rankdata(np.asarray(y)))


# ---------------------------------------------------------------------------
# Decoder step-wise hidden-state capture (deliverable 3: early-decision-
# in-decoding). Runs a fixed number of greedy-decode steps (no early
# break on all-finished) so every example contributes a hidden state at
# every step t, for a clean accuracy-vs-t curve.
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _capture_decoder_output(model: D1Transformer):
    box: dict[str, torch.Tensor | None] = {"value": None}

    def hook(module, inputs, output):
        box["value"] = output

    handle = model.decoder.register_forward_hook(hook)
    try:
        yield box
    finally:
        handle.remove()


@torch.no_grad()
def decode_with_step_hidden(
    model: D1Transformer, src_ids: torch.Tensor, max_steps: int
) -> tuple[torch.Tensor, torch.Tensor]:
    """Greedy-decode `max_steps` tokens (no early stopping), capturing the
    decoder's hidden state (pre output-projection) at the last position
    after each step. Returns (step_hidden, generated):
      step_hidden: (T=max_steps, B, D) -- step_hidden[t] is the hidden
        state that produced token t+1 (t=0 is the state right after BOS,
        using ONLY encoder cross-attention -- no decoded trajectory
        tokens exist yet).
      generated: (B, max_steps+1) token ids including the leading BOS.
    """
    model.eval()
    device = src_ids.device
    memory, src_padding_mask = model.encode(src_ids)
    batch_size = src_ids.size(0)
    generated = torch.full((batch_size, 1), BOS_ID, dtype=torch.long, device=device)
    step_hidden = []
    with _capture_decoder_output(model) as box:
        for _ in range(max_steps):
            logits = model.decode_step(generated, memory, src_padding_mask)
            hidden = box["value"]
            assert hidden is not None
            step_hidden.append(hidden[:, -1, :].detach().clone())
            next_ids = logits[:, -1, :].argmax(dim=-1)
            generated = torch.cat([generated, next_ids.unsqueeze(1)], dim=1)
    return torch.stack(step_hidden, dim=0), generated


def probe_direction_scores(probe: nn.Linear, X: torch.Tensor) -> np.ndarray:
    """Scalar 'reducible-ness' score along the trained probe's decision
    direction: logit(class=reducible) - logit(class=not-reducible)."""
    with torch.no_grad():
        logits = probe(X.float())
        score = logits[:, 1] - logits[:, 0]
    return score.numpy()
