#!/usr/bin/env python3
"""Adversarial stress test for the three theorem candidates in
`results/theorem/candidates.md` (zero-FP sufficient conditions for
D-reducibility mined by `tools/mine_sound_rules.py`, firing almost
exclusively at rings 13-16 -- see that file's "Pool composition caveat":
rings 15-16 have ZERO non-reducible examples anywhere in the pool, so
those rules' soundness there is untested by construction).

Method: targeted mutation search. For each rule, seed from every pooled
config that ALREADY satisfies the rule (thousands, rings 12-16), apply the
diagonal edge-flip operator (`fourcolor.mutate.flip_edge` -- the standard
triangulation-preserving move: remove one non-ring edge, add the opposite
diagonal of its two incident triangles) to produce structurally-valid
near-triangulation neighbors, keep only mutants that (a) pass a
triangulation-validity gate (`fourcolor.mutate.is_legal_configuration` --
a faithful port of the RSST reference oracle's own well-formedness
conditions, PLUS interior connectivity; see that function's docstring for
why the weaker "edge/triangle-count invariant + interior min-degree"
check this gate started with was not sufficient on its own), (b) STILL
satisfy the rule under test, and (c) are novel (not already in the pool
by canonical key). Label survivors with `fourcolor.reduce.check` --
budget-aware, cheaper rings first. Any labeled mutant that is NOT
D-reducible is a hard FALSE POSITIVE: it kills the rule (or forces a
threshold repair). Every false positive is additionally cross-checked
against the independent compiled C oracle (`oracle_cross_check`, using
`build/reduce_stein` -- the 1995 RSST reference implementation as
extended by Steinberger to r<=16) before being reported.

Also stresses the dual rule `r == 11 AND n_interior <= 6 ->
non-reducible` (mined from an ALREADY-EXHAUSTIVE plantri search, per
`results/datagen-d1b-log.txt`: `-P11` was run for n=13..17, all 293554
disk triangulations enumerated, 1630 valid configs, 100% non-reducible).
Since edge flips change neither `n` nor `r`, every flip-mutant of one of
those 1630 seeds automatically still satisfies `r==11 AND n_interior<=6`
-- so this becomes a direct search for an r=11 GRAPH beyond the exhaustive
plantri enumeration (which excludes anything with a ring chord, hence
`-c3`) that turns out to be D-reducible.

Usage:
    .venv/bin/python tools/stress_test_theorem.py --checkpoint-every 5
    (long-running; intended to be launched detached, see the tool's own
    log/checkpoint files under results/theorem/stress_test_*.{json,log})
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from fourcolor import d1_interp as di  # noqa: E402
from fourcolor import d1_features as dfeat  # noqa: E402
from fourcolor.canonical import canonical_key  # noqa: E402
from fourcolor.conf_parser import Configuration  # noqa: E402
from fourcolor.mutate import random_flip_mutants, is_legal_configuration  # noqa: E402
from fourcolor.reduce import check  # noqa: E402

import mine_sound_rules as msr  # noqa: E402

OUT_DIR = ROOT / "results" / "theorem"
CHECKPOINT_JSON = OUT_DIR / "stress_test_checkpoint.json"
LOG_PATH = OUT_DIR / "stress_test.log"
FINAL_JSON = OUT_DIR / "stress_test.json"
FINAL_MD = OUT_DIR / "stress_test.md"

# Independent oracle for cross-validating any false positive this search
# finds: the ORIGINAL 1995 Robertson-Sanders-Seymour-Thomas C program
# (Steinberger's r<=16 extension of it, since our search reaches r=15,16
# where the unmodified 1995 binary's MAXRING=14 cap would reject the
# input) -- a genuinely independent implementation of the same D-
# reducibility check (`fourcolor.reduce` was itself built from the paper
# and differential-tested against this binary; see tests/test_reduce.py
# and results/oracle-rsst-633/), so agreement is strong evidence a "false
# positive" mutant is real and not a bug in this repo's own checker.
ORACLE_BINARY = ROOT / "build" / "reduce_stein"


def oracle_cross_check(adjacency: dict[int, list[int]], r: int, n: int, ident: str, a: int, b: int) -> dict | None:
    """Writes a one-record .conf file and runs it through `build/
    reduce_stein`, parsing its printed verdict + extendable-coloring count.
    Returns None if the oracle binary isn't built or the subprocess fails
    for an unexpected reason (never raises -- this is a best-effort second
    opinion, not required for the search to proceed)."""
    if not ORACLE_BINARY.exists():
        return None
    try:
        lines = [ident, f"{n} {r} {a} {b}", "0"]
        for v in range(1, n + 1):
            nbrs = adjacency[v]
            lines.append(f"{v} {len(nbrs)} " + " ".join(map(str, nbrs)))
        coords = list(range(1, n + 1))
        for i in range(0, len(coords), 8):
            lines.append(" ".join(map(str, coords[i : i + 8])))
        lines.append("")
        with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as f:
            f.write("\n".join(lines) + "\n")
            conf_path = f.name
        try:
            proc = subprocess.run(
                [str(ORACLE_BINARY), conf_path], capture_output=True, text=True, timeout=120
            )
        finally:
            Path(conf_path).unlink(missing_ok=True)
        out = proc.stdout
        if "Error" in out or proc.returncode not in (0, 1) and "D-reducible" not in out:
            return {"ok": False, "raw_tail": out[-500:]}
        oracle_d_reducible = ("***  D-reducible  ***" in out) and ("Not D-reducible" not in out)
        import re

        m = re.search(r"There are (\d+) colourings that extend", out)
        oracle_n_extendable = int(m.group(1)) if m else None
        return {
            "ok": True,
            "oracle_binary": ORACLE_BINARY.name,
            "oracle_d_reducible": oracle_d_reducible,
            "oracle_n_extendable": oracle_n_extendable,
            "matches_our_check": (oracle_n_extendable == a) if oracle_n_extendable is not None else None,
        }
    except Exception as e:  # noqa: BLE001 -- best-effort, never block the search
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Rule definitions -- copied verbatim from results/theorem/candidates.md
# (the exact atoms mined by tools/mine_sound_rules.py's structural variant).
# ---------------------------------------------------------------------------

Atom = tuple[str, str, float]  # (feature_name, op, value)


@dataclass
class Rule:
    name: str
    direction: str  # "reducible" or "nonreducible"
    atoms: list[Atom]

    def holds(self, feats: dict[str, float]) -> bool:
        for name, op, val in self.atoms:
            x = feats[name]
            if op == "ge" and not (x >= val):
                return False
            if op == "le" and not (x <= val):
                return False
            if op == "eq" and not (x == val):
                return False
        return True

    def __str__(self) -> str:
        sym = {"ge": ">=", "le": "<=", "eq": "=="}
        return " AND ".join(f"{n} {sym[o]} {v:g}" for n, o, v in self.atoms)


RULES: list[Rule] = [
    Rule(
        "candidate1",
        "reducible",
        [("n", "ge", 25), ("mean_interior_degree", "ge", 5.733333333333333), ("h5_density", "le", 0.2857142857142857)],
    ),
    Rule(
        "candidate2",
        "reducible",
        [("n", "ge", 25), ("max_run_const_degree_ring", "le", 4), ("n_deg5_ge3_deg5_neighbors", "eq", 0)],
    ),
    Rule(
        "candidate3",
        "reducible",
        [("n_interior", "ge", 11), ("h5_density", "le", 0.2857142857142857), ("n_deg5_ge3_deg5_neighbors", "eq", 0)],
    ),
]

DUAL_RULE = Rule("dual_r11", "nonreducible", [("r", "eq", 11), ("n_interior", "le", 6)])


# ---------------------------------------------------------------------------
# Feature computation (mirrors mine_sound_rules.compute_feature_vector, as
# a name->value dict instead of the fixed-order vector -- we only ever look
# up features by name here).
# ---------------------------------------------------------------------------


def compute_features(adjacency: dict[int, list[int]], r: int, n: int) -> dict[str, float]:
    feats: dict[str, float] = {}
    feats.update(di.shallow_features(adjacency, r, n))
    feats.update(di.structural_candidates(adjacency, r, n, 0, 0))
    feats.update(dfeat.arrangement_features(adjacency, r, n))
    return feats


# ---------------------------------------------------------------------------
# Pool loading (adjacency-preserving; mine_sound_rules.load_pool doesn't
# keep adjacency around once features are extracted, but we need it as
# mutation seed material).
# ---------------------------------------------------------------------------


def load_pool_with_adjacency() -> list[dict]:
    pool: dict[str, dict] = {}
    for path in msr.DEFAULT_POOL_FILES:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                adjacency = {int(v): nbrs for v, nbrs in rec["adjacency"].items()}
                r, n = rec["r"], rec["n"]
                ck = rec.get("canonical_key") or canonical_key(adjacency, r, n)
                if ck in pool:
                    continue
                pool[ck] = {
                    "canonical_key": ck,
                    "ident": rec.get("ident"),
                    "r": r,
                    "n": n,
                    "d_reducible": bool(rec["d_reducible"]),
                    "adjacency": adjacency,
                    "source": rec.get("source", path.stem),
                }
    return list(pool.values())


# ---------------------------------------------------------------------------
# Structural validity gate for a mutant. TWO independent layers, both
# required (AND-ed):
#
#  1. `fourcolor.mutate.is_legal_configuration` -- a faithful port of the
#     RSST reference oracle's OWN `ReadConf` well-formedness conditions
#     (ring degree >= 3, interior degree >= 5, interior ring-contact-arc
#     bound, full rotational consistency). This is the authoritative
#     definition of "legal configuration" and is REQUIRED: an earlier
#     version of this gate (interior-degree + edge/triangle-count only,
#     mirroring tools/datagen.py's plantri-output filter) let through a
#     mutant with a ring vertex of degree 2 -- illegal per RSST condition
#     (2) -- which looked like a false positive for candidate2 until the
#     C oracle itself (`build/reduce_rsst`) rejected it with `ReadErr(2,
#     ...)`. See fourcolor/mutate.py's docstring for the full derivation.
#  2. Interior connectivity (mirrors tools/datagen.py's own filter; not
#     part of the RSST ReadConf conditions but part of what makes a
#     configuration usable/meaningful, and part of the domain the pool's
#     configs -- and hence the mined rules -- were drawn from).
# ---------------------------------------------------------------------------


def structural_gate(adjacency: dict[int, list[int]], r: int, n: int) -> bool:
    cfg = Configuration("mutant", n, r, -1, -1, [], adjacency, [])
    try:
        cfg.validate()
    except ValueError:
        return False
    if not is_legal_configuration(adjacency, r, n):
        return False
    interior = [v for v in adjacency if v > r]
    if not interior:
        return False
    seen = {interior[0]}
    stack = [interior[0]]
    while stack:
        v = stack.pop()
        for u in adjacency[v]:
            if u > r and u not in seen:
                seen.add(u)
                stack.append(u)
    if len(seen) != len(interior):
        return False
    return True


# ---------------------------------------------------------------------------
# Logging / checkpointing
# ---------------------------------------------------------------------------


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


@dataclass
class RuleRunState:
    rule_name: str
    seeds_considered: int = 0
    mutants_generated: int = 0
    mutants_gate_failed: int = 0
    mutants_rule_dropped: int = 0
    mutants_duplicate: int = 0
    mutants_labeled: int = 0
    labels_by_ring: dict[int, int] = field(default_factory=dict)
    false_positives: list[dict] = field(default_factory=list)
    calls_used_by_ring: dict[int, int] = field(default_factory=dict)
    elapsed_sec: float = 0.0

    def as_dict(self) -> dict:
        return {
            "rule": self.rule_name,
            "seeds_considered": self.seeds_considered,
            "mutants_generated": self.mutants_generated,
            "mutants_gate_failed": self.mutants_gate_failed,
            "mutants_rule_dropped": self.mutants_rule_dropped,
            "mutants_duplicate": self.mutants_duplicate,
            "mutants_labeled": self.mutants_labeled,
            "labels_by_ring": self.labels_by_ring,
            "calls_used_by_ring": self.calls_used_by_ring,
            "n_false_positives": len(self.false_positives),
            "false_positives": self.false_positives,
            "elapsed_sec": self.elapsed_sec,
            "verdict": "KILLED" if self.false_positives else "SURVIVED",
        }


def checkpoint(states: dict[str, RuleRunState], extra: dict) -> None:
    doc = {"states": {k: v.as_dict() for k, v in states.items()}, **extra, "checkpoint_time": time.time()}
    tmp = CHECKPOINT_JSON.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(doc, f, indent=2)
    tmp.replace(CHECKPOINT_JSON)


# ---------------------------------------------------------------------------
# Core mutation-search loop for one rule (either direction).
# ---------------------------------------------------------------------------


def run_rule(
    rule: Rule,
    seeds: list[dict],
    ring_budgets: dict[int, int],
    ring_order: list[int],
    tested_cks: set[str],
    pool_cks: set[str],
    tries_per_seed: int,
    rng: random.Random,
    state: RuleRunState,
    checkpoint_cb,
    checkpoint_every: int,
    seed_target_label: bool | None,
) -> None:
    """seed_target_label: if given, restrict seeds used as mutation starting
    points to those with this d_reducible label (used for the dual rule,
    which mines its seeds from the non-reducible r=11 population; the
    top-3 candidates use all seeds -- they're mined to be zero-FP against
    exactly the D-reducible ones, which is the entire pool intersect the
    rule by construction)."""
    t0 = time.time()
    seeds_by_ring: dict[int, list[dict]] = {}
    for s in seeds:
        if seed_target_label is not None and s["d_reducible"] != seed_target_label:
            continue
        seeds_by_ring.setdefault(s["r"], []).append(s)
    for ring in seeds_by_ring:
        rng.shuffle(seeds_by_ring[ring])

    since_checkpoint = 0
    for ring in ring_order:
        budget = ring_budgets.get(ring, 0)
        if budget <= 0:
            continue
        ring_seeds = seeds_by_ring.get(ring, [])
        used = 0
        for seed in ring_seeds:
            if used >= budget:
                break
            state.seeds_considered += 1
            mutants = random_flip_mutants(seed["adjacency"], ring, seed["n"], rng, tries_per_seed)
            for adj in mutants:
                if used >= budget:
                    break
                state.mutants_generated += 1
                n = seed["n"]
                if not structural_gate(adj, ring, n):
                    state.mutants_gate_failed += 1
                    continue
                feats = compute_features(adj, ring, n)
                if not rule.holds(feats):
                    state.mutants_rule_dropped += 1
                    continue
                ck = canonical_key(adj, ring, n)
                if ck in pool_cks or ck in tested_cks:
                    state.mutants_duplicate += 1
                    continue
                tested_cks.add(ck)

                ident = f"mut-{rule.name}-r{ring}-{state.mutants_labeled}"
                cfg = Configuration(ident, n, ring, -1, -1, [], adj, [])
                t_call = time.time()
                res = check(cfg)
                dt_call = time.time() - t_call
                used += 1
                state.mutants_labeled += 1
                state.labels_by_ring[ring] = state.labels_by_ring.get(ring, 0) + 1
                state.calls_used_by_ring[ring] = state.calls_used_by_ring.get(ring, 0) + 1

                is_fp = (rule.direction == "reducible" and not res.d_reducible) or (
                    rule.direction == "nonreducible" and res.d_reducible
                )
                log(
                    f"rule={rule.name} r={ring} n={n} seed={seed['ident']} "
                    f"labeled d_reducible={res.d_reducible} ({dt_call:.2f}s) "
                    f"used={used}/{budget} {'*** FALSE POSITIVE ***' if is_fp else ''}"
                )
                if is_fp:
                    oracle = oracle_cross_check(adj, ring, n, ident, res.n_extendable, res.n_consistent)
                    log(f"  oracle cross-check for {ident}: {oracle}")
                    state.false_positives.append({
                        "ident": ident,
                        "r": ring,
                        "n": n,
                        "seed_ident": seed["ident"],
                        "seed_source": seed.get("source"),
                        "d_reducible": res.d_reducible,
                        "n_extendable": res.n_extendable,
                        "n_consistent": res.n_consistent,
                        "rounds": res.rounds,
                        "adjacency": {str(k): v for k, v in adj.items()},
                        "features": feats,
                        "canonical_key": ck,
                        "oracle_cross_check": oracle,
                    })

                since_checkpoint += 1
                if since_checkpoint >= checkpoint_every:
                    state.elapsed_sec = time.time() - t0
                    checkpoint_cb()
                    since_checkpoint = 0
        # unused budget at this ring is simply not carried further (kept
        # simple; ring buckets are processed smallest-first per the spec's
        # "prioritize smaller rings" -- see main()'s ring_order).
    state.elapsed_sec = time.time() - t0
    checkpoint_cb()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--r12-budget", type=int, default=800)
    ap.add_argument("--r13-budget", type=int, default=500)
    ap.add_argument("--r14-budget", type=int, default=270)
    ap.add_argument("--r15-budget", type=int, default=70)
    ap.add_argument("--r16-budget", type=int, default=17)
    ap.add_argument("--r11-dual-budget", type=int, default=3000)
    ap.add_argument("--tries-per-seed", type=int, default=150)
    ap.add_argument(
        "--tries-per-seed-dual",
        type=int,
        default=400,
        help=(
            "r=11/n_interior<=6 configs are already near the RSST legality "
            "boundary (median ring-vertex degree ~3-4, interior degree "
            "exactly 5) -- most single flips there drop some vertex below "
            "its minimum degree, so the gate-pass yield is roughly 100x "
            "lower than at r=13-16; compensate with far more flip "
            "attempts per seed."
        ),
    )
    ap.add_argument("--checkpoint-every", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--rules", type=str, default="candidate1,candidate2,candidate3,dual_r11")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("")  # fresh log each run

    log("Loading pool (with adjacency, for mutation seeds)...")
    records = load_pool_with_adjacency()
    pool_cks = {r["canonical_key"] for r in records}
    log(f"  {len(records)} deduped configs loaded.")

    ring_budgets = {12: args.r12_budget, 13: args.r13_budget, 14: args.r14_budget, 15: args.r15_budget, 16: args.r16_budget}
    ring_order = [12, 13, 14, 15, 16]

    rng = random.Random(args.seed)
    tested_cks: set[str] = set()
    states: dict[str, RuleRunState] = {}

    requested = set(args.rules.split(","))

    def cb():
        checkpoint(states, {"args": vars(args), "n_pool": len(records)})

    for rule in RULES:
        if rule.name not in requested:
            continue
        log(f"=== Stress-testing {rule.name}: {rule} ===")
        state = RuleRunState(rule.name)
        states[rule.name] = state
        run_rule(
            rule,
            records,
            ring_budgets,
            ring_order,
            tested_cks,
            pool_cks,
            args.tries_per_seed,
            rng,
            state,
            cb,
            args.checkpoint_every,
            seed_target_label=None,
        )
        log(
            f"=== {rule.name} done: {state.mutants_labeled} labeled, "
            f"{len(state.false_positives)} FP -> {'KILLED' if state.false_positives else 'SURVIVED'} ==="
        )

    if "dual_r11" in requested:
        log(f"=== Stress-testing dual rule: {DUAL_RULE} ===")
        state = RuleRunState("dual_r11")
        states["dual_r11"] = state
        run_rule(
            DUAL_RULE,
            records,
            {11: args.r11_dual_budget},
            [11],
            tested_cks,
            pool_cks,
            args.tries_per_seed_dual,
            rng,
            state,
            cb,
            args.checkpoint_every,
            seed_target_label=False,  # mutate the known non-reducible r=11 seeds
        )
        log(
            f"=== dual_r11 done: {state.mutants_labeled} labeled, "
            f"{len(state.false_positives)} FP -> {'KILLED' if state.false_positives else 'SURVIVED'} ==="
        )

    result = {"args": vars(args), "n_pool": len(records), "states": {k: v.as_dict() for k, v in states.items()}}
    with FINAL_JSON.open("w") as f:
        json.dump(result, f, indent=2)
    write_markdown(result)
    log(f"Wrote {FINAL_JSON} and {FINAL_MD}")
    return 0


def write_markdown(result: dict) -> None:
    lines = ["# Adversarial stress test of theorem candidates\n"]
    lines.append(
        "Mutation search (diagonal edge flips, `fourcolor.mutate.flip_edge`) targeted at the "
        "exact region where the three top theorem candidates in `results/theorem/candidates.md` "
        "fire (rings 13-16, where the pool has zero adversarial non-reducible examples), plus "
        "the dual rule `r == 11 AND n_interior <= 6 -> non-reducible`. See `tools/"
        "stress_test_theorem.py` for the method.\n"
    )
    lines.append(f"Pool size: {result['n_pool']} deduped configs. Search args: `{result['args']}`.\n")

    name_to_rule = {r.name: r for r in RULES}
    name_to_rule["dual_r11"] = DUAL_RULE

    for name, st in result["states"].items():
        rule = name_to_rule[name]
        lines.append(f"## {name}: `{rule}`\n")
        lines.append(f"**VERDICT: {st['verdict']}**\n")
        lines.append(
            f"- seeds considered: {st['seeds_considered']}; mutants generated: {st['mutants_generated']} "
            f"(gate-failed: {st['mutants_gate_failed']}, rule-dropped: {st['mutants_rule_dropped']}, "
            f"duplicate/already-known: {st['mutants_duplicate']})"
        )
        lines.append(f"- **novel rule-satisfying mutants labeled via `reduce.check()`: {st['mutants_labeled']}**")
        lines.append(f"- labels by ring: {st['labels_by_ring']}")
        lines.append(f"- wall time: {st['elapsed_sec']:.0f}s")
        if st["false_positives"]:
            lines.append(f"- **{st['n_false_positives']} FALSE POSITIVES FOUND -- rule is UNSOUND as stated:**\n")
            for fp in st["false_positives"]:
                lines.append(f"  - `{fp['ident']}` (r={fp['r']}, n={fp['n']}, seed={fp['seed_ident']} / {fp['seed_source']}): "
                              f"d_reducible={fp['d_reducible']}, n_extendable={fp['n_extendable']}, n_consistent={fp['n_consistent']}")
                oc = fp.get("oracle_cross_check")
                if oc and oc.get("ok"):
                    agree = (oc.get("oracle_d_reducible") is False) and oc.get("matches_our_check")
                    lines.append(
                        f"    - **independent oracle cross-check ({oc.get('oracle_binary')}, the original "
                        f"1995/Steinberger-extended C reference)**: oracle_d_reducible={oc.get('oracle_d_reducible')}, "
                        f"oracle_n_extendable={oc.get('oracle_n_extendable')} "
                        f"({'AGREES -- independently confirmed' if agree else 'DISAGREES -- needs investigation'})"
                    )
                elif oc is not None:
                    lines.append(f"    - independent oracle cross-check FAILED to run: `{oc}`")
                lines.append(f"    - adjacency: `{json.dumps(fp['adjacency'])}`")
                lines.append(f"    - features: `{json.dumps(fp['features'])}`")
        else:
            lines.append("- 0 false positives -- rule survived this stress test on the mutants tested.")
        lines.append("")

    FINAL_MD.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
