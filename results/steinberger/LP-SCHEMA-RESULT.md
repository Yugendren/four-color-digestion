# S1 / LP schema-robustness: the ring≤14 failure is a property of the rule SHAPES, not of the published amounts

**Date:** 2026-08-23 · **Verdict:** ring≤14 pool → **INFEASIBLE**, certified · full pool (control) → **FEASIBLE**

## 0. The claim, stated exactly

> Fix the 84 discharging rule *shapes* of the 2026 near-linear-4CT proof
> (`third_party/discharging-rules/R`). Let `P14` be the sub-pool of the published
> 8,200-configuration D-reducible pool consisting of the 5,895 configurations of ring
> size ≤ 14 (`build/steinberger-pool-r14/D`). Then **there is no vector of nonnegative
> rule amounts `x ∈ R^84_{≥0}` under which the discharging argument closes over `P14`**
> — i.e. under which every vertex of the (hypothetical) minimum counterexample ends with
> charge ≤ 0. Certified by a **12-row irreducible Farkas certificate**, verified over
> exact rationals by a solver-free checker, with **every one of the 12 rows separately
> audited to be necessary for the underlying mathematics** and not merely for the
> released verification code (§5).
>
> Equivalently: S1's failure at ring ≤ 14 is **not** an artifact of the published
> amounts `x0`. Re-tuning the amounts of these 84 shapes cannot rescue it.

Contrast: the **same** machinery over the full 8,200-configuration pool is FEASIBLE, and
`x0` itself satisfies every generated constraint with zero violations. So the encoding is
not vacuously infeasible; it distinguishes the two pools, which is the whole point.

Scope limits are in §8. Read them; the headline is meaningless without them. The two
load-bearing hypotheses are `x ≥ 0` and the reconstruction of the paper's hand-checked
degree-5/6 discharge (§4).

## 1. What the pipeline actually requires (and what it does not)

The naive reading — "the discharging must kill every wheel" — is **wrong**, and encoding
it produces a false result (see §6). The 2026 schema *permits survivors*: the three
gluing lemmas (A.4/A.5/A.6) mop them up. The precise invariant the released C++ enforces
is in `third_party/computer-checks/src/cartwheel.cpp::enum_bad_cartwheels`, applied to
every **fully refined cartwheel** `L` that survives `fix_in_rules` + `fix_out_rules`:

```cpp
int C = cartwheel.upper_bound_of_charge(combined_rule_with_spokes, rules, combined_rules);
assert(C == 0);
assert(d == 7 || d == 8);
assert(darts_by_deg[7].size() + darts_by_deg[8].size() + darts_by_deg[9].size() > 0);
```

S1's failure was exactly these firing: 833 of 16,157 per-wheel jobs aborted — 530 at d=7
and 250 at d=8 on `C == 0` (kind `C_positive`), 51 at d=9 and 2 at d=10 on
`d == 7 || d == 8` (kind `degree_range`). See `results/p3/runs/steinberger-s1/failures.json`.

The condition encoded here, for each such leaf `L`:

| case | requirement | why |
|---|---|---|
| `d(L) ∈ {9,10,11}` | `C(L,x) < 0` | `L` must be pruned before the degree assert |
| `d(L) ∈ {7,8}`, no spoke of degree ≥ 7 | `C(L,x) < 0` | `L` must be pruned before the spoke assert |
| `d(L) ∈ {7,8}`, some spoke ≥ 7 | `C(L,x) ≤ 0` | `C = 0` survives to the gluing lemmas; `C < 0` is pruned in `prune` |

Note `C == 0` is *not* imposed — only `C ≤ 0`. If `C < 0`, `CartWheel::prune` removes `L`
before the assert is ever reached. `C ≤ 0` is therefore the exact necessary-and-sufficient
charge condition at a leaf, and it is *weaker* than what the C++ observes at `x0`.

**Not encoded (deliberately):** the three gluing lemmas. Their satisfaction is an
*additional* necessary condition, so omitting them makes our system a relaxation — which
only strengthens an INFEASIBLE verdict.

## 2. Leaf charge is affine in `x` — no max, no binaries

`upper_bound_of_charge` (`cartwheel.cpp:308`) is

```
initial_charge - out_charge_sum + in_charge_sum,        initial_charge = 10*(6-d)
```

where `in_charge_sum` sums `combined_rule_with_spokes[j].amount` for the *already fixed*
spokes and `amount_of_possible_charge_send` (a per-spoke **max** over non-excluded
combined rules) for the rest. At a leaf all `d` spokes are fixed, so **the max never
runs**. Moreover `prune_by_non_associated_rule` plus its companion assert
(`cartwheel.cpp:291-299`) force, for any survivor,

```
combined_rule_with_spokes[j].combined_flag[k] == 1   ⟺   always_apply(center_darts[j], rules[k])
```

