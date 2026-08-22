# The Cap Theorem (draft proof, γ = 2)
## 2026-08-22. Status: DRAFT — complete modulo pinning the shellability citation (flagged).
## Companion: M2-groundwork-raw.txt (routes, literature, sharp-constant program).

**Setting.** K a configuration in the RSST sense; S = S(K) its free completion: a
near-triangulation of the disk with ring R (induced cycle of length r, the boundary),
k interior vertices, n = r + k vertices total. Φ(K) = the set of ring colorings
(edge colorings of E(R) in 3 colors, up to color symmetry, i.e. canonical classes)
that extend to a *tri-coloring* of S — an edge 3-coloring of E(S) in which the three
edges of every internal triangular face receive three distinct colors. a = |Φ(K)| is
the classical RSST header quantity. P(G, q) = chromatic polynomial.

---

## Lemma 1 (Bridge Lemma — disk Tait correspondence with counting constants)

*For every near-triangulation S of the disk:*
1. *#tri-colorings(S) = P(S,4)/4;*
2. *the S₃ action permuting the three edge colors is free on tri-colorings, so the
   number of tri-colorings up to color symmetry is P(S,4)/24;*
3. *a = |Φ(K)| ≤ P(S,4)/24.*

**Proof.**
(1) Identify the three edge colors with the nonzero elements x, y, z of the Klein
group V = Z₂×Z₂ (note x+y+z = 0 and each element is its own inverse).

*Forward.* Let c : V(S) → V be a proper 4-coloring. Label each edge uv by
t(uv) = c(u)+c(v). Properness gives t(uv) ≠ 0. If two edges uv, vw of an internal
triangle uvw had equal labels, then c(u)+c(v) = c(v)+c(w) forces c(u) = c(w),
contradicting properness on the edge uw. Hence t is a tri-coloring. Translates
c + g (g ∈ V) induce the same t, so each t arises from at least 4 colorings.

*Backward.* Let t be a tri-coloring, regarded as a V-valued 1-cochain. Around any
internal triangular face the three labels are distinct nonzero elements of V, so
their sum is x+y+z = 0. Since S is a triangulated disk, the internal face boundaries
generate its entire cycle space (simple connectivity). Hence t vanishes on all
cycles, so it is exact: fixing any vertex v₀ and any value c(v₀) ∈ V, the assignment
c(u) = c(v₀) + Σ t(e) along any v₀–u path is well defined; exactly 4 potentials c
exist (the choice of c(v₀)), and each is proper because t(uv) = c(u)+c(v) ≠ 0.
Thus tri-colorings correspond 4-to-1 to proper 4-colorings: #tri = P(S,4)/4.

(2) Freeness. Let σ ∈ S₃ fix a tri-coloring t. If σ is a transposition, say x↔y,
then every edge labeled x would need label y and vice versa, so no edge is labeled
x or y; all edges labeled z contradicts triangle-distinctness (any internal triangle
needs three colors). If σ is a 3-cycle, it fixes no color at all, so no edge could
retain its label — impossible since S has edges. Hence all S₃-orbits have size 6 and
the count of color-classes is (P/4)/6 = P(S,4)/24.

(3) Restriction to the ring maps each color-class of tri-colorings of S to one
canonical ring-coloring class (color-equivalent tri-colorings restrict to
color-equivalent ring colorings). By definition Φ(K) is exactly the image of this
map, so a ≤ #classes = P(S,4)/24. ∎

**Sanity anchors (computed on our own data):** wheels give equality:
fr-r8-n9-0 (k=1): a = 43 = P/24; fr-r10-n11-0: a = 171 = P/24; and the closed form
P(W_r,4) = 4(2^r + 2) reproduces the observed max-a at k=1 for every even r in the
corpus. Strictness for k ≥ 2 occurs (e.g. fr-r8-n12-120: a = 81 < 92 = P/24) —
two color-inequivalent tri-colorings can share a ring restriction.

---

## Lemma 2 (Shelling order)

*Every near-triangulation S of the disk admits a vertex ordering v₁, v₂, …, v_n such
that v₁v₂v₃ is a triangle of S and every vᵢ (i ≥ 4), at the moment of its arrival,
is adjacent to the two endpoints of an edge of the already-built complex.*

**Proof.** Every triangulated 2-ball is shellable [CITATION TO PIN: classical;
attributed to Newman (1926); see also Danaraj–Klee's survey on shellability;
non-shellable balls exist only from dimension 3 up]. Fix a shelling T₁, T₂, …, T_F
of the triangles of S: each Tⱼ (j ≥ 2) meets the union of its predecessors in either
one edge or two edges (a shelling step of a 2-disk cannot attach along an edge plus
an isolated vertex). A step attaching along two edges introduces no new vertex.
A step attaching along one edge uv introduces exactly one new vertex w, adjacent to
both u and v, and uv is an edge of the built complex. Ordering vertices by first
appearance (the three vertices of T₁ first) gives the claim; Euler's relation
(F = 2n − r − 2 internal triangles) confirms there are exactly n − 3 vertex-adding
steps and k = n − r two-edge ("closing") steps — one closing step per interior
vertex, a structural fact recorded for the γ-improvement program. ∎

---

## Theorem (Cap, γ = 2)

*For every configuration K of ring size r with k interior vertices:*

  **a = |Φ(K)| ≤ 2^(r+k−3).**

**Proof.** Count proper 4-colorings of S along the ordering of Lemma 2: v₁, v₂, v₃
(a triangle) admit 4·3·2 = 24 joint colorings; each subsequent vertex arrives
adjacent to the two endpoints of an existing edge, which carry distinct colors, so
it has at most 2 admissible colors. Hence P(S,4) ≤ 24·2^(n−3), and by Lemma 1(3),
a ≤ P(S,4)/24 ≤ 2^(n−3) = 2^(r+k−3). ∎

**Remarks.** (i) No interior-degree hypothesis is used; min-degree 5 is a resource
for improving the constant (see γ-program in M2-groundwork). (ii) Tightness at
k = 1: bound 2^(r−2) vs. true wheel value (2^r+2)/6 — factor ≤ 1.5. (iii) The
empirically sharp law appears to be B(r,k) = ((2^r+2)/6)·(4/3)^(k−1), binding at
wheels; proving γ = 4/3 is the sharp-constant program.

---

## Conditional Corollary (mass-law form)

*If the Threshold half holds with A(r) ≥ α·β^r (empirically β ≈ 2.4), then every
D-reducible configuration of ring size r satisfies*

  2^(r+k−3) ≥ a ≥ α·β^r  ⟹  **k ≥ r·log₂(β/2) − O(1)** ,

*i.e. f(r) grows linearly in r; with β = 2.4 the slope is ≥ 0.263. (Observed truth
f(12)/12 ≈ 0.583; the sharp γ = 4/3 would give slope 0.634 — essentially the true
growth, evidence the mass mechanism is the right explanation, not just an
inequality.)*

## Open items to finish M2
1. Pin the shellability citation (library check: Newman 1926; Danaraj–Klee 1978).
2. Independent re-verification of the two computational anchors by a fresh script
   committed next to this file.
3. Referee-grade pass on Lemma 1(3)'s "image" argument (canonicalization details —
   the canonical-class conventions are in src/fourcolor/reduce.py's docstring).
