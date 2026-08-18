# Four Color Theorem as Dataset & Search Space — Technical Dossier

Prepared 2026-08-19. Flags: **[FV]** = fetch-verified this session (URL given); **[KB]** = training knowledge, not re-verified; confidence noted where it matters. WebSearch budget was exhausted; all verification below was done via direct WebFetch on primary URLs.

---

## 1. Anatomy of the RSST proof (Robertson–Sanders–Seymour–Thomas 1997)

**Canonical sources.** The proof is "The four-colour theorem," *JCTB* 70 (1997) 2–44 [KB]. Robin Thomas's project page survives at https://thomas.math.gatech.edu/FC/fourcolor.html [FV]. In 2014 the authors archived everything permanently on arXiv:

- **arXiv:1401.6481 — "Reducibility in the Four-Color Theorem"** (RSST), with ancillary files `reduce.c` and `unavoidable.conf` (the 633 configurations) [FV: https://arxiv.org/abs/1401.6481].
- **arXiv:1401.6485 — "Discharging cartwheels"** (RSST), with ancillary files `discharge.c`, `discharge.pas` (independent Pascal reimplementation by Christopher Carl Heckman), `rules`, `present7`–`present11`, `unavoidable.conf`, plus documentation [FV: https://arxiv.org/abs/1401.6485].

Headline numbers, confirmed on Thomas's page [FV]: **633 reducible configurations** (vs. Appel–Haken's ~1476), **32 discharging rules** (vs. AH's 300+), programs use **integer arithmetic only**, and unavoidability "can be checked by hand in a few months, or, using a computer... in about 20 minutes" (1990s hardware). Independent re-implementation of the checks: Gašper Fijavž under Bojan Mohar [FV, same page].

**What a configuration is.** A *near-triangulation* is a non-null connected loopless plane graph in which every finite region is a triangle [FV]. A *configuration* K is a near-triangulation G(K) plus a map γ_K: V → Z (the degree each vertex will have in the ambient triangulation), subject to consistency conditions; the *ring-size* is determined by the deficiencies on the outer boundary [FV summary + KB detail]. The *free completion* S(K) embeds K inside a surrounding ring circuit R of length r, so every interior vertex attains degree γ. In the 633 set, **ring size ≤ 14** [KB, high confidence].

**Data-structure reality of `unavoidable.conf`** [FV: https://thomas.math.gatech.edu/FC/ftpinfo.html]. Each of the 633 records contains:
1. an identifier string;
2. a header `n r a b`: n = vertices of free completion, r = ring size, plus cardinalities of auxiliary coloring sets used by `reduce.c`;
3. the **contract**: k followed by 2k integers (endpoint pairs of contract edges);
4. the adjacency list of the free completion (ring vertices 1…r; configuration vertices r+1…n);
5. drawing coordinates packed as `1024·x + y` (rendered in `unavoidable.pdf`, also on the site).

Each configuration is a tiny attributed planar graph — typically 4–35 vertices — a perfect unit for tokenized or graph-native ML input.

**D-reducibility, operationally** [KB, high confidence — standard Birkhoff/Heesch machinery in `reduce.c`]. Fix ring R of size r. Proper 4-colorings of R up to the 4! color symmetries number ≈ 3^r/24; for r = 14 this is the classical **199,291** equivalence classes. Compute:
- Φ = ring colorings that extend to a proper 4-coloring of the whole free completion — direct enumeration.
- Kempe closure: a set S of ring colorings is *consistent* if for every θ ∈ S and every partition of the 4 colors into two pairs, there is a signed matching (planar pairing of ring vertices by hypothetical exterior Kempe chains) compatible with θ such that every coloring reachable by flipping chains of that matching lies in S. `reduce.c` computes the **maximal consistent subset of the complement of Φ** by iterated deletion (greatest fixed point). K is **D-reducible** iff this set is **empty**.
- **C-reducibility**: when D fails, use the *contract* X (≤ 4 edges in all 633 cases [KB]): contract X in a minimal counterexample, 4-color the smaller triangulation, check every induced ring coloring lies outside the maximal consistent set. D-reducible = C-reducible with empty contract.

**Discharging / unavoidability mechanics** [KB high confidence, filenames FV]. In an internally 6-connected minimal-counterexample triangulation, assign charge 10(6 − deg v); Euler makes the total +120, so some vertex ends positive under any redistribution. The **32 rules** (`rules` file) each specify a small degree-labeled subgraph and an edge across which a fixed integer charge moves when the pattern matches. RSST prove: if a vertex v ends positive, one of the 633 configurations appears in the *cartwheel* of v (v + neighbors + second neighbors with degrees). Hand arguments cover hub degrees 5, 6, ≥ 12; the machine covers 7–11 — the five presenter files `present7`…`present11` [FV filenames] are **replayable proof scripts**: `discharge.c` reads them line by line, each line exhibiting a configuration hit or splitting into subcases. **The unavoidability proof is already a symbolic search-tree transcript** — a ready-made dataset of (partial cartwheel, action, outcome) triples.

**Formalizations and re-implementations.**
- **Gonthier's Coq proof (2005)**: fully formal; maintained at **https://github.com/coq-community/fourcolor** (Yves Bertot; MathComp/ssreflect; opam-installable) [FV]. Graph theory rebuilt on *combinatorial hypermaps*; reducibility run by reflection [KB].
- **Steinberger's D-only proof**: "An unavoidable set of D-reducible configurations," **arXiv:0905.0043** (2009; Trans. AMS 2010 [KB]) — **2822 configurations, all D-reducible (no contracts)**, settling a Stromquist/AH/RSST conjecture [FV abstract]. Ancillary: `U_2822.conf`, `L_42` (42 discharging rules [KB interp of FV filename]), modified `reduce.c`/`discharge.c`, presenters `p5_2822`…`p11_2822` (machine-checks degrees 5 and 6 too) [FV filenames]. Configurations up to **ring size 16** [KB, moderate].
- **Lean**: 4CT not in mathlib as of early 2026 [KB]. Two active efforts [FV via GitHub API]: **tangentstorm/fourcolor-lean** — AI-assisted Lean 4 port of the Rocq proof, ~10% complete, infrastructure ~96%, actively developed (May 2026) [FV]; WaterKing201030/FourColorTheoremLean (early, Aug 2026) [FV, unexamined].
- **Fresh 2026 result (important)**: Inoue, Kawarabayashi, Miyashita, Mohar, Thomassen, Thorup, "The Four Color Theorem with Linearly Many Reducible Configurations and Near-Linear Time Coloring," **arXiv:2603.24880** — triangulations contain *linearly many pairwise non-overlapping* reducible configurations via discharging + combinatorial-curvature analysis of "flat" regions, yielding **O(n log n)** coloring (vs RSST's quadratic) [FV abstract]. Companion C++ verification repo "computer-checks" [FV]. The closest existing work in spirit — *re-mines the configuration space* for structural abundance. Read first.
- "Xiang" / Cahit "spiral chains": claimed short proofs, not community-accepted; no machinery re-implementations [KB, low confidence].

---

## 2. The search space: alternative unavoidable sets of reducible configurations

**The two dials.** A proof = (set U of configurations, discharging proof that U is unavoidable). Freedom:
1. **Configuration inventory**: which near-triangulations, ring-size cap, D-only vs contracts (and contract size cap).
2. **Discharging design**: charge function (any assignment with positive Euler total), rule set (patterns + amounts — real weights legal; integers chosen for verifiability), hub-degree cutoffs for hand vs machine cases.

**The fundamental trade-off.** More/finer rules ⇒ positive charge cornered into more specific structures ⇒ fewer/smaller configurations suffice. Raising the **ring-size cap** makes many more configurations reducible (Steinberger needed r ≤ 16 for D-only), but D-checking is exponential in r:
- states ≈ 3^r/24: r=12 → ~22k; **r=14 → 199,291**; r=16 → ~1.79M; r=18 → ~16M [KB arithmetic]. Cost per configuration roughly Õ(3^r · poly(r)) with a fixed-point loop. This is why AH/RSST stopped at 14 — **the historically explored region is a hardware artifact, not a mathematical boundary.** On 2026 hardware r=16–18 closures are casually affordable. Genuine headroom.
- Contracts are the other compression lever: a ≤4-edge contract substitutes for enormous ring-size increases. RSST-633-with-contracts vs Steinberger-2822-D-only: **dropping contracts cost ~4.5× in configuration count** [FV counts, KB framing].

**Known minimization attempts / lower bounds.**
- AH ~1476→RSST 633→Steinberger 2822 (different objective: purity). **No published work minimizing |U|** [KB, moderate confidence — searches empty]. The 2026 paper changes the objective (density of disjoint configurations), not count [FV].
- **Lower bounds: essentially nothing known.** No published nontrivial lower bound on the minimum size of an unavoidable set of reducible configurations [KB, high confidence]. Tension: small/low-ring configurations tend to fail reducibility (nothing with ring < 6 is reducible; the **Birkhoff diamond** — ring size 6, Birkhoff 1913 — is the smallest classic reducible configuration) [KB]. Where |U|_min lies between ~1 and 633 is open — legitimately publishable territory.
- **Why naive approaches die (Kempe/Heawood).** Kempe 1879 handled degree ≤4 with single chain flips; at degree 5 he flipped two chains simultaneously, but chains can interlock — Heawood's 1890 counterexample [KB; FV Wikipedia]. Errera and Fritsch graphs are the standard small failure examples. Deep point: D-reducibility *is* the statement "the Kempe-flip dynamical system on ring colorings has no invariant set avoiding Φ" — **the organizing invariant of reducibility, if it exists, is a statement about attractors of Kempe dynamics on the r-cycle.**

---

## 3. Prior ML / automation on 4CT, reducibility, discharging

**Direct ML on 4CT internals: none exists.** arXiv sweep for {four color} × {machine learning, RL, neural} returns nothing on reducibility, discharging, or Kempe chains [FV: arXiv API, 2026-08]. **The field is empty — no incumbent.**

**Automated discharging (symbolic, not ML).**
- Stolee, "Automated discharging arguments for density problems in grids," **arXiv:1409.5922** (2014): genuinely *generates* discharging arguments — closest ancestor of "learned discharging" [FV].
- Cranston & West, "An introduction to the discharging method via graph coloring," **arXiv:1306.4434** — standard survey; no automation [FV]. Practice: discharging-rule weights routinely optimized by **linear programming** (unavoidability is linear in rule amounts once patterns are fixed) — the differentiable-relaxation entry point [KB, high confidence].
- **No SAT-based proof of 4CT** published; reducibility is a greatest-fixed-point computation, QBF/Datalog-shaped rather than one SAT instance [KB, high confidence].
- GNNs for graph coloring: active but orthogonal (Lemos 2019, Schuetz 2022 [KB]; Vanderbush & Weber, neural algorithmic reasoning for k-coloring, arXiv:2601.05137, 2026 [FV]). Useful for architecture priors (message passing ≈ chain propagation).
- Learning Kempe-chain dynamics: nothing published [FV/KB].

---

## 4. Adjacent theory — candidate organizing invariants

- **Tait gateway**: 4CT ⇔ every bridgeless planar cubic graph is 3-edge-colorable. Tutte's conjecture (no-Petersen-minor ⇒ 3-edge-colorable) strictly generalizes 4CT; **proved** by RST + Edwards–Sanders–Seymour–Thomas ("Three-edge-colouring doublecross cubic graphs," **arXiv:1411.4352**, JCTB 2016) [FV abstract] — again via unavoidability/reducibility. **Any learned invariant should extend off the plane to Petersen-minor-free graphs — a strong falsifiable probe.**
- **Penrose/Kauffman**: Penrose 1971 (3-edge-colorings = spin-network evaluation); Kauffman, "Map coloring and the vector cross product" (JCTB 1990): 4CT ⇔ nonvanishing of iterated cross-product associations in R³ [KB]. arXiv: **math/0112266**, **1511.06844**, and 2026: Kauffman–Silver–Williams, "The Penrose–Kauffman Polynomial" (**2604.16635**), Baldridge–Kauffman–McCarty counterexample to Spencer-Brown's polar conjecture (**2607.22398**) [FV]. **Kauffman is actively working this seam in 2026.**
- **Lie-algebraic**: Bar-Natan, "Lie algebras and the four color theorem," **arXiv:q-alg/9606016** (Combinatorica 1997): 4CT ⇔ sl(2) weight-system nonvanishing on trivalent graphs [FV abstract].
- **Temperley–Lieb / chromatic roots**: Kauffman–Saleur (CMP 1993); **Beraha numbers** B_n = 4cos²(π/n) accumulate chromatic roots (B_∞ = 4 is why 4 is special); Tutte's golden identity; **Birkhoff–Lewis conjecture** (no roots in [4,5) — open); Fendley–Krushkal chromatic algebra [KB, high confidence]. **If interp extracts any algebraic invariant from reducibility tables, TL-algebra representation theory at Q = 4 is the most likely identity.**
- **Flow/cohomology**: 4CT ⇔ every bridgeless planar graph has a nowhere-zero Z₂×Z₂-flow; coloring = pair of even subgraphs covering E [KB]. Clean F₂ vector-space encoding, ML-friendly.

---

## 5. Practical data pipeline (M4 Mac mini + RTX 3060)

**Downloads (all live as of 2026-08):**

| Artifact | URL | Contents |
|---|---|---|
| RSST reducibility bundle | https://arxiv.org/e-print/1401.6481 | `reduce.c`, `unavoidable.conf` (633 configs), docs [FV] |
| RSST discharging bundle | https://arxiv.org/e-print/1401.6485 | `discharge.c`, `discharge.pas`, `rules` (32), `present7`–`present11`, docs [FV] |
| Steinberger bundle | https://arxiv.org/e-print/0905.0043 | `U_2822.conf`, `L_42`, modified programs, `p5_2822`–`p11_2822`, README [FV] |
| GT mirror + format docs | https://thomas.math.gatech.edu/FC/ftpinfo.html ; …/OLDFTP/fcdir/unavoidable.pdf | human-readable set + format spec [FV] |
| Gonthier Coq proof | https://github.com/coq-community/fourcolor | full formal proof; reducibility by reflection [FV] |
| Lean 4 port (partial) | https://github.com/tangentstorm/fourcolor-lean | ~10% ported, blueprint [FV] |
| 2026 linear-configs code | GitHub "computer-checks" (C++), arXiv:2603.24880 | verification for Inoue et al. [FV] |

(arXiv ancillary files: download the `e-print` tarball; files in `anc/`.)

**Formats**: `unavoidable.conf` plain text as in §1 — parsed into NetworkX/PyG in an afternoon. `rules` machine-readable; `present*` grammar documented in `discharge.tex` [FV existence; KB grammar]; Heckman's `discharge.pas` is a second reference implementation [FV].

**Re-verification cost** [KB, engineering judgment]: `reduce.c` on all 633 — **well under a minute on M4** (r ≤ 14 → ≤ 200k-element bitset fixed points, integer-only). `discharge.c` over present7–11 — seconds now. Steinberger 2822 at r ≤ 16 — minutes. Gonthier Coq build — 1–3 hours [KB]. Minor K&R-C modernization expected; a 2026 GitHub repo demonstrates the RSST code still compiles and verifies end-to-end [FV via GitHub search]. Everything CPU; the 3060 is purely for training.

**Natural training datasets:**
1. **configuration → {D-reducible, C-reducible-with-contract-k, irreducible}**: enumerate isomorph-free near-triangulations with ring 6–16 (plantri with boundary constraints [KB]); label with reimplemented `reduce`. Keep the full closure trace, not just the bit — train on *why* (which colorings survive how many rounds).
2. **(configuration, ring coloring) → extends?** — per configuration a Boolean table over ~3^(r−1) colorings; huge, exact, and the per-config tables are the objects whose compressibility *is* the research question. Auxiliary target: deletion round in the fixed-point iteration (a learned "Lyapunov function" for Kempe dynamics = organizing-invariant candidate).
3. **cartwheel → (final charge, which-configuration-hits)**: sample degree-labeled second neighborhoods, run the 32 rules; `present7`–`present11` give expert search trees for imitation learning on the case-split policy.
4. **Kempe dynamics environment**: states = ring colorings, actions = (color-pair, chain choice), transitions from signed-matching semantics — exact, cheap environment for RL/world-model probing of chain entanglement (the Heawood failure mode).
5. **Cross-proof transfer set**: RSST-633 vs Steinberger-2822 vs Inoue-et-al as train/test splits — an invariant transferring across independently engineered unavoidable sets is evidence of something real.

**Strategic notes.** (a) The historically searched region (r ≤ 14, integer weights, human-designed patterns) was hardware-limited; r ≤ 18 closures and LP/gradient-relaxed rule weights are now cheap — both goals attack genuinely unexplored territory. (b) Unavoidability is linear-programming-shaped; reducibility is fixed-point-shaped — a differentiable surrogate for the latter is the novel component. (c) Watch arXiv:2603.24880's authors and Kauffman's 2026 papers — the two live adjacent research fronts.
