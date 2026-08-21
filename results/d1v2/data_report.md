# D1-v2 data layer: per-round survivor-SET traces (rings 8-10)

Full per-round survivor SETS (not count buckets) for D-reducibility closure on rings 8, 9, 10, assembled from the existing corpus (data/d1_corpus.jsonl) plus new plantri generation at n=18 -- one ring size beyond anything in the prior corpus. Every record's set_trace comes from a single fourcolor.reduce.check(record_sets=True) call on its own stored adjacency (not copied/joined from a separate source), so trace/verdict/set_trace are self-consistent by construction; the independent cross-check below re-derives the counts trace a SECOND time via a separate check() call to catch encoding bugs.

## Code index maps

| ring r | n canonical codes | file |
|---|---|---|
| 8 | 1094 | data/v2/code_index_r8.json |
| 9 | 3281 | data/v2/code_index_r9.json |
| 10 | 9842 | data/v2/code_index_r10.json |

## Per-ring totals and class balance

| ring r | n configs | d_reducible | not reducible | frac reducible | boundary (total) | boundary: non-red, small C\' (0<n<=50) | boundary: reducible, rounds>=6 |
|---|---|---|---|---|---|---|---|
| 8 | 1432 | 1219 | 213 | 0.851 | 16 | 1 | 15 |
| 9 | 2411 | 1738 | 673 | 0.721 | 193 | 0 | 193 |
| 10 | 3269 | 1287 | 1982 | 0.394 | 776 | 0 | 776 |

## Source breakdown (corpus vs new plantri n=18)

- ring 8: {'corpus:rsst633': 5, 'corpus:steinberger2822': 1, 'corpus:generated': 1156, 'plantri_new': 270}
- ring 9: {'corpus:rsst633': 8, 'corpus:steinberger2822': 8, 'corpus:generated': 1430, 'plantri_new': 965}
- ring 10: {'corpus:rsst633': 31, 'corpus:steinberger2822': 37, 'corpus:generated': 1677, 'corpus:nl4ct_pool': 1, 'plantri_new': 1523}

## Set-trace size distributions

| ring r | mean codes/round (all rounds) | max codes/round | mean round-0 size | max round-0 size | mean rounds/config | max rounds/config |
|---|---|---|---|---|---|---|
| 8 | 275.9 | 1041 | 950.2 | 1041 | 2.82 | 9 |
| 9 | 741.8 | 3175 | 2981.8 | 3175 | 4.13 | 12 |
| 10 | 2197.8 | 9629 | 9261.0 | 9629 | 6.05 | 17 |

## Storage

- `data/v2/code_index_r10.json`: 56.6KB (57979 bytes)
- `data/v2/code_index_r8.json`: 5.4KB (5490 bytes)
- `data/v2/code_index_r9.json`: 18.2KB (18612 bytes)
- `data/v2/traces_r10.jsonl`: 288.1MB (302142101 bytes)
- `data/v2/traces_r8.jsonl`: 8.4MB (8838587 bytes)
- `data/v2/traces_r9.jsonl`: 51.9MB (54403493 bytes)
- **total**: 348.5MB (365466262 bytes)

## Sanity check: round-0..N set SIZES vs an independently recomputed counts trace

Sampled 100 random configs (seed=0) across all three rings from data/v2/traces_r*.jsonl, rebuilt each Configuration from its stored adjacency, called `fourcolor.reduce.check()` fresh (WITHOUT record_sets, a distinct code path from the one that produced the stored set_trace), and compared `len(set_trace[i])` per round against the freshly recomputed `trace[i]` counts, plus `rounds`, `n_consistent`, and `d_reducible` agreement.

**Result: 100/100 exact matches.**

## New plantri n=18 generation status

plantri's search-tree size (and hence full-enumeration wall time) at n=18 is far beyond a single ~30-minute budget for these ring sizes (measured: ~33s CPU per 1/200th `res/mod` split-shard, roughly independent of ring, i.e. a full unsplit n=18 run is on the order of 1-3+ hours per ring). Each (ring, n=18) job runs `res/mod`-split shards to completion one at a time (never truncating a partially-read plantri stream) in a fixed pseudo-random shard order (spread across the whole search space, not a biased prefix), stopping cleanly at a wall-clock budget with a resumable checkpoint.

- ring 8, n=18: 27/200 res/mod shards done, PARTIAL (resumable via --resume), 270 configs kept so far out of 43022929 disk triangulations scanned (elapsed 1787334165.3888042).
- ring 9, n=18: 75/200 res/mod shards done, PARTIAL (resumable via --resume), 965 configs kept so far out of 31568962 disk triangulations scanned (elapsed 1787335884.030433).
- ring 10, n=18: 97/200 res/mod shards done, PARTIAL (resumable via --resume), 1526 configs kept so far out of 9070646 disk triangulations scanned (elapsed 1787337605.626561).

Re-run `tools/d1v2_datagen.py plantri --resume` to continue any partial job, then `tools/d1v2_datagen.py merge` to fold newly-completed shards into `traces_r{r}.jsonl`, then re-run this report.

