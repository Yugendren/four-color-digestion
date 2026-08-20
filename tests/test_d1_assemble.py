"""Corpus-assembly tests against synthetic fixtures (tools/d1_assemble.py).

Exercises: generated-jsonl loading, .conf+report joining, nl4ct-pool
loading, and canonical-form dedup across sources -- without touching the
real (large) data/ and results/ trees.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from fourcolor.conf_parser import serialize as conf_serialize, Configuration  # noqa: E402
import d1_assemble  # noqa: E402

# A tiny ring-6 configuration, reused across fixtures under different
# vertex numberings to exercise dedup.
BASE_ADJ = {
    1: [2, 7, 8, 6],
    2: [1, 3, 7],
    7: [1, 2, 3, 4, 8],
    8: [1, 7, 4, 5, 6],
    6: [1, 8, 5],
    3: [2, 4, 7],
    4: [7, 3, 5, 8],
    5: [8, 4, 6],
}
R, N = 6, 8


def rotated_adj(start: int):
    """A relabeling of BASE_ADJ under a ring rotation start (no reflection,
    interior labels held fixed -- same trick as test_d1_encoding.py)."""
    ring_new = {v: ((v - start) % R) + 1 for v in range(1, R + 1)}
    label = dict(ring_new)
    for v in range(R + 1, N + 1):
        label[v] = v
    inv = {new: old for old, new in label.items()}
    return {new_v: [label[u] for u in BASE_ADJ[inv[new_v]]] for new_v in range(1, N + 1)}


class TestGeneratedLoader(unittest.TestCase):
    def test_load_generated_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            data_dir = Path(d)
            rec = {
                "ident": "gen-test-1",
                "n": N,
                "r": R,
                "adjacency": {str(k): v for k, v in BASE_ADJ.items()},
                "n_extendable": 10,
                "n_consistent": 0,
                "d_reducible": True,
                "rounds": 3,
                "trace": [10, 4, 1, 0],
            }
            (data_dir / "configs_r6_test.jsonl").write_text(json.dumps(rec) + "\n")
            out = d1_assemble.load_generated(data_dir)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["source"], "generated")
            self.assertEqual(out[0]["ident"], "gen-test-1")
            self.assertEqual(out[0]["trace"], [10, 4, 1, 0])


class TestConfReportJoin(unittest.TestCase):
    def test_join_by_ident(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            cfg = Configuration("t.1", N, R, 10, 0, [], BASE_ADJ, list(range(N)))
            conf_path = d / "fixture.conf"
            conf_path.write_text(conf_serialize([cfg]))

            report_path = d / "report.jsonl"
            report = {
                "ident": "t.1",
                "r": R,
                "n": N,
                "computed_a": 10,
                "computed_b": 0,
                "d_reducible": True,
                "rounds": 2,
                "trace": [10, 1, 0],
            }
            report_path.write_text(json.dumps(report) + "\n")

            out = d1_assemble.load_conf_plus_report(conf_path, report_path, "rsst633")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["adjacency"]["1"], BASE_ADJ[1])
            self.assertEqual(out[0]["trace"], [10, 1, 0])
            self.assertEqual(out[0]["n_extendable"], 10)

    def test_unmatched_report_ident_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            cfg = Configuration("t.1", N, R, 10, 0, [], BASE_ADJ, list(range(N)))
            conf_path = d / "fixture.conf"
            conf_path.write_text(conf_serialize([cfg]))

            report_path = d / "report.jsonl"
            report = {"ident": "no-such-ident", "r": R, "n": N, "d_reducible": True}
            report_path.write_text(json.dumps(report) + "\n")

            out = d1_assemble.load_conf_plus_report(conf_path, report_path, "rsst633")
            self.assertEqual(out, [])


class TestDedup(unittest.TestCase):
    def test_dedup_collapses_rotated_duplicate_and_respects_priority(self):
        rec_a = d1_assemble._record(
            "rsst-a", "rsst633", R, N, BASE_ADJ, True, 10, 0, 3, [10, 4, 1, 0]
        )
        rec_b = d1_assemble._record(
            "gen-b", "generated", R, N, rotated_adj(3), True, 10, 0, 3, [10, 4, 1, 0]
        )
        distinct_adj = {
            1: [2, 7, 6], 2: [1, 3, 8, 7], 7: [1, 2, 8, 9, 6], 6: [1, 7, 9, 5],
            3: [2, 4, 8], 8: [2, 3, 4, 9, 7], 9: [7, 8, 4, 5, 6], 5: [6, 9, 4],
            4: [3, 5, 9, 8],
        }
        rec_c = d1_assemble._record(
            "gen-c", "generated", 6, 9, distinct_adj, False, 14, 14, 2, [108, 14, 14]
        )
        kept, stats = d1_assemble.dedup(
            {"rsst633": [rec_a], "generated": [rec_b, rec_c]}
        )
        self.assertEqual(len(kept), 2)
        idents = {r["ident"] for r in kept}
        self.assertEqual(idents, {"rsst-a", "gen-c"})
        self.assertEqual(stats["n_collisions_total"], 1)
        self.assertEqual(stats["cross_source_overlap"][("rsst633", "generated")], 1)

    def test_within_source_duplicate_counted(self):
        rec_a = d1_assemble._record(
            "gen-a", "generated", R, N, BASE_ADJ, True, 10, 0, 3, [10, 4, 1, 0]
        )
        rec_b = d1_assemble._record(
            "gen-b", "generated", R, N, rotated_adj(2), True, 10, 0, 3, [10, 4, 1, 0]
        )
        kept, stats = d1_assemble.dedup({"generated": [rec_a, rec_b]})
        self.assertEqual(len(kept), 1)
        self.assertEqual(stats["within_source_dupes"]["generated"], 1)


class TestNl4ctPoolLoader(unittest.TestCase):
    def test_load_nl4ct_pool_missing_conf_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            pool_verify = d / "pool-verify"
            pool_verify.mkdir()
            conf_dir = d / "D"
            conf_dir.mkdir()
            shard = pool_verify / "shard_r6_0of1.jsonl"
            rec = {
                "ident": "Dmissing",
                "r": 6,
                "n": 8,
                "n_extendable": 10,
                "n_consistent": 0,
                "d_reducible": True,
                "rounds": 3,
            }
            shard.write_text(json.dumps(rec) + "\n")
            out, failures = d1_assemble.load_nl4ct_pool(pool_verify, conf_dir)
            self.assertEqual(out, [])
            self.assertEqual(failures, ["Dmissing"])

    def test_load_nl4ct_pool_trace_is_null(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            pool_verify = d / "pool-verify"
            pool_verify.mkdir()
            conf_dir = d / "D"
            conf_dir.mkdir()

            # near-linear-4ct .conf format: header line, "N R", then one
            # line per interior vertex (rotation). Ring 6, interior 7,8.
            nl4ct_text = "\n8 6\n7 5 1 2 3 4 8\n8 5 1 7 4 5 6\n"
            (conf_dir / "D0000.conf").write_text(nl4ct_text)

            shard = pool_verify / "shard_r6_0of1.jsonl"
            rec = {
                "ident": "D0000",
                "r": 6,
                "n": 8,
                "n_extendable": 10,
                "n_consistent": 0,
                "d_reducible": True,
                "rounds": 3,
            }
            shard.write_text(json.dumps(rec) + "\n")
            out, failures = d1_assemble.load_nl4ct_pool(pool_verify, conf_dir)
            self.assertEqual(failures, [])
            self.assertEqual(len(out), 1)
            self.assertIsNone(out[0]["trace"])
            self.assertEqual(out[0]["source"], "nl4ct_pool")


if __name__ == "__main__":
    unittest.main()
