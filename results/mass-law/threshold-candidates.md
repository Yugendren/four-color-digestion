# Threshold-form mining: the exact D-reducible coloring-mass frontier and the tightest surviving closed forms

**2026-08-23.** Target of the exercise: pin the precise statement that the (T) half of the
Coloring-Mass Law (03-MASS-LAW-PROGRAM.md) should be proved in. The naive form
`d_reducible => a >= 94*2.4**(r-8)` is **KILLED** (43 counterexamples). This file replaces it
with the exact frontier, the tightest closed forms that survive the whole corpus, and what each
implies for f(r).

Corpus: all **59,142** canonically-deduped labeled configurations, rings 6–16, signature
`a2b1feba331bf2962b2b`; **13,169** of them D-reducible. Every claim below carries a receipt in
`lemma_log.jsonl` (75 receipts as of this writing). Reproduce any line with
`.venv/bin/python tools/test_lemma.py --check "<statement>"`.

**HOLDS means "survived the corpus", not proven.** The stress-test lesson
(`results/theorem/stress_test.md`, 236 oracle-confirmed false positives from a pool-zero-FP rule
set) applies in full. Rings 11–16 contain *no adversarially generated* D-reducibles at all — see
§5.

---

## 1. The exact frontier

`min a` = the smallest `a = |Φ(K)|` over all D-reducible configurations of ring size r in the
corpus. `k*` = the interior count of the witness. `#tied` = how many configurations attain the
minimum. `ratio` = min a(r) / min a(r-1).

| r | #D-red | min a | ratio | k* | witness (ident, source) | #tied | 2nd smallest a | a/2.4^r | gen-only min a | #non-red at r |
|---|---|---|---|---|---|---|---|---|---|---|
| 6 | 28 | **16** | -- | 4 | `0.7322` (rsst633) | 1 | 19 | 0.08372 | 19 | 2 |
| 7 | 37 | **39** | 2.438 | 4 | `2.122` (rsst633) | 3 | 43 | 0.08503 | 39 | 6 |
| 8 | 1435 | **94** | 2.410 | 5 | `gen-r8-n13-1494` (generated) | 1 | 95 | 0.08540 | 94 | 302 |
| 9 | 2168 | **211** | 2.245 | 5 | `2.7566` (rsst633) | 1 | 228 | 0.07987 | 228 | 812 |
| 10 | 1891 | **496** | 2.351 | 6 | `122.140` (rsst633) | 1 | 516 | 0.07823 | 516 | 2367 |
| 11 | 209 | **1252** | 2.524 | 7 | `122.1028` (rsst633) | 1 | 1262 | 0.08228 | -- | 1665 |
| 12 | 767 | **2863** | 2.287 | 7 | `126.453966` (rsst633) | 1 | 3127 | 0.07839 | -- | 4174 |
| 13 | 1961 | **6954** | 2.429 | 8 | `126.504366` (rsst633) | 1 | 6977 | 0.07934 | -- | 36534 |
| 14 | 2654 | **17440** | 2.508 | 9 | `2039` (steinberger2822) | 1 | 17538 | 0.08291 | -- | 111 |
| 15 | 1562 | **42957** | 2.463 | 10 | `2420` (steinberger2822) | 1 | 43055 | 0.08509 | -- | 0 |
| 16 | 457 | **100454** | 2.338 | 10 | `D3848` (nl4ct_pool) | 1 | 104783 | 0.08291 | -- | 0 |

### 1.1 The extremal-witness pattern (the single most useful structural fact found)

**At every one of the eleven rings, the minimum-`a` witness sits at the minimum possible interior
count.** `k*` reads 4, 4, 5, 5, 6, 7, 7, 8, 9, 10, 10 for r = 6…16. On rings 8–13 that is
*exactly* the f(r) table `5, 5, 6, 7, 7, 8` proven in `results/theorem/fr_table/THEOREM.md`.

So the coloring-mass frontier and the interior-count frontier are attained by the **same
configurations**. The mass law is not an independent phenomenon layered on top of the f(r)
theorem — the minimal-mass configuration *is* the minimal-interior configuration. Any proof of
(T) should be able to see this; conversely, a proof of (T) plus a cap immediately reproves f(r)
(§4).

