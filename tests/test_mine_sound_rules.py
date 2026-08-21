"""Fast unit tests for tools/mine_sound_rules.py's rule-evaluation
machinery (atom construction/evaluation, the vectorized zero-FP mining
search with its minimality filter, per-ring breakdown, witness-margin
computation, k-fold splitting, and mask-based rule dedup) plus a small
smoke test of the pooling/feature-extraction loader on a couple of real
data files. No dependency on the (multi-minute) full mining run itself."""

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import mine_sound_rules as msr  # noqa: E402


class TestBuildAtoms(unittest.TestCase):
    def test_constant_feature_produces_no_atoms(self):
        X = np.array([[1.0], [1.0], [1.0]])
        atoms = msr.build_atoms(X, ["f"])
        self.assertEqual(atoms, [])

    def test_low_cardinality_feature_gets_eq_ge_le_atoms(self):
        X = np.array([[0.0], [1.0], [2.0]])
        atoms = msr.build_atoms(X, ["f"], eq_cap=20, ge_cap=15, le_cap=15)
        ops = {(a.op, a.value) for a in atoms}
        self.assertIn(("eq", 0.0), ops)
        self.assertIn(("eq", 1.0), ops)
        self.assertIn(("eq", 2.0), ops)
        self.assertIn(("ge", 1.0), ops)
        self.assertIn(("ge", 2.0), ops)
        self.assertIn(("le", 0.0), ops)
        self.assertIn(("le", 1.0), ops)
        # ">= min" and "<= max" are trivially all-true -- excluded
        self.assertNotIn(("ge", 0.0), ops)
        self.assertNotIn(("le", 2.0), ops)

    def test_high_cardinality_feature_skips_eq_and_caps_thresholds(self):
        X = np.arange(100.0).reshape(-1, 1)
        atoms = msr.build_atoms(X, ["f"], eq_cap=5, ge_cap=10, le_cap=10)
        self.assertTrue(all(a.op != "eq" for a in atoms))
        n_ge = sum(1 for a in atoms if a.op == "ge")
        n_le = sum(1 for a in atoms if a.op == "le")
        self.assertLessEqual(n_ge, 10)
        self.assertLessEqual(n_le, 10)

    def test_two_features_no_cross_contamination(self):
        X = np.array([[0.0, 10.0], [1.0, 20.0]])
        atoms = msr.build_atoms(X, ["a", "b"], eq_cap=20)
        self.assertTrue(all(a.feature_name in ("a", "b") for a in atoms))
        a_vals = {a.value for a in atoms if a.feature_name == "a"}
        b_vals = {a.value for a in atoms if a.feature_name == "b"}
        self.assertTrue(a_vals.issubset({0.0, 1.0}))
        self.assertTrue(b_vals.issubset({10.0, 20.0}))


class TestAtomEvaluation(unittest.TestCase):
    def test_holds_ge_le_eq(self):
        X = np.array([[1.0], [2.0], [3.0]])
        ge = msr.Atom(0, "f", "ge", 2.0)
        le = msr.Atom(0, "f", "le", 2.0)
        eq = msr.Atom(0, "f", "eq", 2.0)
        np.testing.assert_array_equal(ge.holds(X), [False, True, True])
        np.testing.assert_array_equal(le.holds(X), [True, True, False])
        np.testing.assert_array_equal(eq.holds(X), [False, True, False])

    def test_slack(self):
        col = np.array([1.0, 2.0, 5.0])
        ge = msr.Atom(0, "f", "ge", 2.0)
        le = msr.Atom(0, "f", "le", 5.0)
        eq = msr.Atom(0, "f", "eq", 2.0)
        np.testing.assert_allclose(ge.slack(col), [-1.0, 0.0, 3.0])
        np.testing.assert_allclose(le.slack(col), [4.0, 3.0, 0.0])
        np.testing.assert_allclose(eq.slack(col), [0.0, 0.0, 0.0])

    def test_evaluate_atoms_matrix_shape_and_values(self):
        X = np.array([[1.0], [2.0], [3.0]])
        atoms = [msr.Atom(0, "f", "ge", 2.0), msr.Atom(0, "f", "le", 2.0)]
        M = msr.evaluate_atoms(X, atoms)
        self.assertEqual(M.shape, (2, 3))
        np.testing.assert_array_equal(M[0], [False, True, True])
        np.testing.assert_array_equal(M[1], [True, True, False])

    def test_rule_mask_is_and_of_atoms(self):
        X = np.array([[1.0], [2.0], [3.0]])
        atoms = [msr.Atom(0, "f", "ge", 2.0), msr.Atom(0, "f", "le", 2.0)]
        M = msr.evaluate_atoms(X, atoms)
        mask = msr.rule_mask(M, (0, 1))
        np.testing.assert_array_equal(mask, [False, True, False])

    def test_atom_str_formats_int_valued_floats_without_decimal(self):
        self.assertEqual(str(msr.Atom(0, "f", "ge", 3.0)), "f >= 3")
        self.assertEqual(str(msr.Atom(0, "f", "le", 2.5)), "f <= 2.5")
        self.assertEqual(str(msr.Atom(0, "f", "eq", 0.0)), "f == 0")


