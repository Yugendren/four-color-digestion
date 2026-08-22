# The Coloring-Mass Program
## 2026-08-22 — the approachable goal after the f(r) theorem. THIS FILE IS THE CANONICAL STATE REFERENCE for the theorem line of work; update it as milestones close.

## What is already DONE and where it lives (do not re-derive)

1. **The f(r) theorem (COMPLETE, rings 8–12, all cells exhausted):** every D-reducible
   configuration of ring size r has ≥ f(r) interior vertices; f = {8:5, 9:5, 10:6, 11:7, 12:7};
   bounds tight against catalogs. First quantitative extension of Birkhoff (1913).
   - Statement + completeness argument + verification protocol: `results/theorem/fr_table/THEOREM.md`
   - Per-(r,n) enumerations + manifests: `results/theorem/fr_table/`
   - r=12 final cell: 1,088 valid configs at interior ≤6, 0 D-reducible (log_r12.txt); update THEOREM.md's r12 status line to "exhaustively proven" (open item).
   - Verified by: our checker (validated on 3,455 catalog configs — see results/differential-*),
     cross-checked vs compiled RSST binary (`build/reduce_rsst`), 6 oracle-abort cases adjudicated
     by third implementation `src/fourcolor/brute_force.py`.
   - Prior-art (novelty confirmed): the research report in this repo's history; key facts: no
     published per-ring interior minimum beyond Birkhoff ring≥6; catalog minima tight at every r;
     C-vs-D nuance (ring-8/int-4 and ring-11/int-6 C-reducible configs exist).
2. **The coloring-mass GAP discovery (2026-08-22, this session):** min extendable-coloring
   count (the `a` = |Φ| value) among D-reducible vs max among below-threshold non-reducible:
   r=8: 94 vs 82 | r=9: 211 vs 172 | r=10: 496 vs 438 | r=11: 1252 vs 1128 | r=12: 2863 vs 2339
   — clean gap at every measurable ring; min_a(D-red) grows ≈ ×2.4/ring
   (94, 211, 496, 1252, 2863, 6954, 17440, 42957, 100454 for r=8..16).
   Reproduce with: the inline miner in session history, or re-mine from
   `results/theorem/fr_table/configs_r*.jsonl` (below-threshold, has n_extendable) +
   `data/d1_corpus.jsonl` (D-reducible population).
3. **Killed en route (preserved honestly):** mined *sufficient* conditions for reducibility
   (results/theorem/candidates.md) were KILLED by adversarial mutation search — 26 oracle-confirmed
   false positives (results/theorem/stress_test.md; tools/stress_test_theorem.py). The dual/necessary
   direction survived and became the theorem. Lesson: pool-zero-FP ≠ sound; always mutate-stress.
4. **Context docs:** 00-ATTACK-PLAN.md, 01-PROBLEM-STATEMENT.md, 02-P3-DESIGN.md (earlier phases:
   verification of all three historical proofs, 7,770-config pruned proof, D1/v2 ML arc whose
   boundary-probe → arrangement-feature extraction led here). Strategy vault: ../nextgen_discovery_research/.

## THE GOAL (approachable statement)

**The Coloring-Mass Law** (conjecture, two halves):
- **(T) Threshold:** there is an increasing function A(r) (~c·2.4^r empirically) such that every
  D-reducible configuration of ring size r has a = |Φ(K)| ≥ A(r). (Φ = ring colorings extendable
  to the free completion; a is the classical header field.)
- **(C) Cap:** a configuration with k interior vertices satisfies a ≤ B(r,k), with B increasing in k.

**Corollary if both proven:** analytic f(r) lower bounds for ALL r — the finite table becomes an
infinite structural law: *reducibility is a coloring-mass threshold phenomenon; interior vertices
supply the mass.* This is the "chapter title" for the 50-year-old case-bash.

## Milestones

- **M1 (compute, launched 2026-08-22): extend the table + test the law out-of-sample.**
  r=13 exhaustion `tools/fr_table.py 13 14 19` (interior ≤6 → proves f(13) ≥ 7; the interior-7/n=20
  cell is a separate later run — plantri n=20 is ~day-scale). Produces below-threshold negatives at
  r=13 → tests the gap prediction (law predicts threshold ≈ 6954·(range) vs sub-threshold max).
- **M2 (math): prove the Cap (C).** Route: a ≤ #tri-colorings of free completion up to color
  symmetry; tri-colorings of planar (near-)triangulations ↔ proper 4-colorings (Tait); bound
  P(G,4)-style counts in terms of k for near-triangulations with interior degrees ≥5. Literature
  needed: Birkhoff–Lewis, chromatic polynomial bounds for triangulations, Tutte's work. A clean
  B(r,k) = c(r)·γ^k with γ < 3 would suffice.
- **M3 (math, hard): understand the Threshold (T).** The Kempe-closure fixed point must eliminate
  ~3^{r-1}/2 − a colorings; small Φ plausibly cannot break every consistent set. Quantify via the
  matching/θ-fit structure (see src/fourcolor/reduce.py's engine and reduce.tex's Thm 3.2 machinery).
  Even partial results (T for special families) are valuable.
- **M4: Lean formalization of the finite f(r) theorem** (727+1,088 configs, finite replay).
- **M5: write-up** (arXiv note: theorem + mass-law conjecture + data) **+ community**: Steinberger
  (bears on his open D-only ring≤14 question), Kawarabayashi–Mohar–Thorup group, digestion-agenda
  principals (Tao/Buzzard framing: machine-discovered, human-translated).

## Session-independent operational notes

- Repo: /Users/yugendren/experiments/four_color_digestion (git; every result committed with
  checksums; `make test` = full suite; .venv Python 3.12).
- Checker call: `from fourcolor.reduce import check` on a `fourcolor.conf_parser.Configuration`
  (ring ≤16 engines; big rings memory-heavy, see _Engine).
- Enumeration completeness = plantri 5.5 (pinned third_party/plantri) + RSST-legality filter
  `fourcolor.mutate.is_legal_configuration` (includes condition 6 — datagen.py's old filter lacked it).
- Long jobs: nohup+disown, checkpointed; waiters get reaped — re-arm freely, all idempotent.