The witnesses themselves are RSST catalog entries at 7 of 11 rings, with a legible progression in
the RSST numbering: `122.140` (r=10) → `122.1028` (r=11) → `126.453966` (r=12) →
`126.504366` (r=13). r=8's witness is machine-generated (`gen-r8-n13-1494`), r=14/15 are
Steinberger's, r=16 is from the nl4ct pool. These are the configurations to hand a human prover.

### 1.2 The residual is flat — the law is a *pure* exponential

`min a(r) / 2.4^r` over eleven rings: 0.08372, 0.08503, 0.08540, 0.07987, 0.07823, 0.08228,
0.07839, 0.07934, 0.08291, 0.08509, 0.08291.

Min 0.07823, max 0.08540, **spread 1.0916** — across a range in which `2.4^r` itself grows by a
factor 6,340. Sweeping the base in steps of 0.005 over [2.30, 2.50], the spread-minimizing base is
**β = 2.400 exactly**, both over rings 6–16 and over rings 8–16. There is no detectable polynomial
correction: the residual is non-monotone and bounces inside a ±4.4% band. This is strong evidence
that the true law is `A(r) = c·β^r` with a single constant, not `c·β^r·poly(r)`.

### 1.3 The 2D frontier `min a(r,k)`

Bold = min a in the cell, subscript = number of D-reducible configurations in the cell.

| r\k | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **6** | **16**<br><sub>1</sub> | **19**<br><sub>1</sub> | **20**<br><sub>3</sub> | **19**<br><sub>6</sub> | **21**<br><sub>17</sub> | . | . | . | . | . | . | . | . |
| **7** | **39**<br><sub>1</sub> | **39**<br><sub>4</sub> | **44**<br><sub>10</sub> | **47**<br><sub>22</sub> | . | . | . | . | . | . | . | . | . |
| **8** | . | **94**<br><sub>7</sub> | **95**<br><sub>33</sub> | **105**<br><sub>82</sub> | **111**<br><sub>224</sub> | **109**<br><sub>640</sub> | **121**<br><sub>449</sub> | . | . | . | . | . | . |
| **9** | . | **211**<br><sub>1</sub> | **231**<br><sub>52</sub> | **228**<br><sub>233</sub> | **248**<br><sub>705</sub> | **260**<br><sub>1177</sub> | . | . | . | . | . | . | . |
| **10** | . | . | **496**<br><sub>10</sub> | **550**<br><sub>375</sub> | **570**<br><sub>1504</sub> | **712**<br><sub>2</sub> | . | . | . | . | . | . | . |
| **11** | . | . | . | **1252**<br><sub>22</sub> | **1383**<br><sub>130</sub> | **1606**<br><sub>51</sub> | **1816**<br><sub>6</sub> | . | . | . | . | . | . |
| **12** | . | . | . | **2863**<br><sub>1</sub> | **3127**<br><sub>142</sub> | **3433**<br><sub>408</sub> | **3803**<br><sub>186</sub> | **4548**<br><sub>30</sub> | . | . | . | . | . |
| **13** | . | . | . | . | **6954**<br><sub>4</sub> | **7714**<br><sub>564</sub> | **8614**<br><sub>888</sub> | **9689**<br><sub>428</sub> | **11217**<br><sub>73</sub> | **13304**<br><sub>4</sub> | . | . | . |
| **14** | . | . | . | . | . | **17440**<br><sub>36</sub> | **18941**<br><sub>933</sub> | **21645**<br><sub>1087</sub> | **24138**<br><sub>500</sub> | **28476**<br><sub>92</sub> | **33018**<br><sub>6</sub> | . | . |
| **15** | . | . | . | . | . | . | **42957**<br><sub>117</sub> | **48749**<br><sub>625</sub> | **54862**<br><sub>547</sub> | **62987**<br><sub>213</sub> | **75893**<br><sub>53</sub> | **91599**<br><sub>7</sub> | . |
| **16** | . | . | . | . | . | . | **100454**<br><sub>1</sub> | **104783**<br><sub>105</sub> | **121126**<br><sub>185</sub> | **139284**<br><sub>111</sub> | **173918**<br><sub>41</sub> | **211458**<br><sub>13</sub> | **273101**<br><sub>1</sub> |