so the spoke combined rules are *determined by the leaf graph*. Hence

```
C(L, x) = 10*(6 - d)  +  Σ_k (IN_k − OUT_k) · x_k
IN_k  = #{ j : always_apply(center_darts[j], rule_k) }          (darts pointing INTO the hub)
OUT_k = #{ i : always_apply(rev(center_darts[i]), rule_k) }     (darts pointing OUT of the hub)
```

purely affine, integer coefficients, no epigraph variables needed.

**Differential validation of this formula (`tools/lp_discharge.py --validate`):** all
**10,094** published full-pool bad cartwheels in
`third_party/computer-checks/wheels/zero` evaluate to **exactly 0** at `x0`, and all
10,094 satisfy `d ∈ {7,8}` (9,366 at d=7, 728 at d=8) with a spoke of degree ≥ 7 — i.e.
the Python form independently reproduces all three C++ asserts on the published output.
0 discrepancies.

## 3. Why a leaf observed at `x0` constrains *every* `x` (the monotonicity lemma)

The refinement forest is explored *with pruning*, so the leaf set we observe depends on
`x0`. The rows are nevertheless valid for all `x ≥ 0`:

- **(a)** `update_degree_by_rule`, `concrete_degree_except_tail`, `refine_always`,
  `refine_never` only ever *narrow degree intervals*; rotations never change. The
  branching is `x`-independent. It is **not** pool-independent — `fix_in_rules` branches
  over the pool-dependent *non-blocked* combined-rule set — but it moves the right way: a
  smaller pool blocks fewer combined rules, so `combined_rules(P_full) ⊆ combined_rules(P14)`
  (measured: 671 vs 681 files, the 671 content-identical members of the 681). Every branch
  available under the full pool remains available under `P14`, so the full-pool forest is
  a sub-forest of the `P14` forest. *(An earlier draft asserted flat pool-independence
  here; that was wrong and was caught by the adversarial pass — the corrected statement is
  what the argument needs, and it holds.)*
- **(b)** `blocked_by_reducible_configuration` is `x`-independent and monotone in the
  pool (unblocked under `P0` ⟹ unblocked under any `P ⊆ P0`);
  `prune_by_non_associated_rule` is both `x`- and pool-independent. So no ancestor of `L`
  is removed by those two tests under the changed inputs.
- **(c)** `upper_bound_of_charge` is **non-increasing along refinement whenever `x ≥ 0`**:
  narrowing degrees can only *add* `always_apply` matches (out-charge up — this is the
  step that needs `x ≥ 0`), can only *remove* candidates surviving `never_apply` (the
  per-spoke max down), and fixing a spoke's combined rule replaces the max by one of its
  own members.
- **(d)** Therefore, for any `x ≥ 0`: either every ancestor survives charge pruning, the
  search reaches `L`, and the assert demands `C(L,x) ≤ 0`; **or** some ancestor `A` has
  `C(A,x) < 0`, and then `C(L,x) ≤ C(A,x) < 0` by (c). Either way `C(L,x) ≤ 0`.

The same argument covers the strict rows.

**Corollary used below:** since `P14 ⊆ P_full` (verified: 0 of the 5,895 names are absent
from the 8,200, and both are symlinks to the same files), **every full-pool leaf row is
also a valid row for the ring≤14 problem.** That is what lets the certificate mix
full-pool rows with ring≤14-only rows.

Consequence of all this: the LP built from *any* observed leaf set is a **relaxation** of
the true feasible set. **INFEASIBLE is a proof; FEASIBLE is not** (it only means these
rows do not suffice).

## 4. The d ≤ 6 half — without it the LP is vacuous

The released code only enumerates hubs of degree 7–11, where the initial charge
`10*(6−d)` is already negative. Taken alone, the leaf rows of §2 are satisfied by
`x = 0` — send nothing, and every hub keeps its negative initial charge. **An LP over the
d ≥ 7 rows alone decides nothing**, and we measured exactly that (§5, `nolow` rows).

The lower bounds on `x` come from the other half of the discharging argument, which the
released code never checks because the paper does it by hand: discharging preserves total
charge (`= 120` by Euler), so the argument needs *every* vertex to end with charge ≤ 0; a
degree-5 vertex starts at `+10` and must give it all away, a degree-6 vertex starts at `0`
and must not end positive.

For `d ∈ {5,6}` we add rows built from a **lower** bound on the hub's final charge, valid
for any `x ≥ 0` and at any level of refinement:

```
LB(w, x) = 10*(6−d) − Σ_i POSS_i(x) + Σ_j ALW_j(x)
POSS_i = Σ x_k over base rules k that are NOT never_apply out of spoke i   (over-count of sends)
ALW_j  = Σ x_k over base rules k that always_apply into the hub from spoke j (under-count of receipts)
```