class TestMineRules(unittest.TestCase):
    """A hand-built toy dataset where the ground truth needs a genuine
    2-atom conjunction (no single atom is sound alone), to check the core
    search finds it and the minimality filter behaves correctly."""

    def _toy(self):
        # feature 0: "a", feature 1: "b". target = (a >= 2) & (b >= 2).
        # Rows where a>=2 alone is NOT sound (row 2 has a=3,b=0 -> negative
        # but a>=2 holds), and b>=2 alone is NOT sound (row 3 has a=0,b=3
        # -> negative but b>=2 holds). Only the conjunction is sound.
        X = np.array([
            [2.0, 2.0],  # positive
            [3.0, 3.0],  # positive
            [3.0, 0.0],  # negative, a>=2 holds alone -> a>=2 unsound alone
            [0.0, 3.0],  # negative, b>=2 holds alone -> b>=2 unsound alone
            [0.0, 0.0],  # negative
        ])
        y = np.array([True, True, False, False, False])
        # eq_cap=0: disable `==` atoms here so the toy stays about ge/le
        # conjunctions specifically (an `==` atom on a value that never
        # recurs among negatives would trivially be a sound single,
        # defeating the "no single atom is sound alone" premise below).
        atoms = msr.build_atoms(X, ["a", "b"], eq_cap=0)
        M = msr.evaluate_atoms(X, atoms)
        return X, y, atoms, M

    def test_finds_the_genuine_conjunction_with_zero_fp(self):
        X, y, atoms, M = self._toy()
        rules = msr.mine_rules(M, y, atoms, promising_fp_cap=10, promising_pair_limit=1000)
        # every returned rule must actually be zero-FP and the atom `a>=2 AND b>=2`
        # (by feature name/op/value, not exact index) must appear
        found = any(
            {(a.feature_name, a.op, a.value) for a in r.atoms} == {("a", "ge", 2.0), ("b", "ge", 2.0)}
            for r in rules
        )
        self.assertTrue(found)
        for r in rules:
            self.assertEqual(r.fp, 0)

    def test_no_single_atom_is_sound_in_this_toy(self):
        X, y, atoms, M = self._toy()
        rules = msr.mine_rules(M, y, atoms, promising_fp_cap=10, promising_pair_limit=1000)
        self.assertTrue(all(r.depth != 1 for r in rules))

    def test_minimality_drops_redundant_superset_rules(self):
        # Here a>=2 ALONE is already sound (no negative row has a>=2), so
        # any 2- or 3-atom rule built by ANDing a>=2 with something else
        # must be filtered out as non-minimal (dominated by the single).
        X = np.array([
            [2.0, 5.0],
            [3.0, 5.0],
            [0.0, 5.0],  # negative
            [0.0, 0.0],  # negative
        ])
        y = np.array([True, True, False, False])
        atoms = msr.build_atoms(X, ["a", "b"])
        M = msr.evaluate_atoms(X, atoms)
        rules = msr.mine_rules(M, y, atoms, promising_fp_cap=10, promising_pair_limit=1000)
        self.assertTrue(any(r.depth == 1 for r in rules))
        for r in rules:
            if r.depth > 1:
                names = {a.feature_name for a in r.atoms}
                self.assertNotIn("a", names, "a longer rule built on top of the already-sound single `a` atom should have been filtered as non-minimal")

    def test_row_mask_restricts_scoring_to_subset(self):
        X, y, atoms, M = self._toy()
        # Drop only row 4 (a negative that isn't needed to rule out either
        # single atom -- row 2 still breaks `a>=2` alone, row 3 still
        # breaks `b>=2` alone) -- the genuine pair stays the minimal sound
        # rule on this subset too, with IDENTICAL coverage (row 4 wasn't
        # positive, so dropping it can't change any rule's coverage count).
        row_mask = np.array([True, True, True, True, False])
        rules_subset = msr.mine_rules(M, y, atoms, row_mask=row_mask, promising_fp_cap=10, promising_pair_limit=1000)
        rules_full = msr.mine_rules(M, y, atoms, promising_fp_cap=10, promising_pair_limit=1000)
        cov_subset = {r.atom_indices: r.coverage for r in rules_subset}
        cov_full = {r.atom_indices: r.coverage for r in rules_full}
        shared = set(cov_subset) & set(cov_full)
        self.assertTrue(shared)
        for k in shared:
            self.assertLessEqual(cov_subset[k], cov_full[k])

    def test_dedup_rules_by_mask_keeps_first_of_each_distinct_satisfying_set(self):
        # two atoms on IDENTICAL underlying data (duplicate feature),
        # thresholded so each is independently zero-FP -- both produce the
        # exact same satisfying mask, so dedup should keep exactly one.
        X = np.array([[5.0, 5.0], [1.0, 1.0]])
        y = np.array([True, False])
        atoms = [msr.Atom(0, "dup_a", "ge", 5.0), msr.Atom(1, "dup_b", "ge", 5.0)]
        M = msr.evaluate_atoms(X, atoms)
        rules = msr.mine_rules(M, y, atoms, promising_fp_cap=10, promising_pair_limit=1000)
        self.assertEqual(len(rules), 2)  # both are individually sound and minimal
        self.assertTrue(all(r.fp == 0 for r in rules))
        deduped = msr.dedup_rules_by_mask(M, rules, limit=10)
        self.assertEqual(len(deduped), 1)