Reading:

* **No D-reducible configuration anywhere in the corpus has k ≤ 3** (`d_reducible => k >= 4`
  HOLDS, support 13,169) and none has `a < 16` (`d_reducible => a >= 16` HOLDS).
* `min a(r,k)` is increasing in k at every ring **except two small inversions**:
  `min a(6,7) = 19 < min a(6,6) = 20` and `min a(8,9) = 109 < min a(8,8) = 111`. So "increasing in
  k" is *not* literally true and a form assuming strict k-monotonicity has to absorb ~2%.
* The k-growth rate is far slower than the r-growth rate: at r=13 the cell minima grow by factors
  1.109, 1.117, 1.125, 1.158, 1.186 per interior vertex — γ ≈ 1.10–1.19, versus β ≈ 2.4 per ring
  unit. **The threshold is overwhelmingly a function of r; k contributes a weak second-order
  factor.** That asymmetry is what limits family (d) (§2d).
* Several frontier cells are supported by a **single configuration**: (9,5), (12,7), (16,10),
  (6,4), (7,4). Cells (13,8) and (13,13) hold 4 each. The extremum is not an isolated outlier at
  most rings (min/2nd-smallest is 0.99–1.00 at r = 8, 11, 13, 14, 15) but *is* isolated at
  r = 6 (16 vs 19), r = 9 (211 vs 228) and r = 12 (2863 vs 3127).

---

## 2. The families swept

Because a pure-r form survives iff `T(r) <= min a(r)` at every ring, and an (r,k) form survives iff
`T(r,k) <= min a(r,k)` at every occupied cell, the survival question is *fully determined* by the
tables in §1. The grids below were fitted against those tables; every reported winner and every
reported near-miss was then re-run through `tools/test_lemma.py` and logged.

### (a) Pure exponential `a >= c·β^r`

Largest surviving `c` for each β (rings 6–16):

| β | largest surviving c | binding ring | max margin | implied-f slope (proven cap) |
|---|---|---|---|---|
| 2.20 | 0.141118 = 16/2.2^6 | 6 | 2.364 | 0.144 |
| 2.30 | 0.108082 = 16/2.3^6 | 6 | 1.516 | 0.198 |
| 2.35 | 0.094998 = 16/2.35^6 | 6 | 1.228 | 0.235 |
| **2.40** | **0.0782293 = 496/2.4^10** | **10** | **1.092** | **0.262** |
| 2.45 | 0.059609 = 100454/2.45^16 | 16 | 1.241 | 0.289 |
| 2.50 | 0.043145 = 100454/2.5^16 | 16 | 1.519 | 0.317 |
| 2.60 | 0.023035 = 100454/2.6^16 | 16 | 2.248 | 0.382 |

β = 2.4 is the unique base at which the form is tight *everywhere at once* rather than propped up
by one endpoint ring. Below 2.4 the r=6 endpoint binds and the fit is slack at high r; above 2.4
the r=16 endpoint binds and the fit is slack at low r — and since rings 15–16 have **zero**
adversarial negatives (§5), a β > 2.4 fit is supported only by the least-trustworthy end of the
corpus. **β = 2.4 is where the data actually is.**

The exact tightest constant is `c = 496/2.4^10 = 0.078229267…`, i.e. `1/c = 12.78294`. The
bracket is sharp and machine-confirmed:

* `a >= 2.4**r / 12.79` — **HOLDS** (0 counterexamples of 13,169)
* `a >= 2.4**r / 12.78` — **KILLED**
* `a >= 2.4**r / 12` — **KILLED**, 15 counterexamples
* `a >= 94 * 2.4**(r-8)` (the naive form, `c = 0.0854`) — **KILLED**, 43 counterexamples

### (b) Wheel-anchored, `W(r) = (2^r + 2)/6`

`W(r)` is the exact `a` of the r-wheel (the k=1 configuration): the corpus contains
`a = 43` at (r,k)=(8,1), `171` at (10,1), `683` at (12,1) — equal to W(8), W(10), W(12) on the nose.

