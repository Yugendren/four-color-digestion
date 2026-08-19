"""Tests for the P3 M1 (combo-blocking attribution) and M2 (usage-ranking merge) code.

Two layers:
  - ``fourcolor.nl4ct.combo_block_attribution``: exercised against real data (small
    sample) the same way ``TestBlockingAttribution`` in ``test_nl4ct.py`` exercises the
    wheel-level attribution -- a genuine differential against ground truth (a combo is
    "ground-truth blocked" iff its normalized file content is absent from
    ``combined_rules/non_blocked``).
  - ``tools/p3_combo_blockers.py`` / ``tools/p3_usage_table.py``'s pure
    parsing/merging helpers (``_norm``, ``_nonblocked_content_set``, ``combo_counts``,
    ``wheel_counts``, ``cartwheel_first_counts``): exercised against tiny synthetic
    fixtures in a temp directory, independent of the (large, slow-to-regenerate) real
    result files, so these tests stay fast and self-contained.
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from fourcolor import nl4ct as m  # noqa: E402
import p3_combo_blockers as cb_tool  # noqa: E402
import p3_usage_table as usage_tool  # noqa: E402

RULE_DIR = m.default_rule_dir()
ALL_DIR = ROOT / "third_party" / "computer-checks" / "combined_rules" / "all"
NON_BLOCKED_DIR = ROOT / "third_party" / "computer-checks" / "combined_rules" / "non_blocked"
CONF_DIR = m.default_conf_dir()


def _have_data() -> bool:
    return RULE_DIR.is_dir() and ALL_DIR.is_dir() and NON_BLOCKED_DIR.is_dir() and CONF_DIR.is_dir()


@unittest.skipUnless(_have_data(), "third_party/computer-checks data not available")
class TestComboBlockAttribution(unittest.TestCase):
    """Differential: combo_block_attribution's verdict, applied directly to each
    combo's own final merged pattern, must agree with ground-truth non_blocked-content
    membership -- see the module docstring in tools/p3_combo_blockers.py for why this
    (non-incremental) check turns out to be exact for this pool."""

    @classmethod
    def setUpClass(cls):
        cls.confs_named = m.load_configurations_with_source(CONF_DIR)
        cls.nb_content = cb_tool._nonblocked_content_set()

    def test_sample_of_all_combos_matches_ground_truth(self):
        # A deterministic sample (every 15th file) keeps this fast while still
        # covering both outcomes (blocked and non-blocked) -- see assertions below.
        paths = sorted(ALL_DIR.glob("*.combined_rule"))[::15]
        self.assertGreater(len(paths), 20)
        n_blocked = 0
        n_nonblocked = 0
        for p in paths:
            cr = m.parse_combined_rule_file(p, n_rules=84)
            att = m.combo_block_attribution(cr, self.confs_named)
            ground_truth_blocked = cb_tool._norm(p.read_text()) not in self.nb_content
            self.assertEqual(att.blocked, ground_truth_blocked, p.stem)
            if att.blocked:
                n_blocked += 1
                # every concretization must have a nonempty, real blocker set.
                for blockers in att.per_concretization:
                    self.assertGreater(len(blockers), 0)
                    for name in blockers:
                        self.assertTrue((CONF_DIR / f"{name}.conf").exists(), name)
            else:
                n_nonblocked += 1
        self.assertGreater(n_blocked, 0)
        self.assertGreater(n_nonblocked, 0)

    def test_combo_block_attribution_center_matches_head_of_st_dart(self):
        # Sanity-check the root vertex used matches rule.cpp's
        # R_tilde.darts[R_tilde.st_id].head exactly (see combo_block_attribution docstring).
        p = sorted(ALL_DIR.glob("*.combined_rule"))[0]
        cr = m.parse_combined_rule_file(p, n_rules=84)
        att_direct = m.block_attribution(cr.g, cr.g.head[cr.st_id], self.confs_named)
        att_helper = m.combo_block_attribution(cr, self.confs_named)
        self.assertEqual(att_direct.blocked, att_helper.blocked)
        self.assertEqual(att_direct.per_concretization, att_helper.per_concretization)


class TestNormAndContentMatching(unittest.TestCase):
    """_norm must make whitespace-insensitive content comparisons safe (the ``all/``
    and ``non_blocked/`` combined_rules directories are two independently-numbered
    combine_rules runs, so files must be matched by CONTENT, not filename -- see
    tools/p3_combo_blockers.py's module docstring)."""

    def test_norm_ignores_surrounding_and_trailing_whitespace(self):
        a = "2 2 1 0\n1 1 0 2 -1 \n2 1 0 1 -1 \n0000\n"
        b = "  2 2 1 0  \n  1 1 0 2 -1\n2 1 0 1 -1\n\n0000\n\n"
        self.assertEqual(cb_tool._norm(a), cb_tool._norm(b))

    def test_norm_distinguishes_different_content(self):
        a = "2 2 1 0\n1 1 0 2 -1 \n2 1 0 1 -1 \n0000\n"
        b = "2 2 1 0\n1 1 0 2 -1 \n2 1 0 1 -1 \n0001\n"
        self.assertNotEqual(cb_tool._norm(a), cb_tool._norm(b))

    def test_nonblocked_content_set_matches_directory_size(self):
        with tempfile.TemporaryDirectory() as td:
            nb_dir = Path(td)
            (nb_dir / "combined_rule_1.combined_rule").write_text("foo\nbar\n")
            (nb_dir / "combined_rule_2.combined_rule").write_text("baz\n")
            # A duplicate (same normalized content, different filename) collapses to
            # one set entry -- matches how combo_counts/attribution treat content
            # identity, not filename identity.
            (nb_dir / "combined_rule_3.combined_rule").write_text("  foo  \nbar\n")
            got = cb_tool._nonblocked_content_set(nb_dir)
            self.assertEqual(got, {"foo\nbar", "baz"})


class TestComboCountsMerge(unittest.TestCase):
    """combo_counts: only BLOCKED combos should contribute usage, and full attribution
    (all_blockers, i.e. union across concretizations) is what gets counted -- see
    tools/p3_usage_table.py's module docstring for the "why only blocked combos"
    argument."""

    def test_counts_only_blocked_combos_using_all_blockers(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "combo_blockers.jsonl"
            records = [
                {"combo_id": "c1", "blocked": True, "all_blockers": ["D0001", "D0002"]},
                {"combo_id": "c2", "blocked": True, "all_blockers": ["D0002"]},
                # Not blocked: must NOT contribute, even though it lists a blocker for
                # one (insufficient) concretization.
                {"combo_id": "c3", "blocked": False, "all_blockers": ["D9999"]},
            ]
            with path.open("w") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")
            counts = usage_tool.combo_counts(path)
            self.assertEqual(counts["D0001"], 1)
            self.assertEqual(counts["D0002"], 2)
            self.assertNotIn("D9999", counts)


class TestWheelCountsMerge(unittest.TestCase):
    def test_counts_only_blocked_wheels_deduped_per_wheel(self):
        with tempfile.TemporaryDirectory() as td:
            p2_dir = Path(td)
            records_d7 = [
                {
                    "blocked": True,
                    # Same blocker repeated across concretizations must count ONCE for
                    # this wheel (dedup via seen_this_wheel), not twice.
                    "blockers_per_concretization": [["D0001"], ["D0001", "D0002"]],
                },
                {"blocked": False, "blockers_per_concretization": [[]]},
            ]
            (p2_dir / "wheel_survivors_d7.jsonl").write_text(
                "\n".join(json.dumps(r) for r in records_d7) + "\n"
            )
            (p2_dir / "wheel_survivors_d8.jsonl").write_text(
                json.dumps({"blocked": True, "blockers_per_concretization": [["D0002"]]}) + "\n"
            )
            counts = usage_tool.wheel_counts(degrees=(7, 8), p2_dir=p2_dir)
            self.assertEqual(counts["D0001"], 1)
            self.assertEqual(counts["D0002"], 2)  # once from d7, once from d8


class TestCartwheelFirstCountsMerge(unittest.TestCase):
    def test_parses_tsv_and_counts_comma_separated_names(self):
        with tempfile.TemporaryDirectory() as td:
            blocklog_dir = Path(td)
            (blocklog_dir / "d7_0.blocklog.tsv").write_text(
                "d7_0\t123\tD0001\n"
                "d7_0\t124\tD0001,D0002\n"
                "\n"  # blank line must be skipped, not crash
            )
            (blocklog_dir / "d7_1.blocklog.tsv").write_text("d7_1\t125\tD0002\n")
            counts = usage_tool.cartwheel_first_counts(blocklog_dir)
            self.assertEqual(counts["D0001"], 2)
            self.assertEqual(counts["D0002"], 2)


class TestUsageTableEndToEnd(unittest.TestCase):
    """The full merge, on a tiny synthetic pool, including the zero-usage count that
    determines deletion batch #1's size."""

    def test_merge_and_zero_usage_count(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pool_dir = root / "pool"
            pool_dir.mkdir()
            for name in ("D0001", "D0002", "D0003", "D0004"):
                (pool_dir / f"{name}.conf").write_text("")

            combo_path = root / "combo_blockers.jsonl"
            combo_path.write_text(
                json.dumps({"combo_id": "c1", "blocked": True, "all_blockers": ["D0001"]}) + "\n"
            )

            p2_dir = root / "p2"
            p2_dir.mkdir()
            (p2_dir / "wheel_survivors_d7.jsonl").write_text(
                json.dumps({"blocked": True, "blockers_per_concretization": [["D0002"]]}) + "\n"
            )

            blocklog_dir = root / "blocklog"
            blocklog_dir.mkdir()
            (blocklog_dir / "d7_0.blocklog.tsv").write_text("d7_0\t1\tD0003\n")

            pool = sorted(p.stem for p in pool_dir.glob("*.conf"))
            self.assertEqual(pool, ["D0001", "D0002", "D0003", "D0004"])

            cc = usage_tool.combo_counts(combo_path)
            wc = usage_tool.wheel_counts(degrees=(7,), p2_dir=p2_dir)
            kc = usage_tool.cartwheel_first_counts(blocklog_dir)

            rows = {
                name: (cc.get(name, 0), wc.get(name, 0), kc.get(name, 0)) for name in pool
            }
            self.assertEqual(rows["D0001"], (1, 0, 0))
            self.assertEqual(rows["D0002"], (0, 1, 0))
            self.assertEqual(rows["D0003"], (0, 0, 1))
            self.assertEqual(rows["D0004"], (0, 0, 0))  # zero-usage -> deletion batch #1

            n_zero = sum(1 for v in rows.values() if v == (0, 0, 0))
            self.assertEqual(n_zero, 1)


if __name__ == "__main__":
    unittest.main()
