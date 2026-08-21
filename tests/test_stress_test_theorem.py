"""Unit tests for tools/stress_test_theorem.py's rule-evaluation and gate
machinery (the parts that are cheap/fast to exercise directly -- the actual
mutation-search-and-label loop is exercised end-to-end by running the tool
itself with tiny budgets, see the smoke-test invocation recorded in
results/theorem/stress_test.md's provenance)."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import stress_test_theorem as stt  # noqa: E402

D1_CORPUS = ROOT / "data" / "d1_corpus.jsonl"


class TestRuleAtomsMatchCandidatesMd(unittest.TestCase):
    """The three RULES + DUAL_RULE atom lists are hand-transcribed from
    results/theorem/candidates.md; this pins them so a future edit to
    candidates.md (re-mining) doesn't silently desync the stress test from
    what it claims to be testing."""

    def test_candidate1(self):
        r = stt.RULES[0]
        self.assertEqual(r.name, "candidate1")
        self.assertEqual(
            [(n, o) for n, o, v in r.atoms],
            [("n", "ge"), ("mean_interior_degree", "ge"), ("h5_density", "le")],
        )

    def test_candidate2(self):
        r = stt.RULES[1]
        self.assertEqual(
            [(n, o) for n, o, v in r.atoms],
            [("n", "ge"), ("max_run_const_degree_ring", "le"), ("n_deg5_ge3_deg5_neighbors", "eq")],
        )

    def test_candidate3(self):
        r = stt.RULES[2]
        self.assertEqual(
            [(n, o) for n, o, v in r.atoms],
            [("n_interior", "ge"), ("h5_density", "le"), ("n_deg5_ge3_deg5_neighbors", "eq")],
        )

    def test_dual_rule(self):
        self.assertEqual(stt.DUAL_RULE.direction, "nonreducible")
        self.assertEqual(
            [(n, o, v) for n, o, v in stt.DUAL_RULE.atoms],
            [("r", "eq", 11), ("n_interior", "le", 6)],
        )


class TestRuleHolds(unittest.TestCase):
    def test_all_atoms_must_hold(self):
        rule = stt.Rule("t", "reducible", [("x", "ge", 5), ("y", "le", 2)])
        self.assertTrue(rule.holds({"x": 5, "y": 2}))
        self.assertFalse(rule.holds({"x": 4, "y": 2}))
        self.assertFalse(rule.holds({"x": 5, "y": 3}))

    def test_eq_atom(self):
        rule = stt.Rule("t", "reducible", [("z", "eq", 0)])
        self.assertTrue(rule.holds({"z": 0}))
        self.assertFalse(rule.holds({"z": 1}))


class TestComputeFeatures(unittest.TestCase):
    def test_matches_candidates_md_reference_values(self):
        # From results/theorem/candidates.md's witness table: ident
        # "1328.1032" (rsst633, r=14, n=25) has n_interior=11,
        # h5_density=0.2, n_deg5_ge3_deg5_neighbors=0, mean_interior_degree
        # =5.81818.
        with D1_CORPUS.open() as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("ident") == "1328.1032":
                    break
            else:
                self.skipTest("witness ident not found in d1_corpus.jsonl")
        adj = {int(k): v for k, v in rec["adjacency"].items()}
        feats = stt.compute_features(adj, rec["r"], rec["n"])
        self.assertEqual(feats["n_interior"], 11.0)
        self.assertAlmostEqual(feats["h5_density"], 0.2)
        self.assertEqual(feats["n_deg5_ge3_deg5_neighbors"], 0.0)
        self.assertAlmostEqual(feats["mean_interior_degree"], 5.818181818181818)
        # And the rule should actually fire on its own documented witness.
        self.assertTrue(stt.RULES[2].holds(feats))  # candidate3


class TestStructuralGate(unittest.TestCase):
    def test_pool_configs_pass_gate(self):
        n_checked = 0
        with D1_CORPUS.open() as f:
            for line in f:
                rec = json.loads(line)
                adj = {int(k): v for k, v in rec["adjacency"].items()}
                self.assertTrue(stt.structural_gate(adj, rec["r"], rec["n"]), rec["ident"])
                n_checked += 1
                if n_checked >= 100:
                    break
        self.assertGreater(n_checked, 0)


class TestOracleCrossCheck(unittest.TestCase):
    def test_returns_none_if_binary_missing(self):
        old = stt.ORACLE_BINARY
        try:
            stt.ORACLE_BINARY = ROOT / "build" / "does_not_exist_binary"
            self.assertIsNone(stt.oracle_cross_check({1: [2], 2: [1]}, 6, 2, "x", 0, 0))
        finally:
            stt.ORACLE_BINARY = old


if __name__ == "__main__":
    unittest.main()