| form | verdict | note |
|---|---|---|
| `a >= 0.377682 * W(r) * 1.25**(k-1)` | HOLDS | tight at (8,10), a=121 |
| `a >= 0.265354 * W(r) * 1.3**(k-1)` | HOLDS | tight at (8,10) |
| `a >= 0.188935 * W(r) * 1.35**(k-1)` | HOLDS | tight at (8,10) |
| `a >= W(r) * 1.3**(k-1)` (no constant) | KILLED | 13,169 counterexamples — every single one |
| `a >= W(r) * 8.727272 / r` | HOLDS | tight at r=6; max margin 16.9, wildly slack |
| `a >= W(r) * 1.2**r / 2.1347` | HOLDS | max margin 1.090 — this is family (a) rewritten |

**Family (b) is a corollary dead end, and for a clean reason.** Any threshold whose r-dependence is
`2^r` has *exactly* the same r-exponent as the proven cap `2^(r+k-3)`; the r's cancel and the
combination yields `f(r) >= 1`, a constant, for every λ. The only wheel-anchored form with any
corollary strength is the one carrying an extra `1.2^r` — which is just `c·2.4^r` in disguise.

**The general principle this exposes:** under a cap of the form `B(r,k) = C·2^r·γ^k`, the implied
f-slope is `(log₂β − 1)/(1 − log₂γ)`. The entire source of f-growth is the excess of the threshold
base β over **2**. A law with β ≤ 2 proves nothing about f. This is the cleanest structural
statement to come out of the sweep.

### (c) Universe fraction `a >= 3^(r-1)/2 / g(r)`

Required `g(r) = 3^(r-1)/2 / min a(r)`: 7.59, 9.35, 11.63, 15.55, 19.84, 23.58, 30.94, 38.21,
45.71, 55.67, 71.42 for r = 6…16.

This grows **geometrically at ratio ρ = 1.2512 ≈ 3/2.398**, not polynomially. A polynomial `g` can
therefore only track it over a finite window, and the fitted quadratic is already binding at the
last ring in the corpus:

| form | verdict | binding | max margin | first ring the extrapolated trend breaks it |
|---|---|---|---|---|
| `a >= 3**(r-1)/2 / (0.278986 * r**2)` | HOLDS | r=16 | 1.535 | **r = 17** |
| `a >= 3**(r-1)/2 / (0.035157 * r**3)` | HOLDS | r=6 | 2.131 | r = 26 |
| `a >= 3**(r-1)/2 / (0.00586 * r**4)` | HOLDS | r=6 | 5.377 | r = 40 |
| `a >= 3**(r-1)/2 / (6 * r)` | HOLDS | — | very slack | (never; far too weak) |
| `a >= 3**(r-1)/2 / (0.25 * r**2)` | KILLED | — | — | 17 counterexamples |
| `a >= 3**(r-1)/2 / (2.1305 * 1.25**r)` | HOLDS | r=10 | 1.092 | (= family (a)) |

Family (c) is the **strongest** family for the corollary (§4) and the **least credible**: the
quadratic version survives the corpus with margin 1.000 at r=16 and is predicted by the corpus's
own trend to die at the very next ring. It is listed because it makes the trade-off explicit, not
because it should be attacked.

### (d) Mixed `a >= c·β^r·γ^k`

| form | verdict | tight at | max margin | implied-f slope (proven cap) |
|---|---|---|---|---|
| `a >= 0.036353 * 2.45**r * 1.05**k` | HOLDS | (16,11), a=104783 | 1.674 | 0.317 |
| `a >= 0.03031 * 2.4**r * 1.1**k` | HOLDS | (16,11) | 1.735 | 0.301 |
| `a >= 0.018588 * 2.4**r * 1.15**k` | HOLDS | (16,11) | 2.072 | 0.302 |
| `a >= 0.0157736 * 2.5**r * 1.1**k` | HOLDS | (16,11) | 2.532 | 0.347 |
| `a >= 0.0367256 * 2.3**r * 1.15**k` | HOLDS | (16,11) | 1.413 | 0.242 |
| `a >= 0.04 * 2.4**r * 1.1**k` | KILLED | — | — | 2,636 counterexamples |

A γ > 1 factor *does* amplify the implied f-slope by `1/(1 − log₂γ)`, but the data only supports
γ ≲ 1.15, so the amplification is at most ~1.3×, and it is paid for by a constant `c` two to four
times smaller and by max margins jumping from 1.09 to 1.7–2.5. Every mixed winner is tight at
`(r,k) = (16,11)` — the *only* ring with no adversarial coverage at all. Family (d) buys a modest
slope improvement with a large credibility loss.

