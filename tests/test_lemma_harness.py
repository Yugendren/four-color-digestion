"""Fast unit tests for the lemma-testing harness: the unified corpus loader
(`fourcolor.lemma_corpus` -- regex line scan, canonical dedup, lazy
adjacency/trace, on-disk index cache) and the checker itself
(`fourcolor.lemma_harness` -- implication desugaring, the numpy vectorizer and
its cross-check against per-record evaluation, the three modes, the gap table,
and the append-only receipt log). Synthetic JSONL for the mechanics plus one
small smoke test on a real committed source file; no dependency on the full
~59k-config corpus (which lives partly under the gitignored data/)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from fourcolor import lemma_harness as lh  # noqa: E402
from fourcolor import lemma_corpus as lc  # noqa: E402


# --------------------------------------------------------------------------
# Small synthetic configurations (a ring-6 wheel with 1..k interior vertices
# is overkill here -- these records only need valid adjacency for the
# canonicalizer, and honest scalar headers).
# --------------------------------------------------------------------------


def wheel_record(ident, r=6, extra=0, a=10, b=0, d=True, rounds=2, source="synth"):
    """Ring of size r plus one hub (plus `extra` hub-adjacent stubs is not
    needed: one interior vertex keeps the canonical BFS well-defined)."""
    n = r + 1
    adjacency = {}
    for v in range(1, r + 1):
        prev = v - 1 if v > 1 else r
        nxt = v + 1 if v < r else 1
        adjacency[str(v)] = [nxt, n, prev]
    adjacency[str(n)] = list(range(1, r + 1))
    return {
        "ident": ident,
        "source": source,
        "r": r,
        "n": n,
        "adjacency": adjacency,
        "n_extendable": a,
        "n_consistent": b,
        "d_reducible": d,
        "rounds": rounds,
        "trace": [100] * rounds + [b],
    }


def write_jsonl(path, records):
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def make_records(rows):
    """rows: list of (ident, r, n, a, b, d_reducible)."""
    out = []
    for i, (ident, r, n, a, b, d) in enumerate(rows):
        out.append(
            lc.ConfigRecord(
                ident=ident,
                source="synth",
                group="synth",
                source_file="synth.jsonl",
                r=r,
                n=n,
                a=a,
                b=b,
                d_reducible=d,
                rounds=3,
                canonical_hash=f"{i:020x}",
                has_adjacency=False,
                has_trace=False,
                path=Path("/nonexistent"),
                offset=0,
            )
        )
    return out


def synth_corpus(rows):
    return lc.Corpus(make_records(rows), {"n_raw": len(rows), "n_duplicates": 0, "n_files": 0})


# --------------------------------------------------------------------------


class TestImpliesSugar(unittest.TestCase):
    def test_plain_expression_untouched(self):
        self.assertEqual(lh.desugar_implies("rec.a >= 1"), "rec.a >= 1")

    def test_word_form(self):
        self.assertEqual(
            lh.desugar_implies("rec.d_reducible implies rec.a >= 94"),
            "implies(rec.d_reducible, rec.a >= 94)",
        )

    def test_arrow_form(self):
        self.assertEqual(lh.desugar_implies("rec.b == 0 => rec.a > 0"), "implies(rec.b == 0, rec.a > 0)")

    def test_ge_is_not_an_arrow(self):
        self.assertEqual(lh.desugar_implies("rec.a >= 3"), "rec.a >= 3")

    def test_right_associative_chain(self):
        self.assertEqual(
            lh.desugar_implies("a implies b implies c"), "implies(a, implies(b, c))"
        )

    def test_implies_inside_parens_is_not_top_level(self):
        # The parenthesised implication is desugared by the recursive call on
        # the right-hand side only after the top-level split.
        self.assertEqual(
            lh.desugar_implies("(rec.a > 1) implies rec.b == 0"),
            "implies((rec.a > 1), rec.b == 0)",
        )

    def test_identifier_containing_implies_is_left_alone(self):
        self.assertEqual(lh.desugar_implies("rec.f('implies_count') > 0"), "rec.f('implies_count') > 0")

    def test_split_implication(self):
        self.assertEqual(lh.split_implication("P implies Q"), ("P", "Q"))
        self.assertIsNone(lh.split_implication("rec.a > 1"))

    def test_empty_side_rejected(self):
        with self.assertRaises(lh.LemmaSyntaxError):
            lh.desugar_implies("rec.a > 1 implies")


class TestVectorizer(unittest.TestCase):
    def setUp(self):
        self.corpus = synth_corpus(
            [
                ("x1", 8, 13, 94, 0, True),
                ("x2", 8, 12, 82, 5, False),
                ("x3", 9, 14, 211, 0, True),
                ("x4", 9, 13, 172, 7, False),
            ]
        )

    def test_scalar_statement_is_vectorized(self):
        pred = lh.compile_predicate("rec.d_reducible implies rec.a >= 94")
        self.assertTrue(pred.vectorized)
        self.assertEqual(pred.columns, {"d_reducible", "a"})

    def test_structure_statement_falls_back_to_scalar(self):
        pred = lh.compile_predicate("len(rec.trace) > 0")
        self.assertFalse(pred.vectorized)
        self.assertIsNotNone(pred.vector_error)

    def test_feature_access_falls_back_to_scalar(self):
        pred = lh.compile_predicate("rec.f('n_deg5_interior') >= 0")
        self.assertFalse(pred.vectorized)

    def test_and_or_not_agree_with_python(self):
        expr = "not (rec.d_reducible and rec.a > 100) or rec.b == 0"
        pred = lh.compile_predicate(expr)
        self.assertTrue(pred.vectorized)
        vec = pred.eval_vector(self.corpus)
        scalar = [pred.eval_record(rec) for rec in self.corpus.records]
        self.assertEqual(list(vec), scalar)

    def test_chained_comparison_agrees_with_python(self):
        pred = lh.compile_predicate("8 <= rec.r < 9")
        vec = pred.eval_vector(self.corpus)
        self.assertEqual(list(vec), [pred.eval_record(r) for r in self.corpus.records])

    def test_k_column_is_n_minus_r(self):
        pred = lh.compile_predicate("rec.k == rec.n - rec.r")
        mask, _ = lh.evaluate(pred, self.corpus)
        self.assertTrue(mask.all())

    def test_crosscheck_catches_a_lying_vector_form(self):
        good = lh.compile_predicate("rec.a >= 94")
        bad = lh.compile_predicate("rec.a >= 1000")
        rigged = lh.Predicate(
            text=good.text,
            desugared=good.desugared,
            scalar_code=good.scalar_code,
            vector_code=bad.vector_code,
            columns=good.columns,
        )
        with self.assertRaises(AssertionError):
            lh.evaluate(rigged, self.corpus, crosscheck=4)

    def test_crosscheck_metadata_reported(self):
        pred = lh.compile_predicate("rec.a > 0")
        _, meta = lh.evaluate(pred, self.corpus)
        self.assertEqual(meta["path"], "vector")
        self.assertEqual(meta["crosschecked"], 4)

    def test_unknown_name_is_rejected_everywhere(self):
        pred = lh.compile_predicate("bogus(rec.a)")
        self.assertFalse(pred.vectorized)
        with self.assertRaises(NameError):
            pred.eval_record(self.corpus.records[0])


class TestModes(unittest.TestCase):
    def setUp(self):
        self.corpus = synth_corpus(
            [
                ("x1", 8, 13, 94, 0, True),
                ("x2", 8, 12, 82, 5, False),
                ("x3", 9, 14, 211, 0, True),
                ("x4", 9, 13, 172, 7, False),
            ]
        )

    def test_universal_holds(self):
        res = lh.check_universal(self.corpus, "rec.a > 0")
        self.assertEqual(res.verdict, "HOLDS")
        self.assertEqual((res.n_true, res.n_false), (4, 0))
        self.assertEqual(res.counterexamples, [])

    def test_universal_killed_lists_counterexamples(self):
        res = lh.check_universal(self.corpus, "rec.a >= 200")
        self.assertEqual(res.verdict, "KILLED")
        self.assertEqual(res.n_false, 3)
        self.assertEqual({ce["ident"] for ce in res.counterexamples}, {"x1", "x2", "x4"})

    def test_counterexample_limit_respected(self):
        res = lh.check_universal(self.corpus, "rec.a >= 200", limit=1)
        self.assertEqual(res.n_false, 3)
        self.assertEqual(len(res.counterexamples), 1)

    def test_universal_with_implication_reports_support(self):
        res = lh.check_universal(self.corpus, "rec.d_reducible implies rec.b == 0")
        self.assertEqual(res.verdict, "HOLDS")
        self.assertEqual(res.support, 2)

    def test_implication_support_and_kill(self):
        res = lh.check_implication(self.corpus, "rec.d_reducible", "rec.a >= 200")
        self.assertEqual(res.support, 2)
        self.assertEqual(res.n_evaluated, 2)
        self.assertEqual(res.verdict, "KILLED")
        self.assertEqual([ce["ident"] for ce in res.counterexamples], ["x1"])

    def test_implication_holds(self):
        res = lh.check_implication(self.corpus, "rec.d_reducible", "rec.a >= 94")
        self.assertEqual(res.verdict, "HOLDS")
        self.assertEqual(res.n_true, 2)

    def test_vacuous_antecedent_is_flagged_not_celebrated(self):
        res = lh.check_implication(self.corpus, "rec.r == 99", "rec.a < 0")
        self.assertEqual(res.verdict, "VACUOUS")
        self.assertEqual(res.support, 0)

    def test_implication_scalar_consequent_evaluated_only_on_support(self):
        # A consequent that would explode on the unsupported records proves
        # laziness: rec.adjacency on a synthetic record raises (no file).
        res = lh.check_implication(self.corpus, "rec.r == 99", "len(rec.adjacency) > 0")
        self.assertEqual(res.verdict, "VACUOUS")

    def test_bound_holds_with_per_ring_slack(self):
        res = lh.fit_bound(self.corpus, "rec.a <= 2**(rec.r + rec.k - 3)")
        self.assertEqual(res.verdict, "HOLDS")
        self.assertEqual(sorted(res.per_ring), [8, 9])
        self.assertEqual(res.per_ring[8]["n"], 2)
        self.assertEqual(res.per_ring[8]["lhs_max"], 94.0)
        self.assertGreaterEqual(res.per_ring[8]["slack_min"], 0)

    def test_bound_killed_reports_violations(self):
        res = lh.fit_bound(self.corpus, "rec.a <= 100")
        self.assertEqual(res.verdict, "KILLED")
        self.assertEqual(res.n_false, 2)
        self.assertEqual(res.per_ring[9]["n_violations"], 2)

    def test_bound_ge_direction(self):
        res = lh.fit_bound(self.corpus, "rec.a >= 1")
        self.assertEqual(res.verdict, "HOLDS")
        self.assertEqual(res.per_ring[8]["slack_min"], 81.0)

    def test_bound_needs_one_comparison(self):
        with self.assertRaises(lh.LemmaSyntaxError):
            lh.fit_bound(self.corpus, "rec.a")
        with self.assertRaises(lh.LemmaSyntaxError):
            lh.fit_bound(self.corpus, "1 <= rec.a <= 2")

    def test_gap_table(self):
        table = lh.gap_table(self.corpus, f_table={8: 5, 9: 5})
        self.assertEqual(table[8]["min_a_d_reducible"], 94)
        self.assertEqual(table[8]["max_a_subthreshold"], 82)
        self.assertEqual(table[8]["gap"], 12)
        self.assertEqual(table[9]["gap"], 39)

    def test_gap_table_reports_nothing_where_f_is_unknown(self):
        table = lh.gap_table(self.corpus, f_table={8: 5})
        self.assertIsNone(table[9]["gap"])
        self.assertIsNone(table[9]["max_a_subthreshold"])
        self.assertEqual(table[9]["n_negative"], 1)

    def test_gap_table_result_is_receiptable(self):
        res = lh.gap_table_result(self.corpus, f_table={8: 5, 9: 5})
        self.assertEqual(res.mode, "gap_table")
        self.assertEqual(res.verdict, "HOLDS")
        self.assertEqual((res.n_true, res.n_false), (2, 0))
        self.assertEqual(res.per_ring[8]["gap"], 12)

    def test_gap_table_result_killed_by_an_inverted_ring(self):
        corpus = synth_corpus(
            [("lo", 8, 13, 50, 0, True), ("hi", 8, 12, 80, 3, False)]
        )
        res = lh.gap_table_result(corpus, f_table={8: 5})
        self.assertEqual(res.verdict, "KILLED")
        self.assertEqual(res.counterexamples[0]["ident"], "ring r=8")

    def test_subset_filters_records_and_columns(self):
        sub = self.corpus.subset(self.corpus.r == 8)
        self.assertEqual(len(sub), 2)
        self.assertEqual(list(sub.a), [94, 82])


class TestReceiptLog(unittest.TestCase):
    def setUp(self):
        self.corpus = synth_corpus([("x1", 8, 13, 94, 0, True), ("x2", 8, 12, 82, 5, False)])

    def test_id_is_deterministic_and_timestamp_free(self):
        a = lh.check_universal(self.corpus, "rec.a > 0")
        b = lh.check_universal(self.corpus, "rec.a  >  0")
        self.assertEqual(a.id, b.id)

    def test_id_depends_on_corpus(self):
        other = synth_corpus([("x1", 8, 13, 94, 0, True)])
        a = lh.check_universal(self.corpus, "rec.a > 0")
        b = lh.check_universal(other, "rec.a > 0")
        self.assertNotEqual(a.id, b.id)

    def test_log_appends_once_per_distinct_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lemma_log.jsonl"
            res = lh.check_universal(self.corpus, "rec.a > 0")
            _, first = lh.log_result(res, path)
            _, second = lh.log_result(res, path)
            self.assertTrue(first)
            self.assertFalse(second)
            other = lh.check_universal(self.corpus, "rec.a > 1000")
            lh.log_result(other, path)
            lines = [json.loads(l) for l in path.read_text().splitlines()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["verdict"], "HOLDS")
            self.assertEqual(lines[1]["verdict"], "KILLED")
            self.assertIn("signature", lines[0]["corpus"])
            self.assertEqual(lines[1]["counterexamples"][0]["ident"], "x1")


class TestCorpusLoader(unittest.TestCase):
    def test_scan_dedup_and_lazy_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write_jsonl(tmp / "a.jsonl", [wheel_record("a1", a=10), wheel_record("a2", r=7, a=20, d=False, b=3)])
            # b.jsonl re-states a1 under a different ident (same graph) plus
            # one genuinely new configuration.
            write_jsonl(tmp / "b.jsonl", [wheel_record("dup-of-a1", a=10), wheel_record("b1", r=8, a=30)])
            rows_a = lc._scan_file(tmp / "a.jsonl", "ga")
            self.assertEqual(len(rows_a), 2)
            self.assertEqual(rows_a[0]["ident"], "a1")
            self.assertEqual(rows_a[0]["a"], 10)
            self.assertTrue(rows_a[0]["adj"] and rows_a[0]["tr"])
            self.assertTrue(rows_a[1]["r"] == 7 and rows_a[1]["d"] is False)

            corpus = self._load(tmp)
            self.assertEqual(len(corpus), 3)
            self.assertEqual([rec.ident for rec in corpus], ["a1", "a2", "b1"])
            kept = corpus.records[0]
            self.assertEqual(kept.dup_sources, ["b.jsonl:synth"])
            self.assertEqual(corpus.stats["n_raw"], 4)
            self.assertEqual(corpus.stats["n_duplicates"], 1)
            self.assertEqual(corpus.stats["conflicts"], [])

            # lazy structure comes back from the source line
            self.assertEqual(kept.k, 1)
            self.assertEqual(sorted(kept.adjacency), list(range(1, 8)))
            self.assertEqual(kept.trace[-1], 0)
            self.assertTrue(kept.canonical_key.startswith("1:3:"))

    def test_label_conflict_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write_jsonl(tmp / "a.jsonl", [wheel_record("a1", d=True, b=0)])
            write_jsonl(tmp / "b.jsonl", [wheel_record("a1-again", d=False, b=4)])
            corpus = self._load(tmp)
            self.assertEqual(len(corpus), 1)
            self.assertEqual(len(corpus.stats["conflicts"]), 1)
            self.assertEqual(corpus.stats["conflicts"][0]["other_d_reducible"], False)

    def test_set_trace_source_yields_trace_lengths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rec = wheel_record("v2rec", rounds=2)
            del rec["trace"]
            rec["set_trace"] = [[0, 1, 2], [0, 1], []]
            write_jsonl(tmp / "a.jsonl", [rec])
            corpus = self._load(tmp)
            self.assertEqual(corpus.records[0].trace, [3, 2, 0])
            self.assertEqual(corpus.records[0].set_trace[0], [0, 1, 2])
            self.assertTrue(corpus.records[0].has_trace)

    def test_index_cache_round_trip_and_invalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "a.jsonl"
            write_jsonl(src, [wheel_record("a1")])
            cache_dir = tmp / "cache"
            orig = lc.CACHE_DIR
            lc.CACHE_DIR = cache_dir
            try:
                rows = lc.index_file(src, "g")
                self.assertEqual(len(list(cache_dir.glob("*.json"))), 1)
                again = lc.index_file(src, "g")
                self.assertEqual(rows, again)
                write_jsonl(src, [wheel_record("a1"), wheel_record("a2", r=7)])
                self.assertEqual(len(lc.index_file(src, "g")), 2)
            finally:
                lc.CACHE_DIR = orig

    def test_summary_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write_jsonl(tmp / "a.jsonl", [wheel_record("a1"), wheel_record("a2", r=7, d=False, b=2)])
            summary = self._load(tmp).summary()
            self.assertEqual(summary["n_records"], 2)
            self.assertEqual(summary["n_d_reducible"], 1)
            self.assertEqual(summary["with_adjacency"], 2)
            self.assertEqual(summary["per_ring"][6]["n"], 1)
            self.assertEqual(summary["per_group"]["g"]["kept"], 2)

    @staticmethod
    def _load(tmp):
        specs = [("g", str(p)) for p in sorted(tmp.glob("*.jsonl"))]
        orig = lc.ROOT
        lc.ROOT = Path("/")
        try:
            return lc.load_corpus(specs=specs, use_cache=False)
        finally:
            lc.ROOT = orig


class TestRealSourceSmoke(unittest.TestCase):
    """One committed f(r)-table shard (10 configs, no precomputed
    canonical_key) end-to-end: index -> dedup -> Cap bound -> receipt."""

    SPEC = [("fr_table", "results/theorem/fr_table/configs_r8_n1[012].jsonl")]

    def test_loads_and_the_proven_cap_holds(self):
        corpus = lc.load_corpus(specs=self.SPEC, use_cache=False)
        self.assertGreaterEqual(len(corpus), 10)
        self.assertTrue(all(rec.r == 8 for rec in corpus))
        self.assertTrue(all(rec.has_adjacency for rec in corpus))
        self.assertFalse(any(rec.d_reducible for rec in corpus))
        res = lh.fit_bound(corpus, "rec.a <= 2**(rec.r + rec.k - 3)")
        self.assertEqual(res.verdict, "HOLDS")
        self.assertGreater(res.per_ring[8]["slack_min"], 0)

    def test_structure_predicate_uses_lazy_path_and_agrees(self):
        corpus = lc.load_corpus(specs=self.SPEC, use_cache=False)
        pred = lh.compile_predicate("rec.trace[-1] == rec.b and len(rec.trace) == rec.rounds + 1")
        self.assertFalse(pred.vectorized)
        mask, meta = lh.evaluate(pred, corpus)
        self.assertEqual(meta["path"], "scalar")
        self.assertTrue(mask.all())

    def test_canonical_dedup_is_idempotent_across_a_repeated_spec(self):
        once = lc.load_corpus(specs=self.SPEC, use_cache=False)
        twice = lc.load_corpus(specs=self.SPEC + self.SPEC, use_cache=False)
        self.assertEqual(len(once), len(twice))
        self.assertEqual(once.signature(), twice.signature())
        self.assertEqual(twice.stats["n_duplicates"], len(once))


if __name__ == "__main__":
    unittest.main()
