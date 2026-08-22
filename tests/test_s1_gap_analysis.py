"""Tests for the Steinberger S1 tooling (``tools/s1_build_pool.py``,
``tools/s1_gap_analysis.py``).

All parsing/aggregation helpers are exercised against tiny synthetic fixtures in a temp
directory so the suite stays fast and independent of the real (GB-scale, slow) run
artifacts -- the same approach ``test_p3_usage.py`` takes for the P3 helpers. Two
light-weight checks additionally touch the real ``third_party`` data when present: the
ring index must cover the full 8,200-config pool with the known ring distribution, and
the pool builder must select exactly the ring<=14 subset.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import s1_build_pool as pool_tool  # noqa: E402
import s1_gap_analysis as gap_tool  # noqa: E402

CONF_DIR = ROOT / "third_party" / "reducible-configurations" / "D"

# Ring distribution of the full 8,200-config D pool (measured 2026-08-23).
REAL_RING_DISTRIBUTION = {
    6: 1, 7: 1, 8: 5, 9: 15, 10: 60, 11: 210, 12: 779,
    13: 2025, 14: 2799, 15: 1695, 16: 526, 17: 69, 18: 15,
}
REAL_N_RING_LE_14 = 5895


def write_conf(path: Path, n: int, r: int) -> None:
    """A minimal well-formed .conf: blank line, ``N R`` header, then interior rows."""
    rows = "".join(f"{i} 5 1 2 3 4 5 \n" for i in range(r + 1, n + 1))
    path.write_text(f"\n{n} {r}\n{rows}")


class TestRingParsing(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_read_ring(self) -> None:
        p = self.dir / "D0001.conf"
        write_conf(p, n=17, r=11)
        self.assertEqual(pool_tool.read_ring(p), 11)

    def test_read_ring_rejects_missing_blank_line(self) -> None:
        p = self.dir / "bad.conf"
        p.write_text("17 11\n12 5 1 2 3 4 5 \n")
        with self.assertRaises(ValueError):
            pool_tool.read_ring(p)

    def test_read_ring_rejects_malformed_header(self) -> None:
        p = self.dir / "bad2.conf"
        p.write_text("\n17 11 3\n")
        with self.assertRaises(ValueError):
            pool_tool.read_ring(p)

    def test_ring_index_and_distribution(self) -> None:
        write_conf(self.dir / "D0000.conf", 15, 10)
        write_conf(self.dir / "D0001.conf", 20, 14)
        write_conf(self.dir / "D0002.conf", 24, 14)
        write_conf(self.dir / "D0003.conf", 26, 16)
        rings = pool_tool.ring_index(self.dir)
        self.assertEqual(rings, {"D0000": 10, "D0001": 14, "D0002": 14, "D0003": 16})
        self.assertEqual(pool_tool.ring_distribution(rings), {10: 1, 14: 2, 16: 1})

    def test_build_selects_and_symlinks(self) -> None:
        src = self.dir / "src"
        src.mkdir()
        write_conf(src / "D0000.conf", 15, 10)
        write_conf(src / "D0001.conf", 20, 14)
        write_conf(src / "D0002.conf", 26, 16)
        out = self.dir / "pool"
        summary = pool_tool.build(out, max_ring=14, conf_dir=src)
        self.assertEqual(summary["n_pool"], 2)
        self.assertEqual(summary["n_excluded"], 1)
        self.assertEqual(summary["ring_distribution_excluded"], {"16": 1})
        names = sorted(p.name for p in (out / "D").glob("*.conf"))
        self.assertEqual(names, ["D0000.conf", "D0001.conf"])
        for p in (out / "D").glob("*.conf"):
            self.assertTrue(p.is_symlink())
            self.assertTrue(p.resolve().exists())

    def test_build_is_idempotent_and_prunes_stale(self) -> None:
        src = self.dir / "src"
        src.mkdir()
        write_conf(src / "D0000.conf", 15, 10)
        write_conf(src / "D0001.conf", 26, 16)
        out = self.dir / "pool"
        pool_tool.build(out, max_ring=16, conf_dir=src)
        self.assertEqual(len(list((out / "D").glob("*.conf"))), 2)
        pool_tool.build(out, max_ring=14, conf_dir=src)
        self.assertEqual(
            sorted(p.name for p in (out / "D").glob("*.conf")), ["D0000.conf"]
        )


@unittest.skipUnless(CONF_DIR.is_dir(), "third_party/reducible-configurations not available")
class TestRealPoolDistribution(unittest.TestCase):
    def test_full_pool_ring_distribution(self) -> None:
        rings = pool_tool.ring_index()
        self.assertEqual(len(rings), 8200)
        self.assertEqual(pool_tool.ring_distribution(rings), REAL_RING_DISTRIBUTION)
        self.assertEqual(sum(1 for r in rings.values() if r <= 14), REAL_N_RING_LE_14)


class TestGapAnalysisParsing(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_norm_rule_and_flag(self) -> None:
        text = "\n4 1 2 3\n1 5 5 4 3 2 -1 \n\n2 5 0 1 3 -1 \n1001\n"
        self.assertEqual(
            gap_tool.norm_rule(text), "4 1 2 3\n1 5 5 4 3 2 -1\n2 5 0 1 3 -1\n1001"
        )
        # Trailing/leading whitespace differences must not change identity.
        self.assertEqual(gap_tool.norm_rule(text), gap_tool.norm_rule(text.replace(" \n", "\n")))
        self.assertEqual(gap_tool.combo_flag(text), "1001")

    def test_rule_contents(self) -> None:
        d = self.dir / "rules"
        d.mkdir()
        (d / "combined_rule_1.combined_rule").write_text("\n4 1 2 3\n1 5 5 -1 \n1000\n")
        (d / "combined_rule_2.combined_rule").write_text("\n4 1 2 3\n1 5 5 -1\n1000")
        contents = gap_tool.rule_contents(d)
        self.assertEqual(set(contents), {"combined_rule_1", "combined_rule_2"})
        # Identical up to whitespace -> identical identity keys.
        self.assertEqual(contents["combined_rule_1"], contents["combined_rule_2"])

    def test_parse_check_log_success(self) -> None:
        p = self.dir / "check_deg8.log"
        p.write_text(
            "[info] Total 10094 cartwheels loaded.\n"
            "[info] Total 19754 configurations loaded.\n"
            "[info] After removing cartwheels with degree 9,\n"
            "[info] 5365 cartwheels remain.\n"
            "[info] Finished checking degree 8 vertices.\n"
        )
        info = gap_tool.parse_check_log(p, "check_deg8")
        self.assertTrue(info["present"])
        self.assertTrue(info["finished"])
        self.assertIsNone(info["assertion"])
        self.assertEqual(info["n_cartwheels_loaded"], 10094)
        self.assertEqual(info["n_configurations_loaded"], 19754)
        self.assertEqual(info["n_cartwheels_remaining"], 5365)

    def test_parse_check_log_assertion_failure(self) -> None:
        p = self.dir / "check_deg8.log"
        p.write_text(
            "[info] Total 10094 cartwheels loaded.\n"
            "[info] 5365 cartwheels remain.\n"
            "Assertion failed: (combined.size() == 0), function check88, "
            "file combine_cartwheel.cpp, line 88.\n"
        )
        info = gap_tool.parse_check_log(p, "check_deg8")
        self.assertFalse(info["finished"])
        self.assertEqual(info["assertion"], "combined.size() == 0")
        self.assertEqual(info["assert_function"], "check88")
        self.assertEqual(info["assert_file"], "combine_cartwheel.cpp")
        self.assertEqual(info["assert_line"], 88)

    def test_parse_check_log_missing(self) -> None:
        info = gap_tool.parse_check_log(self.dir / "nope.log", "check_deg7")
        self.assertFalse(info["present"])
        self.assertFalse(info["finished"])

    def test_parse_gluelog_groups_and_unions(self) -> None:
        p = self.dir / "check_deg8.gluelog.tsv"
        p.write_text(
            "check_deg8\t111\tD2588\n"
            "check_deg8\t222\tD0040,D8199\n"
            "check_deg8\t111\tD2588\n"
            "check_deg8\t111\tD0001\n"
            "garbage line without tabs\n"
        )
        per_hash = gap_tool.parse_gluelog(p)
        self.assertEqual(set(per_hash), {"111", "222"})
        self.assertEqual(per_hash["111"], ["D2588", "D0001"])
        self.assertEqual(per_hash["222"], ["D0040", "D8199"])


class TestGapAnalysisAggregation(unittest.TestCase):
    """analyze_wheels/analyze_gluing against a synthetic run dir + fixture data."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.run_dir = self.dir / "run"
        (self.run_dir / "log").mkdir(parents=True)

    def test_analyze_wheels_counts_and_deltas(self) -> None:
        for d, n in ((7, 3), (8, 1)):
            wd = self.run_dir / "work" / "wheels" / f"d{d}"
            wd.mkdir(parents=True)
            for i in range(n):
                (wd / f"d{d}_{i}.cartwheel").write_text("")
        zero = self.run_dir / "work" / "wheels" / "zero"
        zero.mkdir(parents=True)
        (zero / "d7_0_0.cartwheel").write_text("")
        (self.run_dir / "DONE_enum_cartwheels").write_text("")
        # No p2 survivor fixtures reachable -> predicted revived is 0 everywhere; we are
        # exercising the observed-count/delta arithmetic and the None handling for
        # degrees whose directories do not exist yet.
        orig = gap_tool.P2_DIR
        gap_tool.P2_DIR = self.dir / "no-such-p2"
        try:
            out = gap_tool.analyze_wheels(self.run_dir, {}, 14)
        finally:
            gap_tool.P2_DIR = orig
        self.assertEqual(out["per_degree"]["d7"]["observed"], 3)
        self.assertEqual(out["per_degree"]["d7"]["delta"], 3 - 5439)
        self.assertEqual(out["per_degree"]["d8"]["observed"], 1)
        self.assertIsNone(out["per_degree"]["d9"]["observed"])
        self.assertIsNone(out["per_degree"]["d9"]["delta"])
        self.assertEqual(out["bad_cartwheels"]["observed"], 1)
        self.assertEqual(out["bad_cartwheels"]["delta"], 1 - 10094)

    def test_analyze_wheels_suppresses_mismatch_while_stage_in_flight(self) -> None:
        """A degree whose enum_wheels process is still running is legitimately short;
        matches_prediction must stay None until DONE_enum_wheels lands."""
        wd = self.run_dir / "work" / "wheels" / "d7"
        wd.mkdir(parents=True)
        for i in range(5):
            (wd / f"d7_{i}.cartwheel").write_text("")
        orig = gap_tool.P2_DIR
        gap_tool.P2_DIR = self.dir / "no-such-p2"
        try:
            out = gap_tool.analyze_wheels(self.run_dir, {}, 14)
            self.assertFalse(out["stage_complete"])
            self.assertIsNone(out["per_degree"]["d7"]["matches_prediction"])
            self.assertEqual(out["per_degree"]["d7"]["observed"], 5)

            (self.run_dir / "DONE_enum_wheels").write_text("")
            done = gap_tool.analyze_wheels(self.run_dir, {}, 14)
        finally:
            gap_tool.P2_DIR = orig
        self.assertTrue(done["stage_complete"])
        self.assertFalse(done["per_degree"]["d7"]["matches_prediction"])

    def test_analyze_wheels_predicts_revived_from_attribution(self) -> None:
        p2 = self.dir / "p2"
        p2.mkdir()
        recs = [
            # Blocked, both concretizations keep a ring<=14 blocker -> survives.
            {"degree": 7, "seq": [5, 5, 5], "charge_bound": 25, "blocked": True,
             "blockers_per_concretization": [["D0040"], ["D0040", "D8199"]]},
            # Blocked, one concretization has only ring>14 blockers -> revives.
            {"degree": 7, "seq": [5, 6, 5], "charge_bound": 12, "blocked": True,
             "blockers_per_concretization": [["D8199"], ["D0040"]]},
            # Never blocked -> already counted in the 5439 baseline.
            {"degree": 7, "seq": [6, 6, 6], "charge_bound": 3, "blocked": False,
             "blockers_per_concretization": [[]]},
        ]
        with (p2 / "wheel_survivors_d7.jsonl").open("w") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
        (self.run_dir / "DONE_enum_wheels").write_text("")
        orig = gap_tool.P2_DIR
        gap_tool.P2_DIR = p2
        try:
            out = gap_tool.analyze_wheels(self.run_dir, {"D0040": 8, "D8199": 18}, 14)
        finally:
            gap_tool.P2_DIR = orig
        revived = out["predicted_revived_wheels"][7]
        self.assertEqual(len(revived), 1)
        self.assertEqual(revived[0]["seq"], [5, 6, 5])
        self.assertEqual(revived[0]["sole_blockers_above_ring"], ["D8199"])
        self.assertEqual(out["per_degree"]["d7"]["predicted_total"], 5439 + 1)
        self.assertEqual(out["n_predicted_revived_total"], 1)

    def test_analyze_gluing_flags_failed_check_and_at_risk_composites(self) -> None:
        (self.run_dir / "log" / "check_deg8.log").write_text(
            "[info] Total 9000 cartwheels loaded.\n"
            "[info] 5000 cartwheels remain.\n"
            "Assertion failed: (combined.size() == 0), function check88, "
            "file combine_cartwheel.cpp, line 88.\n"
        )
        (self.run_dir / "log" / "check_7triangle.log").write_text(
            "[info] Total 9000 cartwheels loaded.\n[info] Finished checking 7-triangles.\n"
        )
        glue = self.dir / "glue"
        glue.mkdir()
        (glue / "check_deg8.gluelog.tsv").write_text(
            "check_deg8\t111\tD0040\n"          # safe: ring 8 blocker survives
            "check_deg8\t222\tD8199\n"          # at risk: only blocker is ring 18
            "check_deg8\t333\tD0040,D8199\n"    # at risk: one representative loses its blocker
        )
        orig = gap_tool.BASELINE_GLUELOG
        gap_tool.BASELINE_GLUELOG = glue
        try:
            out, rows = gap_tool.analyze_gluing(
                self.run_dir, {"D0040": 8, "D8199": 18}, 14, None, top_n=5
            )
        finally:
            gap_tool.BASELINE_GLUELOG = orig

        self.assertTrue(out["stage_reached"])
        self.assertTrue(out["any_failure"])
        self.assertEqual(out["failed_checks"], ["check_deg8"])
        self.assertEqual(out["checks"]["check_deg8"]["assert_function"], "check88")
        self.assertTrue(out["checks"]["check_7triangle"]["finished"])

        self.assertEqual(out["baseline_gluelog"]["check_deg8"]["n_composites_logged"], 3)
        self.assertEqual(out["baseline_gluelog"]["check_deg8"]["n_at_risk"], 2)
        self.assertEqual(out["n_at_risk_composites"], 2)
        self.assertEqual(
            out["top_culprit_configs"],
            [{"config": "D8199", "ring": 18, "n_at_risk_composites": 2}],
        )
        by_hash = {r["state_hash"]: r for r in rows}
        self.assertEqual(set(by_hash), {"222", "333"})
        self.assertTrue(by_hash["222"]["all_blockers_above_ring"])
        self.assertFalse(by_hash["333"]["all_blockers_above_ring"])
        self.assertIsNone(out["exact"])
        self.assertIn("main_gluelog", out["exact_mode_command"])

    def test_analyze_gluing_exact_mode_diffs_composites(self) -> None:
        glue = self.dir / "glue"
        glue.mkdir()
        (glue / "check_deg8.gluelog.tsv").write_text(
            "check_deg8\t111\tD0040\ncheck_deg8\t222\tD8199\ncheck_deg8\t333\tD8199\n"
        )
        s1 = self.dir / "glue_s1"
        s1.mkdir()
        (s1 / "check_deg8.gluelog.tsv").write_text("check_deg8\t111\tD0040\n")
        orig = gap_tool.BASELINE_GLUELOG
        gap_tool.BASELINE_GLUELOG = glue
        try:
            out, _ = gap_tool.analyze_gluing(
                self.run_dir, {"D0040": 8, "D8199": 18}, 14, s1, top_n=5
            )
        finally:
            gap_tool.BASELINE_GLUELOG = orig
        exact = out["exact"]["per_check"]["check_deg8"]
        self.assertEqual(exact["n_baseline"], 3)
        self.assertEqual(exact["n_s1"], 1)
        self.assertEqual(exact["lost_state_hashes"], ["222", "333"])