### (e) Dyadic / floor / piecewise

| form | verdict | note |
|---|---|---|
| `a >= 2**(r-2)` | HOLDS | tight at r=6 (16 = 2^4); max margin 6.13 by r=16 |
| `a >= 2**(r-3)` | HOLDS | very slack |
| `a >= floor(2.4**r / 13)` | HOLDS | integer-valued version of T2 |
| `a >= 2**(r+k-3) / 1966` | HOLDS | "cap / 1966"; same k-exponent as the cap ⇒ no f bound |
| `a >= 3 * 2**(r-3)` | KILLED | 6 CEs (r = 6,7,8) |
| `a >= 5 * 2**(r-4)` | KILLED | 6 CEs |
| `a >= 2**(r-1)` | KILLED | 311 CEs |
| `a >= k * 2**(r-4)` | KILLED | 398 CEs |

`a >= 2**(r-2)` is the simplest surviving statement in the whole sweep and is exactly tight at
r=6, but it is asymptotically worthless (β = 2 ⇒ zero f-slope, per §2b). No piecewise or floor
form was needed: family (a) at β = 2.4 already fits to within 9% at every ring, so there is
nothing for a piecewise patch to buy.

---

## 3. Margin profiles

Per-ring margin = `min a(r,·) / T(r,·)`; 1.000 means binding, larger means slack.

| candidate | r=6 | r=7 | r=8 | r=9 | r=10 | r=11 | r=12 | r=13 | r=14 | r=15 | r=16 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 `a >= 2.4**r/12.79` | 1.071 | 1.088 | 1.092 | 1.022 | **1.001** | 1.052 | **1.003** | 1.015 | 1.060 | 1.088 | 1.060 |
| T2 `a >= 2.4**r/13` | 1.088 | 1.105 | 1.110 | 1.038 | **1.017** | 1.070 | **1.019** | 1.031 | 1.078 | 1.106 | 1.078 |
| T3 `a >= 3**(r-1)/2/(0.278986*r**2)` | 1.323 | 1.463 | 1.535 | 1.453 | 1.406 | 1.431 | 1.299 | 1.234 | 1.196 | 1.128 | **1.000** |
| T4 `a >= 0.036353*2.45**r*1.05**k` | 1.674 | 1.586 | 1.489 | 1.401 | 1.307 | 1.282 | 1.197 | 1.130 | 1.101 | 1.055 | **1.000** |
| T5 `a >= 0.03031*2.4**r*1.1**k` | 1.683 | 1.735 | 1.386 | 1.377 | 1.384 | 1.393 | 1.315 | 1.221 | 1.145 | 1.082 | **1.000** |
| T7 `a >= 0.377682*W(r)*1.25**(k-1)` | 1.060 | 1.506 | **1.000** | 1.348 | 1.850 | 1.889 | 1.893 | 1.773 | 1.760 | 1.953 | 2.254 |
| T8 `a >= 2**(r-2)` | **1.000** | 1.219 | 1.469 | 1.648 | 1.938 | 2.445 | 2.796 | 3.396 | 4.258 | 5.244 | 6.131 |
| T9 `a >= 3**(r-1)/2/(0.035157*r**3)` | **1.000** | 1.290 | 1.547 | 1.648 | 1.772 | 1.984 | 1.964 | 2.021 | 2.111 | 2.131 | 2.016 |

**T1 is the only candidate that is near-tight at both ends and in the middle simultaneously**
(every margin in [1.001, 1.092]). It is *within 0.3% of dying at r=12*, where a single
configuration — rsst633 `126.453966`, k=7, a=2863 — supports the whole ring; and within 0.1% at
r=10 (rsst633 `122.140`). Everything else in the table is propped up by exactly one endpoint.

---

## 4. The corollary: what f(r) follows

`T(r,k) <= a <= B(r,k)` with B increasing in k gives `f(r) >= min{k : T(r,k) <= B(r,k)}`.

### 4a. With the PROVEN cap `a <= 2^(r+k-3)` (HOLDS on all 59,142)

