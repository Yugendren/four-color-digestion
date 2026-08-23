"""Tests for tools/lowdeg_refinement_check.py -- the exact enumeration that closes the
coarse-cartwheel gap in the ``d <= 6`` rows of ``tools/lp_discharge.py``.

The tool replaces ~10^7-10^8 calls to ``nl4ct.wheel_is_blocked`` by a *compiled* DNF over
the open second-neighbour degrees, so the two things that must be pinned down are (a) the
compiled predicate really is ``wheel_is_blocked``, and (b) the model count of that DNF is
right.  Both are tested against brute force on a deliberately tiny necklace
(``(5,6,9,9,9)``: only 4 open slots, 625 refinements, so the whole space is enumerable
with the untouched production blocking machinery in ~1 s), plus a spot differential on one
of the real certificate necklaces.
"""

import itertools
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import lowdeg_refinement_check as LR  # noqa: E402
from fourcolor import nl4ct as N  # noqa: E402

# 4 open slots -> 625 refinements, and unblocked as a coarse wheel, so both the
# blocked and the unblocked branch of every predicate get exercised.
TINY = (5, 6, 9, 9, 9)


@unittest.skipUnless(LR.R14_POOL_DIR.is_dir(), f"no pool at {LR.R14_POOL_DIR}")
class TestCompiledBlockingPredicate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.confs = N.load_configurations(LR.R14_POOL_DIR)
        cls.w = N.generate_cartwheel(len(TINY), list(TINY))
        cls.slots = LR.refinement_slots(cls.w)
        cls.terms, cls.always = LR.compile_blocking_dnf(cls.w, cls.confs, cls.slots)

    def test_slots_are_exactly_the_open_second_neighbours(self):
        g = self.w.g
        self.assertEqual(len(self.slots), 4)
        for v in self.slots:
            self.assertGreater(v, len(TINY))  # not the hub, not a spoke
            self.assertEqual((g.deg_lo[v], g.deg_hi[v]), (N.CARTWHEEL_DEG_MIN, N.CARTWHEEL_DEG_MAX))

    def test_dnf_equals_wheel_is_blocked_on_the_whole_refinement_space(self):
        """The compiled DNF must agree with the production blocking test on ALL 625
        refinements -- not a sample."""
        n = 0
        for vals in itertools.product(N.CARTWHEEL_DEGREES, repeat=len(self.slots)):
            a = dict(zip(self.slots, vals))
            self.assertEqual(
                LR.blocked_by_dnf(self.terms, a),
                N.wheel_is_blocked(LR.pin(self.w, a), self.confs),
                msg=f"disagreement at {a}",
            )
            n += 1
        self.assertEqual(n, 5 ** len(self.slots))

    def test_count_blocked_matches_brute_force(self):
        brute = sum(
            LR.blocked_by_dnf(self.terms, dict(zip(self.slots, vals)))
            for vals in itertools.product(N.CARTWHEEL_DEGREES, repeat=len(self.slots))
        )
        n_blocked, witnesses, _ = LR.count_blocked(self.terms, self.slots)
        self.assertEqual(n_blocked, brute)
        self.assertLess(n_blocked, 5 ** len(self.slots))  # this necklace does survive
        self.assertTrue(witnesses)
        for a in witnesses:
            self.assertFalse(N.wheel_is_blocked(LR.pin(self.w, a), self.confs))

    def test_structural_vertex_map_agrees_with_the_degree_aware_homomorphism(self):
        """``structural_vertex_map`` is ``nl4ct.homomorphism('include')`` with the degree
        test deferred; recombining the two must reproduce the original verdict."""
        g = LR.pin(self.w, {v: 7 for v in self.slots}).g
        rnd = random.Random(11)
        confs = rnd.sample(self.confs, 200)
        checked = matched = 0
        for conf in confs:
            for f_star in range(0, len(g.head), 3):
                direct = N.homomorphism(conf.g, conf.dart_id, g, f_star, "include") is not None
                pairs = LR.structural_vertex_map(conf.g, conf.dart_id, g, f_star)
                recombined = pairs is not None and all(
                    conf.g.deg_lo[h] <= g.deg_lo[hs] and g.deg_hi[hs] <= conf.g.deg_hi[h]
                    for h, hs in pairs
                )
                self.assertEqual(direct, recombined)
                checked += 1
                matched += direct
        self.assertGreater(checked, 1000)


@unittest.skipUnless(LR.R14_POOL_DIR.is_dir(), f"no pool at {LR.R14_POOL_DIR}")
class TestTailMaximisedIdentity(unittest.TestCase):
    """``_representative_degree`` collapses a ``[5,9]`` vertex to the single value 9, so
    the coarse blocking test IS the blocking test of the all-9 refinement.  That identity
    is what makes every unblocked low-degree row witnessed by an explicit refinement; if it
    ever breaks, the coarse-row gap reopens."""

    @classmethod
    def setUpClass(cls):
        cls.confs = N.load_configurations(LR.R14_POOL_DIR)

    def test_coarse_and_tail_maximised_agree_on_all_d5_necklaces(self):
        n = 0
        for degs in N.enum_wheel_degree_sequences(5):
            w = N.generate_cartwheel(5, list(degs))
            tm = LR.pin(w, {v: N.CARTWHEEL_DEG_MAX for v in LR.refinement_slots(w)})
            self.assertEqual(
                N.wheel_is_blocked(w, self.confs),
                N.wheel_is_blocked(tm, self.confs),
                msg=f"necklace {degs}",
            )
            n += 1
        self.assertEqual(n, 629)


@unittest.skipUnless(LR.R14_POOL_DIR.is_dir(), f"no pool at {LR.R14_POOL_DIR}")
class TestCertificateNecklaceSurvives(unittest.TestCase):
    """One real IIS necklace, end to end: the row is not spurious."""

    def test_d5_55767_has_unblocked_refinements(self):
        confs = N.load_configurations(LR.R14_POOL_DIR)
        res = LR.analyse((5, 5, 7, 6, 7), confs, rules=None, validate=150)
        self.assertEqual(res["n_slots"], 10)
        self.assertEqual(res["n_refinements"], 5 ** 10)
        self.assertEqual(res["n_blocked"] + res["n_unblocked"], res["n_refinements"])
        self.assertGreater(res["n_unblocked"], 0)
        self.assertFalse(res["coarse_blocked"])
        self.assertFalse(res["tail_maximised_blocked"])
        self.assertFalse(res["blocked_for_every_refinement"])
        self.assertEqual(res["validation"]["disagreements"], 0)
        self.assertTrue(res["witnesses"])
        for wt in res["witnesses"]:
            self.assertFalse(wt["blocked_recheck"])


if __name__ == "__main__":
    unittest.main()