`always_apply` implies the rule genuinely fires and `never_apply` implies it genuinely
cannot, in *any* graph extending the wheel (both tests are sound irrespective of whether
the rule's pattern fits inside the wheel's 2-neighbourhood), so `LB ≤ actual final
charge`, and `actual ≤ 0` forces `LB(w,x) ≤ 0`. Rows are generated over every spoke-degree
necklace in `{5,…,9}^d` up to rotation that the pool does not block. Refining the wheels
further would only strengthen the rows, so the coarsest wheels are the conservative choice.

**Sanity anchor:** at `x0`, the maximum of `LB` over all 580 unblocked d=5 and 2,466
unblocked d=6 wheels is **exactly 0** — never positive. It is attained e.g. at d=5 with
all five spokes of degree 9, where the row is literally `10 − 5·x_rule001 ≤ 0` (and
`x0_rule001 = 2`). So `x0` sits simultaneously on the boundary of the low-degree rows
*and* of all 3,425 distinct full-pool leaf rows. That is the signature of a tightly
optimised discharging scheme, and it is a strong consistency check on this reconstruction:
had we got the d ≤ 6 side wrong in the loose direction, `x0` would have violated it.

This is the single most interpretive part of the whole construction; see §7.3.

## 5. Code-necessary vs math-necessary — the sharpest objection, and its repair

This is the objection that nearly killed the result, so it gets its own section.