class TestPerRingBreakdown(unittest.TestCase):
    def test_counts_covered_and_total_per_ring(self):
        mask = np.array([True, False, True, True])
        target = np.array([True, True, False, True])
        ring = np.array([8, 8, 9, 9])
        out = msr.per_ring_breakdown(mask, target, ring)
        # ring 8: target rows = [0,1] (both True); mask&target -> row0 only
        self.assertEqual(out[8], {"covered": 1, "total_target_in_ring": 2})
        # ring 9: target rows = [3] (row2 is target=False); mask&target -> row3
        self.assertEqual(out[9], {"covered": 1, "total_target_in_ring": 1})

    def test_ring_with_zero_target_rows_is_omitted(self):
        mask = np.array([True, True])
        target = np.array([False, False])
        ring = np.array([10, 10])
        out = msr.per_ring_breakdown(mask, target, ring)
        self.assertEqual(out, {})


class TestRuleWitnesses(unittest.TestCase):
    def test_smallest_margin_first(self):
        X = np.array([[2.0], [5.0], [10.0]])
        records = [{"ident": "a", "r": 8, "n": 10}, {"ident": "b", "r": 8, "n": 10}, {"ident": "c", "r": 8, "n": 10}]
        atoms = (msr.Atom(0, "f", "ge", 2.0),)
        mask = np.array([True, True, True])
        target = np.array([True, True, True])
        out = msr.rule_witnesses(X, records, atoms, mask, target, top_n=3)
        self.assertEqual([w["ident"] for w in out], ["a", "b", "c"])
        self.assertEqual(out[0]["margin"], 0.0)

    def test_empty_when_nothing_satisfies(self):
        X = np.array([[1.0]])
        records = [{"ident": "a", "r": 8, "n": 10}]
        atoms = (msr.Atom(0, "f", "ge", 5.0),)
        mask = np.array([False])
        target = np.array([True])
        out = msr.rule_witnesses(X, records, atoms, mask, target)
        self.assertEqual(out, [])


