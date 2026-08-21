"""Parser tests against the pinned RSST and Steinberger configuration files."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.conf_parser import (  # noqa: E402
    Configuration, for_rsst_oracle, parse_conf, serialize,
)

RSST_CONF = ROOT / "third_party" / "arxiv-1401.6481" / "src" / "anc" / "unavoidable.conf"
STEIN_CONF = ROOT / "third_party" / "arxiv-0905.0043" / "src" / "anc" / "U_2822.conf"
REDUCE_RSST = ROOT / "build" / "reduce_rsst"


class TestRSSTParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configs = parse_conf(RSST_CONF)

    def test_count_is_633(self):
        self.assertEqual(len(self.configs), 633)

    def test_first_record_matches_inspection(self):
        c = self.configs[0]
        self.assertEqual(c.ident, "0.7322")
        self.assertEqual((c.n, c.r, c.a, c.b), (10, 6, 16, 0))
        self.assertEqual(c.contract, [])
        self.assertEqual(c.adjacency[1], [2, 7, 10, 6])
        self.assertEqual(c.adjacency[10], [9, 5, 6, 1, 7])
        self.assertEqual(len(c.coords), 10)

    def test_ring_size_bounds(self):
        # RSST reduce.c has MAXRING 14; every ring size must be 6..14.
        for c in self.configs:
            self.assertGreaterEqual(c.r, 6, c.ident)
            self.assertLessEqual(c.r, 14, c.ident)

    def test_vertex_bound(self):
        # VERTS 27 in reduce.c means n <= 26.
        for c in self.configs:
            self.assertLessEqual(c.n, 26, c.ident)

    def test_contract_sizes(self):
        # All RSST contracts have at most 4 edges (dossier §1).
        for c in self.configs:
            self.assertLessEqual(len(c.contract), 4, c.ident)

    def test_round_trip(self):
        text = serialize(self.configs)
        tmp = ROOT / "build" / "roundtrip-rsst.conf"
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_text(text)
        reparsed = parse_conf(tmp)
        self.assertEqual(len(reparsed), len(self.configs))
        for a, b in zip(self.configs, reparsed):
            self.assertEqual(a, b)

    def test_networkx_export(self):
        g = self.configs[0].to_networkx()
        self.assertEqual(g.number_of_nodes(), 10)
        # Every finite face of a near-triangulation completion is a triangle,
        # so the graph is connected and has minimum degree >= 2.
        degrees = [d for _, d in g.degree()]
        self.assertGreaterEqual(min(degrees), 2)


class TestSteinbergerParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configs = parse_conf(STEIN_CONF)

    def test_count_is_2822(self):
        self.assertEqual(len(self.configs), 2822)

    def test_all_d_reducible_means_empty_contracts(self):
        # Steinberger's set is D-only: no contracts anywhere.
        for c in self.configs:
            self.assertEqual(c.contract, [], c.ident)

    def test_ring_size_bounds(self):
        # Steinberger's reduce.c has MAXRING 16.
        for c in self.configs:
            self.assertGreaterEqual(c.r, 6, c.ident)
            self.assertLessEqual(c.r, 16, c.ident)

    def test_ring_16_present(self):
        # His set genuinely uses the extended ring sizes.
        self.assertTrue(any(c.r >= 15 for c in self.configs))


# Two fixtures pulled from a real plantri -P8 -c3 run (tools/datagen.py's
# relabeling): a D-reducible ring-8/n=13 configuration and a non-D-reducible
# ring-8/n=10 one. Neither ring vertex's neighbor list happens to start at
# its RSST-required position (e.g. vertex 3 of RED is [2, 4, 10]: ring
# neighbors 2 and 4 are both present, but RSST condition (4) requires the
# list to start at 4 and end at 2) -- exactly the case `for_rsst_oracle`
# exists to fix. n=13 > 8 also exercises `serialize`'s coordinate-wrapping.
RED_ADJ = {1: [2, 9, 8], 2: [1, 3, 10, 9], 3: [2, 4, 10], 4: [3, 5, 11, 10],
           5: [11, 4, 6, 12], 6: [12, 5, 7, 13], 7: [8, 13, 6],
           8: [1, 9, 13, 7], 9: [1, 2, 10, 11, 12, 13, 8],
           10: [2, 3, 4, 11, 9], 11: [9, 10, 4, 5, 12], 12: [9, 11, 5, 6, 13],
           13: [9, 12, 6, 7, 8]}
RED_R, RED_N, RED_A, RED_B = 8, 13, 95, 0  # D-reducible: b (|C'|) is 0

NONRED_ADJ = {1: [2, 9, 10, 8], 2: [1, 3, 9], 3: [2, 4, 9], 4: [9, 3, 5],
              5: [9, 4, 6], 6: [9, 5, 7, 10], 7: [10, 6, 8], 8: [1, 10, 7],
              9: [1, 2, 3, 4, 5, 6, 10], 10: [1, 9, 6, 7, 8]}
NONRED_R, NONRED_N, NONRED_A, NONRED_B = 8, 10, 53, 220  # not D-reducible


class TestForRsstOracle(unittest.TestCase):
    def test_rotates_ring_lists_to_rsst_start(self):
        cfg = Configuration("red", RED_N, RED_R, RED_A, RED_B, [], RED_ADJ, [])
        # Sanity: this fixture really does have a ring vertex whose list
        # does not already start at the RSST-required position.
        self.assertNotEqual(cfg.adjacency[3][0], 4)

        fixed = for_rsst_oracle(cfg, a=RED_A, b=RED_B)
        for i in range(1, RED_R + 1):
            nbrs = fixed.adjacency[i]
            expected_start = 1 if i == RED_R else i + 1
            expected_end = RED_R if i == 1 else i - 1
            self.assertEqual(nbrs[0], expected_start, i)
            self.assertEqual(nbrs[-1], expected_end, i)
            # Rotation is a cyclic relabel only -- same neighbor set.
            self.assertEqual(set(nbrs), set(cfg.adjacency[i]), i)

    def test_coords_filled_when_absent(self):
        cfg = Configuration("red", RED_N, RED_R, RED_A, RED_B, [], RED_ADJ, [])
        fixed = for_rsst_oracle(cfg, a=RED_A, b=RED_B)
        self.assertEqual(len(fixed.coords), RED_N)


class TestSerializeCoordWrapping(unittest.TestCase):
    def test_no_line_exceeds_8_coordinate_numbers(self):
        # reduce.c's ReadConf reads coordinates by fgets()-ing one line at a
        # time and sscanf()-ing AT MOST 8 numbers per call; a coords line
        # with more than 8 numbers silently loses the rest. serialize() must
        # never emit such a line.
        cfg = Configuration("red", RED_N, RED_R, RED_A, RED_B, [], RED_ADJ,
                             list(range(1, RED_N + 1)))
        text = serialize([cfg])
        lines = text.splitlines()
        # ident, header, contract = 3 lines; then n adjacency rows; then the
        # coordinate line(s); then a trailing blank separator line.
        coord_lines = lines[3 + RED_N:-1]
        self.assertTrue(coord_lines)
        for line in coord_lines:
            self.assertLessEqual(len(line.split()), 8, line)
        # And the numbers really do round-trip through the real 8-per-line
        # convention used by the pinned RSST catalog file (spot check).
        flat = [int(x) for line in coord_lines for x in line.split()]
        self.assertEqual(flat, list(range(1, RED_N + 1)))

    def test_empty_coords_does_not_corrupt_multi_record_round_trip(self):
        # Regression: serialize() used to emit a single blank line for
        # cfg.coords == [] (the common case for internally-built
        # Configurations, e.g. tools/datagen.py). parse_conf's tokenizer
        # drops blank lines entirely, so with 2+ records that blank coords
        # line vanished and the coords-reading loop for record 1 ran on
        # into record 2's identifier line, corrupting the whole parse.
        cfg1 = Configuration("c1", NONRED_N, NONRED_R, NONRED_A, NONRED_B, [],
                              NONRED_ADJ, [])
        cfg2 = Configuration("c2", RED_N, RED_R, RED_A, RED_B, [], RED_ADJ, [])
        text = serialize([cfg1, cfg2])
        reparsed = parse_conf_text(text)
        self.assertEqual(len(reparsed), 2)
        self.assertEqual(reparsed[0].ident, "c1")
        self.assertEqual(reparsed[0].adjacency, NONRED_ADJ)
        self.assertEqual(reparsed[1].ident, "c2")
        self.assertEqual(reparsed[1].adjacency, RED_ADJ)


class TestRsstOracleCrossCheck(unittest.TestCase):
    """Runs the actual compiled RSST oracle (build/reduce_rsst) against the
    two fixtures above and checks its verdict against the header a-value
    self-check + printed '*** D-reducible ***' / 'NOT proposed a contract'
    behavior (see checkcontract()/printstatus() in reduce.c): skipped if
    the binary hasn't been built (`make oracle` / Makefile's build/
    reduce_rsst rule)."""

    @classmethod
    def setUpClass(cls):
        if not REDUCE_RSST.exists():
            raise unittest.SkipTest(f"{REDUCE_RSST} not built (see Makefile)")

    def _run(self, adj, r, n, a, b, tmp_path) -> subprocess.CompletedProcess:
        cfg = Configuration("t", n, r, a, b, [], adj, [])
        fixed = for_rsst_oracle(cfg, a=a, b=b)
        tmp_path.write_text(serialize([fixed]))
        return subprocess.run([str(REDUCE_RSST), str(tmp_path)],
                               capture_output=True, text=True)

    def test_d_reducible_fixture_verified_by_oracle(self, tmp_path=Path("/tmp/_test_rsst_red.conf")):
        proc = self._run(RED_ADJ, RED_R, RED_N, RED_A, RED_B, tmp_path)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("D-reducible", proc.stdout)
        self.assertIn("Reducibility of 1 configurations verified", proc.stdout)

    def test_non_d_reducible_fixture_rejected_by_oracle(self, tmp_path=Path("/tmp/_test_rsst_nonred.conf")):
        proc = self._run(NONRED_ADJ, NONRED_R, NONRED_N, NONRED_A, NONRED_B, tmp_path)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Not D-reducible", proc.stdout)
        self.assertIn("NO CONTRACT PROPOSED", proc.stdout)


def parse_conf_text(text: str):
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as f:
        f.write(text)
        path = f.name
    return parse_conf(path)


if __name__ == "__main__":
    unittest.main()