`upper_bound_of_charge` counts only `always_apply` rules outward, and `fix_out_rules`
stops refining once no rule is `dominantly_apply`-but-not-`always_apply`. But
`dominantly_apply` is **strictly stronger** than `has_intersection`
(`pseudo_configuration.cpp:417-423`: it additionally demands the rule's degree interval
be unbounded above, or the cartwheel vertex's be bounded). So a leaf can retain rules that
are **neither `always_apply` nor `never_apply`** on an out-dart — rules that might fire in
some realization but are not counted in `out_charge_sum`. **Measured: 11 of 5,292
(rule, out-dart) pairs across the IIS leaves are undetermined.** For those leaves `C`
*strictly over-estimates* the hub's true final charge, so `C(L,x) ≤ 0` would be a
condition of the released *verification procedure* rather than of the argument itself.

Two blunt diagnostics confirm this is not hypothetical — **both make the ring≤14 LP
FEASIBLE**:

| diagnostic | rows | ring≤14 verdict |
|---|---|---|
| `--exact-only` (drop every row with an undetermined out-pair; 80,063 of 97,860 leaves survive) | 42,121 | **FEASIBLE** |
| `--conservative` (keep all rows but over-count the OUT side, `leaf_row_conservative`) | 52,400 | **FEASIBLE** |

So the naive reading — "the certificate proves the mathematics is impossible" — is **not**
supported by those two row sets. Both, however, are needlessly lossy: one throws rows
away, the other weakens rows that did not need weakening.

**The repair (`row_is_math_necessary`, `--audit-necessity`).** Pass to the
**tail-maximised** leaf: narrow every open tail `[a,9]` (a < 9) to `[9,9]`. Since `9`
means "9 or more" in the cartwheel abstraction, this simply restricts attention to the
sub-family of realizations in which every unpinned second-neighbour has large degree. If
the tail-maximised leaf

1. has a **fully determined OUT side** (every rule `always_apply` or `never_apply` on
   every out-dart), and
2. yields the **identical row** (same coefficients, same constant, same strictness), and
3. is **still unblocked** by the pool,

then in those realizations `OUT` is exact while `IN` can only *exceed* the branch's flag
sum, so `true final charge ≥ C(L,x)`. The argument's requirement `true final charge ≤ 0`
then forces `C(L,x) ≤ 0`. Undetermined *IN* rules are harmless precisely because they push
the true charge **up**, in the direction that makes the row easier to justify.

**Result of the audit: all 12 IIS rows pass.** The 9 degree-7 rows satisfy (1)-(3)
individually — including the 5 whose original leaves had undetermined out-pairs, all of
which become exact under tail-maximisation with the row unchanged and still unblocked —
and the 3 degree-5 rows are mathematically necessary by construction (they are already in
lower-bound form: over-count OUT, under-count IN). Machine-readable in
`results/steinberger/iis_math_necessity.json` (`all_mathematically_necessary: true`).

Hence the certified infeasibility is a statement about the discharging argument, not only
about the released code. What remains scoped to the released code is nothing in the
12-row certificate; the wider 48,509-row system does contain code-only rows, which is why
we report the audited IIS as the actual proof object.

## 6. Results

Rows are deduplicated by `(coeffs, constant, strict)`. Reproduce with
`.venv/bin/python tools/lp_discharge.py --all` (~14 min, ~2 GB peak).

| variant | rows | strict rows | `x0` violations | status |
|---|---|---|---|---|
| **control**, full pool, integral, with d≤6 | 3,511 | 0 | **0** | **FEASIBLE** |
| control, full pool, real, with d≤6 | 3,511 | 0 | 0 | FEASIBLE |
| control, full pool, integral, *no* d≤6 | 3,425 | 0 | 0 | FEASIBLE (vacuous) |
| control, full pool, real, *no* d≤6 | 3,425 | 0 | 0 | FEASIBLE (vacuous) |
| **main**, ring≤14, integral, with d≤6 | 48,509 | 96 | 9,647 | **INFEASIBLE** (cert. `yᵀb = −30`, 19 rows) |
| **main**, ring≤14, real, with d≤6 | 48,509 | 96 | 9,551 | **INFEASIBLE** (cert. `yᵀb = −30`, 19 rows) |
| main, ring≤14, integral, *no* d≤6 | 48,423 | 96 | 9,647 | FEASIBLE (vacuous — `x = 0`) |
| main, ring≤14, real, *no* d≤6 | 48,423 | 96 | 9,551 | FEASIBLE (vacuous — `x = 0`) |
| control, `--exact-only` (§5 diagnostic) | 2,620 | 0 | 0 | FEASIBLE |
| main, `--exact-only` (§5 diagnostic) | 42,121 | 96 | 8,699 | FEASIBLE — *rows dropped, too lossy* |
| control, `--conservative` (§5 diagnostic) | 4,321 | 0 | 0 | FEASIBLE |
| main, `--conservative` (§5 diagnostic) | 52,400 | 96 | 8,741 | FEASIBLE — *rows weakened, too lossy* |

The last four rows are the §5 diagnostics. They are why the headline is carried by the
**audited 12-row IIS** rather than by the raw 48,509-row verdict: those two blunt
relaxations lose the contradiction, while the targeted tail-maximisation audit shows the
IIS survives intact. Note also that `x0` still violates **8,741 rows even in the fully
conservative (mathematically necessary) system**, with `LBC(x0)` up to +3 — i.e. at `x0`
the ring≤14 argument fails not merely as a verification artifact but genuinely, at
thousands of degree-7/8 hubs that really do retain positive charge.

Leaf inputs for the main run: 97,860 fully-refined cartwheels → 48,423 distinct rows.
Composition: 10,094 published full-pool leaves; 10,581 leaves from the 15,324 S1 per-wheel
jobs that completed; 77,185 leaves recovered from the 833 jobs that aborted on an assert,
by re-running them with an NDEBUG (Release) build so the asserts are compiled out
(`tools/lp_rerun_failed_wheels.sh`, 833/833 succeeded, 21 min wall, 8-way parallel).
Rows by hub degree: d=7 40,257 · d=8 8,070 · d=9 93 · d=10 3 · d=5 26 · d=6 60 (the 3,046
low-degree wheels collapse to only 86 distinct rows). The 93 d=9 and 3 d=10 rows are
exactly the strict rows corresponding to S1's 51+2 `degree_range` failures.

**Positive control passed on both required counts:** the full-pool LP is FEASIBLE, and
`x0` satisfies **every one of the 3,511** generated rows numerically (0 violations). The
control was also run *without* the d≤6 rows to demonstrate that the trivially-feasible
regime exists and is not what we are reporting.

### The certificate

`results/steinberger/lp_main_certificate.json` — 19 rows out of 48,509, all with
**non-strict** right-hand sides, so **the result does not depend on integrality of the
amounts**: the same certificate proves infeasibility over the reals.

| yᵢ | d | spoke degrees | rhs | C(x0) | source | origin |
|---|---|---|---|---|---|---|
| 19 | 7 | 5,5,8,5,6,5,7 | 10 | 0 | d7_1155_1.cartwheel | full ∩ r14 |
| 21 | 7 | 5,5,5,8,5,5,7 | 10 | 0 | d7_166_0.cartwheel | full ∩ r14 |
| 17 | 7 | 5,5,5,8,5,5,7 | 10 | 0 | d7_166_1.cartwheel | full ∩ r14 |
| 14 | 7 | 5,6,5,6,7,5,8 | 10 | 0 | d7_1782_2.cartwheel | full ∩ r14 |
| 12 | 7 | 5,6,5,8,5,7,6 | 10 | 0 | d7_1932_3.cartwheel | full ∩ r14 |
| 4 | 7 | 5,5,7,5,5,7,7 | 10 | 0 | d7_710_10.cartwheel | full ∩ r14 |
| 4 | 7 | 5,5,7,5,5,7,7 | 10 | 0 | d7_710_14.cartwheel | full ∩ r14 |
| 21 | 7 | 5,5,7,5,6,5,8 | 10 | 0 | d7_722_3.cartwheel | full ∩ r14 |
| 9 | 7 | 5,5,7,5,7,5,7 | 10 | 0 | d7_740_16.cartwheel | full ∩ r14 |
| 8 | 7 | 5,5,7,5,7,5,7 | 10 | 0 | d7_740_18.cartwheel | full ∩ r14 |
| 13 | 7 | 5,5,7,5,7,5,7 | 10 | 0 | d7_740_19.cartwheel | full ∩ r14 |
| 20 | 7 | 5,7,5,7,6,7,7 | 10 | **2** | d7_3358_2133.cartwheel | **ring≤14 only** |
| 6 | 7 | 5,7,5,7,6,7,7 | 10 | **2** | d7_3358_2134.cartwheel | **ring≤14 only** |
| 30 | 7 | 5,7,5,7,7,6,7 | 10 | **2** | d7_3372_1881.cartwheel | **ring≤14 only** |
| 4 | 7 | 5,7,5,7,7,7,7 | 10 | **3** | d7_3376_1132.cartwheel | **ring≤14 only** |
| 2 | 5 | 5,5,6,7,7 | −10 | −3 | d5-55677 | low-degree row |
| 43 | 5 | 5,5,7,6,7 | −10 | −2 | d5-55767 | low-degree row |
| 75 | 5 | 5,7,5,7,7 | −10 | 0 | d5-57577 | low-degree row |
| 85 | 5 | 5,7,6,7,7 | −10 | 0 | d5-57677 | low-degree row |

Exact totals: `min_k (yᵀA)_k = 0` (need ≥ 0), `yᵀb = −30` (need < 0), all `yᵢ > 0`.

**Irreducible core (`lp_main_certificate_iis.json`, `--iis`).** The 19-row support is not
minimal. Greedy deletion filtering shrinks it to a **12-row irreducible infeasible
subsystem** — 9 degree-7 hub rows and 3 degree-5 rows — which is *irreducible* in the
strict sense: for each of the 12, deleting it alone restores feasibility (verified, all
12). Its certificate (`yᵀb = −20`, multipliers 75, 75, 25, 75, 55, 60, 15, 55, 25, 75,
168, 219) also passes `tools/verify_farkas.py`. All four ring≤14-only rows survive into
the IIS. This 12-row system is the smallest human-inspectable object carrying the whole
result.

**C++-side cross-confirmation of the certificate rows.** The four ring≤14-only rows come
from wheels `d7_3358`, `d7_3372`, `d7_3376` — and those are precisely three of the wheels
whose S1 job the *C++* aborted, with `Assertion failed: (C == 0), function
enum_bad_cartwheels, file cartwheel.cpp, line 417`
(`results/p3/runs/steinberger-s1/log/d7/enum_d7_3358.log`). The other eleven degree-7 rows
come from wheels whose jobs completed normally (so their leaves have `C = 0` under `x0`,
matching the `C(x0) = 0` column). The Python row semantics and the C++ asserts agree
wheel-by-wheel on the certificate's own support.

### What the 12-row IIS actually says

The irreducible core is **9 degree-7 hub rows + 3 degree-5 rows** — and *nothing else*.
Concretely:

- **No degree-8, degree-9 or degree-10 rows appear.** The contradiction does not need
  S1's 53 `degree_range` failures at all, nor any of its 250 degree-8 `C_positive`
  failures. This *sharpens* S1's empirical picture: S1 found the damage concentrated at
  hub degrees 7 and 8 (530 + 250 of 833 aborts), and the LP says the irreducible cause
  sits entirely at **hub degree 7**, colliding with the degree-5 discharge.
- **Every one of the 9 degree-7 hubs has a degree-5 spoke**, and the spoke necklaces are
  `5,5,8,5,6,5,7` · `5,5,5,8,5,5,7` · `5,5,7,5,5,7,7` · `5,5,7,5,6,5,8` · `5,5,7,5,7,5,7`
  · `5,7,5,7,6,7,7` (×2) · `5,7,5,7,7,6,7` · `5,7,5,7,7,7,7`. The three degree-5 rows are
  `5,5,7,6,7` · `5,7,5,7,7` · `5,7,6,7,7`. The whole contradiction lives in the
  degree-5/degree-7 interface.
- **Only 19 of the 84 rules carry a nonzero coefficient** anywhere in the 12 rows:
  rule001, rule002_{1,2}, rule003_{1,2}, rule004_{1,2}, rule008_{1,2}, rule009_{1,2},
  rule010_{1,2}, rule011_{1,2}, rule023_{1,2}, rule032_{1,2}. **65 of the 84 shapes are
  irrelevant to the obstruction** — re-tuning them cannot help.
- In the Farkas combination, **78 of the 84 rule columns cancel exactly** (`(yᵀA)_k = 0`);
  only 6 have slack (rule008_1: 10, rule010_2: 55, rule011_2: 25, rule023_1: 25,
  rule023_2: 5, rule032_2: 45). The near-total cancellation is why the contradiction is so
  tight: `yᵀb = −20` against a system whose every row is tight or nearly tight at `x0`.
- Read as arithmetic: the three degree-5 rows say *a degree-5 vertex must give away all
  10 units of its charge*, which forces the amounts on rule001/rule002/rule003/rule004 up;
  the nine degree-7 rows cap what a degree-7 hub with degree-5 neighbours may receive back.
  With the ring≤14 pool no longer blocking the four offending degree-7 cartwheels, those
  two demands cannot both be met by any nonnegative amounts.

**The infeasibility is genuinely caused by the ring≤14-only rows.** Delete the four
ring≤14-only rows from the 19-row support and the remaining 15 rows — every one of which
is also valid for the *full* pool — are FEASIBLE, and `x0` satisfies all 15. So the
contradiction is not lurking in the full-pool constraints; it is created by exactly the
cartwheels that the ring≤14 pool fails to block.

The structure is legible: **four degree-5 lower-bound rows** (a degree-5 vertex must
discharge all 10 units) pull the amounts *up*; **fifteen degree-7 hub rows** cap what a
degree-7 hub may receive and pull them *down*; the four ring≤14-only rows are precisely
the ones `x0` violates (by 2, 2, 2 and 3 units), and they are the additional pressure that
makes the system inconsistent. Eleven of the fifteen degree-7 rows are also valid for the
full pool — the certificate is *not* full-pool-derivable, as it must not be, since the
control is FEASIBLE.

### Independent verification (the actual deliverable)

`.venv/bin/python tools/verify_farkas.py` → **`FARKAS CERTIFICATE VERIFIED`**, exit 0.

The verifier is solver-free and uses `fractions.Fraction` throughout — no float on the
checking path. Critically, it does **not** trust the certificate's stored coefficients: it
re-derives every row from its source (`.cartwheel` files re-parsed and re-run through
`leaf_row`; low-degree tags rebuilt with `generate_cartwheel` and re-run through
`lowdeg_row`) and fails loudly on any mismatch. It then checks (a) `y ≥ 0`, (b) `y ≠ 0`,
(c) `(yᵀA)_k ≥ 0` for all 84 columns, (d) `yᵀb < 0`, prints the contradiction chain
`0 ≤ (yᵀA)x = yᵀ(Ax) ≤ yᵀb = −30 < 0`, and independently confirms that `x0` violates 4 of
the 19 support rows. Deliberate corruption of a single coefficient is rejected with an
exact claimed-vs-re-derived diff.

## 7. The strong ("kill every wheel") encoding, and why it is not used

The alternative encoding — *every stage-1 wheel the pool does not block must have
`upper_bound_of_charge < 0`* — is what a naive reading suggests and is what the
max-of-affine / cutting-plane machinery is for: `f_w(x) = 10(6−d) − ⟨out,x⟩ + Σ_i max(0,
max_c ⟨flag_c, x⟩)`, convex, so `max < 0` iff every selection is `< 0`, giving an
LP-representable feasible set with exponentially many rows to be generated on demand.

It is **not** a correct encoding of "the argument closes": survivors are permitted, and
indeed the published proof at `x0` leaves 5,439 + 6,790 + 3,285 + 626 + 8 = 16,148 stage-1
wheels alive on purpose. Imposing it would reject the published proof itself.

**We ran it anyway, as a negative control, and it fails exactly as predicted**
(`tools/lp_wheel_level.py --control`, 16,148 wheels, 10,778 rows incl. the 86 low-degree
rows, 93 s): the **full-pool** run is **INFEASIBLE at iteration 0** with a verified 10-row
certificate (`yᵀb = −175`; support = 3 degree-5, 2 degree-6 and 5 degree-7 rows). So the
strong condition cannot be met by *any* nonnegative amounts even with the complete
8,200-configuration pool — i.e. it would "disprove" the published theorem. **That is the
concrete demonstration that the strong encoding is the wrong one**, and the reason the
headline result uses the leaf-level encoding of §1–§2 instead. Reported as a measurement,
never as evidence for the headline claim.

Two traps this encoding shares with §4: the per-spoke max in
`amount_of_possible_charge_send` has an **implicit zero option** (`amount` is initialised
to 0) which `nl4ct.charge_bound_symbolic` omits from `in_choices` — measured to be
harmless here (0 of 128,306 spokes have an empty candidate list, and with `x ≥ 0` any
existing candidate already dominates the zero option), but the tool adds it
unconditionally to match the C++ semantics; and without the d≤6 rows it too is trivially
satisfied by `x = 0`.

(The ring≤14 wheel-level run is likewise INFEASIBLE in 1 iteration, `yᵀb = −380`, 10-row
support — but that verdict carries no weight given the control. A further caveat specific
to this tool: the on-disk wheel sets are themselves stage-1 survivors computed *at* `x0`,
so unlike the leaf-level result there is no monotonicity lemma making its rows valid for
every `x`.)

## 8. Scope — what this does and does not prove

1. **These 84 shapes only.** Nothing here rules out a *different* set of rule shapes,
   or extra shapes added to these 84. Deciding that requires column generation over rule
   patterns (generate a violated wheel/leaf, then price out new planar degree-interval
   patterns that would fix it) — **future work**, and much harder: the pricing problem is
   a search over planar patterns, not an LP.
2. **This pool only.** `P14` is exactly `{c ∈ published 8,200-config D pool : ring(c) ≤ 14}`.
   A ring≤14 unavoidable set built from *other* D-reducible configurations of ring ≤ 14
   (there are many not in the published pool) is **not** covered. This result therefore
   does not settle Steinberger's question; it settles it for this pool and these shapes.
3. **The d ≤ 6 rows are a reconstruction.** The released code does not check degree-5/6
   vertices — the paper does that by hand — so §4 is our reading of the argument's other
   half, not a port of released code. It is the load-bearing assumption: without those
   rows the LP is feasible (§5). Evidence that the reading is right: at `x0` the bound is
   ≤ 0 on all 3,046 unblocked low-degree wheels and tight (= 0) on several, exactly as an
   optimised scheme should be; and the specific tight row `10 − 5·x_rule001 ≤ 0` is
   forced by rule001's shape (degree-5 source, unconditional). Further evidence: running
   the *released C++* with `--enum_wheels -d 5` and `-d 6` returns exactly 580 and 2,466
   unblocked wheels, matching the Python generation used here wheel-for-wheel. Evidence
   that would break it: any reading under which a degree-5 vertex may end with positive
   charge, or under which its initial charge is not `+10`. **We were not able to obtain
   the paper text** (arXiv:2603.24880 §7–8) in this environment, so this reconstruction is
   checked only against the code and against `x0`'s behaviour. It is the single largest
   remaining risk, and it is load-bearing: 3 of the 12 IIS rows are degree-5 rows.
4. **Unblocked ≠ realizable.** Rows are generated for every local structure the pool does
   not block, exactly as the C++ decides which wheels to analyse. If some such structure
   is geometrically impossible in a minimum counterexample for a reason outside the pool,
   its row is spurious. This is anti-conservative for an INFEASIBLE verdict — but it is
   the same standard the published proof itself uses (the pool *is* the unavoidable set),
   so accepting the proof's framework means accepting these rows.
5. **`x ≥ 0` is a hypothesis, not a theorem.** It is used twice: in the monotonicity
   lemma (§3c) and in the low-degree bound (§4). Negative amounts — a rule that sends
   charge backwards along its dart — are outside the claim. Arguably a negative amount is
   a different rule shape rather than a different amount, but the honest statement carries
   the hypothesis.
6. **Integrality is not needed.** All 19 (and all 12 IIS) certificate rows are non-strict, and the `--real`
   variant is INFEASIBLE with the same certificate, so the claim holds over `R_{≥0}^84`.
7. **The relaxation direction is the safe one.** The row set omits the gluing lemmas and
   omits every leaf the `x0`-pruned search never reached. Both omissions make the encoded
   feasible set *larger* than the true one, so INFEASIBLE transfers. The corresponding
   cost is that the FEASIBLE control verdict is only a non-refutation, not a positive
   result about the full pool.
8. **`always_apply`/`never_apply`/blocking are taken as the realizability semantics**,
   exactly as the C++ does. Our Python port of them was previously differentially
   validated against the C++ on all 5,690,937 wheel candidates at hub degrees 7–11
   (`src/fourcolor/nl4ct.py` docstring), and is re-validated here on all 10,094 published
   leaves (§2).

## 9. Adversarial pass

The formulation was put through a reviewer prompted to **refute** it, defaulting to "the
encoding is wrong", across ten named attack lines (dart direction and index
correspondence; the monotonicity lemma; pool-subset direction; validity of the d≤6 lower
bound; sign conventions; `generate_cartwheel` at d=5,6; low-degree blocking; certificate
validity and its dependence on ring≤14-only rows; direct falsification search; solver
plumbing and row-index alignment). Outcome: **one real error found and fixed, one
genuine scope correction adopted, the rest survived.**

