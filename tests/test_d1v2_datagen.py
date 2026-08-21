"""Fast tests for tools/d1v2_datagen.py: index-map determinism, boundary-flag
logic, set-trace index encode/decode, and a corpus-fixture datagen run --
all against tiny synthetic ring-6 fixtures, never touching the real (large)
data/v2 tree.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from fourcolor.conf_parser import Configuration  # noqa: E402
from fourcolor.reduce import check                # noqa: E402
import d1v2_datagen                               # noqa: E402

# Same tiny ring-6 fixture used by test_d1_assemble.py.
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


class TestCodeIndexDeterminism(unittest.TestCase):
    def test_repeated_build_is_identical_and_sorted(self):
        for r in (6, 7):
            a = d1v2_datagen.build_code_index(r)
            b = d1v2_datagen.build_code_index(r)
            self.assertEqual(a, b)
            self.assertEqual(a, sorted(a))
            self.assertEqual(len(a), len(set(a)))

    def test_load_or_build_writes_and_reuses_file(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(d1v2_datagen, "V2_DIR", Path(d)):
                codes1, idx1 = d1v2_datagen.load_or_build_code_index(6)
                path = d1v2_datagen.code_index_path(6)
                self.assertTrue(path.exists())
                on_disk = json.loads(path.read_text())
                self.assertEqual(on_disk["r"], 6)
                self.assertEqual(on_disk["n_codes"], len(codes1))
                self.assertEqual(on_disk["codes"], codes1)
                # index map is a bijection code -> position
                self.assertEqual(len(idx1), len(codes1))
                for i, c in enumerate(codes1):
                    self.assertEqual(idx1[c], i)
                # second call reuses the file rather than rebuilding
                codes2, idx2 = d1v2_datagen.load_or_build_code_index(6)
                self.assertEqual(codes1, codes2)
                self.assertEqual(idx1, idx2)


class TestBoundaryFlag(unittest.TestCase):
    def test_nonreducible_small_consistent_is_boundary(self):
        self.assertTrue(d1v2_datagen.boundary_flag(False, 1, 3))
        self.assertTrue(d1v2_datagen.boundary_flag(False, 50, 3))

    def test_nonreducible_large_or_zero_consistent_is_not_boundary(self):
        self.assertFalse(d1v2_datagen.boundary_flag(False, 51, 3))
        self.assertFalse(d1v2_datagen.boundary_flag(False, 0, 3))

    def test_reducible_slow_closure_is_boundary(self):
        self.assertTrue(d1v2_datagen.boundary_flag(True, 0, 6))
        self.assertTrue(d1v2_datagen.boundary_flag(True, 0, 9))

    def test_reducible_fast_closure_is_not_boundary(self):
        self.assertFalse(d1v2_datagen.boundary_flag(True, 0, 5))


class TestSetTraceEncoding(unittest.TestCase):
    def test_encode_set_trace_round_trips_via_index_map(self):
        cfg = Configuration("t.1", N, R, -1, -1, [], BASE_ADJ, [])
        res = check(cfg, record_sets=True)
        codes = d1v2_datagen.build_code_index(R)
        code_to_idx = {c: i for i, c in enumerate(codes)}
        encoded = d1v2_datagen.encode_set_trace(res.set_trace, code_to_idx)
        self.assertEqual(len(encoded), len(res.set_trace))
        decoded = [[codes[i] for i in rnd] for rnd in encoded]
        self.assertEqual(decoded, res.set_trace)
        # indices are valid positions into the sorted code list
        for rnd in encoded:
            for i in rnd:
                self.assertTrue(0 <= i < len(codes))

    def test_make_v2_record_boundary_and_shape(self):
        codes = d1v2_datagen.build_code_index(R)
        code_to_idx = {c: i for i, c in enumerate(codes)}
        cfg = Configuration("t.1", N, R, -1, -1, [], BASE_ADJ, [])
        res = check(cfg, record_sets=True)
        rec = d1v2_datagen.make_v2_record("t.1", N, R, BASE_ADJ, res, code_to_idx, "test")
        self.assertEqual(rec["ident"], "t.1")
        self.assertEqual(rec["r"], R)
        self.assertEqual(rec["n"], N)
        self.assertEqual(rec["rounds"], res.rounds)
        self.assertEqual(rec["n_consistent"], res.n_consistent)
        self.assertEqual(rec["d_reducible"], res.d_reducible)
        self.assertEqual(len(rec["set_trace"]), len(res.set_trace))
        self.assertEqual(
            rec["boundary"],
            d1v2_datagen.boundary_flag(res.d_reducible, res.n_consistent, res.rounds),
        )


class TestCorpusFixture(unittest.TestCase):
    def test_cmd_corpus_writes_expected_record(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            corpus_path = d / "d1_corpus.jsonl"
            corpus_rec = {
                "ident": "fixture-1",
                "source": "generated",
                "r": R,
                "n": N,
                "adjacency": {str(k): v for k, v in BASE_ADJ.items()},
                "d_reducible": True,
                "n_extendable": None,
                "n_consistent": None,
                "rounds": None,
                "trace": None,
            }
            # Fill in the real verdict so the mismatch-detection sanity check
            # inside cmd_corpus has something to agree with.
            cfg = Configuration("fixture-1", N, R, -1, -1, [], BASE_ADJ, [])
            res = check(cfg)
            corpus_rec["d_reducible"] = res.d_reducible
            corpus_rec["n_extendable"] = res.n_extendable
            corpus_rec["n_consistent"] = res.n_consistent
            corpus_rec["rounds"] = res.rounds
            corpus_path.write_text(json.dumps(corpus_rec) + "\n")

            v2_dir = d / "v2"
            with mock.patch.object(d1v2_datagen, "CORPUS_PATH", corpus_path), \
                 mock.patch.object(d1v2_datagen, "V2_DIR", v2_dir):
                d1v2_datagen.cmd_corpus([R])
                out_path = d1v2_datagen.corpus_checkpoint_path(R)
                self.assertTrue(out_path.exists())
                recs = [json.loads(l) for l in out_path.read_text().splitlines() if l]
                self.assertEqual(len(recs), 1)
                rec = recs[0]
                self.assertEqual(rec["ident"], "fixture-1")
                self.assertEqual(rec["d_reducible"], res.d_reducible)
                self.assertEqual(rec["n_consistent"], res.n_consistent)
                self.assertEqual(len(rec["set_trace"]), rec["rounds"] + 1)
                self.assertIn("boundary", rec)
                # code index map was built as a side effect
                self.assertTrue(d1v2_datagen.code_index_path(R).exists())


if __name__ == "__main__":
    unittest.main()