class TestAnalyzeCombos(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _combo_text(self, tag: str, flag: str) -> str:
        return f"\n4 1 2 3\n1 5 5 {tag} -1 \n{flag}\n"

    def test_revived_combos_matched_against_prediction(self) -> None:
        all_dir = self.dir / "all"
        nb_dir = self.dir / "nb"
        run_nb = self.dir / "run" / "work" / "combined_rules" / "non_blocked"
        run_all = self.dir / "run" / "work" / "combined_rules" / "all"
        for d in (all_dir, nb_dir, run_nb, run_all):
            d.mkdir(parents=True)

        kept = self._combo_text("2", "1000")     # unblocked in both pools
        revived = self._combo_text("3", "0100")  # blocked only by a ring-18 config
        (all_dir / "combined_rule_1.combined_rule").write_text(kept)
        (all_dir / "combined_rule_2.combined_rule").write_text(revived)
        (nb_dir / "c1.combined_rule").write_text(kept)
        (run_nb / "c1.combined_rule").write_text(kept)
        (run_nb / "c2.combined_rule").write_text(revived)
        (self.dir / "run" / "DONE_combine").write_text("")
        (run_all / "c1.combined_rule").write_text(kept)
        (run_all / "c2.combined_rule").write_text(revived)

        blockers = self.dir / "combo_blockers.jsonl"
        with blockers.open("w") as fh:
            fh.write(json.dumps({
                "combo_id": "combined_rule_1", "amount": 1, "n_concretizations": 1,
                "blocked": False, "blockers_per_concretization": [[]],
            }) + "\n")
            fh.write(json.dumps({
                "combo_id": "combined_rule_2", "amount": 3, "n_concretizations": 1,
                "blocked": True, "blockers_per_concretization": [["D8199"]],
            }) + "\n")

        orig = (gap_tool.BASELINE_ALL, gap_tool.BASELINE_NON_BLOCKED, gap_tool.COMBO_BLOCKERS)
        gap_tool.BASELINE_ALL = all_dir
        gap_tool.BASELINE_NON_BLOCKED = nb_dir
        gap_tool.COMBO_BLOCKERS = blockers
        try:
            out = gap_tool.analyze_combos(
                self.dir / "run", {"D0040": 8, "D8199": 18}, 14
            )
        finally:
            (gap_tool.BASELINE_ALL, gap_tool.BASELINE_NON_BLOCKED,
             gap_tool.COMBO_BLOCKERS) = orig

        self.assertTrue(out["stage_reached"])
        self.assertEqual(out["n_non_blocked"], 2)
        self.assertEqual(out["n_revived"], 1)
        self.assertEqual(out["revived"][0]["combo_id"], "combined_rule_2")
        self.assertEqual(out["revived"][0]["rule_flag"], "0100")
        self.assertTrue(out["revived"][0]["predicted"])
        self.assertEqual(out["n_predicted_revived"], 1)
        self.assertTrue(out["prediction_matches_observed"])
        self.assertEqual(out["n_unexpectedly_reblocked"], 0)

    def test_stage_not_reached_still_predicts(self) -> None:
        all_dir = self.dir / "all"
        nb_dir = self.dir / "nb"
        all_dir.mkdir()
        nb_dir.mkdir()
        blockers = self.dir / "combo_blockers.jsonl"
        blockers.write_text(json.dumps({
            "combo_id": "combined_rule_9", "amount": 2, "n_concretizations": 2,
            "blocked": True, "blockers_per_concretization": [["D8199"], ["D0040"]],
        }) + "\n")
        orig = (gap_tool.BASELINE_ALL, gap_tool.BASELINE_NON_BLOCKED, gap_tool.COMBO_BLOCKERS)
        gap_tool.BASELINE_ALL = all_dir
        gap_tool.BASELINE_NON_BLOCKED = nb_dir
        gap_tool.COMBO_BLOCKERS = blockers
        try:
            out = gap_tool.analyze_combos(self.dir / "absent-run", {"D0040": 8, "D8199": 18}, 14)
        finally:
            (gap_tool.BASELINE_ALL, gap_tool.BASELINE_NON_BLOCKED,
             gap_tool.COMBO_BLOCKERS) = orig
        self.assertFalse(out["stage_reached"])
        self.assertEqual(out["n_predicted_revived"], 1)
        self.assertEqual(out["predicted_n_non_blocked"], 672)
        self.assertEqual(
            out["predicted_revived"][0]["sole_blockers_above_ring"], ["D8199"]
        )


if __name__ == "__main__":
    unittest.main()