| threshold | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | slope |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **true f(r)** | **5** | **5** | **6** | **7** | **7** | **8** | ? | ? | ? | ? | ? | ? | ? | ~0.60 |
| T1 `2.4^r/12.79` | 2 | 2 | 2 | 3 | 3 | 3 | 4 | 4 | 4 | 4 | 5 | 5 | 5 | +0.250 |
| T2 `2.4^r/13` | 2 | 2 | 2 | 3 | 3 | 3 | 3 | 4 | 4 | 4 | 5 | 5 | 5 | +0.250 |
| T3 `3^(r-1)/2/(0.279r²)` | 1 | 2 | 2 | 2 | 3 | 3 | 3 | 4 | 4 | 5 | 5 | 5 | 6 | +0.417 |
| T4 `.036353·2.45^r·1.05^k` | 1 | 1 | 2 | 2 | 2 | 3 | 3 | 3 | 4 | 4 | 4 | 5 | 5 | +0.333 |
| T5 `.03031·2.4^r·1.1^k` | 1 | 1 | 1 | 1 | 2 | 2 | 2 | 3 | 3 | 3 | 4 | 4 | 4 | +0.250 |
| T7 wheel `.377682·W·1.25^(k-1)` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 |
| T8 `2^(r-2)` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 |

Closed form for the leader: **T1 + proven cap ⟹ `f(r) >= ⌈0.26303·r − 0.6768⌉`.**

Every candidate is *consistent* with the true table (necessarily — each was verified against the
configurations that realise it), and every β > 2 candidate gives an **unbounded** f(r), which is
already the qualitative prize: the finite table becomes an infinite law. But quantitatively all of
them are 4–5 interior vertices below the truth at r=13 and the slope is less than half the
empirical 0.60.

### 4b. The bottleneck is the Cap, not the threshold

The proven cap is loose by **15× to 1,966×** against the observed maxima:

| (r,k) | max a among D-red | 2^(r+k-3) | slack |
|---|---|---|---|
| (10,6) | 538 | 8,192 | 15× |
| (13,8) | 7,496 | 262,144 | 35× |
| (13,13) | 14,599 | 8,388,608 | 575× |
| (16,10) | 100,454 | 8,388,608 | 84× |
| (16,16) | 273,101 | 536,870,912 | 1,966× |

Two much tighter caps that **HOLD on all 59,142 records** (bound-mode receipts logged):

* **`a <= (2^r + 2)/6 · (4/3)^(k-1)`** — the *wheel cap*. Note the shape: it says the wheel value
  `W(r)` is the k=1 base case and each additional interior vertex multiplies the mass by at most
  4/3. It has **no fudge constant** and is **exactly tight at every wheel in the corpus**
  (r = 8, 10, 12 at k=1). The exact minimal base is G* = 1.3224310 (binding at r=13, k=2, a=1806,
  `fr-r13-n15-4`); `a <= W(r)·1.322432^(k-1)` HOLDS, `a <= W(r)·1.3^(k-1)` is KILLED (48 CEs).
* **`a <= 2^r · 1.3^k / 7`** — the same thing with the wheel constant absorbed.

Combining T1 with the **wheel cap** instead:

| threshold + wheel cap `W(r)·(4/3)^(k-1)` | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | slope |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **true f(r)** | **5** | **5** | **6** | **7** | **7** | **8** | ? | ? | ? | ? | ? | ? | ? | ~0.60 |
| T1 `2.4^r/12.79` | 4 | 5 | 5 | 6 | 6 | **7** | 8 | 8 | 9 | 10 | 10 | 11 | 12 | +0.667 |
| T2 `2.4^r/13` | 4 | 5 | 5 | 6 | 6 | 7 | 8 | 8 | 9 | 10 | 10 | 11 | 11 | +0.583 |
| T3 `3^(r-1)/2/(0.279r²)` | 3 | 3 | 4 | 5 | 6 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | +0.833 |
| T4 `.036353·2.45^r·1.05^k` | 2 | 3 | 4 | 5 | 6 | 6 | 7 | 8 | 9 | 10 | 11 | 11 | 12 | +0.833 |

