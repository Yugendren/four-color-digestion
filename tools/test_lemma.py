#!/usr/bin/env python3
"""Machine-check a candidate mass-law statement against every labeled
configuration this repo holds -- the "third checker" for the M2/M3 proof work
(03-MASS-LAW-PROGRAM.md). Run a lemma HERE before anyone tries to prove it.

  # corpus inventory (per source, per ring, adjacency/trace coverage)
  .venv/bin/python tools/test_lemma.py --summary

  # universal check; `A implies B` (or `A => B`) is the implication connective
  .venv/bin/python tools/test_lemma.py \
      --check "rec.d_reducible implies rec.a >= 94 * 2.4**(rec.r - 8)"

  # same thing with explicit antecedent/consequent (reports P-support)
  .venv/bin/python tools/test_lemma.py --implies "rec.d_reducible" "rec.a >= 94"

  # bound-fitting: does it hold, and how tight is it per ring?
  .venv/bin/python tools/test_lemma.py --bound "rec.a <= 2**(rec.r + rec.k - 3)"

  # restrict the population first
  .venv/bin/python tools/test_lemma.py --check "rec.b > 0" --filter "not rec.d_reducible"

  # the known coloring-mass gap facts (reproduces the table in 03-MASS-LAW-PROGRAM.md)
  .venv/bin/python tools/test_lemma.py --gap-table

Statement syntax: a Python expression over one record `rec` --
  rec.r rec.n rec.k rec.a rec.b rec.rounds rec.d_reducible  (k = n - r,
  a = |Phi| = n_extendable, b = n_consistent), rec.ident rec.source rec.group,
  the lazy structure rec.adjacency / rec.trace / rec.set_trace /
  rec.canonical_key, the lazy hand-features rec.f('name'), and/or/not,
  arithmetic including **, abs log log2 exp sqrt floor ceil min max len sum
  any all, and `A implies B`. See fourcolor.lemma_harness for the full
  contract (scalar statements are evaluated vectorized and cross-checked
  against per-record evaluation).

Performance: a statement over the scalar columns alone runs vectorized over all
~59k configs in well under a second. A statement touching rec.adjacency /
rec.trace / rec.f(...) is evaluated per record, which json-parses source lines
(the v2 trace sources are ~90KB per line) -- prefer `--implies P Q` over
`--check "P implies Q"` when only the consequent needs structure, since
implication mode evaluates the consequent on the P-population only, and use
`--filter` to cut the population first.

Every run appends a receipt (statement, corpus size + content signature,
verdict, counterexamples) to results/mass-law/lemma_log.jsonl under a
timestamp-free content hash. `--no-log` suppresses it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor import lemma_harness as lh  # noqa: E402
from fourcolor.lemma_corpus import load_corpus  # noqa: E402


def fmt_summary(summary: dict) -> str:
    lines = [
        f"corpus: {summary['n_records']} unique configurations "
        f"({summary['n_raw']} raw records across {summary['n_files']} files, "
        f"{summary['n_duplicates']} canonical duplicates folded, "
        f"{summary['n_conflicts']} label conflicts)",
        f"        {summary['n_d_reducible']} D-reducible | "
        f"{summary['with_adjacency']} with adjacency | {summary['with_trace']} with trace",
        "",
        f"{'source group':<14}{'raw':>8}{'kept':>8}{'D-red':>8}",
    ]
    for group, row in summary["per_group"].items():
        lines.append(f"{group:<14}{row.get('raw', 0):>8}{row['kept']:>8}{row['d_reducible']:>8}")
    lines += ["", f"{'source':<28}{'kept':>8}"]
    for source, count in summary["per_source"].items():
        lines.append(f"{source:<28}{count:>8}")
    lines += ["", f"{'r':>3}{'n':>9}{'D-red':>8}{'k range':>10}{'adj':>8}{'trace':>8}"]
    for r, row in summary["per_ring"].items():
        lines.append(
            f"{r:>3}{row['n']:>9}{row['d_reducible']:>8}"
            f"{f'{row['k_min']}-{row['k_max']}':>10}{row['with_adjacency']:>8}{row['with_trace']:>8}"
        )
    return "\n".join(lines)


def fmt_gap_table(table: dict) -> str:
    lines = [
        "coloring-mass gap: min a over D-reducible vs max a over below-threshold "
        "(k < f(r)) non-reducible",
        "(no gap is reported at rings where f(r) is not proven -- '-' means undefined, not zero)",
        f"{'r':>3}{'f(r)':>6}{'#D-red':>9}{'min a':>9}{'#neg':>8}{'#sub-neg':>10}{'max a':>9}{'gap':>9}",
    ]
    for r, row in table.items():
        def dash(value: object) -> str:
            return "-" if value is None else str(value)

        lines.append(
            f"{r:>3}{dash(row['f_r']):>6}{row['n_d_reducible']:>9}{dash(row['min_a_d_reducible']):>9}"
            f"{row['n_negative']:>8}{dash(row['n_subthreshold_negative']):>10}"
            f"{dash(row['max_a_subthreshold']):>9}{dash(row['gap']):>9}"
        )
    return "\n".join(lines)


def fmt_result(result: lh.LemmaResult, limit: int) -> str:
    lines = [
        f"[{result.mode}] {result.statement}",
    ]
    if result.filter_expr:
        lines.append(f"  filter: {result.filter_expr}")
    lines.append(
        f"  corpus: {result.n_corpus} configs (signature {result.corpus_signature}); "
        f"evaluated {result.n_evaluated}"
        + (f"; antecedent support {result.support}" if result.support is not None else "")
    )
    lines.append(f"  eval path: {result.eval_meta}")
    lines.append(f"  VERDICT: {result.verdict} -- {result.n_true} satisfy, {result.n_false} violate")
    if result.mode == "bound":
        lines.append("")
        lines.append(
            f"  {'r':>3}{'n':>8}{'viol':>7}{'lhs max':>13}{'rhs min':>13}"
            f"{'slack min':>13}{'slack max':>13}{'max lhs/rhs':>13}  tightest"
        )
        for r, row in sorted(result.per_ring.items()):
            lines.append(
                f"  {r:>3}{row['n']:>8}{row['n_violations']:>7}{row['lhs_max']:>13.4g}"
                f"{row['rhs_min']:>13.4g}{row['slack_min']:>13.4g}{row['slack_max']:>13.4g}"
                f"{row['ratio_max']:>13.4g}  {row['tightest']} (k={row['tightest_k']})"
            )
    else:
        lines.append("")
        lines.append(f"  {'r':>3}{'n':>8}{'true':>8}{'false':>8}")
        for r, row in sorted(result.per_ring.items()):
            lines.append(f"  {r:>3}{row['n']:>8}{row['n_true']:>8}{row['n_false']:>8}")
    if result.counterexamples:
        lines.append("")
        lines.append(f"  counterexamples (showing {len(result.counterexamples)} of {result.n_false}):")
        for ce in result.counterexamples[:limit]:
            lines.append(
                f"    {ce['ident']:<22} {ce['source']:<26} r={ce['r']:<3} k={ce['k']:<3} "
                f"a={ce['a']:<7} b={ce['b']:<7} D={ce['d_reducible']}"
            )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", metavar="EXPR", help="universal check of a statement over the corpus")
    mode.add_argument("--implies", nargs=2, metavar=("P", "Q"), help="implication check P => Q")
    mode.add_argument("--bound", metavar="EXPR", help="bound fitting, e.g. 'rec.a <= 2**(rec.r + rec.k - 3)'")
    mode.add_argument("--summary", action="store_true", help="corpus inventory only")
    mode.add_argument("--gap-table", action="store_true", help="the known coloring-mass gap facts")
    ap.add_argument("--filter", metavar="EXPR", default=None, help="restrict the corpus before checking")
    ap.add_argument("--limit", type=int, default=20, help="max counterexamples to list (default 20)")
    ap.add_argument("--group-by", default="r", choices=["r", "n", "k"], help="bound-mode grouping (default r)")
    ap.add_argument("--crosscheck", type=int, default=256, help="vector-vs-scalar sample size (0 disables)")
    ap.add_argument("--no-log", action="store_true", help="do not append a receipt to the registry")
    ap.add_argument("--rebuild-index", action="store_true", help="rescan every source file")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    corpus = load_corpus(rebuild=args.rebuild_index)

    if args.summary:
        summary = corpus.summary()
        print(json.dumps(summary, indent=2) if args.json else fmt_summary(summary))
        return 0
    if args.gap_table:
        result = lh.gap_table_result(corpus)
        if args.json:
            print(json.dumps(result.to_json(), indent=2))
        else:
            print(fmt_gap_table(result.per_ring))
            print(
                f"\n  VERDICT: {result.verdict} -- positive gap at {result.n_true} of "
                f"{result.n_true + result.n_false} measurable rings "
                f"(corpus {result.n_corpus}, signature {result.corpus_signature})"
            )
        if not args.no_log:
            path, appended = lh.log_result(result)
            if not args.json:
                print(
                    f"  receipt {result.id} -> {path.relative_to(ROOT)}"
                    + ("" if appended else " (already logged)")
                )
        return 0 if result.verdict == "HOLDS" else 1

    if args.filter:
        fpred = lh.compile_predicate(args.filter)
        fmask, _ = lh.evaluate(fpred, corpus, crosscheck=args.crosscheck)
        corpus = corpus.subset(fmask)
        if len(corpus) == 0:
            print(f"filter {args.filter!r} selected 0 configurations", file=sys.stderr)
            return 2

    try:
        if args.check is not None:
            result = lh.check_universal(
                corpus, args.check, limit=args.limit, filter_expr=args.filter, crosscheck=args.crosscheck
            )
        elif args.implies is not None:
            result = lh.check_implication(
                corpus, args.implies[0], args.implies[1], limit=args.limit,
                filter_expr=args.filter, crosscheck=args.crosscheck,
            )
        else:
            result = lh.fit_bound(
                corpus, args.bound, limit=args.limit, filter_expr=args.filter, group_by=args.group_by
            )
    except lh.LemmaSyntaxError as exc:
        print(f"statement error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.to_json(), indent=2))
    else:
        print(fmt_result(result, args.limit))

    if not args.no_log:
        path, appended = lh.log_result(result)
        if not args.json:
            rel = path.relative_to(ROOT)
            print(f"\n  receipt {result.id} -> {rel}" + ("" if appended else " (already logged)"))
    return 0 if result.verdict == "HOLDS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
