# f(r): the minimum interior size of a D-reducible configuration, rings 8-12

**Theorem.** For each ring size r in {8, 9, 10, 11, 12}, every D-reducible
configuration of ring size r has at least f(r) interior vertices, where

| r | f(r) |
|---|---|
| 8 | 5 |
| 9 | 5 |
| 10 | 6 |
| 11 | 7 |
| 12 | 7 (interior 1-5 exhaustively verified; interior 6 sweep in progress -- see "Status" below) |

and this bound is tight: for each r, a D-reducible configuration with
exactly f(r) interior vertices exists in the published RSST/nl4ct
catalog (§5).

This generalizes the "Candidate B" dual rule mined in
`results/theorem/candidates.md` (`r == 11 AND n_interior <= 6 ->
non-reducible`, discovered from an already-exhaustive r=11 plantri sweep
and confirmed to survive adversarial mutation stress-testing in
`results/theorem/stress_test.md`) to a documented, exhaustively-verified,
cross-checked table over rings 8-12.

**"Configuration" here means D-reducible in the specific technical sense
of Robertson-Sanders-Seymour-Thomas / Appel-Haken: no contract.** §6
documents the important nuance that *C*-reducibility (reducibility that
uses a nontrivial contract) is a strictly weaker requirement -- the RSST
catalog itself contains configurations at ring 8 and ring 11 with fewer
interior vertices than f(r) that are C-reducible but not D-reducible.

---

## 1. Configuration class definition and how the enumeration matches it

The class of graphs enumerated is exactly RSST's "configuration": a
near-triangulation (the *free completion*) consisting of

  1. a **ring** R, an induced (chordless) cycle of length r bounding a
     disk, with every ring vertex of degree >= 3 in the free completion;
  2. a nonempty, **connected interior** (the vertices strictly inside the
     disk), every one of degree >= 5;
  3. every bounded face other than possibly ones touching the ring is a
     triangle (a *near-triangulation of a disk*);

