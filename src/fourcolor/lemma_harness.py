"""The THIRD CHECKER: machine-test a candidate mathematical statement about
configurations against the entire labeled corpus before anyone spends effort
proving it.

Motivation (03-MASS-LAW-PROGRAM.md, M2/M3, and the lesson from
results/theorem/stress_test.md): a plausible-looking lemma is cheap to state
and expensive to prove, and this repo already holds ~59k labeled
configurations that can refute a false one in under a second. Every mass-law
candidate -- forms of the Cap B(r,k), forms of the Threshold A(r), structural
implications feeding either -- goes through here first.

THREE MODES

  universal    P                 -- does P hold for EVERY config? Lists up to
                                   `limit` counterexamples with ident+source.
  implication  P implies Q       -- restricted to the P-population; reports
                                   support |P| (a vacuous "lemma" is flagged,
                                   not celebrated) and Q's counterexamples.
  bound        LHS <= RHS        -- does the bound hold, and HOW TIGHT is it?
                                   Per-ring min/max/gap statistics of the
                                   slack RHS-LHS, plus the tightest witness.

STATEMENT SYNTAX is a Python expression over one record `rec` with:

  rec.r rec.n rec.k rec.a rec.b rec.rounds rec.d_reducible   (scalar columns;
        k = n - r interior count, a = |Phi| = n_extendable, b = n_consistent)
  rec.ident rec.source rec.group                             (provenance)
  rec.adjacency rec.trace rec.set_trace rec.canonical_key    (lazy structure)
  rec.f('name') / rec.features['name']                       (lazy hand-features)
  and / or / not, the comparisons, arithmetic including **, plus
  abs log log2 exp sqrt floor ceil min max len sum any all,
  and the implication connective  `A implies B`  (equivalently `A => B`),
  which is right-associative and binds looser than everything else.

EVALUATION. A statement touching only the scalar columns is compiled twice:
once as written (per-record) and once AST-rewritten into numpy (and/or/not ->
&/|/logical_not, chained comparisons expanded), then evaluated vectorized over
the whole corpus in one shot -- and cross-checked against the per-record form
on a random sample, so the fast path can never silently disagree with the
honest one. A statement touching adjacency/trace/features falls back to
per-record evaluation, which lazily json-parses only the lines it reaches
(important: the v2 trace sources are ~460MB).

Every run's verdict is appended to `results/mass-law/lemma_log.jsonl` with a
timestamp-free content hash over (mode, statement, filter, corpus signature),
so the same check on the same corpus is the same receipt.
"""

from __future__ import annotations

import ast
import hashlib
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from fourcolor.lemma_corpus import ROOT, SCALAR_FIELDS, ConfigRecord, Corpus

LOG_PATH = ROOT / "results" / "mass-law" / "lemma_log.jsonl"

# The proven f(r) table (results/theorem/fr_table/THEOREM.md + M1).
F_TABLE = {8: 5, 9: 5, 10: 6, 11: 7, 12: 7, 13: 8}

# Names a statement may call. The vector column is None for helpers that
# have no elementwise numpy analogue -- using one forces the scalar path.
_SCALAR_FUNCS: dict[str, Any] = {
    "abs": abs,
    "min": min,
    "max": max,
    "len": len,
    "sum": sum,
    "any": any,
    "all": all,
    "int": int,
    "float": float,
    "round": round,
    "sorted": sorted,
    "set": set,
    "list": list,
    "tuple": tuple,
    "dict": dict,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "log": np.log,
    "log2": np.log2,
    "exp": np.exp,
    "sqrt": np.sqrt,
    "floor": np.floor,
    "ceil": np.ceil,
}
_VECTOR_FUNCS: dict[str, Any] = {
    "abs": np.abs,
    "log": np.log,
    "log2": np.log2,
    "exp": np.exp,
    "sqrt": np.sqrt,
    "floor": np.floor,
    "ceil": np.ceil,
    "minimum": np.minimum,
    "maximum": np.maximum,
    "where": np.where,
    "logical_not": np.logical_not,
}


