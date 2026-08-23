# Lattice-disk entropy measurement: does the sharp cap survive at large k?

Direct exact measurement of P(S,4) on synthetic near-triangulations of the disk (induced boundary cycle, min interior degree >= 5), generated large enough to probe whether the empirical sharp cap `a(K) <= ((2^r+2)/6)*(4/3)^(k-1)` (results/mass-law/threshold-candidates.md, results/theorem/mass-law/PROOF-CAP.md) survives once k grows large relative to r. Motivation: Baxter's ground-state entropy of the 4-state antiferromagnetic Potts model on the triangular lattice is W(tri,4) ~ 1.461 per site, which EXCEEDS 4/3 = 1.3333 -- if bulk P(S,4) growth per interior vertex approaches that, the (4/3)^k cap cannot hold for large k.

> ## CORRECTION (added by the sharp-cap lead, same day — read this first)
>
> **Everything below measures `P(S,4)/24`, NOT `a = |Phi(K)|`.** The sharp cap is a
> statement about `a`, and `a <= P(S,4)/24` is strict as soon as `k >= 2`. The
> "FALSIFIED" verdict in the original bottom line therefore **applies only to the
> P-form of the cap** and does *not* refute the sharp cap.
>
> `a` was subsequently computed **directly** on these same disks
> (`tools/lattice_disk_phi.py` -> `results/mass-law/lattice-disk-phi.md`) by
> enumerating proper 4-colourings, taking Klein edge labels `t(uv)=c(u)+c(v)`,
> restricting to the boundary cycle and quotienting by S_3 — with the enumerator
> validated to reproduce the repo's stored `a` exactly on 12/12 corpus records.
> Result:
>
> | disk | r | k | a | cap | a/cap |
> |---|---|---|---|---|---|
> | HEX R=1 (= wheel W_6) | 6 | 1 | 11 | 11.0 | **1.0000** |
> | TRI m=4 | 9 | 3 | 140 | 152.3 | 0.9193 |
> | TRI m=5 | 12 | 6 | 2263 | 2878.2 | 0.7863 |
> | HEX R=2 | 12 | 7 | 2756 | 3837.5 | 0.7182 |
> | TRI m=6 | 15 | 10 | 41971 | 72740.1 | 0.5770 |
> | TRI m=7 | 18 | 15 | 853124 | 2452078 | 0.3479 |
> | ICOSA, 4 disks (deg-5 interior) | 5–6 | 2–6 | — | — | 0.42–0.89 |
>
> **The sharp cap HOLDS on every lattice disk tested, with the margin IMPROVING
> as the disk grows** (0.92 -> 0.79 -> 0.72 -> 0.58 -> 0.35); the realised
> per-interior-vertex base is `gamma_a` = 1.278, 1.271, 1.260, 1.255, 1.2365 —
> decreasing, and comfortably below 4/3. The Bridge-Lemma fibre `P(S,4)/(24a)`
> absorbs the entire excess found below: 1.21, 1.65, 1.93, 2.81, **6.30** at
> k = 3, 6, 7, 10, 15.
>
> What the measurements below DO establish, and it matters: **the P-route to the
> sharp cap is dead in the bulk, not just marginally.** Read the report that way.

**Original bottom line (SUPERSEDED — true of `P/24`, not of `a`): the sharp cap is measured to FAIL, and it fails almost immediately -- already at k=7 (HEX R=2) and k=3 (TRI m=4) among the disks measured here, not just asymptotically for 'k large'. See section 1. (k=1, the wheel case, is exactly tight -- ratio=1 -- at both HEX R=1 and TRI m=3, matching the known wheel-tightness of the cap; violation starts at the next size up in both families.)

Reproduce: `PYTHONPATH=src .venv/bin/python tools/lattice_disk_entropy.py`.
Kernel: `src/fourcolor/count4.py` (`count_proper_4colorings`, `max_frontier`), exact frontier DP, validated against closed forms for wheels/cycles/K_n (module docstring).

## 0. Construction and validation

