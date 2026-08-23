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

- **M1: COMPLETE (2026-08-23).** f(13) = 8 established: interior <=6 (n<=19: 1,445 valid at
  interior 6 alone) and interior 7 (n=20: 6,710 valid) fully exhausted 8-way-sharded, ZERO
  D-reducible; tightness from catalogs (min interior 8 at r=13). Table now rings 8-13:
  f = 5,5,6,7,7,8. **Mass-law gap CONFIRMED OUT-OF-SAMPLE at r=13**: max a among the newly
  enumerated below-threshold negatives = 6,003 < 6,954 = min a among catalog D-reducibles
  (margin 951). Original M1 text follows for provenance:
  r=13 exhaustion `tools/fr_table.py 13 14 19` (interior ≤6 → proves f(13) ≥ 7; the interior-7/n=20
  cell is a separate later run — plantri n=20 is ~day-scale). Produces below-threshold negatives at
  r=13 → tests the gap prediction (law predicts threshold ≈ 6954·(range) vs sub-threshold max).
- **M2 (math): PARTIAL (2026-08-23). See `results/mass-law/PROOF-SHARP-CAP.md`.**
  Attempted the sharp cap `a ≤ ((2^r+2)/6)(4/3)^(k-1)`. **Not proven; the obstruction is
  now precisely localized and it is the Bridge Lemma itself.** What IS proven:
  (i) *base case exact* — `k=1` gives `a = (2^r + 2(-1)^r)/6 = P(W_r,4)/24`, with the full
  equality-case argument (fibres of the restriction map are singletons except at the 3
  monochromatic rims when r is even, whose stabilizer exactly compensates); adversarially
  re-verified four ways including the compiled 1995 RSST C oracle, r=5..12.
  (ii) *star-first cap* — `a ≤ min over interior h of (2^deg h + 2(-1)^deg h)·2^(n-deg h-1)/6
  ≤ 11·2^(r+k-7)`, i.e. the weak cap's constant improved by 11/16 and now EXACTLY TIGHT at
  every wheel. Implies `f(r) ≥ ⌈0.26303r − 0.1367⌉` (was −0.6768): **+1 interior vertex at
  6 of 10 rings, slope unchanged.** γ = 3/2 proven at k = 2 only.
  (iii) **THE OBSTRUCTION (rigorous, 10 vertices):** for `gen-r8-n10-2` (r=8,k=2),
  `P(S,4)/24 = 61 > 57.33 = W(8)·4/3 > 55 = a`. So no proof factoring through `a ≤ P(S,4)/24`
  can reach γ = 4/3 — the floor for that route is `61/43 = 1.4186` (implied f-slope ≤ 0.52).
  The P-form of the sharp cap is KILLED on 1,960/59,142 corpus configs and by 4 orders of
  magnitude on triangular-lattice disks. Reaching 4/3 requires bounding `|Φ|` directly
  (ring-trace transfer matrix, not tri-colourings).
  (iv) **The sharp cap itself got STRONGER:** `a` computed exactly on adversarial
  triangular-lattice disks up to (r,k) = (18,15) — cap holds every time with the margin
  *improving* (0.92→0.35) and γ_a *decreasing* (1.278→1.2365). New tools:
  `src/fourcolor/count4.py` (exact P(G,4)), `tools/p4_measure.py`, `tools/star_order_check.py`,
  `tools/arc_profile.py`, `tools/lattice_disk_entropy.py`, `tools/lattice_disk_phi.py`.
  Original M2 text follows for provenance: Route: a ≤ #tri-colorings of free completion up to color
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
- **Lemma-testing harness (the third checker): test any candidate statement BEFORE proving it.**
  `.venv/bin/python tools/test_lemma.py --check "rec.d_reducible implies rec.a >= 94*2.4**(rec.r-8)"`
  (also `--implies P Q`, `--bound "rec.a <= 2**(rec.r+rec.k-3)"`, `--filter EXPR`, `--summary`,
  `--gap-table`). Runs over all 59,142 canonically-deduped labeled configs (rings 6–16; d1_corpus
  + v2 traces + fr_table + generated), ~0.2s for scalar statements, and appends a timestamp-free
  receipt to `results/mass-law/lemma_log.jsonl`. Corpus loader `src/fourcolor/lemma_corpus.py`,
  checker `src/fourcolor/lemma_harness.py`, syntax + verdict semantics in `results/mass-law/README.md`.
  HOLDS means "survived the corpus", not proven — see the stress-test lesson in item 3 above.
