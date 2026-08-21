#!/usr/bin/env python3
"""Mine THEOREM-CANDIDATE conditions: short conjunctions of threshold
predicates over the pooled feature libraries (arrangement H5 features from
`fourcolor.d1_features`, structural candidates + shallow features from
`fourcolor.d1_interp`, plus ring size `r`) that are ZERO-false-positive
sufficient conditions for D-reducibility -- and the dual, zero-false-
positive sufficient conditions for NON-reducibility -- against the ENTIRE
labeled pool assembled here (data/d1_corpus.jsonl + data/v2/traces_r{8,9,
10}.jsonl + data/configs_r*.jsonl, deduped by `fourcolor.canonical.
canonical_key`).

Every source file already carries a ground-truth `d_reducible` label
(computed by fourcolor.reduce / the differential oracle pipeline
elsewhere in this repo -- see those files' own docstrings), so this tool
does not re-run the reducibility checker; it only pools, dedups, extracts
features, and searches.

Rule space (task spec): conjunctions of at most 3 atomic predicates, each
`feature >= t`, `feature <= t`, or `feature == v`, thresholds drawn from
each feature's own observed value grid (capped -- see `build_atoms` --
to keep the atom count, and hence the O(A^2) pairwise search, tractable).
Enumeration is fully vectorized:
  * All A atoms are evaluated once into a dense (A, N) boolean matrix `M`.
  * Level 1 (single atoms): reduces to two column-sums (per class).
  * Level 2 (pairs): the ENTIRE A x A false-positive-count and coverage-
    count matrices are each a single matmul, `M_neg @ M_neg.T` /
    `M_pos @ M_pos.T` (a pair's FP count is exactly the dot product of its
    two atoms' boolean rows restricted to the negative class -- AND of
    0/1 masks is elementwise product, and summing a product is a dot
    product) -- so all ~A^2/2 pairs are scored in one BLAS call each.
  * Level 3 (triples): would need an A^3 tensor to do the same trick
    densely, which is not worth materializing. Instead, for each
    "promising" pair (one that is CLOSE to zero-FP already -- small
    nonzero FP count, decent coverage -- zero-FP pairs are dominated
    candidates for extension, see the minimality note below) we AND its
    mask down to one boolean vector and multiply that single vector
    against the WHOLE atom matrix (`M_neg @ pair_mask`) -- one matrix-
    vector product gives the FP count of every possible third atom at
    once. This is the same trick one level down, applied per promising
    pair rather than densely over all triples.

Minimality / irredundancy filter: a k-atom zero-FP rule is only reported
if NONE of its proper sub-conjunctions (already fully enumerated at a
shallower level, so this is an O(1) matrix lookup) is itself zero-FP --
otherwise the extra atom(s) are provably not doing any work (removing
them cannot increase the false-positive count and cannot decrease
coverage), so the shorter rule already dominates it. This keeps the
reported list to genuinely irreducible sufficient conditions.

See results/theorem/candidates.md for the final write-up (top-3 rules as
plain-language statements with witnesses) and results/theorem/
mining_results.json for the full ranked lists, per-ring breakdowns, and
5-fold cross-validation honesty check.

Usage:
    .venv/bin/python tools/mine_sound_rules.py
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from fourcolor import d1_interp as di  # noqa: E402
from fourcolor import d1_features as dfeat  # noqa: E402
from fourcolor.canonical import canonical_key  # noqa: E402

# ---------------------------------------------------------------------------
# Combined feature library: shallow (includes ring size `r`) + structural
# candidates (minus n_consistent -- tautological: n_consistent == 0 <=>
# d_reducible by fourcolor.reduce's own definition; see tools/
# d1_interrogate.py's TAUTOLOGICAL_CANDIDATES and tools/d1v2_interrogate.py's
# STRUCTURAL_CANDIDATE_NAMES, which this mirrors) + the arrangement (H5)
# features. No name collisions across the three libraries.
# ---------------------------------------------------------------------------

STRUCTURAL_CANDIDATE_NAMES = [n for n in di.STRUCTURAL_FEATURE_NAMES if n != "n_consistent"]
FEATURE_NAMES: list[str] = (
    list(di.SHALLOW_FEATURE_NAMES) + list(STRUCTURAL_CANDIDATE_NAMES) + list(dfeat.ARRANGEMENT_FEATURE_NAMES)
)

DEFAULT_POOL_FILES = (
    [ROOT / "data" / "d1_corpus.jsonl"]
    + sorted((ROOT / "data" / "v2").glob("traces_r*.jsonl"))
    + sorted((ROOT / "data").glob("configs_r*.jsonl"))
)


def compute_feature_vector(
    adjacency: dict[int, list[int]], r: int, n: int, n_extendable: float, n_consistent: float
) -> list[float]:
    feats: dict[str, float] = {}
    feats.update(di.shallow_features(adjacency, r, n))
    feats.update(di.structural_candidates(adjacency, r, n, n_extendable, n_consistent))
    feats.update(dfeat.arrangement_features(adjacency, r, n))
    return [feats[name] for name in FEATURE_NAMES]


# ---------------------------------------------------------------------------
# Pooling + dedup
# ---------------------------------------------------------------------------


def load_pool(files: list[Path] | None = None) -> tuple[list[dict], dict]:
    """Pools every record in `files` (default: DEFAULT_POOL_FILES), dedups
    by fourcolor.canonical.canonical_key (computed if a source file doesn't
    already carry one), and precomputes each surviving record's combined
    feature vector. Raises AssertionError if the same canonical key carries
    conflicting d_reducible labels across sources (would indicate a data
    integrity bug, not expected on this pool)."""
    files = list(files) if files is not None else list(DEFAULT_POOL_FILES)
    pool: dict[str, dict] = {}
    n_raw = 0
    conflicts: list[tuple] = []
    for path in files:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                n_raw += 1
                rec = json.loads(line)
                adjacency = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
                r, n = rec["r"], rec["n"]
                ck = rec.get("canonical_key") or canonical_key(adjacency, r, n)
                d_red = bool(rec["d_reducible"])
                src = rec.get("source", path.stem)
                if ck in pool:
                    if pool[ck]["d_reducible"] != d_red:
                        conflicts.append((ck, pool[ck]["ident"], rec.get("ident"), path.name))
                    pool[ck]["dup_sources"].append(f"{path.name}:{src}")
                    continue
                feats = compute_feature_vector(adjacency, r, n, rec["n_extendable"], rec["n_consistent"])
                pool[ck] = {
                    "canonical_key": ck,
                    "ident": rec.get("ident"),
                    "r": r,
                    "n": n,
                    "d_reducible": d_red,
                    "features": feats,
                    "source_file": path.name,
                    "source": src,
                    "dup_sources": [],
                }
    if conflicts:
        raise AssertionError(
            f"{len(conflicts)} canonical-key label conflicts across pooled sources "
            f"(first 5: {conflicts[:5]})"
        )
    stats = {"n_raw": n_raw, "n_deduped": len(pool), "n_conflicts": len(conflicts), "n_files": len(files)}
    return list(pool.values()), stats


def load_raw_source(path: Path, source_filter: str | None = None) -> list[dict]:
    """Loads one JSONL file's records directly (no pooling/dedup), each with
    its combined feature vector precomputed -- used for the nl4ct_pool
    honesty check, which needs the RAW population (not the deduped pool,
    which may have folded some nl4ct_pool records into other sources'
    canonical-key groups)."""
    out = []
    with path.open() as f:
        for line in f:
            rec = json.loads(line)
            if source_filter is not None and rec.get("source") != source_filter:
                continue
            adjacency = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
            r, n = rec["r"], rec["n"]
            feats = compute_feature_vector(adjacency, r, n, rec["n_extendable"], rec["n_consistent"])
            out.append({
                "ident": rec.get("ident"),
                "r": r,
                "n": n,
                "d_reducible": bool(rec["d_reducible"]),
                "features": feats,
            })
    return out


def pool_to_matrices(records: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    X = np.asarray([rec["features"] for rec in records], dtype=np.float64)
    y = np.asarray([rec["d_reducible"] for rec in records], dtype=bool)
    ring = np.asarray([rec["r"] for rec in records], dtype=np.int64)
    return X, y, ring


# ---------------------------------------------------------------------------
# Atoms
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Atom:
    feature_idx: int
    feature_name: str
    op: str  # "ge", "le", "eq"
    value: float

    def holds(self, x: np.ndarray) -> np.ndarray:
        col = x[:, self.feature_idx]
        if self.op == "ge":
            return col >= self.value
        if self.op == "le":
            return col <= self.value
        return col == self.value

    def slack(self, col: np.ndarray) -> np.ndarray:
        """Non-negative distance from `col` to this atom's threshold: how
        much room a satisfying value has before it would violate the atom.
        `==` atoms are always exactly at their own boundary (slack 0)."""
        if self.op == "ge":
            return col - self.value
        if self.op == "le":
            return self.value - col
        return np.zeros_like(col)

    def __str__(self) -> str:
        sym = {"ge": ">=", "le": "<=", "eq": "=="}[self.op]
        v = self.value
        v = int(v) if float(v).is_integer() else v
        return f"{self.feature_name} {sym} {v}"


def rule_str(atoms: tuple[Atom, ...]) -> str:
    return " AND ".join(str(a) for a in atoms)


def build_atoms(
    X: np.ndarray, feature_names: list[str], eq_cap: int = 20, ge_cap: int = 15, le_cap: int = 15
) -> list[Atom]:
    """One Atom per (feature, op, threshold) from that feature's own
    observed-value grid. Low-cardinality features (<= eq_cap distinct
    observed values -- true of every count/degree/ring-size feature in
    this library) get an `==` atom per value; every feature gets `>=`/`<=`
    atoms at up to ge_cap/le_cap thresholds (the full unique-value grid if
    it's already that short, else evenly-spaced quantile picks of it) --
    caps keep the atom count, and hence the O(A^2) pairwise search below,
    bounded regardless of how many distinct floating-point values a
    near-continuous feature (e.g. h5_density) happens to take."""
    atoms: list[Atom] = []
    for f, name in enumerate(feature_names):
        u = np.unique(X[:, f])
        if len(u) <= 1:
            continue
        if len(u) <= eq_cap:
            for v in u:
                atoms.append(Atom(f, name, "eq", float(v)))

        ge_vals = u[1:]  # exclude min: ">= min" is trivially all-true
        if len(ge_vals) > ge_cap:
            idx = np.unique(np.round(np.linspace(0, len(ge_vals) - 1, ge_cap)).astype(int))
            ge_vals = ge_vals[idx]
        for v in ge_vals:
            atoms.append(Atom(f, name, "ge", float(v)))

        le_vals = u[:-1]  # exclude max: "<= max" is trivially all-true
        if len(le_vals) > le_cap:
            idx = np.unique(np.round(np.linspace(0, len(le_vals) - 1, le_cap)).astype(int))
            le_vals = le_vals[idx]
        for v in le_vals:
            atoms.append(Atom(f, name, "le", float(v)))
    return atoms


def evaluate_atoms(X: np.ndarray, atoms: list[Atom]) -> np.ndarray:
    """Dense (len(atoms), N) boolean satisfaction matrix."""
    M = np.empty((len(atoms), X.shape[0]), dtype=bool)
    for i, a in enumerate(atoms):
        M[i] = a.holds(X)
    return M


def rule_mask(M: np.ndarray, atom_indices: tuple[int, ...]) -> np.ndarray:
    return functools.reduce(np.logical_and, (M[i] for i in atom_indices))


# ---------------------------------------------------------------------------
# Mining
# ---------------------------------------------------------------------------


@dataclass
class RuleResult:
    atom_indices: tuple[int, ...]
    atoms: tuple[Atom, ...]
    depth: int
    fp: int
    coverage: int

    def as_dict(self) -> dict:
        return {
            "rule": rule_str(self.atoms),
            "depth": self.depth,
            "fp": self.fp,
            "coverage": self.coverage,
            "atom_indices": list(self.atom_indices),
        }


def mine_rules(
    M: np.ndarray,
    target: np.ndarray,
    atoms: list[Atom],
    row_mask: np.ndarray | None = None,
    max_depth: int = 3,
    promising_fp_cap: int = 60,
    promising_pair_limit: int = 4000,
) -> list[RuleResult]:
    """Every MINIMAL (irredundant -- see module docstring) zero-false-
    positive rule of depth <= max_depth, sufficient for `target` (a
    boolean array over the same N columns as M): `target[c]` is the
    "positive" class (d_reducible for the main search, ~d_reducible for
    the dual non-reducibility search). Sorted by (coverage desc, depth
    asc). `row_mask` restricts scoring to a row subset (the 5-fold CV
    honesty check's train folds) without needing to re-slice/rebuild M."""
    N = M.shape[1]
    if row_mask is None:
        row_mask = np.ones(N, dtype=bool)
    pos = target & row_mask
    neg = (~target) & row_mask
    Mpos = M[:, pos].astype(np.float32)
    Mneg = M[:, neg].astype(np.float32)

    FP1 = Mneg.sum(axis=1)
    Cov1 = Mpos.sum(axis=1)

    results: list[RuleResult] = []
    for i in range(len(atoms)):
        if FP1[i] == 0 and Cov1[i] > 0:
            results.append(RuleResult((i,), (atoms[i],), 1, 0, int(Cov1[i])))

    if max_depth < 2 or len(atoms) < 2 or Mpos.shape[1] == 0 or Mneg.shape[1] == 0:
        return sorted(results, key=lambda r: (-r.coverage, r.depth))

    FP2 = Mneg @ Mneg.T
    Cov2 = Mpos @ Mpos.T
    A = len(atoms)
    iu, ju = np.triu_indices(A, k=1)
    fp2_flat = FP2[iu, ju]
    cov2_flat = Cov2[iu, ju]

    zero_pair = np.nonzero((fp2_flat == 0) & (cov2_flat > 0))[0]
    for idx in zero_pair:
        i, j = int(iu[idx]), int(ju[idx])
        if FP1[i] > 0 and FP1[j] > 0:  # minimality: both singles must fail alone
            results.append(RuleResult((i, j), (atoms[i], atoms[j]), 2, 0, int(cov2_flat[idx])))

    if max_depth < 3:
        return sorted(results, key=lambda r: (-r.coverage, r.depth))

    promising = np.nonzero((fp2_flat > 0) & (fp2_flat <= promising_fp_cap) & (cov2_flat > 0))[0]
    if len(promising) > promising_pair_limit:
        order = np.argsort(-cov2_flat[promising])[:promising_pair_limit]
        promising = promising[order]

    seen: set[tuple[int, int, int]] = set()
    for idx in promising:
        i, j = int(iu[idx]), int(ju[idx])
        mask_ij_neg = Mneg[i] * Mneg[j]
        mask_ij_pos = Mpos[i] * Mpos[j]
        fp3 = Mneg @ mask_ij_neg  # (A,) FP count of every possible 3rd atom k, one matvec
        cov3 = Mpos @ mask_ij_pos  # (A,) coverage count of every possible 3rd atom k
        for k in np.nonzero((fp3 == 0) & (cov3 > 0))[0]:
            k = int(k)
            if k == i or k == j:
                continue
            if FP1[k] == 0 or FP2[i, k] == 0 or FP2[j, k] == 0:
                continue  # minimality: every proper sub-conjunction must fail alone
            trip = tuple(sorted((i, j, k)))
            if trip in seen:
                continue
            seen.add(trip)
            results.append(RuleResult(trip, tuple(atoms[t] for t in trip), 3, 0, int(cov3[k])))

    return sorted(results, key=lambda r: (-r.coverage, r.depth))


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------


def per_ring_breakdown(mask: np.ndarray, target: np.ndarray, ring: np.ndarray) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for rr in sorted(set(ring.tolist())):
        ring_mask = ring == rr
        total_target = int((ring_mask & target).sum())
        if total_target == 0:
            continue
        covered = int((ring_mask & mask & target).sum())
        out[int(rr)] = {"covered": covered, "total_target_in_ring": total_target}
    return out


def rule_witnesses(
    X: np.ndarray, records: list[dict], atoms: tuple[Atom, ...], mask: np.ndarray, target: np.ndarray, top_n: int = 5
) -> list[dict]:
    """The `top_n` satisfying-and-target-class configs with the SMALLEST
    margin (min over the rule's atoms of that atom's slack) -- i.e. the
    configs where a proof attempt / new-data verification is most likely
    to break, because at least one predicate is barely satisfied."""
    idx = np.nonzero(mask & target)[0]
    if len(idx) == 0:
        return []
    slacks = np.stack([a.slack(X[idx, a.feature_idx]) for a in atoms], axis=0)
    margin = slacks.min(axis=0)
    order = np.argsort(margin)[:top_n]
    out = []
    for o in order:
        i = int(idx[o])
        rec = records[i]
        out.append({
            "ident": rec["ident"],
            "source": rec.get("source"),
            "r": rec["r"],
            "n": rec["n"],
            "margin": float(margin[o]),
            "atom_values": {a.feature_name: float(X[i, a.feature_idx]) for a in atoms},
        })
    return out


def kfold_indices(n: int, k: int = 5, seed: int = 0) -> list[np.ndarray]:
    rng = np.random.RandomState(seed)
    idx = rng.permutation(n)
    return [np.sort(fold) for fold in np.array_split(idx, k)]


# ---------------------------------------------------------------------------
# Feature variants: FULL (every feature the task spec lists, including
# n_extendable/n_extendable_ratio) and STRUCTURAL (drops n_extendable and
# n_extendable_ratio). n_extendable is not tautological with d_reducible
# the way n_consistent is (already excluded -- see STRUCTURAL_CANDIDATE_
# NAMES), but it IS the output of running most of fourcolor.reduce's own
# coloring-extension search on the config -- a "sufficient condition"
# expressed in terms of it is not checkable by graph inspection alone, so
# it is not a genuine theorem-candidate predicate in the sense this task
# wants (see the FULL-vs-STRUCTURAL split below and results/theorem/
# candidates.md's design-decision note). Both are mined and reported;
# candidates.md's top-3 plain-language write-up uses STRUCTURAL only.
# ---------------------------------------------------------------------------

LEAKY_FEATURE_NAMES = {"n_extendable", "n_extendable_ratio"}


def feature_variant(name: str) -> tuple[list[int], list[str]]:
    if name == "full":
        idx = list(range(len(FEATURE_NAMES)))
    elif name == "structural":
        idx = [i for i, n in enumerate(FEATURE_NAMES) if n not in LEAKY_FEATURE_NAMES]
    else:
        raise ValueError(name)
    return idx, [FEATURE_NAMES[i] for i in idx]


@dataclass
class Variant:
    name: str
    feature_idx: list[int]
    feature_names: list[str]
    X: np.ndarray
    atoms: list[Atom]
    M: np.ndarray


def build_variant(name: str, X_full: np.ndarray) -> Variant:
    idx, names = feature_variant(name)
    X = X_full[:, idx]
    atoms = build_atoms(X, names)
    M = evaluate_atoms(X, atoms)
    return Variant(name, idx, names, X, atoms, M)


# ---------------------------------------------------------------------------
# Cross-validation honesty check
# ---------------------------------------------------------------------------


def cross_validate(
    variant: Variant, target: np.ndarray, k: int = 5, seed: int = 0, top_k_per_fold: int = 3, **mine_kwargs
) -> list[dict]:
    """For each of k folds: mines (target's zero-FP minimal rules) using
    ONLY the other k-1 folds, then evaluates the resulting top-`top_k_
    per_fold` rules' false-positive/coverage counts on the untouched held-
    out fold -- the real leakage test (unlike checking a full-pool-mined
    rule on a subset of the pool it was already guaranteed zero-FP on,
    which is trivially safe by monotonicity and proves nothing)."""
    N = variant.M.shape[1]
    folds = kfold_indices(N, k=k, seed=seed)
    out = []
    for fi, test_idx in enumerate(folds):
        test_mask = np.zeros(N, dtype=bool)
        test_mask[test_idx] = True
        train_mask = ~test_mask
        fold_rules = mine_rules(variant.M, target, variant.atoms, row_mask=train_mask, **mine_kwargs)
        for rank, rule in enumerate(fold_rules[:top_k_per_fold], start=1):
            mask = rule_mask(variant.M, rule.atom_indices)
            test_fp = int((mask & test_mask & ~target).sum())
            test_cov = int((mask & test_mask & target).sum())
            out.append({
                "fold": fi,
                "fold_rank": rank,
                "rule": rule_str(rule.atoms),
                "atom_indices": list(rule.atom_indices),
                "train_coverage": rule.coverage,
                "test_fp": test_fp,
                "test_coverage": test_cov,
            })
    return out


def rule_rank_across_folds(
    variant: Variant, target: np.ndarray, atom_indices: tuple[int, ...], k: int = 5, seed: int = 0, **mine_kwargs
) -> list[dict]:
    """For ONE specific rule (an atom-index tuple, e.g. one of the final
    top-3 candidates chosen from full-pool mining), checks -- independently
    per fold, mining on that fold's 4/5 training rows only -- where this
    exact conjunction would have ranked among the training-only zero-FP
    minimal rules (discoverability: would an analyst who only ever saw 80%
    of the pool have surfaced this same candidate?), or whether it was
    "subsumed" (a proper subset of its atoms was independently zero-FP on
    that fold's training rows, which is a legitimate minimality-filter
    artifact of a smaller sample, not evidence against the rule)."""
    N = variant.M.shape[1]
    folds = kfold_indices(N, k=k, seed=seed)
    target_set = frozenset(atom_indices)
    out = []
    for fi, test_idx in enumerate(folds):
        test_mask = np.zeros(N, dtype=bool)
        test_mask[test_idx] = True
        train_mask = ~test_mask
        fold_rules = mine_rules(variant.M, target, variant.atoms, row_mask=train_mask, **mine_kwargs)
        rank = None
        for pos, cand in enumerate(fold_rules, start=1):
            if frozenset(cand.atom_indices) == target_set:
                rank = pos
                break
        subsumed_by = None
        if rank is None:
            for cand in fold_rules:
                if frozenset(cand.atom_indices) < target_set:
                    subsumed_by = rule_str(cand.atoms)
                    break
        out.append({"fold": fi, "rank_among_fold_minimal_rules": rank, "subsumed_by": subsumed_by})
    return out


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def summarize_rule(
    variant: Variant, records: list[dict], rule: RuleResult, target: np.ndarray, ring: np.ndarray, witnesses_n: int = 5
) -> dict:
    mask = rule_mask(variant.M, rule.atom_indices)
    d = rule.as_dict()
    d["per_ring"] = per_ring_breakdown(mask, target, ring)
    d["witnesses"] = rule_witnesses(variant.X, records, rule.atoms, mask, target, top_n=witnesses_n)
    return d


def dedup_rules_by_mask(M: np.ndarray, rules: list[RuleResult], limit: int) -> list[RuleResult]:
    """Keeps the first (highest-ranked, since `rules` is already sorted by
    coverage desc/depth asc) rule for each DISTINCT satisfying bitmask,
    dropping later ones with an identical mask. Needed because this
    feature library has literal duplicates under different names (e.g.
    shallow's `deg_5` and structural's `n_deg5_total` are both "count of
    full-graph degree-5 vertices" -- see FEATURE_NAMES), so syntactically
    different rules can define the exact same satisfying set and otherwise
    burn multiple slots in a top-K list on what is really one rule."""
    seen: set[bytes] = set()
    out: list[RuleResult] = []
    for rule in rules:
        mask = rule_mask(M, rule.atom_indices)
        key = mask.tobytes()
        if key in seen:
            continue
        seen.add(key)
        out.append(rule)
        if len(out) >= limit:
            break
    return out


def evaluate_rule_on_population(mask_source_X: np.ndarray, rule: RuleResult) -> np.ndarray:
    """Boolean satisfaction mask of `rule` over an EXTERNAL feature matrix
    that is already restricted to the same variant's columns, same order,
    as the atoms' `feature_idx` values expect."""
    return functools.reduce(np.logical_and, (a.holds(mask_source_X) for a in rule.atoms))


def nl4ct_pool_check(variant: Variant, reducible_top: list[RuleResult], nonreducible_top: list[RuleResult]) -> dict:
    """Loads the RAW 4828 nl4ct_pool records directly out of data/
    d1_corpus.jsonl (source == 'nl4ct_pool', not the deduped pool -- see
    `load_raw_source`'s docstring) -- all reducible by construction. Any
    reducible-sufficient rule satisfied there is a coverage data point
    only (can't be a false positive: the population is 100% reducible).
    Any NON-reducibility-sufficient rule satisfied there IS a hard false
    positive and would falsify that rule; checked explicitly."""
    raw = load_raw_source(ROOT / "data" / "d1_corpus.jsonl", source_filter="nl4ct_pool")
    Xraw = np.asarray([rec["features"] for rec in raw], dtype=np.float64)[:, variant.feature_idx]
    n = len(raw)
    red = []
    for rule in reducible_top:
        mask = evaluate_rule_on_population(Xraw, rule)
        red.append({"rule": rule_str(rule.atoms), "hits": int(mask.sum()), "n": n})
    nonred = []
    for rule in nonreducible_top:
        mask = evaluate_rule_on_population(Xraw, rule)
        nonred.append({"rule": rule_str(rule.atoms), "false_positives": int(mask.sum()), "n": n})
    return {"n_nl4ct_pool_raw": n, "reducible_rules_coverage": red, "nonreducible_rules_false_positives": nonred}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=str, default=str(ROOT / "results" / "theorem"))
    ap.add_argument("--top-reducible", type=int, default=20)
    ap.add_argument("--top-nonreducible", type=int, default=10)
    ap.add_argument("--promising-fp-cap", type=int, default=60)
    ap.add_argument("--promising-pair-limit", type=int, default=4000)
    ap.add_argument("--cv-folds", type=int, default=5)
    ap.add_argument("--cv-top-k-per-fold", type=int, default=3)
    ap.add_argument("--witnesses", type=int, default=5)
    ap.add_argument("--skip-full-variant-cv", action="store_true", help="skip CV for the 'full' feature variant (saves time; structural variant CV always runs)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading + pooling + deduping...", flush=True)
    records, pool_stats = load_pool()
    print(f"  {pool_stats}")
    X_full, y, ring = pool_to_matrices(records)
    mine_kwargs = dict(promising_fp_cap=args.promising_fp_cap, promising_pair_limit=args.promising_pair_limit)

    pool_stats["per_ring"] = {
        int(rr): {
            "total": int((ring == rr).sum()),
            "reducible": int(((ring == rr) & y).sum()),
            "nonreducible": int(((ring == rr) & ~y).sum()),
        }
        for rr in sorted(set(ring.tolist()))
    }

    result: dict = {"pool_stats": pool_stats, "feature_names_full": FEATURE_NAMES, "variants": {}}

    variants = {name: build_variant(name, X_full) for name in ("structural", "full")}

    for vname, variant in variants.items():
        print(f"\n=== variant={vname} (n_atoms={len(variant.atoms)}) ===", flush=True)
        red_rules = mine_rules(variant.M, y, variant.atoms, **mine_kwargs)
        nonred_rules = mine_rules(variant.M, ~y, variant.atoms, **mine_kwargs)
        print(f"  reducible-sufficient: {len(red_rules)} minimal zero-FP rules found")
        print(f"  nonreducible-sufficient (dual): {len(nonred_rules)} minimal zero-FP rules found")

        top_red = dedup_rules_by_mask(variant.M, red_rules, args.top_reducible)
        top_nonred = dedup_rules_by_mask(variant.M, nonred_rules, args.top_nonreducible)

        red_summaries = [summarize_rule(variant, records, r, y, ring, args.witnesses) for r in top_red]
        nonred_summaries = [summarize_rule(variant, records, r, ~y, ring, args.witnesses) for r in top_nonred]

        do_cv = vname == "structural" or not args.skip_full_variant_cv
        cv_red = cv_nonred = []
        if do_cv:
            print("  cross-validating (reducible direction)...", flush=True)
            cv_red = cross_validate(variant, y, k=args.cv_folds, top_k_per_fold=args.cv_top_k_per_fold, **mine_kwargs)
            print("  cross-validating (nonreducible dual)...", flush=True)
            cv_nonred = cross_validate(variant, ~y, k=args.cv_folds, top_k_per_fold=args.cv_top_k_per_fold, **mine_kwargs)

        nl4ct = nl4ct_pool_check(variant, top_red[:5], top_nonred[:5])

        result["variants"][vname] = {
            "n_atoms": len(variant.atoms),
            "feature_names": variant.feature_names,
            "n_reducible_minimal_rules_total": len(red_rules),
            "n_nonreducible_minimal_rules_total": len(nonred_rules),
            "reducible_top": red_summaries,
            "nonreducible_top": nonred_summaries,
            "cross_validation": {"reducible": cv_red, "nonreducible": cv_nonred},
            "nl4ct_pool_check": nl4ct,
        }

        print(f"  top reducible rule: {red_summaries[0]['rule'] if red_summaries else '(none)'}")
        print(f"  top nonreducible rule: {nonred_summaries[0]['rule'] if nonred_summaries else '(none)'}")

        if vname == "structural":
            struct = variant
            top3 = top_red[:3]  # dedup_rules_by_mask is prefix-consistent across limits

    # Per-fold rank-tracking for the final top-3 (structural variant, reducible
    # direction) -- the "would this specific candidate be discoverable/robust
    # from only 80% of the data" check, feeding results/theorem/candidates.md.
    print("\nRanking final top-3 structural reducible rules across CV folds...", flush=True)
    top3_fold_ranks = []
    for rule in top3:
        ranks = rule_rank_across_folds(struct, y, rule.atom_indices, k=args.cv_folds, **mine_kwargs)
        top3_fold_ranks.append({"rule": rule_str(rule.atoms), "atom_indices": list(rule.atom_indices), "fold_ranks": ranks})
    result["final_top3_structural_reducible_fold_ranks"] = top3_fold_ranks

    # Dense-ring supplementary analysis: rings 8-11 are the only ones with
    # deep, roughly-balanced ADVERSARIAL negative-example coverage (plantri-
    # exhaustive generation, see tools/d1v2_datagen.py + data/configs_r*.jsonl)
    # -- rings 15-16 have ZERO non-reducible examples anywhere in the pool
    # (see pool_stats["per_ring"]: both are 100% reducible), and rings 12-14
    # are >=90% reducible, because those large-ring populations are almost
    # entirely the historical CURATED sets (rsst633/steinberger2822/
    # nl4ct_pool -- configurations already known/published as reducible, not
    # an exhaustive search that could have turned up counterexamples). A
    # full-pool zero-FP rule that only fires at large rings is a completely
    # honest claim against the data actually assembled here, but it is much
    # weaker evidence of a genuine invariant than a rule that has survived
    # contact with a real adversarial negative population. This mines
    # separately, scoring ONLY against rows with r in DENSE_RINGS, then
    # reports each surviving rule's behavior against the FULL pool too (it
    # is not guaranteed to still be zero-FP outside the dense-ring subset).
    DENSE_RINGS = (8, 9, 10, 11)
    dense_mask = np.isin(ring, DENSE_RINGS)
    print(
        f"\nDense-ring supplementary mining (r in {DENSE_RINGS}, "
        f"{int(dense_mask.sum())} configs, {int((dense_mask & y).sum())} reducible / "
        f"{int((dense_mask & ~y).sum())} not)...",
        flush=True,
    )
    dense_rules = mine_rules(struct.M, y, struct.atoms, row_mask=dense_mask, **mine_kwargs)
    dense_top = dedup_rules_by_mask(struct.M, dense_rules, 10)
    dense_summaries = []
    for rule in dense_top:
        mask_full = rule_mask(struct.M, rule.atom_indices)
        dense_summaries.append({
            "rule": rule_str(rule.atoms),
            "depth": rule.depth,
            "dense_subset_coverage": rule.coverage,
            "dense_subset_fp": rule.fp,
            "full_pool_fp": int((mask_full & ~y).sum()),
            "full_pool_coverage": int((mask_full & y).sum()),
            "per_ring_full_pool": per_ring_breakdown(mask_full, y, ring),
            "witnesses_full_pool": rule_witnesses(struct.X, records, rule.atoms, mask_full, y, top_n=args.witnesses),
        })
    result["dense_ring_definition"] = {
        "rings": list(DENSE_RINGS),
        "n": int(dense_mask.sum()),
        "n_reducible": int((dense_mask & y).sum()),
        "n_nonreducible": int((dense_mask & ~y).sum()),
    }
    result["dense_ring_reducible_top"] = dense_summaries
    print(f"  top dense-ring rule: {dense_summaries[0]['rule'] if dense_summaries else '(none)'}")

    with (out_dir / "mining_results.json").open("w") as f:
        json.dump(result, f, indent=2)
    print(f"\nWrote {out_dir / 'mining_results.json'}")

    write_candidates_md(out_dir, result, records, y, ring)
    print(f"Wrote {out_dir / 'candidates.md'}")
    return 0


def fmt_per_ring(per_ring: dict) -> str:
    parts = []
    for rr in sorted(per_ring, key=int):
        d = per_ring[str(rr)] if isinstance(rr, str) else per_ring[rr]
        parts.append(f"r={rr}: {d['covered']}/{d['total_target_in_ring']}")
    return "; ".join(parts)


def write_candidates_md(out_dir: Path, result: dict, records: list[dict], y: np.ndarray, ring: np.ndarray) -> None:
    lines: list[str] = []
    lines.append("# Theorem-candidate sufficient conditions for D-reducibility\n")
    lines.append(
        f"Mined from a pool of {result['pool_stats']['n_deduped']} distinct configurations "
        f"(deduped by `fourcolor.canonical.canonical_key` from {result['pool_stats']['n_raw']} raw "
        f"records across {result['pool_stats']['n_files']} source files: `data/d1_corpus.jsonl`, "
        "`data/v2/traces_r{8,9,10}.jsonl`, `data/configs_r*.jsonl`; 0 label conflicts found at "
        "matching canonical keys), rings 6-16, "
        f"{int(y.sum())} D-reducible / {int((~y).sum())} not, via `tools/mine_sound_rules.py`. "
        "See `results/theorem/mining_results.json` for the full ranked lists (top-20 reducible-"
        "sufficient / top-10 non-reducibility-sufficient rules, both the `structural` and `full` "
        "feature variants, 5-fold cross-validation, and the nl4ct_pool honesty check).\n"
    )
    lines.append(
        "**Design decision -- `structural` vs `full` feature variant**: the task's feature pool "
        "includes `n_extendable`/`n_extendable_ratio` (`fourcolor.d1_interp.STRUCTURAL_CANDIDATE_"
        "NAMES`, used verbatim from `tools/d1v2_interrogate.py`, minus only the tautological "
        "`n_consistent`). `n_extendable` is not tautological with the label the way `n_consistent` "
        "is, but it IS the output of running most of `fourcolor.reduce`'s own ring-coloring-"
        "extension search on the configuration -- a 'sufficient condition' phrased in terms of it "
        "is not checkable by graph inspection alone, so it does not read as a genuine theorem "
        "candidate. Both variants are mined (see the JSON for `full`); this write-up's top-3 use "
        "the **`structural`** variant only (`n_extendable`/`n_extendable_ratio` excluded -- every "
        "predicate below is a pure function of the configuration's ring size and adjacency "
        "structure).\n"
    )

    lines.append("## Pool composition caveat -- read this before the numbers below\n")
    lines.append(
        "Ring coverage in this pool is NOT uniform between 'exhaustively searched, adversarial' "
        "and 'curated, already-known-reducible': rings 8-11 have deep negative-example coverage "
        "(plantri-exhaustive generation over both boundary colorings and full configuration "
        "search -- see `data/configs_r*.jsonl` / `data/v2/traces_r{8,9,10}.jsonl`), but rings "
        "12-16 are almost entirely the historical CURATED sets (rsst633/steinberger2822/"
        "nl4ct_pool -- actual configurations from the published discharging rules, i.e. "
        "PRE-SELECTED to be reducible). Rings 15-16 have **zero** non-reducible examples anywhere "
        "in the pool. A rule that is zero-FP against the *whole pool* is an honest claim against "
        "the data actually assembled, but at rings >= 12 that claim has had essentially no chance "
        "to be falsified (there was no adversarial search there to generate a counterexample), so "
        "read the top-3 below (which, as their per-ring tables show, cover almost exclusively "
        "rings 13-16) with that in mind. See 'Dense-ring supplementary candidates' further down "
        "for rules validated specifically against the rings that DO have deep adversarial negative "
        "search coverage.\n"
    )
    lines.append("| ring | total | D-reducible | not D-reducible | frac reducible |")
    lines.append("|---|---|---|---|---|")
    for rr, d in sorted(result["pool_stats"]["per_ring"].items(), key=lambda kv: int(kv[0])):
        frac = d["reducible"] / d["total"] if d["total"] else 0.0
        lines.append(f"| {rr} | {d['total']} | {d['reducible']} | {d['nonreducible']} | {frac:.3f} |")
    lines.append("")

    struct = result["variants"]["structural"]
    top3 = struct["reducible_top"][:3]
    fold_rank_lookup = {tuple(d["atom_indices"]): d for d in result["final_top3_structural_reducible_fold_ranks"]}

    for i, rule in enumerate(top3):
        lines.append(f"## Candidate {i + 1}: `{rule['rule']}`\n")
        lines.append(
            f"**Statement.** Let K be a configuration (ring size r, n total vertices, degree-5 "
            f"interior subgraph H5 as defined in `fourcolor.d1_features`) satisfying "
            f"{rule['rule']}. Then, on the {result['pool_stats']['n_deduped']}-configuration pool "
            f"tested (rings 6-16), K is always D-reducible ({rule['coverage']} configurations "
            "satisfy this condition; 0 counterexamples).\n"
        )
        lines.append(f"- **Coverage**: {rule['coverage']} D-reducible configs overall (of {int(y.sum())} total D-reducible in the pool).")
        lines.append(f"- **Per-ring coverage** (covered / total-D-reducible-in-that-ring): {fmt_per_ring(rule['per_ring'])}")
        fr = fold_rank_lookup.get(tuple(rule["atom_indices"]))
        if fr:
            rank_str = ", ".join(
                f"fold {d['fold']}: " + (f"rank #{d['rank_among_fold_minimal_rules']}" if d["rank_among_fold_minimal_rules"] else f"subsumed by `{d['subsumed_by']}`" if d["subsumed_by"] else "not found")
                for d in fr["fold_ranks"]
            )
            lines.append(
                f"- **5-fold CV discoverability**: mining independently on each fold's 4/5 training "
                f"subset (blind to the held-out 1/5), this exact rule's rank among that fold's own "
                f"zero-FP minimal reducible-sufficient rules (by training coverage): {rank_str}."
            )
        lines.append("- **Witness configs nearest the boundary** (satisfying the rule with the smallest per-atom slack -- where a proof attempt should focus, and where new data is most likely to break the rule):")
        for w in rule["witnesses"]:
            vals = ", ".join(f"{k}={v:g}" for k, v in w["atom_values"].items())
            lines.append(f"  - `{w['ident']}` (source={w['source']}, r={w['r']}, n={w['n']}, margin={w['margin']:g}): {vals}")
        lines.append("")

    dd = result["dense_ring_definition"]
    lines.append("## Dense-ring supplementary candidates (r in {8,9,10,11}, the adversarially-searched rings)\n")
    lines.append(
        f"Mined with scoring restricted to the {dd['n']} configs at rings 8-11 "
        f"({dd['n_reducible']} D-reducible / {dd['n_nonreducible']} not -- the subset with real "
        "exhaustive negative-example coverage, per the caveat above), then each surviving rule is "
        "evaluated against the FULL pool for honesty (not guaranteed to stay zero-FP outside its "
        "mining subset). These are weaker in headline coverage than the top-3 above but rest on "
        "much more adversarially-tested ground.\n"
    )
    lines.append("| rule | dense-subset coverage/FP | full-pool coverage/FP | per-ring (full pool) |")
    lines.append("|---|---|---|---|")
    for r in result["dense_ring_reducible_top"][:5]:
        lines.append(
            f"| `{r['rule']}` | {r['dense_subset_coverage']}/{r['dense_subset_fp']} | "
            f"{r['full_pool_coverage']}/{r['full_pool_fp']} | {fmt_per_ring(r['per_ring_full_pool'])} |"
        )
    lines.append("")

    nl4ct = struct["nl4ct_pool_check"]
    lines.append("## nl4ct_pool cross-check\n")
    lines.append(
        f"All {nl4ct['n_nl4ct_pool_raw']} raw `nl4ct_pool` records (source=='nl4ct_pool' in "
        "`data/d1_corpus.jsonl`, loaded independently of the deduped pool above) are D-reducible "
        "by construction, so a reducible-sufficient rule firing there is only a coverage data "
        "point (cannot be a false positive); a non-reducibility-sufficient rule firing there WOULD "
        "be a hard false positive (falsifying that rule) -- checked explicitly, 0 found (see table "
        "below).\n"
    )
    lines.append("| rule | direction | hits on nl4ct_pool (n=%d) |" % nl4ct["n_nl4ct_pool_raw"])
    lines.append("|---|---|---|")
    for row in nl4ct["reducible_rules_coverage"][:3]:
        lines.append(f"| `{row['rule']}` | reducible-sufficient (coverage only) | {row['hits']} |")
    for row in nl4ct["nonreducible_rules_false_positives"][:3]:
        lines.append(f"| `{row['rule']}` | non-reducibility-sufficient (FP if >0) | {row['false_positives']} |")
    lines.append("")

    nonred_top = struct["nonreducible_top"][:1]
    if nonred_top:
        r0 = nonred_top[0]
        lines.append("## Bonus: strongest non-reducibility-sufficient dual rule\n")
        lines.append(
            f"`{r0['rule']}` -- {r0['coverage']} non-reducible configs covered, 0 false positives "
            f"(no D-reducible config in the pool satisfies it). Per-ring: {fmt_per_ring(r0['per_ring'])}.\n"
        )

    (out_dir / "candidates.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