- **Found and fixed:** the pool-independence claim in the monotonicity lemma (§3a) was
  false — `fix_in_rules` branches over the pool-dependent non-blocked combined-rule set.
  The corrected statement (full-pool combined rules are a content-exact subset of the
  ring≤14 ones, 671 ⊂ 681, so the forest only grows) is what the argument needs and holds.
- **Adopted:** the code-necessary vs math-necessary distinction, which became §5 and
  motivated the tail-maximisation audit. Without that audit the claim would have had to be
  scoped to the released procedure.
- **Survived, with evidence:** dart directions and index correspondence are uniquely
  pinned by the 10,094 simultaneous equations `C(L,x0) = 0`; monotonicity held on 2,145
  parent/child pairs with `x ≥ 0` and failed on 8 of them when negative amounts were
  allowed (so `x ≥ 0` is exactly load-bearing, not decorative); no rule has a finite upper
  degree bound above 8, which voids the `[9,9]` "9-or-more" ambiguity; the released C++
  run with `--enum_wheels -d 5`/`-d 6` returns exactly the 580 and 2,466 unblocked wheels
  the Python generates; restricting the `ALW` in-contributions to rule001 alone still
  gives INFEASIBLE; relaxing `never_apply` at boundary darts still gives INFEASIBLE; six
  different solver configurations all report Infeasible; and a uniform slack of 0.082 on
  every right-hand side is the minimum needed to restore feasibility.
