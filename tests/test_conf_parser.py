"""Parser tests against the pinned RSST and Steinberger configuration files."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor.conf_parser import parse_conf, serialize  # noqa: E402

RSST_CONF = ROOT / "third_party" / "arxiv-1401.6481" / "src" / "anc" / "unavoidable.conf"
STEIN_CONF = ROOT / "third_party" / "arxiv-0905.0043" / "src" / "anc" / "U_2822.conf"


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


if __name__ == "__main__":
    unittest.main()