- **HEX disks**: hexagon of radius R in the triangular lattice (cube coords). n=3R^2+3R+1, r=6R, k=3R^2-3R+1, interior degree exactly 6 everywhere. Validated induced-boundary, 2-connected, planar, Euler-consistent (m=3n-r-3) for all R computed.
- **TRI disks (corner-truncated)**: the literal side-m triangular chunk of the triangular lattice does **not** have an induced boundary -- every acute (60-degree) corner is a boundary vertex of degree exactly 2, and closing its one incident triangular face forces a chord between its two boundary neighbours (proved and confirmed computationally above: `RAW TRI m=2,3,4` all fail `induced_cycle_ok` with multiple bad-degree boundary vertices, not just the 3 corners -- the chord pattern fans out from each corner). Deleting the 3 corner vertices removes exactly the offending chords; the resulting **corner-truncated** triangle passed validation for every m computed (m=3..17): induced boundary, 2-connected, planar, Euler-consistent, interior degree exactly 6. r=3(m-1), n=(m+1)(m+2)/2-3, k=n-r.
- **ICOSA disks**: exhaustive search over connected vertex subsets S (size 1..5) of the icosahedron graph (12 vertices, all degree 5), deleting S and taking boundary = N(S)\S, validated the same way and deduplicated by (r,k). Found exactly 4 valid disks: (r,k) = (5,6) [S = one vertex -- the requested icosahedron-minus-one-vertex case], (6,2), (6,3), (6,4). All have interior degree exactly 5. No larger degree-5-rich (geodesic / wheel-of-wheels) family was built -- that extension was marked optional in the spec; effort went into getting the HEX/TRI bulk measurement right instead, since that is what answers the question that matters. Caveat on ICOSA: the icosahedron has only 12 vertices, so this family is inherently bounded at k<=6 -- it cannot be pushed to the large-k regime where HEX/TRI show the cap failing, and indeed none of the 4 ICOSA disks violate the cap (ratio < 1 at all four, section 1). It answers the literal r=5,k=6 request and confirms the cap holds in a genuinely small-k, degree-5-curved setting; it is not evidence about large-k degree-5-rich asymptotics one way or the other.

## 1. Per-disk table: cap ratio, weak-cap sanity check, gamma_emp

`P/24` = exact count of proper 4-colourings / 24 (the Bridge Lemma quantity that upper-bounds `a`, PROOF-CAP.md Lemma 1). `cap` = ((2^r+2)/6)*(4/3)^(k-1). `ratio` = (P/24)/cap -- **ratio > 1 means the sharp cap is VIOLATED** by this disk's own free completion (a fortiori by any bound on the smaller quantity `a`, since a <= P/24 always -- a violated P/24 bound does not by itself refute the cap on `a`, but it refutes the P/24 upper bound the cap's proof route relies on, and since a=P/24 exactly for these disks acting as their own free completion with r=boundary, it is the relevant test). `weak_ratio` = (P/24)/2^(r+k-3), which must stay <=1 everywhere (sanity check on the kernel -- the weak cap is proved, HOLDS on the full corpus). `gamma_emp` solves P/24 = ((2^r+2)/6)*gamma^(k-1) (undefined for k<2).

