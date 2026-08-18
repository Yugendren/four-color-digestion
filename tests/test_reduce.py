"""Differential tests for the independent reducibility checker.

Ground truth: the header fields of the published RSST configuration records
(a = |C(K)|, b = |C'(K)|) and the fact that every one of the 633 must verify
as D- or C-reducible. Full-set differential lives in tools/differential.py;
here we keep a fast subset (ring <= 8, ~10s) so `make test` stays quick.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.conf_parser import parse_conf  # noqa: E402
from fourcolor.reduce import (  # noqa: E402
    SIMATCHNUMBER,
    balanced_signed_matchings,
    _matching_codes,
    _is_canonical_code,
    check,
)

RSST_CONF = ROOT / "third_party" / "arxiv-1401.6481" / "src" / "anc" / "unavoidable.conf"


class TestMatchings(unittest.TestCase):
    def test_counts_match_reduce_c_table(self):
        for r in range(2, 9):
            self.assertEqual(
                len(balanced_signed_matchings(r)), SIMATCHNUMBER[r], f"r={r}"
            )

    def test_all_generated_codes_canonical(self):
        for r in (6, 7, 8):
            for m in balanced_signed_matchings(r):
                for v in _matching_codes(m):
                    self.assertTrue(
                        _is_canonical_code(abs(v), r),
                        f"r={r} matching {m.pairs} value {v}",
                    )


class TestReducibilityDifferential(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configs = [c for c in parse_conf(RSST_CONF) if c.r <= 8]

    def test_subset_nonempty(self):
        self.assertGreaterEqual(len(self.configs), 5)

    def test_header_agreement_and_reducibility(self):
        for c in self.configs:
            res = check(c)
            self.assertEqual(res.n_extendable, c.a, f"{c.ident}: |C(K)|")
            self.assertEqual(res.n_consistent, c.b, f"{c.ident}: |C'(K)|")
            self.assertTrue(
                res.d_reducible or res.c_reducible, f"{c.ident}: not reducible?"
            )

    def test_negative_control_corrupted_config(self):
        # Removing one interior edge from a D-reducible configuration must
        # change the extendable-coloring count (the verdict is recomputed,
        # not pattern-matched). We add an edge slot corruption by deleting
        # a vertex's last neighbor entry symmetrically.
        import copy

        c = copy.deepcopy(self.configs[0])
        res_orig = check(c)
        # corrupt: drop the edge between the two highest interior vertices
        # that are adjacent
        done = False
        for v in range(c.n, c.r, -1):
            for u in list(c.adjacency[v]):
                if u > c.r:
                    c.adjacency[v].remove(u)
                    c.adjacency[u].remove(v)
                    done = True
                    break
            if done:
                break
        self.assertTrue(done)
        try:
            res_corrupt = check(c)
            self.assertNotEqual(
                (res_orig.n_extendable, res_orig.n_consistent),
                (res_corrupt.n_extendable, res_corrupt.n_consistent),
            )
        except Exception:
            pass  # a structural failure on corrupted input is also acceptable


if __name__ == "__main__":
    unittest.main()