class LemmaSyntaxError(ValueError):
    """Raised for a statement this harness refuses to evaluate."""


# ---------------------------------------------------------------------------
# `A implies B` -> implies(A, B)
# ---------------------------------------------------------------------------

_IMPLIES_WORD = re.compile(r"\bimplies\b")


def _top_level_implies(text: str) -> int | None:
    """Index of the first depth-0 `implies` / `=>` connective, or None."""
    depth = 0
    quote: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0:
            if ch == "=" and text.startswith("=>", i):
                return i
            if ch == "i" and _IMPLIES_WORD.match(text, i) and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
                return i
        i += 1
    return None


def desugar_implies(text: str) -> str:
    """Rewrite the infix implication connective into `implies(P, Q)` calls
    (right-associative, loosest binding)."""
    pos = _top_level_implies(text)
    if pos is None:
        return text
    width = 2 if text.startswith("=>", pos) else len("implies")
    left = text[:pos].strip()
    right = desugar_implies(text[pos + width :].strip())
    if not left or not right:
        raise LemmaSyntaxError(f"implication with an empty side: {text!r}")
    return f"implies({left}, {right})"


def split_implication(text: str) -> tuple[str, str] | None:
    """(antecedent, consequent) if the statement's top connective is an
    implication, else None -- lets the CLI report antecedent support."""
    pos = _top_level_implies(text)
    if pos is None:
        return None
    width = 2 if text.startswith("=>", pos) else len("implies")
    return text[:pos].strip(), text[pos + width :].strip()


def _implies_scalar(p: Any, q: Any) -> bool:
    return (not p) or bool(q)


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------


class _Vectorizer(ast.NodeTransformer):
    """Rewrites a boolean-valued scalar expression into numpy elementwise
    form. Raises LemmaSyntaxError on anything that cannot be vectorized, and
    the caller falls back to per-record evaluation."""

    def __init__(self) -> None:
        self.columns: set[str] = set()

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        vals = [self.visit(v) for v in node.values]
        op = ast.BitAnd() if isinstance(node.op, ast.And) else ast.BitOr()
        out = vals[0]
        for v in vals[1:]:
            out = ast.BinOp(left=out, op=op, right=v)
        return out

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        if isinstance(node.op, ast.Not):
            return ast.Call(
                func=ast.Name(id="logical_not", ctx=ast.Load()),
                args=[self.visit(node.operand)],
                keywords=[],
            )
        node.operand = self.visit(node.operand)
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        operands = [self.visit(node.left)] + [self.visit(c) for c in node.comparators]
        parts = [
            ast.Compare(left=operands[i], ops=[node.ops[i]], comparators=[operands[i + 1]])
            for i in range(len(node.ops))
        ]
        out = parts[0]
        for p in parts[1:]:
            out = ast.BinOp(left=out, op=ast.BitAnd(), right=p)
        return out

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        if isinstance(node.value, ast.Name) and node.value.id == "rec":
            if node.attr not in SCALAR_FIELDS:
                raise LemmaSyntaxError(f"rec.{node.attr} is not a vectorizable column")
            self.columns.add(node.attr)
            return ast.Name(id=f"_col_{node.attr}", ctx=ast.Load())
        raise LemmaSyntaxError("only `rec.<field>` attribute access is allowed")

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if not isinstance(node.func, ast.Name):
            raise LemmaSyntaxError("only plain function calls are allowed")
        name = node.func.id
        if name == "implies":
            if len(node.args) != 2:
                raise LemmaSyntaxError("implies() takes exactly two arguments")
            p = self.visit(node.args[0])
            q = self.visit(node.args[1])
            return ast.BinOp(
                left=ast.Call(func=ast.Name(id="logical_not", ctx=ast.Load()), args=[p], keywords=[]),
                op=ast.BitOr(),
                right=q,
            )
        if name not in _VECTOR_FUNCS:
            raise LemmaSyntaxError(f"{name}() has no elementwise form")
        node.args = [self.visit(a) for a in node.args]
        node.keywords = []
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in ("rec", "implies") or node.id in _VECTOR_FUNCS:
            return node
        raise LemmaSyntaxError(f"unknown name {node.id!r}")

    def generic_visit(self, node: ast.AST) -> ast.AST:
        allowed = (
            ast.Expression,
            ast.BinOp,
            ast.Constant,
            ast.Load,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.FloorDiv,
            ast.Mod,
            ast.Pow,
            ast.USub,
            ast.UAdd,
            ast.Eq,
            ast.NotEq,
            ast.Lt,
            ast.LtE,
            ast.Gt,
            ast.GtE,
            ast.BitAnd,
            ast.BitOr,
            ast.Tuple,
        )
        if not isinstance(node, allowed):
            raise LemmaSyntaxError(f"{type(node).__name__} is not allowed in a vectorized statement")
        return super().generic_visit(node)


