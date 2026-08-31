# STATE — read this first

Last updated 2026-08-31. This file is the entry point after any gap. It says what is
DONE (do not redo), what is OPEN, and what the next move is. The numbered docs
(00–03) are the historical design records; `03-MASS-LAW-PROGRAM.md` remains the
canonical state file for the coloring-mass line specifically.

## What this project is

Machine digestion of the Four Color Theorem's computer proofs: verify them
independently, measure how they actually work, shrink them, and hunt for the
organizing principle behind reducibility.

## RESULTS (all committed, all with artifacts)

| # | Result | Grade | Artifact |
|---|---|---|---|
| 1 | **No nonnegative rule amounts on the 84 rule shapes of arXiv:2603.24880 close the discharging argument over the 5,895 ring<=14 configurations.** 12-row Farkas certificate, verified in exact rationals without a solver. Bears on Steinberger's 2009 open question. | Certified | `results/steinberger/LP-SCHEMA-RESULT.md`, `tools/verify_farkas.py` |
| 2 | **f(r) = 5,5,6,7,7,8 for r=8..13** — minimum interior vertices for D-reducibility. Exhaustive, tight, triple-verified. First quantitative extension of Birkhoff (1913). | Proven | `results/theorem/fr_table/THEOREM.md` |
| 3 | **First independent verification of all three published 4CT proofs**: 633 (RSST) + 2,822 (Steinberger) + 7,697 of the 2026 pool, from a checker built from the papers' mathematics, not ported code. Plus full 2026 pipeline reproduction. | Verified | `results/differential-*/`, `results/p3/runs/` |
| 4 | **430 of the 2026 proof's 8,200 configurations are removable** — pipeline re-verifies end to end at 7,770. | Verified | `results/p3/runs/batch1b/` |
| 5 | **`reduce.c` (the canonical 1995 reducibility oracle) miscomputes \|Phi\| on 6 of 70 generic inputs** (30–46% undercount), adjudicated by a third independent implementation. Fail-safe: it aborts rather than returning a wrong verdict. | Verified | `results/theorem/fr_table/THEOREM.md` §4.3, `src/fourcolor/brute_force.py` |
| 6 | **Wheel closed form** a = (2^r + 2(-1)^r)/6, exact with equality case; improved cap a <= 11*2^(r+k-7), tight at wheels; gamma=3/2 at k=2. | Proven | `results/mass-law/PROOF-SHARP-CAP.md` |
| 7 | **Obstruction theorem**: no proof factoring through a <= P(S,4)/24 can reach the 4/3 constant (explicit 10-vertex witness, floor 61/43). | Proven | same file |
| 8 | **Coloring-mass law** (conjecture): D-reducible => a >= 2.4^r/13; with the cap it reproduces the f(r) table to within one vertex at every ring. | Corpus-supported | `results/mass-law/threshold-candidates.md` |

## OPEN / NEXT MOVES

1. **Ship the paper.** `paper/short.tex` (certificate thesis, calibrated length) is the
   submission candidate; `paper/main.tex` is the 43-page extended record; `paper/AUDIT.md`
   lists 38 findings (6 BLOCKER) — check they are all applied to short.tex before sending.
   Target: arXiv (math.CO primary, cs.DM + cs.LO cross-list) then EJC or SIAM J. Discrete Math.
2. **File GitHub issues** on github.com/near-linear-4ct: the 430 removable configs and the
   `reduce.c` defect. Free, time-sensitive, opens contact with the six authors.
3. **Falsification sweep (do before publishing the mass law).** Rings 11–16 contain ZERO
   adversarially generated D-reducibles — all catalog. Generate adversarial D-reducibles at
   r=11..13 and test the threshold. A single config at r=12 with a <= 2,856 kills it.
4. **Second instance** — run `tools/lp_discharge.py` machinery on a published discharging LP
   (a Bousquet et al. square-coloring instance). Turns a one-off into a method. ~1 week.
5. **Lean-check the 12-row certificate** — 12 rows of rationals, 84 columns. Template exists
   (LRAT-Catcher, arXiv:2607.00815). Upgrades grade to Proven on the arithmetic half. ~weekend.
6. **Harder, blocked**: the sharp cap via Temperley–Lieb transfer matrices (the only route the
   obstruction theorem leaves open); the threshold half (no proof route identified);
   deeper pruning (needs full attribution, not first-match); f(r) beyond r=13 (compute).

## KNOWN WEAK POINTS (state these in any write-up)

- "Unblocked != realizable": four certificate rows describe wheels shown unblocked by the
  pool, not shown to occur in a minimum counterexample. Same standard the published proof
  uses, but a referee will push here.
- 3 of 12 certificate rows rest on a reconstruction of the degree-5/6 discharge (the paper
  discharges it by one sentence citing Steinberger 2010; released code never implements it).
- Rings 11–16 of the mass-law frontier are catalog-only (see open move 3).
- The machine-learning line produced no result the scripts could not. Reported honestly and
  separately; do not frame this project as AI discovery.

## OPERATIONAL

- Repo: this directory. `.venv` = Python 3.12; `make test` = full suite (~295 tests; 2
  pre-existing failures in `test_d1v2_interrogate` are ring-8 data drift, unrelated).
- Long runs: `nohup ... & disown`, prefix with `caffeinate -i` (this Mac sleeps after 1 min idle
  and has killed two agents). One heavy job at a time — 16GB.
- Primary sources pinned + checksummed in `third_party/` (4 arXiv bundles, plantri, the
  near-linear-4ct repos). `tools/fetch_sources.py` re-verifies.
- Repo is ~4.9GB; `data/` and run artifacts are gitignored. Results are committed.
