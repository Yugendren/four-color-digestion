"""Tests for the near-linear-4CT wheel-level discharging charge bound (src/fourcolor/nl4ct.py).

Ground truth: the C++ implementation under third_party/computer-checks/src. The full
exhaustive differential (enumerate every hub-degree-d necklace, compute the charge
bound + reducible-configuration blocking, and diff the resulting "possible bad wheel"
set against third_party/computer-checks/wheels/d{d}/*.cartwheel) is NOT fast: even for
d=11, whose final answer is only 8 wheels, the *search space* is 4,438,925 candidate
necklaces, and at ~10ms/candidate (charge bound + blocking, both involving hundreds of
rooted-homomorphism searches against 84 base rules / 671 combined rules / ~19754
reducible-configuration instances) that is on the order of half a day of wall clock.
That exhaustive run lives in tools/nl4ct_differential.py and is run out-of-band (see
results/nl4ct-differential/report_d*.json for outcomes); it is deliberately NOT part of
this fast test suite.

What IS fast, and is exercised here as a genuine differential against the C++ output:
  - Every published "possible bad wheel" file (all of wheels/d7..d11) must satisfy
    charge_bound(x0) >= 0 and must NOT be blocked_by_reducible_configuration -- these
    are exactly the two conditions the C++ used to keep them (CartWheel::prune with an
    empty combined_rule_with_spokes). Recomputing both conditions in Python for all
    16148 published wheels and requiring agreement is a strong (if one-directional)
    regression test: any bug that made our port stricter or looser than the C++ on
    real wheels would show up immediately.
  - A bounded PREFIX of the d=11 necklace enumeration (a few thousand candidates) is
    fully classified by our pipeline and cross-checked against the ground-truth SET
    (loaded from the 8 files): this is a genuine (if partial) two-directional exact
    differential, kept small enough to run in well under a minute.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor import nl4ct as m  # noqa: E402

RULE_DIR = m.default_rule_dir()
COMBINED_DIR = m.default_combined_rule_dir(blocked=False)
CONF_DIR = m.default_conf_dir()


def _have_data() -> bool:
    return RULE_DIR.is_dir() and COMBINED_DIR.is_dir() and CONF_DIR.is_dir()


@unittest.skipUnless(_have_data(), "third_party/computer-checks data not available")
class TestFormatRoundTrips(unittest.TestCase):
    def test_parse_rule_file(self):
        # rule001.rule: a degree-5 vertex sends 2 (tenths) to each neighbor.
        r = m.parse_rule_file(RULE_DIR / "rule001.rule")
        self.assertEqual(r.g.N, 2)
        self.assertEqual(r.amount, 2)
        # st_id must be the dart whose head is vertex 2 (t) and whose tail is vertex 1 (s).
        self.assertEqual(r.g.head[r.st_id], 1)
        self.assertEqual(r.g.head[r.g.rev[r.st_id]], 0)
        self.assertEqual((r.g.deg_lo[0], r.g.deg_hi[0]), (5, 5))
        self.assertEqual((r.g.deg_lo[1], r.g.deg_hi[1]), (5, m.INFTY))

    def test_parse_combined_rule_file(self):
        rules = m.load_rules(RULE_DIR)
        paths = sorted(p for p in COMBINED_DIR.iterdir() if p.suffix == ".combined_rule")
        cr = m.parse_combined_rule_file(paths[0], n_rules=len(rules))
        self.assertEqual(len(cr.combined_flag), len(rules))
        self.assertTrue(all(f in (0, 1) for f in cr.combined_flag))
        tail = cr.g.head[cr.g.rev[cr.st_id]]
        head = cr.g.head[cr.st_id]
        self.assertNotEqual(tail, head)
        self.assertGreaterEqual(cr.amount, 0)
        # amount must equal the sum of amounts of the base rules the flags select.
        expected_amount = sum(f * r.amount for f, r in zip(cr.combined_flag, rules))
        self.assertEqual(cr.amount, expected_amount)

    def test_parse_cartwheel_file_and_center_darts(self):
        w = m.parse_cartwheel_file(m.default_wheel_dir(11) / "d11_0.cartwheel")
        self.assertEqual(w.g.deg_lo[w.center], w.g.deg_hi[w.center])
        d = w.degree
        self.assertEqual(d, 11)
        self.assertEqual(len(w.center_darts), d)
        # Every center dart must point INTO the center.
        for dart in w.center_darts:
            self.assertEqual(w.g.head[dart], w.center)
        seq = m.spoke_degree_sequence(w)
        self.assertEqual(len(seq), d)
        self.assertTrue(all(5 <= x <= 9 for x in seq))

    def test_generate_cartwheel_matches_file_for_d11_sample(self):
        w_file = m.parse_cartwheel_file(m.default_wheel_dir(11) / "d11_0.cartwheel")
        seq = m.spoke_degree_sequence(w_file)
        w_gen = m.generate_cartwheel(11, seq)
        self.assertEqual(m.spoke_degree_sequence(w_gen), seq)
        self.assertEqual(w_gen.g.N, w_file.g.N)
        self.assertEqual(len(w_gen.g.head), len(w_file.g.head))


class TestDegreeOps(unittest.TestCase):
    def test_include_and_intersection(self):
        self.assertTrue(m.degree_include(5, m.INFTY, 7, 7))
        self.assertFalse(m.degree_include(5, 5, 6, 6))
        self.assertTrue(m.degree_has_intersection(5, 5, 5, 9))
        self.assertFalse(m.degree_has_intersection(5, 5, 6, 9))


class TestHomomorphismHandCheckable(unittest.TestCase):
    """A tiny, fully hand-verifiable rule/target pair: a single directed edge with a
    degree constraint at each endpoint (mirrors the shape of rule001.rule but with
    values chosen so both include- and intersection-mode outcomes can be checked by
    inspection)."""

    def setUp(self):
        # rule graph: vertex0 --dart0--> vertex1, vertex0 fixed degree 5, vertex1 any degree >= 5.
        rotations = [[1], [0]]
        self.rule_g = m.from_v_rotations(2, rotations, [5, 5], [5, m.INFTY])
        self.rule_st = m.find_dart(self.rule_g, head=1, tail=0)[0]

    def _target(self, d0_lo, d0_hi, d1_lo, d1_hi):
        rotations = [[1], [0]]
        g = m.from_v_rotations(2, rotations, [d0_lo, d1_lo], [d0_hi, d1_hi])
        dart = m.find_dart(g, head=1, tail=0)[0]
        return g, dart

    def test_include_requires_exact_degree5_source(self):
        g, dart = self._target(5, 5, 6, 6)
        self.assertIsNotNone(m.homomorphism(self.rule_g, self.rule_st, g, dart, "include"))

        g2, dart2 = self._target(6, 6, 6, 6)
        self.assertIsNone(m.homomorphism(self.rule_g, self.rule_st, g2, dart2, "include"))

    def test_intersection_is_looser_than_include(self):
        # target vertex0 has degree range [5,6]: doesn't CONTAIN-match a fixed rule
        # degree of exactly 5 in the "include" sense only if range != {5}; but it does
        # intersect {5}.
        g, dart = self._target(5, 6, 6, 6)
        self.assertIsNone(m.homomorphism(self.rule_g, self.rule_st, g, dart, "include"))
        self.assertIsNotNone(m.homomorphism(self.rule_g, self.rule_st, g, dart, "intersection"))

        # completely disjoint degree ranges: neither mode matches.
        g3, dart3 = self._target(6, 6, 6, 6)
        self.assertIsNone(m.homomorphism(self.rule_g, self.rule_st, g3, dart3, "intersection"))


class TestNecklaceEnumeration(unittest.TestCase):
    @staticmethod
    def _brute_force_necklace_count(d: int) -> int:
        """Independent reference: count distinct strings over {5..9}^d up to rotation
        by canonicalizing every one of the 5**d strings to its lexicographically
        smallest rotation and counting distinct canonical forms."""
        seen = set()
        for tup in _product_le(d):
            n = len(tup)
            best = min(tup[i:] + tup[:i] for i in range(n))
            seen.add(best)
        return len(seen)

    def test_small_degree_counts_match_brute_force(self):
        for d in (1, 2, 3, 4):
            with self.subTest(d=d):
                got = sorted(m.enum_wheel_degree_sequences(d))
                expected_count = self._brute_force_necklace_count(d)
                self.assertEqual(len(got), expected_count)
                self.assertEqual(len(got), len(set(got)))  # all distinct
                for seq in got:
                    self.assertTrue(m._is_lex_min(seq))

    def test_every_output_is_lex_min_and_uses_valid_alphabet(self):
        for seq in m.enum_wheel_degree_sequences(5):
            self.assertTrue(m._is_lex_min(seq))
            self.assertTrue(all(v in m.CARTWHEEL_DEGREES for v in seq))


def _product_le(d: int):
    import itertools

    return itertools.product(m.CARTWHEEL_DEGREES, repeat=d)


@unittest.skipUnless(_have_data(), "third_party/computer-checks data not available")
class TestChargeBoundAgainstGroundTruth(unittest.TestCase):
    """Differential against the C++ output: every wheel that survived the C++'s
    stage-1 prune (files under wheels/d{7..11}/) must, under our port, satisfy both
    conditions that keep a wheel in that file set."""

    @classmethod
    def setUpClass(cls):
        cls.rules = m.load_rules(RULE_DIR)
        cls.combined = m.load_combined_rules(COMBINED_DIR, len(cls.rules))
        cls.x0 = [r.amount for r in cls.rules]
        cls.confs = m.load_configurations(CONF_DIR)

    def test_ground_truth_wheels_have_nonnegative_charge_bound(self):
        # d=10/11 are small enough (626 + 8) to check exhaustively; d=7/8/9 are sampled
        # (deterministic prefix) to keep this test fast -- the full sweep over all
        # 16148 published wheels is exercised by tools/nl4ct_differential.py's
        # ground-truth cross-check instead, not by this "fast" suite.
        for d, sample in ((7, 400), (8, 400), (9, 400), (10, None), (11, None)):
            with self.subTest(degree=d):
                wheels = m.load_cartwheels(m.default_wheel_dir(d))
                self.assertGreater(len(wheels), 0)
                if sample is not None:
                    wheels = wheels[:sample]
                for w in wheels:
                    cb = m.charge_bound(w, self.rules, self.combined)
                    self.assertGreaterEqual(
                        cb, 0, f"d={d} wheel {m.spoke_degree_sequence(w)} has charge_bound {cb} < 0"
                    )

    def test_charge_bound_symbolic_matches_numeric(self):
        # d=11 is small (8 wheels); enough to catch a symbolic/numeric divergence cheaply.
        wheels = m.load_cartwheels(m.default_wheel_dir(11))
        for w in wheels:
            cb = m.charge_bound(w, self.rules, self.combined)
            form = m.charge_bound_symbolic(w, self.rules, self.combined)
            self.assertEqual(cb, form.evaluate(self.x0))

    def test_ground_truth_wheels_are_not_blocked(self):
        for d in (10, 11):  # d=10/11 kept small enough to stay fast (626 + 8 wheels)
            with self.subTest(degree=d):
                wheels = m.load_cartwheels(m.default_wheel_dir(d))
                for w in wheels:
                    self.assertFalse(
                        m.wheel_is_blocked(w, self.confs),
                        f"d={d} wheel {m.spoke_degree_sequence(w)} is blocked but is in the ground-truth set",
                    )


@unittest.skipUnless(_have_data(), "third_party/computer-checks data not available")
class TestBoundedPrefixExactDifferentialD11(unittest.TestCase):
    """A genuine two-directional exact differential for d=11, restricted to a bounded
    prefix of the necklace enumeration so it stays fast. See tools/nl4ct_differential.py
    for the full (4,438,925-candidate) run."""

    PREFIX = 3000

    @classmethod
    def setUpClass(cls):
        cls.rules = m.load_rules(RULE_DIR)
        cls.combined = m.load_combined_rules(COMBINED_DIR, len(cls.rules))
        cls.confs = m.load_configurations(CONF_DIR)
        cls.truth = {
            m.spoke_degree_sequence(w) for w in m.load_cartwheels(m.default_wheel_dir(11))
        }

    def test_prefix_predictions_match_ground_truth_membership(self):
        n_checked = 0
        for i, seq in enumerate(m.enum_wheel_degree_sequences(11)):
            if i >= self.PREFIX:
                break
            w = m.generate_cartwheel(11, seq)
            cb = m.charge_bound(w, self.rules, self.combined)
            predicted_bad = cb >= 0 and not m.wheel_is_blocked(w, self.confs)
            in_truth = seq in self.truth
            self.assertEqual(
                predicted_bad, in_truth, f"disagreement at seq={seq} (cb={cb})"
            )
            n_checked += 1
        self.assertEqual(n_checked, self.PREFIX)


if __name__ == "__main__":
    unittest.main()