def _scalar_env(rec: ConfigRecord) -> dict[str, Any]:
    """Evaluation namespace for a single record. Everything goes in GLOBALS,
    not locals: a comprehension inside the statement gets its own scope and
    can only close over globals, so `min(len(v) for v in rec.adjacency.values())`
    would raise NameError on `len` if the helpers lived in locals."""
    env: dict[str, Any] = {"__builtins__": {}, "rec": rec, "implies": _implies_scalar}
    env.update(_SCALAR_FUNCS)
    return env


def _vector_env(corpus: Corpus) -> dict[str, Any]:
    env: dict[str, Any] = {"__builtins__": {}}
    env.update(_VECTOR_FUNCS)
    for name, col in corpus.columns().items():
        env[f"_col_{name}"] = col
    return env


@dataclass
class Predicate:
    """A compiled statement: always a per-record form, plus a numpy form
    when the statement only touches scalar columns."""

    text: str
    desugared: str
    scalar_code: Any
    vector_code: Any | None
    columns: set[str] = field(default_factory=set)
    vector_error: str | None = None

    @property
    def vectorized(self) -> bool:
        return self.vector_code is not None

    def eval_record(self, rec: ConfigRecord) -> bool:
        return bool(eval(self.scalar_code, _scalar_env(rec)))

    def eval_vector(self, corpus: Corpus) -> np.ndarray:
        if self.vector_code is None:
            raise LemmaSyntaxError(f"statement is not vectorizable: {self.vector_error}")
        out = eval(self.vector_code, _vector_env(corpus))
        return np.asarray(out, dtype=bool)


def compile_predicate(text: str) -> Predicate:
    """Compile a statement to both evaluation forms."""
    desugared = desugar_implies(text.strip())
    try:
        tree = ast.parse(desugared, mode="eval")
    except SyntaxError as exc:
        raise LemmaSyntaxError(f"cannot parse statement: {exc}") from exc
    scalar_code = compile(tree, "<lemma>", "eval")
    vector_code = None
    columns: set[str] = set()
    vector_error = None
    try:
        vec = _Vectorizer()
        vtree = ast.fix_missing_locations(vec.visit(ast.parse(desugared, mode="eval")))
        vector_code = compile(vtree, "<lemma-vec>", "eval")
        columns = vec.columns
    except LemmaSyntaxError as exc:
        vector_error = str(exc)
    return Predicate(text.strip(), desugared, scalar_code, vector_code, columns, vector_error)


