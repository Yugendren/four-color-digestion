"""Tests for the independent brute-force |C(K)| tie-breaker.

Cross-checks `fourcolor.brute_force.brute_force_extendable_codes` (a
deliberately differently-implemented recomputation -- see that module's
docstring) against `fourcolor.reduce.extendable_codes` on a sample of the
pinned RSST catalog plus a handful of small generated configurations that
were found (via `tools/fr_table_crosscheck.py`) to trip up the compiled
`build/reduce_rsst` oracle's own count. Agreement here is what justifies
trusting `fourcolor.reduce.check` over the oracle for those cases (see
`results/theorem/fr_table/THEOREM.md`).
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.brute_force import brute_force_extendable_codes  # noqa: E402
from fourcolor.conf_parser import Configuration, parse_conf  # noqa: E402
from fourcolor.reduce import extendable_codes  # noqa: E402

RSST_CONF = ROOT / "third_party" / "arxiv-1401.6481" / "src" / "anc" / "unavoidable.conf"

# Three configurations from results/theorem/fr_table/ that made
# build/reduce_rsst abort with "ERROR: DISCREPANCY IN NUMBER OF EXTENDING
# COLOURINGS" against fourcolor.reduce.check's count -- the exact cases
# this module was written to independently adjudicate.
DISPUTED_FIXTURES = [
    # (ident, r, n, adjacency, reduce_py_n_extendable)
    ("fr-r8-n12-172", 8, 12,
     {1: [2, 9, 10, 11, 8], 2: [1, 3, 9], 3: [2, 4, 12, 9], 4: [3, 5, 12],
      5: [10, 12, 4, 6, 11], 6: [11, 5, 7], 7: [11, 6, 8], 8: [1, 11, 7],
      9: [1, 2, 3, 12, 10], 10: [1, 9, 12, 5, 11], 11: [1, 10, 5, 6, 7, 8],
      12: [9, 3, 4, 5, 10]}, 72),
    ("fr-r9-n13-269", 9, 13,
     {1: [2, 10, 9], 2: [1, 3, 11, 12, 10], 3: [2, 4, 11], 4: [3, 5, 13, 11],
      5: [6, 13, 4], 6: [10, 12, 13, 5, 7], 7: [10, 6, 8], 8: [10, 7, 9],
      9: [1, 10, 8], 10: [1, 2, 12, 6, 7, 8, 9], 11: [2, 3, 4, 13, 12],
      12: [2, 11, 13, 6, 10], 13: [11, 4, 5, 6, 12]}, 147),
]


class TestBruteForceMatchesReduce(unittest.TestCase):
    def test_agrees_on_catalog_sample(self):
        # brute_force_extendable_codes has no gauge-fixing or smart
        # variable ordering (deliberately -- see module docstring), so its
        # runtime is exponential-ish in edge count; restrict to small
        # configs (interior <= 6, i.e. <= ~20 edges) to keep this test
        # fast while still spanning several ring sizes.
        configs = [c for c in parse_conf(RSST_CONF) if c.n - c.r <= 6]
        self.assertGreaterEqual(len(configs), 5)
        for c in configs[::3]:
            with self.subTest(ident=c.ident):
                expected = extendable_codes(c)
                got = brute_force_extendable_codes(c)
                self.assertEqual(got, expected)

    def test_agrees_on_disputed_fixtures(self):
        # These are exactly the configs where the compiled RSST oracle
        # disagreed with fourcolor.reduce.check -- confirm the brute-force
        # tie-breaker sides with reduce.check, not the oracle.
        for ident, r, n, adj, expected_count in DISPUTED_FIXTURES:
            with self.subTest(ident=ident):
                cfg = Configuration(ident, n, r, -1, -1, [], adj, [])
                cfg.validate()
                expected = extendable_codes(cfg)
                got = brute_force_extendable_codes(cfg)
                self.assertEqual(len(expected), expected_count)
                self.assertEqual(got, expected)


if __name__ == "__main__":
    unittest.main()
