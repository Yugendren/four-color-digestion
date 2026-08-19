#!/usr/bin/env python3
"""P3 M1: combo-blocking attribution.

For each of the 1,832 combined rules under
``third_party/computer-checks/combined_rules/all``, determine (a) whether it is
blocked by the pool -- equivalently, whether it is ABSENT from
``combined_rules/non_blocked`` (671 present / 1,161 absent, see
``rule.cpp``'s ``run_combine_rules`` / ``CombinedRule::add_rule_to_combination``,
Lemma A.2 in ``01-PROBLEM-STATEMENT.md``) -- and (b) the FULL set of source ``.conf``
files that block it (``fourcolor.nl4ct.combo_block_attribution``), not just the first
match the C++ short-circuits on.

Semantics note (see ``combo_block_attribution`` docstring): a combined rule's
"non_blocked" membership is really determined by an INCREMENTAL, filtered
rule-combination search tree (each intermediate merge along its unique construction
path must itself be unblocked). This script instead applies
``blocked_by_reducible_configuration`` directly to each combo's own final merged
pattern -- a cheaper, non-incremental check. Validated exactly against the
671-present/1,161-absent split (by CONTENT, not filename, since ``all/`` and
``non_blocked/`` are independently-numbered combine_rules runs -- see
``_nonblocked_content_set``): 1,832/1,832 combos agree, so the two notions coincide for
this pool (blocking turns out to be monotone under rule combination here).

Usage:
    tools/p3_combo_blockers.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fourcolor import nl4ct as m  # noqa: E402

RESULTS_DIR = ROOT / "results" / "p3"
ALL_DIR = ROOT / "third_party" / "computer-checks" / "combined_rules" / "all"
NON_BLOCKED_DIR = ROOT / "third_party" / "computer-checks" / "combined_rules" / "non_blocked"
N_BASE_RULES = 84


def _norm(text: str) -> str:
    """Whitespace-normalized file content, used as a structural identity key across
    the two independently-numbered ``all/`` and ``non_blocked/`` combine_rules runs
    (see module docstring)."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip() != ""]
    return "\n".join(lines)


def _nonblocked_content_set(nb_dir: Path | None = None) -> set[str]:
    if nb_dir is None:
        nb_dir = NON_BLOCKED_DIR
    return {_norm(p.read_text()) for p in nb_dir.glob("*.combined_rule")}


def run() -> None:
    t0 = time.time()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    confs_named = m.load_configurations_with_source(m.default_conf_dir())
    print(f"loaded {len(confs_named)} named configuration instances "
          f"({len({n for n, _ in confs_named})} distinct source files)")

    nb_content = _nonblocked_content_set()
    all_paths = sorted(ALL_DIR.glob("*.combined_rule"))
    print(f"{len(all_paths)} combined rules under combined_rules/all, "
          f"{len(nb_content)} distinct contents under combined_rules/non_blocked")

    jsonl_path = RESULTS_DIR / "combo_blockers.jsonl"
    jf = jsonl_path.open("w")

    n_blocked = 0
    n_ground_truth_blocked = 0
    n_agree = 0
    distinct_blockers: set[str] = set()

    for i, p in enumerate(all_paths):
        text = p.read_text()
        cr = m.parse_combined_rule_file(p, N_BASE_RULES)
        att = m.combo_block_attribution(cr, confs_named)
        ground_truth_blocked = _norm(text) not in nb_content
        if ground_truth_blocked:
            n_ground_truth_blocked += 1
        if att.blocked == ground_truth_blocked:
            n_agree += 1
        if att.blocked:
            n_blocked += 1
        distinct_blockers |= att.all_blockers
        record = {
            "combo_id": p.stem,
            "combined_flag_popcount": sum(cr.combined_flag),
            "amount": cr.amount,
            "n_concretizations": att.n_concretizations,
            "blocked": att.blocked,
            "ground_truth_blocked": ground_truth_blocked,
            "blockers_per_concretization": [sorted(s) for s in att.per_concretization],
            "all_blockers": sorted(att.all_blockers),
        }
        jf.write(json.dumps(record) + "\n")
        if (i + 1) % 300 == 0:
            print(f"{i + 1}/{len(all_paths)} elapsed={time.time() - t0:.1f}s", flush=True)

    jf.close()

    assert n_agree == len(all_paths), (
        f"combo_block_attribution disagreed with ground truth on "
        f"{len(all_paths) - n_agree}/{len(all_paths)} combos"
    )
    assert n_blocked == 1161, f"expected 1161 blocked, got {n_blocked}"
    assert len(all_paths) - n_blocked == 671, f"expected 671 non-blocked, got {len(all_paths) - n_blocked}"

    summary = {
        "n_combos_total": len(all_paths),
        "n_blocked": n_blocked,
        "n_non_blocked": len(all_paths) - n_blocked,
        "n_agree_with_ground_truth": n_agree,
        "n_distinct_blocker_sources": len(distinct_blockers),
        "elapsed_seconds": time.time() - t0,
        "jsonl": str(jsonl_path.relative_to(ROOT)),
    }
    summary_path = RESULTS_DIR / "combo_blockers_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run()