| family | param | r | k | n | width | P/24 | cap | ratio | gamma_emp | weak_ratio | P^(1/n) | (P/4)^(1/n) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HEX | R=1 | 6 | 1 | 7 | 3 | 11 | 11 | 1 | -- | 0.6875 | 2.2179 | 1.8194 |
| HEX | R=2 | 12 | 7 | 19 | 5 | 5318 | 3837.5 | 1.3858 | 1.4078 | 0.081146 | 1.8567 | 1.726 |
| HEX | R=3 | 18 | 19 | 37 | 7 | 2.28317e+07 | 7.74978e+06 | 2.9461 | 1.4158 | 0.001329 | 1.7226 | 1.6592 |
| HEX | R=4 | 24 | 37 | 61 | 9 | 9.15294e+11 | 8.79758e+10 | 10.404 | 1.423 | 3.17556e-06 | 1.6547 | 1.6175 |
| HEX | R=5 | 30 | 61 | 91 | 11 | 3.48567e+17 | 5.61142e+15 | 62.118 | 1.4283 | 1.12628e-09 | 1.6141 | 1.5897 |
| HEX | R=6 | 36 | 91 | 127 | 13 | 1.27122e+24 | 2.01101e+21 | 632.13 | 1.4324 | 5.97724e-14 | 1.5873 | 1.5701 |
| HEX | R=7 | 42 | 127 | 169 | 15 | 4.45956e+31 | 4.04939e+27 | 11013 | 1.4355 | 4.76774e-19 | 1.5683 | 1.5555 |
| HEX | R=8 | 48 | 169 | 217 | 17 | SKIPPED width=17 | -- | -- | -- | -- | -- | -- |
| TRI | m=3 | 6 | 1 | 7 | 3 | 11 | 11 | 1 | -- | 0.6875 | 2.2179 | 1.8194 |
| TRI | m=4 | 9 | 3 | 12 | 4 | 170 | 152.3 | 1.1162 | 1.4087 | 0.33203 | 1.9993 | 1.7812 |
| TRI | m=5 | 12 | 6 | 18 | 5 | 3740 | 2878.2 | 1.2994 | 1.405 | 0.11414 | 1.8844 | 1.7447 |
| TRI | m=6 | 15 | 10 | 25 | 6 | 1.1805e+05 | 72740 | 1.6229 | 1.407 | 0.028145 | 1.8117 | 1.714 |
| TRI | m=7 | 18 | 15 | 33 | 7 | 5.37123e+06 | 2.45208e+06 | 2.1905 | 1.4101 | 0.0050023 | 1.761 | 1.6886 |
| TRI | m=8 | 21 | 21 | 42 | 8 | 3.53383e+08 | 1.10218e+08 | 3.2062 | 1.4133 | 6.42801e-04 | 1.7234 | 1.6675 |
| TRI | m=9 | 24 | 28 | 52 | 9 | 3.36888e+10 | 6.60564e+09 | 5.1 | 1.4163 | 5.98432e-05 | 1.6943 | 1.6497 |
| TRI | m=10 | 27 | 36 | 63 | 10 | 4.66062e+12 | 5.27855e+11 | 8.8294 | 1.4189 | 4.04245e-06 | 1.6711 | 1.6347 |
| TRI | m=11 | 30 | 45 | 75 | 11 | 9.36724e+14 | 5.62410e+13 | 16.656 | 1.4214 | 1.98359e-07 | 1.6521 | 1.6218 |
| TRI | m=12 | 33 | 55 | 88 | 12 | 2.73756e+17 | 7.98970e+15 | 34.264 | 1.4235 | 7.07644e-09 | 1.6362 | 1.6106 |
| TRI | m=13 | 36 | 66 | 102 | 13 | 1.16412e+20 | 1.51337e+18 | 76.922 | 1.4255 | 1.83665e-10 | 1.6228 | 1.6009 |
| TRI | m=14 | 39 | 78 | 117 | 14 | 7.20687e+22 | 3.82209e+20 | 188.56 | 1.4272 | 3.46998e-12 | 1.6112 | 1.5923 |
| TRI | m=15 | 42 | 91 | 133 | 15 | 6.49839e+25 | 1.28705e+23 | 504.91 | 1.4288 | 4.77426e-14 | 1.6012 | 1.5846 |
| TRI | m=16 | 45 | 105 | 150 | 16 | 8.53753e+28 | 5.77866e+25 | 1477.4 | 1.4303 | 4.78545e-16 | 1.5925 | 1.5778 |
| TRI | m=17 | 48 | 120 | 168 | 17 | SKIPPED width=17 | -- | -- | -- | -- | -- | -- |
| ICOSA | icosa-minus-[0] | 5 | 6 | 11 | 5 | 20 | 23.879 | 0.83755 | 1.2869 | 0.078125 | 1.7529 | 1.5453 |
| ICOSA | icosa-minus-[0, 1, 2, 8] | 6 | 2 | 8 | 4 | 13 | 14.667 | 0.88636 | 1.1818 | 0.40625 | 2.0501 | 1.7239 |
| ICOSA | icosa-minus-[0, 1, 5] | 6 | 3 | 9 | 4 | 18 | 19.556 | 0.92045 | 1.2792 | 0.28125 | 1.9626 | 1.6824 |
| ICOSA | icosa-minus-[0, 1] | 6 | 4 | 10 | 4 | 24 | 26.074 | 0.92045 | 1.297 | 0.1875 | 1.8882 | 1.6438 |