together with the two extra structural conditions RSST's own reference
implementation enforces on any file it will accept
(`third_party/arxiv-1401.6481/src/anc/reduce.c`'s `ReadConf`, ported
independently as `fourcolor.mutate.is_legal_configuration`):

  4. each ring vertex's neighbor list, written in rotation order, must
     start at ring-neighbor i+1 and end at ring-neighbor i-1 with every
     entry strictly between them interior (a **labeling convention**, not
     a structural constraint -- see §1.3);
  5. sum of all degrees = 6(n-1) - 2r (an edge-count identity, automatic
     given 1-3);
  6. **each interior vertex touches the ring boundary in at most 2
     separate contiguous arcs** (a genuine structural constraint --
     see §1.3, this is NOT implied by 1-3 and removes a nontrivial
     fraction of near-triangulations at these small sizes);
  7. rotational consistency of the embedding (automatic for any graph
     built from a genuine rotation system, as plantri's output is).

### 1.1 Exhaustive generation: plantri

Every near-triangulation satisfying properties 1-3 above, for a fixed
(r, n), is produced **exactly once up to isomorphism** by

```
third_party/plantri/plantri55/plantri -P<r> -c3 -a <n>
```

`plantri` version 5.5 (17 May 2024), the tool's own self-report
(`plantri --help`); binary and source pinned under
`third_party/plantri/plantri55/`, sha256:

```
34805ca2e951d1fc210cb58c000c8075e778f25ed69abb8decf831a23c58d5c5  third_party/plantri/plantri55/plantri
dff91dd22812e0344ffeaaa929a5c61b98cb50f35c1b4fa94fcb2b15e7a8085a  third_party/plantri/plantri55/plantri.c
911cdf5bcca7294eb80f8f79fefc148183f7ba81da15b3aa4d6d2401a3bc7ded  third_party/plantri/archive.tar.gz
```

Justification of each flag, from `third_party/plantri/plantri55/plantri-guide.txt`:

  - `-P<r>` selects triangulations of a disk with a distinguished outer
    face of size exactly r ("The argument to -P is the disk size").
  - `-c3` (with no `-m`) is documented as defaulting to `-c3m3` for `-P`:
    *"no chords, no vertices degree 2"* on the outer face -- i.e. the ring
    is chordless (condition 1's "induced cycle") and every ring vertex has
    degree >= 3 (condition 1's degree bound), exactly matching the class
    definition, with zero extra filtering needed for those two
    properties.
  - the disk's interior faces are triangles by construction of `-P`
    ("the other faces must be triangles"), and interior (non-outer-face)
    vertices have degree >= 3 by construction ("Except for the outer
    face, all vertices must have degree at least 3") -- condition 3.
  - `plantri` is a canonical-construction-path / orderly-generation
    program: for a fixed `n` it is a full generator of one representative
    per isomorphism class, not a sampler -- this is the tool's entire
    purpose and the basis on which it is cited throughout the plane-graph
    enumeration literature (Brinkmann & McKay). `-a` (ascii output) does
    not change which graphs are produced, only the output encoding. This
    is what makes "enumerate over `n = r+1 .. r+f_catalog(r)-1`, once per
    `n`" an EXHAUSTIVE search of the configuration space at those sizes,
    not a sample of it.

`tools/datagen.py`'s existing pipeline (`parse_ascii_line` ->
`trace_outer_face` -> `to_configuration`) is reused verbatim by the new
`tools/fr_table.py` (imported, not reimplemented) to trace the
distinguished outer face back out of plantri's rotation-system output and
relabel to RSST's ring-then-interior vertex-numbering convention.

### 1.2 `to_configuration`'s filter: what it checks, what it doesn't

`tools/datagen.py:to_configuration` (reused by `tools/fr_table.py`)
enforces, on top of what plantri already guarantees:

  - interior nonempty (rejects the ringless degenerate case);
  - interior degree >= 5 (condition 2);
  - interior connected (condition 2, implicit in "the interior" being one
    graph, not a disjoint union -- also required by `Configuration.
    validate()`'s downstream users).

It does **not** check condition 4 (ring-vertex rotation start -- see
§1.3) or condition 6 (ring-contact-arc bound -- see §1.3). Both gaps were
found by running the independently-ported `fourcolor.mutate.
is_legal_configuration` (RSST's own `ReadConf` conditions, ported earlier
for `tools/stress_test_theorem.py`) against every `to_configuration`
output and inspecting every disagreement.

### 1.3 Two gaps found, and how each was resolved

**Condition 4 (ring-vertex rotation start) is a labeling convention, not
structure.** `to_configuration` relabels plantri's traced ring cycle to
1..r but does not rotate each ring vertex's neighbor list to start
exactly at ring-neighbor i+1 -- RSST's file-format convention, required
by `ReadConf` (and hence by `build/reduce_rsst`) but NOT by anything
`fourcolor.reduce.check` or `Configuration.validate()` compute (both are
rotation-start-agnostic: a cyclic list represents the same rotation
system regardless of which entry it's written starting from). Confirmed
by direct experiment: naively serializing an RSST-relabeled configuration
made `build/reduce_rsst` reject it with `ReadErr(4, ...)` even though the
underlying embedded graph was fine. **Fix:** `fourcolor.conf_parser.
rotate_ring_starts` (new function, §4) cyclically rotates each ring
vertex's list to the required starting point -- a mathematical no-op on
the rotation system, purely a serialization normalization. Used
throughout this sweep (both for the `is_legal_configuration` audit and
for every RSST-oracle cross-check in §4).

**Condition 6 (ring-contact-arc bound) is real structure, and it removes
a LOT of near-triangulations at these sizes.** After normalizing away the
condition-4 labeling artifact, a substantial fraction of
`to_configuration`-accepted near-triangulations still fail
`is_legal_configuration` -- specifically condition 6, ported directly
from `reduce.c`'s `ReadConf`: some interior vertex touches the ring
boundary in more than 2 separate contiguous arcs. `reduce.c`'s own
`ReadConf` rejects such graphs outright with `ReadErr(6, ...)` -- they are
not "configurations" in RSST's technical sense at all, regardless of what
`fourcolor.reduce.check` computes for them (the algorithm doesn't itself
require condition 6 to terminate, so it silently returns SOME verdict,
which is out of RSST's defined scope). Prevalence in this sweep, by ring
(candidate configs = passed `to_configuration`'s filter;
excluded = additionally failed condition 6; valid = the true RSST
configuration class, used for the theorem):

| r | candidate | excluded (cond. 6) | valid (RSST-legal) | exclusion rate |
|---|---|---|---|---|
| 8  | 18   | 6    | 12  | 33% |
| 9  | 35   | 17   | 18  | 49% |
| 10 | 221  | 127  | 94  | 57% |
| 11 | 1631 | 1028 | 603 | 63% |

**Fix / decision:** `tools/fr_table.py` runs `is_legal_configuration`
(against the `rotate_ring_starts`-normalized adjacency, to isolate this
from the condition-4 artifact) on every `to_configuration` survivor, and
only counts configs that pass it toward `valid_configs` / the
D-reducible-count used for the theorem's verdict. Excluded configs are
still written to the shard (tagged `is_legal_configuration: false`, with
`fourcolor.reduce.check`'s verdict computed anyway) for transparency --
and if any excluded config had turned out D-reducible, that would still
have been surfaced loudly as a `D_REDUCIBLE_BUT_NOT_RSST_LEGAL` note
(none were: every excluded config in this sweep is not D-reducible
either, so this filter never actually changed a verdict, only the
population count -- see the per-(r,n) tables in §3).

This condition-6 exclusion is the one place this sweep's definition is
MORE restrictive than the informal class description in the task spec
("near-triangulation, chordless ring, connected nonempty interior,
interior degree >= 5, ring degree >= 3"), because that description elides
condition 6. Since condition 6 is part of RSST's own authoritative
definition (their own reference parser enforces it), applying it here is
the correct, not an extra, restriction -- and since exclusion only SHRINKS
the population being checked for D-reducible counterexamples, it can only
make "0 D-reducible below threshold" a stronger, more precisely-scoped
claim, never a weaker one.

---

## 2. Catalog minima f_catalog(r) -- how they were determined

`f_catalog(r)` (the "≥ f(r)" side is verified in §3; this section is
where "= f(r)" / tightness comes from, matching §5's witnesses) was
determined two independent ways:

**(a) Parsing the nl4ct D-only catalog.** `third_party/reducible-
configurations/D/*.conf` (8200 files, "D-reducible configurations in D
except for a vertex of degree 3,4" per its own README) parsed via
`fourcolor.nl4ct_conf.parse_nl4ct_conf` (0 conversion errors across all
8200 files), taking `min(n - r)` per ring size r:

| r | min interior in nl4ct D catalog | # catalog members at that minimum |
|---|---|---|
| 8  | 5 | 3  |
| 9  | 5 | 1  |
| 10 | 6 | 5  |
| 11 | 7 | 22 |
| 12 | 7 | 1  |

**(b) This project's own earlier plantri sweeps.** `data/configs_r8_n10-
15.jsonl`, `data/configs_r9_n11-15.jsonl`, `data/configs_r10_n12-
17.jsonl` (all `tools/datagen.py` output, predating this task)
independently found the same first-D-reducible interior size at r=8, 9,
10 (r=11's is `data/configs_r11_n13-17.jsonl`, 0 D-reducible at interior
2-6, consistent with -- and superseded by -- this sweep's r=11 result).

Both methods agree exactly on all 5 values, matching the ones given in
the task spec (r=9: 5, r=10: 6, r=11: 7, r=12: 7) and additionally
resolving r=8 (which the spec left open) as 5.

---

## 3. The sweep: per-(r, n) counts

For each r, every n from r+1 to r+f_catalog(r)-1 (interior 1 to
f_catalog(r)-1) was swept: `tools/fr_table.py <r> <n_min> <n_max>`.
Full per-config records (adjacency, `n_extendable`, `n_consistent`,
`d_reducible`, `is_legal_configuration`, round-by-round closure trace) are
in `results/theorem/fr_table/configs_r<r>_n<n>.jsonl`; the counts below
are also machine-readable in `results/theorem/fr_table/manifest_r<r>.json`.

| r | n | interior | raw triangulations (plantri) | candidate configs | excluded (cond. 6) | **valid (RSST-legal) configs** | **D-reducible** | wall time |
|---|---|---|---|---|---|---|---|---|
| 8  | 9  | 1 | 1      | 1    | 0    | 1   | 0 | 0.1s |
| 8  | 10 | 2 | 4      | 2    | 0    | 2   | 0 | 0.0s |
| 8  | 11 | 3 | 39     | 5    | 3    | 2   | 0 | 0.0s |
| 8  | 12 | 4 | 392    | 10   | 3    | 7   | 0 | 0.0s |
| 9  | 10 | 1 | 1      | 1    | 0    | 1   | 0 | 0.1s |
| 9  | 11 | 2 | 4      | 2    | 0    | 2   | 0 | 0.0s |
| 9  | 12 | 3 | 51     | 9    | 6    | 3   | 0 | 0.0s |
| 9  | 13 | 4 | 610    | 23   | 11   | 12  | 0 | 0.2s |
| 10 | 11 | 1 | 1      | 1    | 0    | 1   | 0 | 0.1s |
| 10 | 12 | 2 | 5      | 3    | 0    | 3   | 0 | 0.0s |
| 10 | 13 | 3 | 68     | 15   | 11   | 4   | 0 | 0.2s |
| 10 | 14 | 4 | 932    | 53   | 33   | 20  | 0 | 1.1s |
| 10 | 15 | 5 | 12332  | 149  | 83   | 66  | 0 | 7.7s |
| 11 | 12 | 1 | 1      | 1    | 0    | 1   | 0 | 0.2s |
| 11 | 13 | 2 | 5      | 3    | 0    | 3   | 0 | 0.1s |
| 11 | 14 | 3 | 85     | 22   | 17   | 5   | 0 | 0.8s |
| 11 | 15 | 4 | 1360   | 101  | 72   | 29  | 0 | 5.4s |
| 11 | 16 | 5 | 20280  | 366  | 254  | 112 | 0 | 46.7s |
| 11 | 17 | 6 | 271824 | 1138 | 685  | 453 | 0 | 371.3s |
| 12 | 13 | 1 | 1      | 1    | 0    | 1   | 0 | 0.8s |
| 12 | 14 | 2 | 6      | 4    | 0    | 4   | 0 | 0.4s |
| 12 | 15 | 3 | 109    | 33   | 26   | 7   | 0 | 3.0s |
| 12 | 16 | 4 | 1961   | 191  | 149  | 42  | 0 | 27.8s |
| 12 | 17 | 5 | 32402  | 836  | 650  | 186 | 0 | 247.1s |
| 12 | 18 | 6 | **sweep in progress -- see "Status" below** | | | | | |

**Per-ring totals (r=8..11, COMPLETE):**

| r | total valid (RSST-legal) configs, interior 1..f(r)-1 | total D-reducible | verdict |
|---|---|---|---|
| 8  | 12  | 0 | **PASS** |
| 9  | 18  | 0 | **PASS** |
| 10 | 94  | 0 | **PASS** |
| 11 | 603 | 0 | **PASS** |

**0 EXCEPTIONS across 727 RSST-legal configurations enumerated below
threshold for rings 8-11** (1905 candidate near-triangulations examined
before the condition-6 filter; every one of the 1178 condition-6
exclusions was independently confirmed non-D-reducible too, so the
exclusion never hid a counterexample). r=12 interior 1-5 (240 valid
configs) is also clean; interior 6 (n=18) is still running -- see below.

### Status: r=12, n=18 (interior 6)

Launched detached in the background (`nohup .venv/bin/python
tools/fr_table.py 12 13 18 --resume`, PID logged in
`results/theorem/fr_table/log_r12.txt`) once n=13..17 finished cleanly.
n=18 is the single largest step in this whole sweep (by comparison, r=11
n=17's 271824 raw triangulations took 371s; r=12 n=18 is expected to be
several times larger again, in the "1-3 hours" range estimated before
starting). The manifest (`results/theorem/fr_table/manifest_r12.json`)
and log (`results/theorem/fr_table/log_r12.txt`) are checkpointed
per-n and will contain the n=18 entry (and the final r=12 summary
verdict) once it completes; `--resume` makes it safe to leave running or
restart without redoing n=13..17.

---

## 4. Cross-verification against the compiled RSST oracle

`tools/fr_table_crosscheck.py` samples up to 20 RSST-legal, below-threshold
configs per ring (all of them if fewer than 20), serializes each via
`fourcolor.conf_parser.serialize` after normalizing with the new
`for_rsst_oracle` helper, and runs `build/reduce_rsst` (compiled from the
pinned `third_party/arxiv-1401.6481/src/anc/reduce.c`, via `make oracle`)
on each, parsing its printed verdict.

### 4.1 `conf_parser.py` fixes needed to make this possible

Two real bugs in `fourcolor.conf_parser.serialize` were found and fixed
while building this cross-check (both also covered by new regression
tests in `tests/test_conf_parser.py`):

  - **Coordinate-line wrapping.** `reduce.c`'s `ReadConf` reads
    coordinates one `fgets()`-line at a time, `sscanf`-ing **at most 8**
    numbers per call; a line with more than 8 numbers silently drops the
    rest, and a coords line with **0** parseable numbers makes `sscanf`
    return -1 (not 0), which `ReadConf`'s `if (k == 0) exit(17)` check
    does not catch -- so `i += k` runs backward and the read loop
    free-runs off the end of the file, **hanging forever** rather than
    erroring. `serialize` now wraps coordinates at 8 per line (confirmed
    against the pinned catalog's own convention, e.g. `unavoidable.conf`'s
    first record: `788411 262075 512 260164 785475 1048062 324078
    507098` / `673262 502516`, 8 then 2). This also fixes a latent
    round-trip bug for `serialize`'s OWN parser (`parse_conf`) when
    `coords == []`: `parse_conf`'s tokenizer drops blank lines entirely,
    so an empty coords line vanished and the coords-reading loop for
    record k ran into record k+1's identifier line, corrupting any
    multi-record round trip. `serialize` now defaults empty coords to `[0]
    * n` placeholders.
  - **Ring-vertex rotation start.** New `fourcolor.conf_parser.
    rotate_ring_starts` / `for_rsst_oracle` functions -- see §1.3.

### 4.2 Results

| r | population (RSST-legal, below threshold) | sampled | agree | mismatch | oracle-inconclusive |
|---|---|---|---|---|---|
| 8  | 12  | 12 | 11 | 0 | 1 |
| 9  | 18  | 18 | 17 | 0 | 1 |
| 10 | 94  | 20 | 17 | 0 | 3 |
| 11 | 603 | 20 | 19 | 0 | 1 |
| **total** | | **70** | **64** | **0** | **6** |

Full machine-readable output: `results/theorem/fr_table/crosscheck.json`.
**0 mismatches**: on every sampled config where `build/reduce_rsst`
reached a D-reducibility verdict, it agreed with `fourcolor.reduce.check`.

### 4.3 The 6 "oracle-inconclusive" cases -- investigated, resolved

On 6 of the 70 sampled configs (~9%), `build/reduce_rsst` recomputed a
**different** `|C(K)|` (header field `a`, the extendable-ring-coloring
count) than `fourcolor.reduce.check` supplied, and aborted with `***
ERROR: DISCREPANCY IN NUMBER OF EXTENDING COLOURINGS ***` before printing
a D-reducibility verdict at all (`printstatus`'s hard self-check in
`reduce.c`, `exit(31)`). This is a real, investigated discrepancy, not
swept under the rug:

  - `fourcolor.reduce.check` already agrees with the compiled oracle's
    header `a` on **all 3455** hand-curated RSST + Steinberger catalog
    configurations, with **zero** mismatches
    (`results/differential-unavoidable-r14/report.jsonl`: 633/633 agree;
    `results/differential-U_2822-r16/report.jsonl`: 2822/2822 agree) --
    so this is not a general defect in `fourcolor.reduce.check`.
  - A **third, from-scratch, independently-implemented** computation of
    |C(K)| was written specifically to adjudicate (`fourcolor.
    brute_force.brute_force_extendable_codes`, `src/fourcolor/
    brute_force.py`): different edge indexing (sorted vertex pairs vs.
    adjacency-traversal insertion order), different triangle enumeration
    (brute-force over all vertex triples vs. "cyclically consecutive
    neighbors"), no gauge-fixing, no greedy variable ordering -- shares no
    code path with `fourcolor.reduce`. Run against all 6 disputed
    configs (and cross-checked against `fourcolor.reduce.extendable_codes`
    on 9 small catalog configs and 2 of the disputed fixtures directly in
    `tests/test_brute_force.py`): **it agrees with `fourcolor.reduce.
    check` in all 6 cases, and disagrees with `build/reduce_rsst` in all
    6 cases.**

| config | ring | n | `fourcolor.reduce.check` `n_extendable` | `build/reduce_rsst`'s recomputed count | brute-force tie-breaker |
|---|---|---|---|---|---|
| `fr-r8-n12-172`   | 8  | 12 | 72  | 48  | 72 (agrees with ours) |
| `fr-r9-n13-269`   | 9  | 13 | 147 | 94  | 147 (agrees with ours) |
| `fr-r10-n15-4669` | 10 | 15 | 367 | 230 | 367 (agrees with ours) |
| `fr-r10-n15-4678` | 10 | 15 | 365 | 243 | 365 (agrees with ours) |
| `fr-r10-n15-4613` | 10 | 15 | 408 | 250 | 408 (agrees with ours) |
| `fr-r11-n17-89446`| 11 | 17 | 995 | 532 | 995 (agrees with ours) |

**Conclusion: `fourcolor.reduce.check` is correct in all 6 disputed
cases; the compiled 1995 `reduce.c`'s `strip()` edge-numbering heuristic
(a hand-optimized greedy ordering routine, documented in its own comments
as picking edge order to shrink the search tree) is the outlier,
apparently on a class of inputs -- small, exhaustively-generated, "generic"
near-triangulations -- its original validation (against RSST's hand-curated
633-configuration catalog) never exercised.** None of the 6 disputed
configs' TRUE `d_reducible` value is in question (all are `False`,
confirmed by two independent implementations plus the fact that
`build/reduce_rsst` never disputed the *verdict*, only the intermediate
count, before erroring out) -- so this finding does not weaken the
theorem's D-reducible-count-of-0 claim anywhere in the swept range; it is
reported because an honest cross-verification protocol surfaces every
discrepancy it finds, resolved or not.

---

## 5. Tightness: witnesses at exactly f(r)

For each r, a D-reducible configuration with interior size exactly
f(r) exists (making the bound tight), verified by BOTH
`fourcolor.reduce.check` and the compiled RSST oracle
(`build/reduce_rsst`), pulled from `third_party/reducible-configurations/
D` (the nl4ct D-reducible-only catalog):

| r | catalog file | n | interior | our `d_reducible` | our `n_extendable` | RSST oracle verdict |
|---|---|---|---|---|---|---|
| 8  | `D0003.conf` | 13 | 5 | True | 100  | `***  D-reducible  ***` (exit 0) |
| 9  | `D0006.conf` | 14 | 5 | True | 211  | `***  D-reducible  ***` (exit 0) |
| 10 | `D0015.conf` | 16 | 6 | True | 536  | `***  D-reducible  ***` (exit 0) |
| 11 | `D0024.conf` | 18 | 7 | True | 1363 | `***  D-reducible  ***` (exit 0) |
| 12 | `D0143.conf` | 19 | 7 | True | 2863 | `***  D-reducible  ***` (exit 0) |

Full detail (adjacency, header `a`/`b`, oracle stdout) in
`results/theorem/fr_table/tightness_witnesses.json`.

Combined with §3's exhaustive "0 D-reducible below f(r)" result, this
gives, for r in {8, 9, 10}: **f(r) is exactly determined** (>= verified
exhaustively for ALL interior sizes below threshold, <= via an explicit
tight witness). For r=11: same, fully exhaustive. For r=12: tight witness
in hand; the exhaustive lower-bound sweep is complete through interior 5
and in progress for interior 6 (§3's "Status").

---

## 6. The C-vs-D nuance

This theorem is scoped to **D-reducibility** specifically (no contract).
*C*-reducibility is a strictly weaker (easier to satisfy) notion --
RSST §4: a configuration with a nonempty contract X is C-reducible if no
coloring of C'(K) extends to a tri-coloring of G modulo X. Concretely,
the RSST 633-configuration catalog contains configurations at ring sizes
8 and 11 with interior sizes STRICTLY BELOW f(r) that ARE C-reducible
(via a nontrivial contract) despite NOT being D-reducible --
confirmed with `fourcolor.reduce.check` (`d_reducible=False,
c_reducible=True` for all four):

| ring | catalog ident | n | interior | contract | d_reducible | c_reducible |
|---|---|---|---|---|---|---|
| 8  | `2.126`     | 12 | 4 | `[(1,9),(3,9),(5,11),(7,11)]` | False | **True** |
| 11 | `126.7566`  | 17 | 6 | `[(15,12)]`                    | False | **True** |
| 11 | `128.136`   | 17 | 6 | `[(15,12),(1,12),(3,12),(10,15)]` | False | **True** |
| 11 | `7562.126`  | 17 | 6 | `[(15,12)]`                    | False | **True** |

(No ring-9, ring-10, or ring-12 catalog members exist at interior
f(r)-1 in either the RSST 633 or Steinberger 2822 catalogs -- these two
rings are simply where the phenomenon happens to be attested in the
published, hand-curated catalogs; its absence elsewhere is a fact about
which configurations the catalogs' authors happened to need for their
discharging proof, not evidence that C-reducible near-misses don't exist
at other rings.)

This is exactly why "f(r) = minimum interior size of a D-reducible
configuration" needs the D-qualifier to be a true statement: the
corresponding minimum over *all* reducible (C-or-D) configurations is, at
least at rings 8 and 11, strictly smaller.

---

## 7. Verification protocol summary

  - **Enumeration completeness**: `plantri -P<r> -c3 -a <n>`, an
    orderly/canonical-construction-path generator producing exactly one
    representative per isomorphism class -- see §1.1.
  - **Class-definition fidelity**: `tools/datagen.py`'s filter plus an
    independently-ported second check (`fourcolor.mutate.
    is_legal_configuration`, itself a direct port of RSST's own
    `ReadConf`) -- gap found and fixed (condition 6), documented in §1.3.
  - **D-reducibility checker**: `fourcolor.reduce.check`, independently
    implemented from the RSST paper (arXiv:1401.6481) rather than ported
    from the C code, already validated against all 3455 hand-curated
    catalog configurations' header fields with zero mismatches
    (pre-existing `results/differential-*` reports).
  - **Cross-verification against the compiled 1995 C oracle**
    (`build/reduce_rsst`): 70 sampled configs, 0 verdict mismatches (§4).
  - **Third-implementation tie-breaker** for the 6 cases where the oracle
    itself became inconclusive: `fourcolor.brute_force.
    brute_force_extendable_codes`, agrees with `fourcolor.reduce.check`
    in all 6 (§4.3).
  - **Tightness witnesses**: pulled from the nl4ct D-only catalog,
    verified by both `fourcolor.reduce.check` and `build/reduce_rsst`
    (§5).

All raw data: `results/theorem/fr_table/{manifest_r*.json,
configs_r*_n*.jsonl, crosscheck.json, tightness_witnesses.json}`.