**T1 + the wheel cap gives f = 4, 5, 5, 6, 6, 7 against the true 5, 5, 6, 7, 7, 8 — off by at most
one at every ring** (table slopes are endpoint r=8→20 differences; T1's asymptotic slope is
0.6338, versus the true ≈0.60). Closed form:

> `f(r) >= ⌈ 1 + (log₂(2.4^r/12.79) − log₂((2^r+2)/6)) / log₂(4/3) ⌉ = ⌈0.63375·r − 1.6306⌉`

That is an analytic near-reproduction of the entire f(r) theorem, valid for all r, from two
inequalities. **The threshold half is empirically settled; the M2 cap is where the remaining
factor of 2.4 in f-slope lives.** Recommendation for the program: the wheel cap
`a <= W(r)·(4/3)^(k-1)` — an induction that adds one interior vertex at a time and multiplies the
extendable-coloring count by ≤ 4/3 — is now the highest-value target, above further threshold
refinement.

Caveat on the pairing: T1's implied slope (0.634) slightly **exceeds** the empirical true f-slope
(~0.60 from six points). Extrapolated, the implied bound would overtake the truth around r ≈ 54,
so at least one of {T1, the wheel cap, the 0.60 slope estimate} must weaken before then. T5 or T6
paired with the tight wheel cap give implied slopes 0.92–1.00 and would cross around r ≈ 20 —
another reason to prefer T1 over the mixed forms.

---

## 5. Sanity guards — where the corpus does and does not constrain

| r | D-reducible | of which adversarially generated | non-reducible negatives | catalog-only? |
|---|---|---|---|---|
| 6 | 28 | 27 | 2 | |
| 7 | 37 | 36 | 6 | |
| 8 | 1435 | 1430 | 302 | |
| 9 | 2168 | 2153 | 812 | |
| 10 | 1891 | 1832 | 2367 | |
| 11 | 209 | **0** | 1665 | **YES** |
| 12 | 767 | **0** | 4174 | **YES** |
| 13 | 1961 | **0** | 36534 | **YES** |
| 14 | 2654 | **0** | 111 | **YES** |
| 15 | 1562 | **0** | 0 | **YES** |
| 16 | 457 | **0** | 0 | **YES** |

**Only rings 6–10 have machine-generated D-reducibles.** At rings 11–16 the entire D-reducible
population is the union of the three published catalogs (rsst633, steinberger2822, nl4ct_pool),
and at rings 15–16 there is not even a non-reducible negative population. A frontier read off
rings 14–16 measures *what catalog authors chose to publish*, not what exists.

### Catalog-artifact test

Re-running the winners with `--filter "rec.source not in ('rsst633','steinberger2822','nl4ct_pool')"`
(support 5,478 records, effectively rings 6–10 only):

| form | full corpus | generated-only |
|---|---|---|
| `a >= 496*2.4**(r-10)` | HOLDS | **HOLDS** |
| `a >= 2.4**r/13` | HOLDS | **HOLDS** |
| `a >= 2.4**r/12` | KILLED (15 CEs) | **KILLED (2 CEs)** |
| `a >= 3**(r-1)/2/(0.278986*r**2)` | HOLDS | **HOLDS** |
| `a >= 0.036353*2.45**r*1.05**k` | HOLDS | **HOLDS** |
| `a <= (2^r+2)/6 * (4/3)**(k-1)` | HOLDS | **HOLDS** |

The generated-only frontier is `{6:19, 7:39, 8:94, 9:228, 10:516}` versus the all-source
`{6:16, 7:39, 8:94, 9:211, 10:496}`. Catalogs supply the strict minimum at r = 6, 9 and 10 and
tighten the β=2.4 constant by only **3.9%** (0.081384 → 0.078229). The `2.4^r/12` form is killed
by the generated population independently of any catalog. **Conclusion: the frontier is not a
catalog artifact on the rings where we can check** — but that check covers only r ≤ 10, and the
tightness of every candidate at r ≥ 14 is untested.

### Which rings genuinely constrain

For T1 at β=2.4, the binding constraints are **r=10 (margin 1.001)** and **r=12 (margin 1.003)** —
both single-configuration rsst633 witnesses. Rings 6, 7, 8, 15 are the slackest (margin ≈ 1.07–1.09)
and contribute nothing to the constant. Rings 15 and 16 do not constrain T1 at all yet also cannot
falsify it, having no adversarial coverage.