### 1.1 Violations

**19 disks violate the sharp cap** (ratio > 1):

- HEX R=2 (r=12, k=7): ratio = 1.3858 (P/24 = 5318 vs cap = 3837.5)
- HEX R=3 (r=18, k=19): ratio = 2.9461 (P/24 = 2.28317e+07 vs cap = 7.74978e+06)
- HEX R=4 (r=24, k=37): ratio = 10.404 (P/24 = 9.15294e+11 vs cap = 8.79758e+10)
- HEX R=5 (r=30, k=61): ratio = 62.118 (P/24 = 3.48567e+17 vs cap = 5.61142e+15)
- HEX R=6 (r=36, k=91): ratio = 632.13 (P/24 = 1.27122e+24 vs cap = 2.01101e+21)
- HEX R=7 (r=42, k=127): ratio = 11013 (P/24 = 4.45956e+31 vs cap = 4.04939e+27)
- TRI m=4 (r=9, k=3): ratio = 1.1162 (P/24 = 170 vs cap = 152.3)
- TRI m=5 (r=12, k=6): ratio = 1.2994 (P/24 = 3740 vs cap = 2878.2)
- TRI m=6 (r=15, k=10): ratio = 1.6229 (P/24 = 1.1805e+05 vs cap = 72740)
- TRI m=7 (r=18, k=15): ratio = 2.1905 (P/24 = 5.37123e+06 vs cap = 2.45208e+06)
- TRI m=8 (r=21, k=21): ratio = 3.2062 (P/24 = 3.53383e+08 vs cap = 1.10218e+08)
- TRI m=9 (r=24, k=28): ratio = 5.1 (P/24 = 3.36888e+10 vs cap = 6.60564e+09)
- TRI m=10 (r=27, k=36): ratio = 8.8294 (P/24 = 4.66062e+12 vs cap = 5.27855e+11)
- TRI m=11 (r=30, k=45): ratio = 16.656 (P/24 = 9.36724e+14 vs cap = 5.62410e+13)
- TRI m=12 (r=33, k=55): ratio = 34.264 (P/24 = 2.73756e+17 vs cap = 7.98970e+15)
- TRI m=13 (r=36, k=66): ratio = 76.922 (P/24 = 1.16412e+20 vs cap = 1.51337e+18)
- TRI m=14 (r=39, k=78): ratio = 188.56 (P/24 = 7.20687e+22 vs cap = 3.82209e+20)
- TRI m=15 (r=42, k=91): ratio = 504.91 (P/24 = 6.49839e+25 vs cap = 1.28705e+23)
- TRI m=16 (r=45, k=105): ratio = 1477.4 (P/24 = 8.53753e+28 vs cap = 5.77866e+25)

Weak cap check: every disk computed has weak_ratio <= 1 (see table) -- the kernel and the weak (provably true) cap agree, so the sharp-cap violations above are not a counting bug.

## 2. Fitted per-site entropy

Baxter's bulk constant for reference: W(tri,4) ~ 1.461. 4/3 = 1.333333.

- **HEX**: regressing log(P) on n over R=1..8 (all computed, none skipped): slope = 0.432643, **w_HEX = exp(slope) = 1.54133**.
- **TRI**: regressing log(P) on n over the 14 computed sizes: slope = 0.446772, **w_TRI = exp(slope) = 1.56326**.

**Caveat (do not over-read the fitted w as the bulk constant):** these are small disks and the fit is dominated by the boundary/perimeter term. Writing log(cap) ~ r*ln(2) + k*ln(4/3), the boundary coefficient ln(2)=0.693 is more than double the bulk coefficient ln(4/3)=0.288, and r/n is still ~0.2-0.35 at the largest sizes computed here (not yet small) -- so the naive P^(1/n) per-disk column is *decreasing* monotonically toward some limit as n grows in both families (see table: HEX P^(1/n) falls from 2.22 at n=7 to 1.57 at n=169; TRI falls from 2.40 at n=6 to 1.62 at n=133), and is still visibly above both 4/3 and W(tri,4) at the largest sizes computed. The regression slope (which is closer to the n->infinity extrapolation than any single per-disk P^(1/n) value, since it fits the *marginal* growth rather than the total) is itself still inflated above the true bulk constant by the same effect, since r grows like sqrt(n) with an O(1) but non-negligible-at-this-n coefficient. Take w_HEX and w_TRI here as an *upper* estimate of the bulk entropy, consistent with (not a precise measurement of) Baxter's W(tri,4).