class TestKfoldIndices(unittest.TestCase):
    def test_folds_partition_all_indices_disjointly(self):
        folds = msr.kfold_indices(23, k=5, seed=0)
        self.assertEqual(len(folds), 5)
        all_idx = np.concatenate(folds)
        self.assertEqual(sorted(all_idx.tolist()), list(range(23)))
        for i in range(5):
            for j in range(i + 1, 5):
                self.assertEqual(len(set(folds[i].tolist()) & set(folds[j].tolist())), 0)

    def test_deterministic_given_seed(self):
        f1 = msr.kfold_indices(50, k=5, seed=7)
        f2 = msr.kfold_indices(50, k=5, seed=7)
        for a, b in zip(f1, f2):
            np.testing.assert_array_equal(a, b)


class TestFeatureVariant(unittest.TestCase):
    def test_structural_variant_excludes_leaky_features(self):
        idx, names = msr.feature_variant("structural")
        self.assertNotIn("n_extendable", names)
        self.assertNotIn("n_extendable_ratio", names)
        self.assertEqual(len(idx), len(names))

    def test_full_variant_includes_everything(self):
        idx, names = msr.feature_variant("full")
        self.assertEqual(names, msr.FEATURE_NAMES)

    def test_invalid_variant_name_raises(self):
        with self.assertRaises(ValueError):
            msr.feature_variant("nope")


class TestComputeFeatureVector(unittest.TestCase):
    def test_length_matches_feature_names(self):
        adjacency = {1: [2, 3], 2: [3, 1], 3: [1, 2]}
        vec = msr.compute_feature_vector(adjacency, r=3, n=3, n_extendable=2, n_consistent=0)
        self.assertEqual(len(vec), len(msr.FEATURE_NAMES))
        self.assertTrue(all(isinstance(v, float) for v in vec))


class TestLoadPoolSmoke(unittest.TestCase):
    """Real-data smoke test (small slice) -- confirms the loader, dedup,
    and conflict detection wiring work end to end without needing the
    full ~17k-record pool or the multi-minute mining run."""

    def test_loads_and_dedups_a_small_real_file(self):
        traces = ROOT / "data" / "v2" / "traces_r8.jsonl"
        if not traces.exists():
            self.skipTest("data/v2/traces_r8.jsonl not present")
        import itertools
        import json
        import tempfile

        lines = []
        with traces.open() as f:
            for line in itertools.islice(f, 30):
                lines.append(line)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "small.jsonl"
            p.write_text("".join(lines))
            records, stats = msr.load_pool([p])
        self.assertEqual(stats["n_raw"], 30)
        self.assertGreater(stats["n_deduped"], 0)
        self.assertLessEqual(stats["n_deduped"], 30)
        self.assertEqual(stats["n_conflicts"], 0)
        for rec in records:
            self.assertEqual(len(rec["features"]), len(msr.FEATURE_NAMES))

    def test_conflicting_labels_at_same_canonical_key_raise(self):
        import json
        import tempfile

        adjacency = {1: [2, 3], 2: [3, 1], 3: [1, 2]}
        rec_true = {
            "ident": "x1", "r": 3, "n": 3, "adjacency": adjacency,
            "d_reducible": True, "n_extendable": 1, "n_consistent": 0,
        }
        rec_false = dict(rec_true, ident="x2", d_reducible=False)
        with tempfile.TemporaryDirectory() as td:
            p1 = Path(td) / "a.jsonl"
            p2 = Path(td) / "b.jsonl"
            p1.write_text(json.dumps(rec_true) + "\n")
            p2.write_text(json.dumps(rec_false) + "\n")
            with self.assertRaises(AssertionError):
                msr.load_pool([p1, p2])


if __name__ == "__main__":
    unittest.main()
