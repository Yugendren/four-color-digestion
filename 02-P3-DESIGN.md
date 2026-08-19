# P3 Design: Prune-and-Verify Configuration-Set Minimization
## 2026-08-20 — follows 01-PROBLEM-STATEMENT.md; informed by results/p2-coverage/report.md

## What P2 taught us (and the trap it exposed)

1. Wheel-level blocking is trivially concentrated (85/8,200 configs) — but that level is not where the proof's real work happens.
2. Cartwheel-level blocking implicates ≥7,422/8,200 configs as *first responders* across 2.25M events — but first-match logging cannot distinguish "necessary" from "first in file order among many matches." One-shot set cover on this data would be UNSOUND.
3. **The trap (caught before it bit):** the pool is load-bearing in TWO places, and P2 measured only one. Besides wheel/cartwheel blocking, configurations also block *rule combinations* (Lemma A.2: 1,161 of 1,832 combined rules are excluded because a config blocks their merged patch). Removing a config could revive blocked combos → more possible incoming charge → different (larger) bad-wheel sets → a broken or changed proof, even for configs that never appear in any wheel/cartwheel blocklog. Any deletion argument must account for BOTH roles.

## The method: batched prune-and-verify (attribution-free, always-sound)

The pipeline itself is the oracle. Every accepted iterate is, by construction, a complete verified proof instance with a smaller U.

```
current U := full pool (8,200)
repeat:
  1. rank configs by measured usage (combo-blocking events + wheel + cartwheel first-match counts)
  2. propose deletion batch B (start: configs with ZERO usage in ALL THREE roles)
  3. re-run pipeline with U \ B:
       combine_rules (Lemma A.2 blocking against U\B)
       enum_wheels d7..11 -> counts may change; that is allowed
       enum_cartwheels    -> survivors may change; allowed
       three gluing checks -> MUST pass (asserts live)
  4. pass -> accept U := U\B (a new, smaller, fully verified proof); commit artifacts
     fail -> bisect B (halve until the breaking configs are isolated); restore those, continue
until no batch of size >= threshold survives
```

Properties: sound at every step (no reliance on incomplete attribution); monotone progress; each accepted iterate is independently publishable ("a proof of 4CT with |U| configurations in the wheel-based schema"); bisection cost is logarithmic in batch size.

Cost model: one full pipeline re-run = combine (~minutes) + wheels (~1.5h wall, parallel) + cartwheels (~3-4h, parallel) + gluing (~15 min) ≈ **~5-6h per iterate** on this machine. Batching + bisection should reach a local minimum in 10-30 runs (days-scale, background). Optimization later: prune wheels/cartwheels re-runs to degrees actually affected.

## Immediate measurements needed BEFORE the first prune

- **M1 — combo-blocking attribution** (cheap: 1,832 combos): which configs block which combined rules. Without this, role (iii) usage is unknown and even "zero-usage" deletion is unsafe. Deliverable: results/p3/combo_blockers.jsonl + usage table merge.
- **M2 — usage ranking table**: per config, (combo-block count, wheel-block count, cartwheel first-match count). The zero-row set is deletion batch #1; the long tail (usage 1-10) forms subsequent batches.

## Endgame layers (after the greedy floor is reached)

- Exact-necessity certificates: for the final small U, test each remaining config by single deletion (|U| pipeline runs, parallelizable) → a minimality certificate w.r.t. single deletions.
- P4 lower bound: with full attribution on the FINAL small instance (cheap at that size), the covering LP dual gives the schema-relative lower bound.
- P5: co-optimize rule amounts x between prune rounds (charge changes shift which wheels need blocking at all).

## Acceptance gates (unchanged from the problem statement)

Every accepted U': full pipeline green with asserts live + our independent reducibility verification (fourcolor.reduce) of every member + committed transcripts with checksums. Claims schema-qualified per 01-PROBLEM-STATEMENT.md.
