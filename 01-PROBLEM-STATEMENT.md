# Problem Statement: Configuration-Set Minimization (Sub-goal A)
## 2026-08-19 — first-principles definition, written before solving. Supersedes loose talk of "the LP loop."

## The object we are optimizing

A **proof instance** in the validated (2026 wheel-based) schema is a triple (U, R, x):
- U ⊆ P, a set of configurations from a pool P where every member is *reducible* (our independent checker is the arbiter);
- R = rule shapes (planar degree-interval patterns with a charge dart), x ∈ Z^|R| their amounts;
- validity = the full pipeline succeeds: combine rules → enumerate wheels (d=7..11) → keep "bad" wheels (charge bound ≥ 0 under x AND not blocked by U) → refine to bad cartwheels → the three gluing lemmas hold on the survivors.

**Key structural fact:** survivors are permitted. The charge argument need not kill every wheel; gluing mops up. Therefore "LP away all bad wheels" is a *stronger sufficient condition* than validity — useful as a target, wrong as the definition.

## The objective, and why

**Minimize |U|.** Reasons: (a) it is the historical metric of proof economy (Appel–Haken ~1834 → RSST 633 → RSST-advertised 591); (b) it is the digestion metric — fewer cases is the direction of human comprehensibility; (c) the pool and machinery are fully validated on this machine, making every candidate solution end-to-end checkable.

x and R are instruments. Optimizing them serves |U| (better discharging corners charge into fewer configurations).

## Honest comparability constraints (must appear in any write-up)

1. A minimal U in the wheel-based schema is **not directly comparable** to RSST's 591/633 (axle-based schema, C-reducibility with contracts allowed, ring ≤ 14). Claims must be schema-qualified. If |U'| < 591 anyway, the headline is legitimate with the qualification stated.
2. Any claimed (U', x') must be re-verified end-to-end: pipeline re-run with asserts live, PLUS our independent reducibility check of every member of U' (which also closes an open gap: the 2026 pool's reducibility has never been independently verified — their own verification was external to the released code).
3. The lower bound (P4) is **relative to (schema, rule shapes R, pool P)**. No absolute claim. It is still the first lower bound of any kind on unavoidable-set size.

## Problem ladder

- **P1 — foundation (DONE).** Symbolic charge bound as a linear form in x, validated exactly against the C++ on all 5,692,937 wheel candidates, d=7..11.
- **P2 — coverage measurement (NEXT).** For each bad wheel (and if needed each degree concretization), compute the set of pool configurations that block it. Deliverable: the coverage (incidence) structure + its measured size, and the analogous data at the cartwheel level. This determines whether P3 is a tractable MILP. Do not assume; measure — the concretization enumeration is the known exponential cliff.
- **P3 — set-cover minimization.** Fix x = x0 (published amounts). MILP: minimize |U'| s.t. every wheel that must be blocked (those not killed by charge, and whose survival would break the downstream lemmas) is blocked by some chosen config. Two variants: (strong) block everything the current proof blocks — guaranteed-valid, conservative; (exact) allow new survivors as long as gluing still passes — requires re-running gluing per candidate, use as a refinement loop. Acceptance gate: full pipeline green + our reducibility verification of U'.
- **P4 — lower bound.** LP-relaxation dual / MILP bound of P3's covering structure: the first lower bound on |U| for this schema. Cheap once P2 exists; publishable regardless of P3's outcome.
- **P5 — instrument optimization (later).** Co-optimize x (MILP with the per-spoke max linearized via binaries), then column generation over new rule shapes; each improvement feeds back into P3.

## Resource realities

- Coverage computation cost is the unknown; the C++ `blocked_by_reducible_configuration` is the hot path. If Python is too slow, instrument or wrap the C++ (it already computes block verdicts during enum_wheels; extending it to *record which config* blocked is a small patch).
- MILP scale estimate: ≤ 16,148 wheels (likely fewer constraints after charge-killed ones drop) × 8,200 config-columns — well within HiGHS territory if the incidence structure is sparse. Measure first (P2).
- All heavy runs: background, checkpointed, committed with checksums, failures preserved.
