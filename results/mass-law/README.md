# Coloring-Mass Law: machine-checked lemma registry

`lemma_log.jsonl` is the provenance trail for the M2/M3 proof work
(03-MASS-LAW-PROGRAM.md). Every candidate statement about configurations gets
run through `tools/test_lemma.py` against the whole labeled corpus BEFORE
anyone tries to prove it, and the run appends a receipt here.

## Running a candidate

```
.venv/bin/python tools/test_lemma.py --summary
.venv/bin/python tools/test_lemma.py --check "rec.d_reducible implies rec.a >= 94 * 2.4**(rec.r - 8)"
.venv/bin/python tools/test_lemma.py --implies "rec.d_reducible" "rec.a >= 94"
.venv/bin/python tools/test_lemma.py --bound  "rec.a <= 2**(rec.r + rec.k - 3)"
.venv/bin/python tools/test_lemma.py --gap-table
```

Statement syntax and the evaluation contract (scalar statements run
vectorized and are cross-checked against per-record evaluation; adjacency /
trace / hand-feature statements run lazily per record) are documented in
`src/fourcolor/lemma_harness.py`. The corpus (which files, how dedup works,
what `a`/`b`/`k` mean) is documented in `src/fourcolor/lemma_corpus.py`.
Exit code is 0 for HOLDS, 1 for KILLED/VACUOUS, 2 for a bad statement, so a
candidate can be gated in a script.

## Receipt fields

Each line is one claim:

* `id` -- blake2b over (mode, whitespace-normalized statement, filter, corpus
  signature). Timestamp-free: the same check on the same corpus is the same
  receipt, and re-running does not duplicate the line.
* `corpus.signature` -- content hash over every record's (canonical form, r,
  n, a, b, d_reducible). Changes if and only if the corpus changes, which is
  what makes an old verdict re-auditable.
* `verdict` -- `HOLDS` (no counterexample in the corpus -- NOT a proof),
  `KILLED` (counterexamples listed), `VACUOUS` (no record satisfies the
  antecedent, so the statement says nothing).
* `n_true` / `n_false` / `support` / `per_ring` / `counterexamples` (up to 20,
  with ident + source file so any one can be pulled and re-checked against
  `fourcolor.reduce.check`).

`HOLDS` means "survived the corpus", nothing more. The lesson from
`results/theorem/stress_test.md` (236 oracle-confirmed false positives from a
pool-zero-FP rule set) applies: a surviving statement is a candidate worth a
proof attempt, not a theorem.

## Baseline entries

The three receipts created when the harness was built, which also serve as its
self-validation:

| mode | statement | verdict |
|---|---|---|
| bound | `rec.a <= 2**(rec.r + rec.k - 3)` (the Cap, in its trivial provable form) | HOLDS on 59,142 |
| gap_table | min a over D-reducible > max a over below-threshold negatives, per ring | HOLDS at all 6 measurable rings (8-13), reproducing the table in 03-MASS-LAW-PROGRAM.md |
| implication | `rec.a >= 94 * 2.4**(rec.r - 8) implies rec.d_reducible` (the CONVERSE of the threshold -- deliberately false) | KILLED, 2,349 counterexamples |