- **Ablations:** the degree-6 rows alone (with all leaf rows) are FEASIBLE; the degree-5
  rows alone are already INFEASIBLE. The obstruction is a degree-5 vs degree-7 collision,
  consistent with the IIS composition.

## 10. Artifacts

| path | what |
|---|---|
| `tools/lp_discharge.py` | formulation, row extraction, LP, certificate search (`--validate/--control/--main/--all/--real/--no-lowdeg`) |
| `tools/verify_farkas.py` | solver-free exact-rational certificate verifier with row re-derivation |
| `tools/lp_wheel_level.py` | the strong max-of-affine cutting-plane encoding (§6), measurement only |
| `tools/lp_rerun_failed_wheels.sh` | NDEBUG re-run of the 833 aborted S1 wheel jobs |
| `results/steinberger/lp_main_certificate.json` | the 19-row Farkas certificate |
| `results/steinberger/lp_{control,main}_stats.json` | per-run statistics |
| `results/steinberger/lp_variants_summary.json` | the 8-variant matrix of §5 |
| `results/steinberger/lowdeg_rows_{control,main}.json` | cached d≤6 rows |
| `results/p3/runs/steinberger-s1/work/wheels/zero_ndebug/` | 77,185 recovered leaves |
| `third_party/computer-checks/build-ndebug/` | Release/NDEBUG build (pristine `build/` untouched) |
| `results/steinberger/lp_main_certificate_iis.json` | the 12-row irreducible certificate (**the proof object**) |
| `results/steinberger/iis_math_necessity.json` | per-row mathematical-necessity audit (§5) |
| `results/steinberger/lp_{exact_only,conservative}.log` | the two §5 diagnostics |
| `results/steinberger/wheel_level_{control,main}_stats.json` | the strong-encoding negative control (§7) |
| `tests/test_lp_discharge.py`, `tests/test_verify_farkas.py` | fast tests (20 tests, 11 s) |