---

## 6. Ranked candidates, exact statements, and what would make each false

### #1 — T1: `d_reducible ⟹ a ≥ 2.4^r / 12.79`

equivalently `a ≥ 496·2.4^(r−10)` (both HOLD; `2.4^r/12.78` is KILLED, so this is optimal to
within 0.08% for base 2.4).

* Survives all 13,169 D-reducibles and all 5,478 generated-only.
* Margins 1.001–1.092 at all eleven rings; the only form tight everywhere at once.
* Implied f: `⌈0.263r − 0.677⌉` under the proven cap; `⌈0.634r − 1.631⌉` under the wheel cap,
  reproducing the f(r) table to within 1.
* Simplest of the strong forms: one base, one constant, no k.

**What would make it false:** a single D-reducible configuration at r=12 with `a ≤ 2856`, or at
r=10 with `a ≤ 495`. Ring 12's D-reducible population is 767 configurations, all catalog, with the
minimum realised by exactly one (`126.453966`); ring 10's by exactly one (`122.140`). Adversarial
generation at rings 11–13 is the direct test. Asymptotically it would fail if the true base is
below 2.4 — the residual band ±4.4% over 11 rings makes a base of 2.35 or 2.45 hard but not
impossible to rule out, and rings 15–16 (the only ones pushing the base up) are catalog-only.

### #2 — T2: `d_reducible ⟹ a ≥ 2.4^r / 13`

* Same shape, 1.7% of slack bought back. Margins 1.017–1.110; **no ring is binding**.
* Implied f identical to T1 under the proven cap; one weaker at r=12 and r=20 under the wheel cap.
* **Preferred over T1 as the statement to attempt a proof of**, precisely because nothing is
  binding: a proof does not have to be tight at rsst633 `126.453966`, and a proof technique losing
  <1.7% still lands. `floor(2.4^r/13)` also HOLDS if an integer-valued statement is wanted.

**What would make it false:** a D-reducible configuration at r=10 with `a ≤ 487` or r=12 with
`a ≤ 2809`. Same asymptotic exposure as T1.

### #3 — T4: `d_reducible ⟹ a ≥ 0.036353 · 2.45^r · 1.05^k`

* Best of the mixed family: strongest implied f-slope (0.333) among corpus-supported forms under
  the proven cap, and it is the only top-3 entry that uses k at all.
* Survives full corpus and generated-only.
* Cost: max margin 1.674 (it is slack by 67% at r=6) and it binds at (16,11) — a
  single-catalog-source cell with no adversarial coverage whatsoever.

**What would make it false:** any D-reducible configuration at r=16, k=11 with `a < 104,783`;
more generally the whole fit rests on rings 14–16, exactly the rings with no negatives. Also, if
the true k-exponent is ≥ 1.10 rather than 1.05 (the r=13 row of §1.3 suggests 1.11–1.19), the
constant is wrong. Lowest credibility of the three despite the better slope.

### Honourable mentions

* **T3 `a ≥ 3^(r-1)/2 / (0.278986·r²)`** — strongest implied f under the proven cap (slope 0.417,
  f(20) ≥ 6) and a conceptually attractive "a constant polynomial fraction of the coloring
  universe" statement. **Predicted by the corpus's own trend to be false at r = 17.** Not worth
  proof effort. The cubic version buys until r ≈ 26 with the same objection.
* **T8 `a ≥ 2^(r-2)`** — simplest surviving statement in the sweep, exactly tight at r=6, probably
  the easiest to prove. Implies nothing about f (β = 2). Worth stating as a warm-up lemma only.
* **The wheel cap `a ≤ (2^r+2)/6 · (4/3)^(k-1)`** — not a threshold, but the highest-value item
  this sweep surfaced. See §4b.

---

## 7. Receipts

All 75 receipts are in `lemma_log.jsonl` and are content-hashed against corpus signature
`a2b1feba331bf2962b2b`. Re-running any statement reproduces the same receipt id. Verdict counts
from this session: family (a) 10 statements, (b) 8, (c) 7, (d) 6, (e) 6, caps 9, generated-only
guards 6, per-ring exclusion guards 11, structural probes 3.