def evaluate(
    pred: Predicate,
    corpus: Corpus,
    crosscheck: int = 256,
    seed: int = 0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Boolean mask of `pred` over `corpus`, plus how it was computed.

    On the vectorized path a random sample of up to `crosscheck` records is
    re-evaluated per-record and compared; a disagreement is a harness bug and
    raises rather than being reported as a mathematical fact."""
    meta: dict[str, Any] = {"path": "vector" if pred.vectorized else "scalar"}
    if not corpus.records:
        return np.zeros(0, dtype=bool), meta
    if pred.vectorized:
        mask = pred.eval_vector(corpus)
        if mask.shape == ():
            mask = np.broadcast_to(mask, (len(corpus),)).copy()
        if mask.shape != (len(corpus),):
            raise LemmaSyntaxError(f"statement produced shape {mask.shape}, expected ({len(corpus)},)")
        if crosscheck:
            rng = random.Random(seed)
            idx = (
                range(len(corpus))
                if len(corpus) <= crosscheck
                else rng.sample(range(len(corpus)), crosscheck)
            )
            bad = [i for i in idx if bool(pred.eval_record(corpus.records[i])) != bool(mask[i])]
            if bad:
                raise AssertionError(
                    f"vectorized statement disagrees with per-record evaluation on "
                    f"{len(bad)} sampled records (first: {corpus.records[bad[0]].label()})"
                )
            meta["crosschecked"] = len(list(idx))
        return mask, meta
    meta["reason"] = pred.vector_error
    mask = np.fromiter((pred.eval_record(rec) for rec in corpus.records), dtype=bool, count=len(corpus))
    return mask, meta


# ---------------------------------------------------------------------------
# Results + registry
# ---------------------------------------------------------------------------


@dataclass
class LemmaResult:
    mode: str
    statement: str
    verdict: str
    n_corpus: int
    n_evaluated: int
    n_true: int
    n_false: int
    counterexamples: list[dict[str, Any]]
    per_ring: dict[int, dict[str, Any]]
    corpus_signature: str
    filter_expr: str | None = None
    support: int | None = None
    eval_meta: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        h = hashlib.blake2b(digest_size=8)
        payload = "|".join(
            [
                self.mode,
                " ".join(self.statement.split()),
                " ".join((self.filter_expr or "").split()),
                self.corpus_signature,
            ]
        )
        h.update(payload.encode())
        return h.hexdigest()

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mode": self.mode,
            "statement": self.statement,
            "filter": self.filter_expr,
            "verdict": self.verdict,
            "corpus": {
                "n_records": self.n_corpus,
                "n_evaluated": self.n_evaluated,
                "signature": self.corpus_signature,
                "rings": sorted(self.per_ring),
            },
            "support": self.support,
            "n_true": self.n_true,
            "n_false": self.n_false,
            "counterexamples": self.counterexamples,
            "per_ring": {str(r): v for r, v in sorted(self.per_ring.items())},
            "eval": self.eval_meta,
            "extra": self.extra,
        }


def _ring_breakdown(corpus: Corpus, mask: np.ndarray, considered: np.ndarray | None = None) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    rings = corpus.r
    keep = considered if considered is not None else np.ones(len(corpus), dtype=bool)
    for r in sorted(set(rings.tolist())):
        sel = (rings == r) & keep
        n = int(sel.sum())
        if n == 0:
            continue
        n_true = int((sel & mask).sum())
        out[int(r)] = {"n": n, "n_true": n_true, "n_false": n - n_true}
    return out


def _examples(corpus: Corpus, indices: np.ndarray, limit: int) -> list[dict[str, Any]]:
    out = []
    for i in indices[:limit]:
        rec = corpus.records[int(i)]
        out.append(
            {
                "ident": rec.ident,
                "source": f"{rec.group}/{rec.source}",
                "file": rec.source_file,
                "r": rec.r,
                "k": rec.k,
                "a": rec.a,
                "b": rec.b,
                "d_reducible": rec.d_reducible,
            }
        )
    return out


def check_universal(
    corpus: Corpus,
    statement: str,
    limit: int = 20,
    filter_expr: str | None = None,
    crosscheck: int = 256,
) -> LemmaResult:
    """Does `statement` hold for EVERY record? Lists up to `limit` counterexamples."""
    pred = compile_predicate(statement)
    mask, meta = evaluate(pred, corpus, crosscheck=crosscheck)
    n_true = int(mask.sum())
    n_false = len(corpus) - n_true
    bad = np.flatnonzero(~mask)
    parts = split_implication(statement)
    support = None
    if parts is not None:
        ante = compile_predicate(parts[0])
        ante_mask, _ = evaluate(ante, corpus, crosscheck=0)
        support = int(ante_mask.sum())
    verdict = "HOLDS" if n_false == 0 else "KILLED"
    if verdict == "HOLDS" and support == 0:
        verdict = "VACUOUS"
    return LemmaResult(
        mode="universal",
        statement=statement.strip(),
        verdict=verdict,
        n_corpus=len(corpus),
        n_evaluated=len(corpus),
        n_true=n_true,
        n_false=n_false,
        counterexamples=_examples(corpus, bad, limit),
        per_ring=_ring_breakdown(corpus, mask),
        corpus_signature=corpus.signature(),
        filter_expr=filter_expr,
        support=support,
        eval_meta=meta,
    )


def check_implication(
    corpus: Corpus,
    antecedent: str,
    consequent: str,
    limit: int = 20,
    filter_expr: str | None = None,
    crosscheck: int = 256,
) -> LemmaResult:
    """P => Q evaluated on the P-population only (so `n_evaluated` is the
    real support and a vacuous statement is visible as such)."""
    p = compile_predicate(antecedent)
    q = compile_predicate(consequent)
    p_mask, p_meta = evaluate(p, corpus, crosscheck=crosscheck)
    support = int(p_mask.sum())
    if support == 0:
        return LemmaResult(
            mode="implication",
            statement=f"{antecedent.strip()} implies {consequent.strip()}",
            verdict="VACUOUS",
            n_corpus=len(corpus),
            n_evaluated=0,
            n_true=0,
            n_false=0,
            counterexamples=[],
            per_ring={},
            corpus_signature=corpus.signature(),
            filter_expr=filter_expr,
            support=0,
            eval_meta={"antecedent": p_meta},
        )
    if q.vectorized:
        q_mask, q_meta = evaluate(q, corpus, crosscheck=crosscheck)
    else:
        q_meta = {"path": "scalar", "reason": q.vector_error}
        q_mask = np.zeros(len(corpus), dtype=bool)
        for i in np.flatnonzero(p_mask):
            q_mask[i] = q.eval_record(corpus.records[int(i)])
        q_meta["evaluated_lazily"] = support
    holds = q_mask | ~p_mask
    bad = np.flatnonzero(p_mask & ~q_mask)
    n_true = support - len(bad)
    return LemmaResult(
        mode="implication",
        statement=f"{antecedent.strip()} implies {consequent.strip()}",
        verdict="HOLDS" if len(bad) == 0 else "KILLED",
        n_corpus=len(corpus),
        n_evaluated=support,
        n_true=n_true,
        n_false=int(len(bad)),
        counterexamples=_examples(corpus, bad, limit),
        per_ring=_ring_breakdown(corpus, holds, considered=p_mask),
        corpus_signature=corpus.signature(),
        filter_expr=filter_expr,
        support=support,
        eval_meta={"antecedent": p_meta, "consequent": q_meta},
    )


_COMPARE_OPS = {ast.LtE: "<=", ast.Lt: "<", ast.GtE: ">=", ast.Gt: ">"}


def split_bound(statement: str) -> tuple[str, str, str]:
    """(lhs, op, rhs) of a single top-level comparison, e.g.
    `rec.a <= 2**(rec.r + rec.k - 3)`."""
    tree = ast.parse(statement.strip(), mode="eval")
    node = tree.body
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        raise LemmaSyntaxError("bound mode needs exactly one comparison, e.g. 'rec.a <= f(rec.r, rec.k)'")
    op = type(node.ops[0])
    if op not in _COMPARE_OPS:
        raise LemmaSyntaxError("bound comparison must be one of <=, <, >=, >")
    return ast.unparse(node.left), _COMPARE_OPS[op], ast.unparse(node.comparators[0])


def _eval_numeric(expr: str, corpus: Corpus, crosscheck: int = 64) -> np.ndarray:
    """Numeric (not boolean) evaluation of one side of a bound."""
    pred = compile_predicate(expr)
    if pred.vectorized:
        vals = np.asarray(eval(pred.vector_code, _vector_env(corpus)), dtype=np.float64)
        if vals.shape == ():
            vals = np.full(len(corpus), float(vals))
        if crosscheck:
            rng = random.Random(0)
            idx = range(len(corpus)) if len(corpus) <= crosscheck else rng.sample(range(len(corpus)), crosscheck)
            for i in idx:
                got = float(eval(pred.scalar_code, _scalar_env(corpus.records[i])))
                if not np.isclose(got, vals[i], rtol=1e-9, atol=1e-9):
                    raise AssertionError(f"vectorized side {expr!r} disagrees per-record at index {i}")
        return vals
    return np.array(
        [float(eval(pred.scalar_code, _scalar_env(rec))) for rec in corpus.records],
        dtype=np.float64,
    )


def fit_bound(
    corpus: Corpus,
    statement: str,
    limit: int = 20,
    filter_expr: str | None = None,
    group_by: str = "r",
) -> LemmaResult:
    """Bound-fitting mode: evaluate both sides of a proposed inequality and
    report, per ring, how much slack the data leaves -- min (the tightest
    config, i.e. how close the bound is to being wrong), max, and the range
    of each side. Verdict HOLDS iff there are no violations."""
    lhs_txt, op, rhs_txt = split_bound(statement)
    lhs = _eval_numeric(lhs_txt, corpus)
    rhs = _eval_numeric(rhs_txt, corpus)
    if op in ("<=", "<"):
        slack = rhs - lhs
        ok = slack >= 0 if op == "<=" else slack > 0
    else:
        slack = lhs - rhs
        ok = slack >= 0 if op == ">=" else slack > 0
    keys = corpus.r if group_by == "r" else getattr(corpus, group_by)
    per_ring: dict[int, dict[str, Any]] = {}
    for key in sorted(set(keys.tolist())):
        sel = keys == key
        idx = np.flatnonzero(sel)
        s = slack[sel]
        tight = int(idx[int(np.argmin(s))])
        per_ring[int(key)] = {
            "n": int(sel.sum()),
            "n_violations": int((~ok[sel]).sum()),
            "lhs_min": float(lhs[sel].min()),
            "lhs_max": float(lhs[sel].max()),
            "rhs_min": float(rhs[sel].min()),
            "rhs_max": float(rhs[sel].max()),
            "slack_min": float(s.min()),
            "slack_max": float(s.max()),
            "ratio_max": float(np.max(lhs[sel] / np.where(rhs[sel] == 0, np.nan, rhs[sel])))
            if np.any(rhs[sel] != 0)
            else float("nan"),
            "tightest": corpus.records[tight].label(),
            "tightest_k": corpus.records[tight].k,
        }
    bad = np.flatnonzero(~ok)
    return LemmaResult(
        mode="bound",
        statement=statement.strip(),
        verdict="HOLDS" if len(bad) == 0 else "KILLED",
        n_corpus=len(corpus),
        n_evaluated=len(corpus),
        n_true=int(ok.sum()),
        n_false=int(len(bad)),
        counterexamples=_examples(corpus, bad, limit),
        per_ring=per_ring,
        corpus_signature=corpus.signature(),
        filter_expr=filter_expr,
        eval_meta={"lhs": lhs_txt, "op": op, "rhs": rhs_txt, "group_by": group_by},
        extra={"global_slack_min": float(slack.min()), "global_slack_max": float(slack.max())},
    )


def gap_table(corpus: Corpus, f_table: dict[int, int] | None = None) -> dict[int, dict[str, Any]]:
    """The coloring-mass GAP fact (03-MASS-LAW-PROGRAM.md item 2 / M1): per
    ring, min a over D-REDUCIBLE configs vs max a over BELOW-THRESHOLD
    (k < f(r)) non-reducible configs. A positive gap at every measurable ring
    is the empirical content of the Threshold half of the law."""
    f_table = F_TABLE if f_table is None else f_table
    out: dict[int, dict[str, Any]] = {}
    for r in sorted(set(corpus.r.tolist())):
        red = corpus.d_reducible & (corpus.r == r)
        neg = (~corpus.d_reducible) & (corpus.r == r)
        # "Below threshold" is only meaningful where f(r) is proven; at other
        # rings the negatives include interior >= f(r) configs, for which the
        # law predicts nothing, so no gap is reported rather than a fake one.
        known = int(r) in f_table
        sub = (neg & (corpus.k < f_table[int(r)])) if known else np.zeros(len(corpus), dtype=bool)
        row: dict[str, Any] = {
            "f_r": f_table.get(int(r)),
            "n_d_reducible": int(red.sum()),
            "n_negative": int(neg.sum()),
            "n_subthreshold_negative": int(sub.sum()) if known else None,
            "min_a_d_reducible": int(corpus.a[red].min()) if red.any() else None,
            "max_a_subthreshold": int(corpus.a[sub].max()) if known and sub.any() else None,
        }
        if row["min_a_d_reducible"] is not None and row["max_a_subthreshold"] is not None:
            row["gap"] = row["min_a_d_reducible"] - row["max_a_subthreshold"]
        else:
            row["gap"] = None
        out[int(r)] = row
    return out


def gap_table_result(corpus: Corpus, f_table: dict[int, int] | None = None) -> LemmaResult:
    """`gap_table` packaged as a receipt-able claim: 'at every ring where
    f(r) is proven, min a over D-reducibles exceeds max a over below-threshold
    negatives'. KILLED if any measurable ring's gap is <= 0."""
    table = gap_table(corpus, f_table)
    measurable = {r: row for r, row in table.items() if row["gap"] is not None}
    failed = [r for r, row in measurable.items() if row["gap"] <= 0]
    return LemmaResult(
        mode="gap_table",
        statement=(
            "min a over D-reducible > max a over below-threshold (k < f(r)) non-reducible, "
            "at every ring where f(r) is proven"
        ),
        verdict="HOLDS" if not failed and measurable else ("VACUOUS" if not measurable else "KILLED"),
        n_corpus=len(corpus),
        n_evaluated=sum(row["n_d_reducible"] + (row["n_subthreshold_negative"] or 0) for row in measurable.values()),
        n_true=len(measurable) - len(failed),
        n_false=len(failed),
        counterexamples=[{"ident": f"ring r={r}", "source": "gap_table", **measurable[r]} for r in failed],
        per_ring=table,
        corpus_signature=corpus.signature(),
        extra={"f_table": {str(k): v for k, v in (f_table or F_TABLE).items()}},
    )


def log_result(result: LemmaResult, path: Path | None = None) -> tuple[Path, bool]:
    """Append the receipt to the registry. Returns (path, appended); a run
    that reproduces an already-logged (id, verdict, counts) is not duplicated,
    so the log stays a set of distinct machine-checked claims."""
    path = LOG_PATH if path is None else path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_json()
    line = json.dumps(payload, sort_keys=True)
    if path.exists():
        with path.open() as f:
            for existing in f:
                if existing.strip() == line:
                    return path, False
    with path.open("a") as f:
        f.write(line + "\n")
    return path, True