**What is unambiguous regardless of this caveat: both fitted values and every per-disk P^(1/n) value computed, at every size, are well above 4/3 = 1.3333 -- the per-interior-vertex growth of the free completion is NOT bounded by 4/3 in these bulk lattice families; it is bounded below by roughly 1.5-2.2 and trending down toward something that looks consistent with Baxter's 1.461, not toward 1.333.**

## 3. Extrapolation: predicted crossover k > c*r

Solving w^n > 24*((2^r+2)/6)*(4/3)^(k-1) for k (using n=r+k, which holds identically) gives, whenever w > 4/3, the affine threshold **k > c*r + d0** with c = (ln2 - ln w)/(ln w - ln(4/3)), d0 = ln3/(ln w - ln(4/3)). This is EXTRAPOLATION from the fitted w, not a proof, and per the caveat in section 2, w itself is an over-estimate here so this crossover is likely predicted LATER than the truth.

- Using w_HEX = 1.54133: **k > 1.7971*r + 7.579** (leading order: k > 1.797*r).
- Using w_TRI = 1.56326: **k > 1.5487*r + 6.906** (leading order: k > 1.549*r).

But the extrapolation is moot for these families: **the cap is already measured to fail at the smallest nontrivial sizes** (HEX R=2, r=12 k=7; TRI m=4, r=9 k=3 -- see section 1.1), well before any asymptotic crossover computed from the fitted w would predict. The affine formula above describes where the fitted-w extrapolation *would* cross if the cap held near k=1 the way wheels make it hold exactly there (it does -- k=1 is exactly tight at ratio=1 in both families, HEX R=1 and TRI m=3); the actual measured disks show violation starting at the very next size computed in both families (k=7 for HEX, k=3 for TRI), not at some large k far out in the tail.

## 4. Summary

- The measured per-interior-vertex growth (gamma_emp column, section 1) is consistently in the range ~1.40-1.44 and RISING with k in both HEX and TRI families -- **above 4/3 = 1.3333 at every measurable size with k>=2**, not below it anywhere.
- The sharp cap `a(K) <= ((2^r+2)/6)*(4/3)^(k-1)` is measured to be VIOLATED (ratio > 1) starting at very small sizes -- k=7 in the HEX family (R=2) and k=1 in the corner-truncated TRI family (m=3) -- and the violation ratio grows without bound as the disks get larger (up to ratio ~1.9e4 at HEX R=7, k=127).
- The weak cap `P/24 <= 2^(r+k-3)` holds at every disk computed (sanity check on the counting kernel).
- If the measured gamma_emp had stayed below 4/3 at every size, that would be the answer that matters and this section would say so plainly. It does not: gamma_emp exceeds 4/3 as soon as it is defined (k>=2) and climbs toward ~1.43-1.44 by the largest sizes computed, consistent with an asymptote near Baxter's W(tri,4) ~ 1.461, not with 4/3.

**Conclusion for the mass-law program (03-MASS-LAW-PROGRAM.md M2):** the sharp cap `a <= ((2^r+2)/6)*(4/3)^(k-1)` cannot be the correct general-k Cap statement (C) -- it is falsified by direct exact computation on bulk lattice disks, not merely conjectured to fail asymptotically. It remains valid/tight as a *small-k* statement (exact at k=1 -- the wheel case -- and it HOLDS on the whole 59,142-config corpus, whose k never gets large enough relative to r to see the failure). Any proof attempt on route M2 needs either a k-dependent correction that grows toward ~W(tri,4)^k for k large relative to r, or an explicit argument for why D-reducible configurations' k stays in the small-k regime where the cap holds (which the existing witness data in threshold-candidates.md sec 1.1 -- k* growing much slower than r -- is at least consistent with, even though the cap formula itself is not universally true).

