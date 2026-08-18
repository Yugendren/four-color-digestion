# METHOD Survey: Machine Attack on the Four Color Theorem's Proof Structure
**Scope:** Sub-goal A (smaller unavoidable set of reducible configurations) + Sub-goal B (interp-extraction of the reducibility invariant). Flags: **[FV]** = fetched/verified 2026-08-19; **[KB]** = model knowledge, not re-verified. (WebSearch budget exhausted; all [FV] via direct WebFetch/arXiv-API/PDF reads.)

---

## 0. Headline findings that change the design space

1. **Automated discharging via LP exists and is published.** Bousquet–Deschamps–de Meyer–Pierron, *"Square coloring planar graphs with automatic discharging"* ([arXiv:2204.05791](https://arxiv.org/abs/2204.05791)) is almost exactly the inner loop for sub-goal A, code released **[FV]** (read pp.1–5). Precursor: Stolee, *"Automated Discharging Arguments for Density Problems in Grids"* ([arXiv:1409.5922](https://arxiv.org/abs/1409.5922)) **[FV]**.
2. **A 2026 paper already re-engineered the 4CT proof structure**: Inoue et al., "The Four Color Theorem with Linearly Many Reducible Configurations and Near-Linear Time Coloring" ([arXiv:2603.24880](https://arxiv.org/abs/2603.24880)), D-reducible configurations, curvature-based discharging, open C++ verification code ([github.com/near-linear-4ct/computer-checks](https://github.com/near-linear-4ct/computer-checks), MIT) **[FV]**. Best modern verifier codebase and the paper to position against.
3. **633 is not even the record.** Steinberger (p.4): RSST "advertised an alternate unavoidable set of only **591** configurations containing some block-count reducible configurations" **[FV]**. True target: **<591** (or <633 under RSST's exact reducibility notions) — cite correctly or the contribution claim is wrong.
4. **The data-starvation premise is false.** Steinberger tested **>130,000 configurations; 42.8% D-reducible** (~90% C-or-D-reducible); RSST tested ~14,000 (54.4% D-reducible) **[FV, Steinberger PDF p.3]**. Labeled, roughly balanced datasets of 10⁵–10⁶ configurations are cheaply generatable. "Only 633 positives" confuses *the published set* with *the positive class*.

---

## 1. Sub-goal A — Set minimization methods

### 1a. LP/ILP formulations of discharging — the anchor method
**Bousquet et al. loop [FV]:** initial charge deg(x) − α; discharging rules are local transfers whose amounts are **LP variables**; constraints assert final charge ≥ 0 on every local neighborhood type *not containing* a configuration from the current reducible set 𝒞. Given 𝒞, the LP either finds rule values proving unavoidability, or is infeasible and emits violating neighborhoods = **candidate configurations**; a reducibility checker labels one, it joins 𝒞, loop repeats. Cutting-plane/back-and-forth; "not entirely autonomous"; framed as "a first step towards a fully automated discharging prover."

**Fit to 4CT:** RSST/Steinberger discharging is exactly this schema (Steinberger 42 rules vs RSST 32 vs AH 487 **[FV]**). Fix rule *shapes*, let LP choose amounts; finite cartwheel/wheel enumeration as constraint generator (near-linear-4ct repo enumerates wheels for hub degrees 7–11: 5,439 wheels at degree 7 down to 8 at degree 11 **[FV]**) → unavoidability-checking becomes finite LP feasibility. Collapses one level of the bilevel problem.

**Set minimization on top:** with a large precomputed pool of D-reducible configurations (§3), "smallest unavoidable subset" = minimize |S| s.t. ∃ rule values making every rule-feasible neighborhood contain a member of S. Bilevel (rules and set interact) — pure ILP won't close it; practical scheme = column generation / alternating: outer loop proposes subsets (greedy, MaxSAT over a *fixed* rule set, or evolutionary), inner LP re-solves rules. **[KB synthesis; no prior work does set-minimization for 4CT — that is the gap]**

**LP duality lower bounds:** no literature exists on lower bounds for unavoidable-set size **[FV — searches empty]**. The LP dual of the covering relaxation (fixed rule schema, enumerated neighborhood universe) gives the first nontrivial *schema-relative* lower bound — publishable even if minimization stalls. **[KB]**

### 1b. Closest solved analogues
- **Subercaseaux–Heule**, packing chromatic number of the square grid = 15 ([arXiv:2301.09757](https://arxiv.org/abs/2301.09757)) — custom encoding, verified UNSAT proof reducing trust to the encoding **[FV]**. Template for a *certifying* unavoidability check.
- Steinberger's own search: 130k configs explored to assemble 2,822 D-reducible at ring ≤ 16; he **failed** to find a D-only set at ring ≤ 14 and "ha[s] no opinion" whether one exists **[FV]** — that open question is itself a named target.
- Cranston–West guide ([arXiv:1306.4434](https://arxiv.org/abs/1306.4434)) **[FV abstract]**; treat 2204.05791 as the LP citation.

### 1c. Search-loop options
- **FunSearch/AlphaEvolve-style program synthesis of rule sets** (FunSearch blog **[FV]**; AlphaEvolve [arXiv:2506.13131](https://arxiv.org/abs/2506.13131) **[FV]**): rule sets *are* short programs; verifier exact and minutes-fast — shape fits. The loop discipline (evaluator + diversity archive) runs with a small local model or LLM-free mutations. **[KB sizing]**
- **PatternBoost** ([arXiv:2411.00566](https://arxiv.org/abs/2411.00566)) + follow-ups (percolating sets [2411.19734](https://arxiv.org/abs/2411.19734); no-three-in-line vs ILP/RL [2512.11469](https://arxiv.org/abs/2512.11469); Hadamard [2604.11101](https://arxiv.org/abs/2604.11101); dominating sets [2605.02193](https://arxiv.org/abs/2605.02193)) **[FV]**: designed for exactly this hardware class; strongest evidenced learned proposer for the outer loop.
- **Pure RL (policy gradients over set edits): avoid** — sparse episodic reward with a cheap exact verifier means evolutionary/CEM/PatternBoost dominate; the no-three-in-line comparison found RL the weakest scaler **[FV per that paper]**.

---

## 2. Sub-goal B — Invariant extraction

### 2a. Precedents [all FV]
- **Zeta-map methodology** ([arXiv:2511.12421](https://arxiv.org/abs/2511.12421), [arXiv:2605.30482](https://arxiv.org/abs/2605.30482)): 1-layer 1-head encoder-decoder transformer on the zeta map; cross-attention + probing + causal interventions → extracted "scaffolding map," proved equivalent. The direct template.
- **Davies et al. knot theory** ([arXiv:2111.15323](https://arxiv.org/abs/2111.15323)): attribution over hand-chosen invariants → conjecture → theorem. Weaker interp; canonical "it produced a theorem" precedent.
- **Othello-GPT** ([arXiv:2210.13382](https://arxiv.org/abs/2210.13382)): next-move training yields an emergent, intervention-verified internal board model. Precedent for "train on the *process*, probe out the *state*."
- **Neural algorithmic reasoning** (Veličković–Blundell, [arXiv:2105.02761](https://arxiv.org/abs/2105.02761)): imitating algorithm *intermediate steps* yields better generalization and inspectable representations; message passing aligns with DP **[FV]**. D-reducibility is literally a fixed-point/DP computation — NAR is the theoretical backing for process supervision here.

### 2b. GNN vs transformer — tooling verdict
- GNN explainability remains post-hoc (subgraph masks, relevance walks); **no mechanistic ecosystem** — no circuits, no SAEs, no standard probing **[FV — scan of 10 recent papers]**.
- Transformer side: TransformerLens/patching/SAEs/probes mature; zeta-map proves them on tiny math transformers **[KB tooling; FV zeta-map]**.
- Configurations are tiny (≤ ~30 vertices, ring 6–14) with canonical encodings already defined (`unavoidable.conf` format **[FV]**; boundary-first spiral orderings **[KB]**). Nothing forces graph-native models at this scale.

### 2c. Outcome vs process — the key design call
**Train to simulate the D-reducibility fixed point, not (only) classify:**
- Input = canonical config encoding; supervision = the *trajectory* of the consistent-set computation (which ring-coloring classes survive each Kempe-closure iteration) + a final reducible/not head. Every intermediate label is free — the verifier computes them anyway.
- Rationale: (i) Othello-GPT + NAR show process-trained models build probeable internal state **[FV]**; (ii) an outcome classifier risks shortcut correlates (degree statistics, ring size) that interp would faithfully but uselessly recover; (iii) the invariant, if it exists, is a certificate-like summary of the fixed point — pressure the model to represent the dynamics the invariant compresses.
- Hybrid: dual-head (trajectory + outcome), then probe for low-dimensional structure predicting the outcome *earlier* than the simulation converges — **that gap is exactly where a human-legible invariant would live**. **[KB design synthesis]**
- Honest risk: unlike the zeta map, possibly no compact invariant separates D-reducible from not — Steinberger's 42.8%-positive soup suggests a complicated boundary. Frame sub-goal B as "extract *partial* invariants / fast sound filters" (useful for A's pool generation even if no theorem falls out). **[KB]**

---

## 3. Data-regime reality check

- **Positives:** the positive *class* is huge (42.8% of 130k tested **[FV]**), not 633.
- **Generation:** plantri (McKay–Brinkmann, [users.cecs.anu.edu.au/~bdm/plantri/](https://users.cecs.anu.edu.au/~bdm/plantri/)) generates planar and **disk triangulations** at >5M graphs/sec, C, Apache-2.0 **[FV]**. Filter to configuration constraints, label with the checker.
- **Labeling cost:** reducibility grows ~4× per unit ring size; ring-16 ≈ minutes on 2009 hardware **[FV Steinberger p.3]** → ring 14 well under 1s now; ring ≤ 11 sub-millisecond–millisecond. **~10⁵–10⁶ labeled configs at ring ≤ 12 in days on M4/3060; ring 13–14 in the 10⁴–10⁵ range.**
- **Verdict:** supervised training fully feasible; choose process-supervision for *interp quality*, not data scarcity — process labels multiply supervision per config for free.

---

## 4. Hybrid/exotic options, honestly

| Option | Assessment |
|---|---|
| FunSearch-style rule-set synthesis | Best exotic fit for A; LLM-free or small-local-LLM; evaluator + island archive is load-bearing. **[FV precedents / KB sizing]** |
| GFlowNets ([arXiv:2305.17010](https://arxiv.org/abs/2305.17010) **[FV]**) | Training overhead unjustified when plantri enumerates the space exhaustively at relevant sizes. Avoid for A; marginal for B curation. |
| QD / MAP-Elites archive | Cheap and genuinely useful: archive D-reducible configs binned by (ring size, hub profile, charge signature) as the pool feeding set-cover; shared artifact between A and B. Secondary. **[KB]** |
| ILP-duality lower bounds | Do it — schema-relative bound; no prior art **[FV absence]**. |
| Kempe-chain RL environment | No precedent **[FV]**; as proof route avoid (Kempe failure is the classical dead end); chain dynamics are computed exactly by the verifier — use its traces as supervision, no RL needed. |
| e-graphs / equality saturation | Poor fit: discharging rules are charge-flow inequalities, not equational rewrites. Avoid. **[KB]** |

---

## 5. Verifier engineering (the actual critical path)

| Asset | Where | Notes |
|---|---|---|
| RSST `reduce.c`, `discharge.c`, `unavoidable.conf`, `rules`, Heckman's `discharge.pas` | [GT ftp](https://thomas.math.gatech.edu/FC/ftpinfo.html); arXiv:1401.6481 / 1401.6485 **[FV]** | 633-set reducibility verified "in ~20 min" on 1990s hardware → seconds–minute today. Independent re-implementation exists (Fijavž) **[FV]**. |
| Steinberger ancillary | [arXiv:0905.0043](https://arxiv.org/abs/0905.0043) `aux/` **[FV]** | RSST's two programs verify his entire different proof with trivial modifications — **swap config + rule files, keep programs** **[FV pp.2–3]**. |
| near-linear-4ct `computer-checks` | [github.com/near-linear-4ct/computer-checks](https://github.com/near-linear-4ct/computer-checks), C++/CMake, MIT **[FV]** | Wheel enumeration (deg 7–11), bad-cartwheel detection, discharging+config verification. Best skeleton for the LP constraint generator. |
| coq-community/fourcolor | [github](https://github.com/coq-community/fourcolor) **[FV]** | Gold-standard cross-check; end-game formalization path (proof structure identical). |
| Misc GitHub | LKCoffee/four-color-theorem-verification (C); olleicua/Py4_color_Reduction (Python) **[FV]** | Sanity oracles. |

**Performance targets [KB estimates on FV anchors]:** bitset-parallel D-reducibility fixed point, memoized by canonical form: <1ms at ring ≤ 11, <100ms at ring 13, ~1s at ring 14; differential-test vs RSST 633 + Steinberger 2822. Inner LP: sub-second with HiGHS. Full unavoidability check: minutes → outer-loop throughput ~10²–10³ candidate proof-structures/day on M4, 3060 free for B training. Enough for PatternBoost/evolutionary loops; not for RL — the quantitative reason RL scores "avoid." Make it certifying (log LP duals + reducibility transcripts), per the Subercaseaux–Heule trusted-core pattern **[FV]**.

---

## Recommendation matrix

| Sub-goal | Method | Verdict |
|---|---|---|
| A | LP for rules + iterative config generation (Bousquet-style) | **Primary** |
| A | Precomputed D-reducible pool + MaxSAT/ILP subset minimization with rule re-solve (column generation) | **Primary** (paired) — the novelty gap: nobody has run set-minimization on 4CT |
| A | PatternBoost/FunSearch-style evolved proposer over rule shapes + config edits | Secondary (add when exact loop plateaus) |
| A | LP-duality schema-relative lower bound | Secondary — cheap, novel, publishable hedge |
| A | RL set-editing, GFlowNets, e-graphs | Avoid |
| B | Small transformer (1–4 layer), canonical sequence encoding, **process-supervised** on the fixed-point trajectory + outcome head; TransformerLens stack | **Primary** — zeta-map template |
| B | GNN on same targets | Secondary (generalization baseline; not the extraction vehicle) |
| B | Outcome-only classifier | Secondary (control for shortcut features) |
| B | Davies-style attribution over hand-crafted invariants | Secondary (cheap first pass) |
| B | Kempe-chain RL | Avoid (use verifier traces as supervision instead) |
| A+B | QD/MAP-Elites archive of reducible configs | Secondary — one artifact serves both |

**Bottom line:** For A — the **exact stack** (LP rules + reducibility checker + subset minimization), learned proposers added only as accelerator; competitive frame: "beat 591, or settle Steinberger's open D-only ring≤14 question." For B — the **zeta-map pipeline transplanted to a process-supervised tiny transformer**, GNN and outcome-only classifier as controls; data volume is solved, so all design freedom goes to maximizing interp handles.