## 11. Reproduce

```bash
# 0. one-off: NDEBUG build + recover the leaves from the 833 aborted S1 wheel jobs (~21 min)
cmake -S third_party/computer-checks -B third_party/computer-checks/build-ndebug -DCMAKE_BUILD_TYPE=Release
cmake --build third_party/computer-checks/build-ndebug --target main -j 8
bash tools/lp_rerun_failed_wheels.sh

# 1. the linear form vs the C++ asserts on all 10,094 published leaves  (~13 s)
.venv/bin/python tools/lp_discharge.py --validate       # -> n_bad: 0

# 2. control + main + the 8-variant matrix                              (~14 min)
.venv/bin/python tools/lp_discharge.py --all

# 3. shrink to the irreducible certificate                              (~5 min)
.venv/bin/python tools/lp_discharge.py --iis

# 3b. audit every IIS row for MATHEMATICAL necessity, not just code necessity  (~2 min)
.venv/bin/python tools/lp_discharge.py --audit-necessity   # -> all_mathematically_necessary: true

# 3c. the two §5 diagnostics that motivate 3b (both FEASIBLE -- see §5/§6)
.venv/bin/python tools/lp_discharge.py --exact-only
.venv/bin/python tools/lp_discharge.py --conservative

# 4. INDEPENDENT verification (no solver, exact rationals, rows re-derived from source)
.venv/bin/python tools/verify_farkas.py                                          # 19-row
.venv/bin/python tools/verify_farkas.py --certificate results/steinberger/lp_main_certificate_iis.json

# 5. tests
.venv/bin/python -m unittest tests.test_lp_discharge tests.test_verify_farkas
```
