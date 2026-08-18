# Four Color Digestion — Attack Plan
## 2026-08-19. Sources: sources/4ct-proof-dossier.md (proof anatomy, data pipeline) and sources/method-survey.md (method evaluation). Strategy context: ../nextgen_discovery_research/ (esp. 07-HIGH-VALUE-TARGETS.md).

## Mission

Digest the Four Color Theorem's computer proof: (A) find a **smaller unavoidable set** of reducible configurations than the known records, and/or (B) **extract the organizing invariant** behind reducibility from trained models — contributing directly to the Tao/Buzzard "digestion" agenda. Every claim machine-verified; end-game formalization path via the Coq proof (structurally identical for any new set).

## Why this is winnable (the five research findings that de-risk it)

1. **Zero incumbents**: an arXiv sweep found no ML ever applied to reducibility, discharging, or Kempe chains. The field is empty.
2. **Data is abundant, not scarce**: the positive class is ~43% of 130k+ tested configurations (Steinberger), and plantri generates disk triangulations at >5M/sec. 10⁵–10⁶ labeled configs at ring ≤ 12 in days on this hardware.
3. **The explored region is a hardware artifact**: AH/RSST stopped at ring size 14 because of 1990s compute; ring 16–18 closure computations are now casually affordable. Genuine unexplored territory.
4. **The key inner-loop technique is published with code**: discharging-as-LP (Bousquet et al. 2022) + wheel enumeration (near-linear-4ct 2026 C++ repo) collapse unavoidability-checking to LP feasibility.
5. **All verifier components exist and are swap-compatible**: RSST's `reduce.c`/`discharge.c` verify Steinberger's entirely different proof with trivial modifications — new config/rule files, same programs.

## Honest competitive frame

- The record to beat for sub-goal A is **591** (RSST's advertised alternate set), not 633. Cite correctly.
- A named open question is available as a crisp target: **does a D-only unavoidable set exist at ring ≤ 14?** (Steinberger tried, failed, and explicitly has "no opinion.") Either answer is a result.
- **No lower bound on unavoidable-set size exists in the literature** — an LP-duality schema-relative bound would be the first, and is cheap.
- Live adjacent fronts to watch (and potentially connect with): the Inoue et al. near-linear-4CT group (arXiv:2603.24880) and Kauffman's active 2026 papers on algebraic reformulations.

## Architecture decision (the founder's question, answered)

**Not one method — two, matched to the two sub-goals:**

### Sub-goal A: smaller unavoidable set → EXACT OPTIMIZATION STACK (not RL, not transformer-first)
```
plantri generates candidate configurations (ring 6–16)
   → fast reimplemented D-reducibility checker labels them (bitset fixed point)
   → QD/MAP-Elites archive bins the reducible pool by (ring size, hub profile, charge signature)
   → INNER LOOP: discharging rules as LP variables; wheel enumeration generates constraints;
     LP feasible = unavoidability proven; infeasible = emits violating neighborhoods → new candidates
   → OUTER LOOP: MaxSAT/ILP subset minimization over the pool, alternating with LP rule re-solve
   → PatternBoost-style learned proposer added ONLY when the exact loop plateaus
   → certifying logs (LP duals + reducibility transcripts) throughout
```
RL scored **avoid** on quantitative grounds (episodes are minutes-scale; evolutionary/exact methods dominate at this throughput; the published head-to-head found RL the weakest scaler). GFlowNets and e-graphs also scored avoid (enumeration beats learned sampling at these sizes; no equational structure).

### Sub-goal B: reducibility invariant → INVERTED LOOP with PROCESS SUPERVISION (the math-transformer, with a twist)
```
canonical sequence encoding of configurations (boundary-first spiral; unavoidable.conf format)
   → small transformer (1–4 layers) trained to SIMULATE the D-reducibility fixed point
     (which ring-coloring classes survive each Kempe-closure round — labels free from the verifier)
     + outcome head (reducible / not)
   → controls: outcome-only classifier (shortcut detector), GNN (generalization baseline)
   → interrogation: TransformerLens probes, activation patching, attention analysis
   → the money question: does a low-dimensional internal structure predict the outcome
     EARLIER than the simulation converges? That gap is where a human-legible invariant lives.
   → candidate identity checks: Temperley–Lieb algebra at Q=4, Bar-Natan sl(2), flow/F2 encodings
   → falsifiable transfer probe: does the invariant extend to Petersen-minor-free graphs (Tutte/RST)?
```
The twist vs a plain classifier: process-trained models (Othello-GPT, neural algorithmic reasoning) build probeable internal state; outcome classifiers learn shortcut correlates that interpretability would faithfully but uselessly recover.

**Shared spine**: one verifier stack, one configuration archive, one data factory — the same "specialist models, general engine" design from the Mericanii methodology. Deep insight from the dossier worth keeping in view: *D-reducibility is the statement that Kempe-flip dynamics on ring colorings has no invariant set avoiding the extendable colorings* — the invariant, if it exists, is a statement about attractors of that dynamical system.

## Deliverables ladder (every rung publishable)

1. **Modern open-source 4CT toolkit** (parser, fast checker, differential-tested vs RSST-633 + Steinberger-2822) — community value regardless of outcomes; the reference implementation.
2. **Schema-relative lower bound** on unavoidable-set size (LP duality) — first of its kind.
3. **Set-size result**: beat 591, or settle D-only-at-ring≤14 either way.
4. **Invariant result**: extracted partial invariants / fast sound reducibility filters (useful even below theorem grade), with the dual-head early-prediction gap as the discovery instrument.
5. **Transfer test**: any extracted invariant probed on Petersen-minor-free graphs — evidence of something real beyond the plane.
6. **End-game**: new set swapped into the Coq/Gonthier framework for formal verification.

## Phase plan

- **Phase 0 (weeks 1–3): verifier stack.** Download arXiv bundles (1401.6481, 1401.6485, 0905.0043 ancillary files); parse `unavoidable.conf`; modernize/reimplement `reduce.c` as a bitset-parallel fixed point (<1ms at ring ≤11, ~1s at ring 14); differential-test against all 633 + 2,822; replay `present7`–`present11` through `discharge.c`. Clone near-linear-4ct computer-checks as the modern skeleton.
- **Phase 1 (weeks 3–6): data factory.** plantri → configuration filter → labeling runs; QD archive; keep full closure traces (the process-supervision labels). First dataset release.
- **Phase 2A (months 2–4): exact minimization loop.** LP rules + wheel constraints; MaxSAT subset minimization; lower-bound computation; PatternBoost proposer if plateaued.
- **Phase 2B (parallel, months 2–4): inverted loop.** Process-supervised transformer + controls; interrogation protocol; invariant candidates tested against the algebraic identities in the dossier §4.
- **Phase 3 (months 4+):** whichever thread is winning gets the compute; write up; formalize.

## Relationship to the wider Mericanii plan

This project **is** Rung 1–2 of the flywheel (04-EXECUTION-FLYWHEEL) applied to the flagship target from 07-HIGH-VALUE-TARGETS. The zeta-map pipeline reimplementation (Rung 0, nextgen plan) shares the interrogation tooling with Phase 2B — build once, use in both. The verifier-first discipline, matched-budget gates, and archive-as-asset rules from the vault apply unchanged.
