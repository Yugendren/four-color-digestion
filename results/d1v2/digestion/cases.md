# Ring-10 boundary error-set digestion: control_encoder_summary vs shallow_plus_structural

Same seed-0 probe split as `results/d1v2/v2run/interrogation.json` (reconstructed via `tools/d1v2_interrogate.py`'s own `load_ring_split`, verified against its recorded split sizes; probe-test split stratified-by-label seed=0, test_frac=0.2). 21 of the probe-test split's 98 examples are boundary=True.

- `control_encoder_summary` probe boundary accuracy: 0.9048 (19/21)
- `shallow_plus_structural` probe boundary accuracy: 0.7619 (16/21)

## Confusion breakdown (boundary probe-test examples, n=21)

| group | n | idents |
|---|---|---|
| `encoder_right_struct_wrong` | 4 | gen-r10-n18-res125-21693, gen-r10-n18-res62-30377, gen-r10-n18-res161-25540, gen-r10-n18-res125-21698 |
| `struct_right_encoder_wrong` | 1 | gen-r10-n17-527317 |
| `both_right` | 15 | gen-r10-n17-515711, gen-r10-n18-res85-32784, gen-r10-n17-498034, gen-r10-n17-528912, gen-r10-n18-res141-28412, gen-r10-n17-518690, gen-r10-n18-res101-30375, 71, gen-r10-n18-res128-32607, gen-r10-n18-res73-36455, gen-r10-n18-res80-35658, gen-r10-n18-res54-37561, gen-r10-n18-res79-21267, gen-r10-n17-518142, gen-r10-n18-res132-27157 |
| `both_wrong` | 1 | gen-r10-n16-29491 |

## encoder_right_struct_wrong: full case dumps

The configs `control_encoder_summary`'s probe gets right and `shallow_plus_structural`'s probe gets wrong -- the target set.

### encoder_right_struct_wrong: ident=gen-r10-n18-res125-21693

- n=18, r=10, d_reducible=True, boundary=True
- source=plantri_new, canonical_key=1:3:2,11,10|2:3:1,3,11|3:4:2,4,12,11|4:4:3,5,13,12|5:5:4,6,14,15,13|6:3:5,7,14|7:5:6,8,16,17,14|8:3:7,9,16|9:3:8,10,16|10:5:1,11,17,16,9|11:7:1,2,3,12,18,17,10|12:5:3,4,13,18,11|13:5:4,5,15,18,12|14:5:5,6,7,17,15|15:5:5,14,17,18,13|16:5:7,8,9,10,17|17:7:7,16,10,11,18,15,14|18:5:11,12,13,15,17
- n_extendable=621, n_consistent=0
- degree sequence (v=1..n): [5, 3, 5, 4, 4, 3, 3, 5, 3, 3, 5, 7, 5, 5, 5, 7, 5, 5]
- adjacency:
  ```
  1: [2, 11, 12, 13, 10]
  2: [1, 3, 11]
  3: [2, 4, 17, 14, 11]
  4: [3, 5, 18, 17]
  5: [16, 18, 4, 6]
  6: [16, 5, 7]
  7: [16, 6, 8]
  8: [12, 16, 7, 9, 13]
  9: [13, 8, 10]
  10: [1, 13, 9]
  11: [1, 2, 3, 14, 12]
  12: [1, 11, 14, 15, 16, 8, 13]
  13: [1, 12, 8, 9, 10]
  14: [11, 3, 17, 15, 12]
  15: [12, 14, 17, 18, 16]
  16: [12, 15, 18, 5, 6, 7, 8]
  17: [3, 4, 18, 15, 14]
  18: [15, 17, 4, 5, 16]
  ```
- structural candidates: {"n_deg5_interior": 6.0, "n_deg5_total": 9.0, "max_run_deg5_ring": 1.0, "max_run_const_degree_ring": 2.0, "n_triangles_deg5": 4.0, "n_diamonds_deg5": 3.0, "n_extendable": 621.0, "n_extendable_ratio": 0.03155006858710562, "n_consistent": 0.0}
- trace shape: rounds=6, survivor_counts=[9221, 1448, 1065, 765, 344, 97, 0], monotonic_nonincreasing=True, first_round_drop_ratio=0.8429671402234031, final_survivors=0
- set_trace (full raw per-round surviving-code-index lists, up to thousands of ints each round -- NOT reproduced here since it isn't human-legible as raw integers; the survivor_counts trajectory above IS the human-legible summary of it, and the full raw list is retrievable by ident from `data/v2/traces_r10.jsonl` (ident=gen-r10-n18-res125-21693) or `results/d1v2/digestion/error_set.json`)

### encoder_right_struct_wrong: ident=gen-r10-n18-res62-30377

- n=18, r=10, d_reducible=True, boundary=True
- source=plantri_new, canonical_key=1:3:2,11,10|2:3:1,3,11|3:4:2,4,12,11|4:3:3,5,12|5:7:4,6,13,14,15,16,12|6:3:5,7,13|7:3:6,8,13|8:5:7,9,17,14,13|9:3:8,10,17|10:5:1,11,18,17,9|11:7:1,2,3,12,16,18,10|12:5:3,4,5,16,11|13:5:5,6,7,8,14|14:5:5,13,8,17,15|15:5:5,14,17,18,16|16:5:5,15,18,11,12|17:6:8,9,10,18,15,14|18:5:10,11,16,15,17
- n_extendable=644, n_consistent=0
- degree sequence (v=1..n): [7, 3, 4, 3, 3, 5, 3, 5, 3, 3, 5, 5, 5, 5, 5, 7, 5, 6]
- adjacency:
  ```
  1: [2, 11, 12, 13, 14, 15, 10]
  2: [1, 3, 11]
  3: [2, 4, 16, 11]
  4: [3, 5, 16]
  5: [16, 4, 6]
  6: [16, 5, 7, 18, 17]
  7: [18, 6, 8]
  8: [14, 18, 7, 9, 15]
  9: [15, 8, 10]
  10: [1, 15, 9]
  11: [1, 2, 3, 16, 12]
  12: [1, 11, 16, 17, 13]
  13: [1, 12, 17, 18, 14]
  14: [1, 13, 18, 8, 15]
  15: [1, 14, 8, 9, 10]
  16: [11, 3, 4, 5, 6, 17, 12]
  17: [12, 16, 6, 18, 13]
  18: [13, 17, 6, 7, 8, 14]
  ```
- structural candidates: {"n_deg5_interior": 6.0, "n_deg5_total": 8.0, "max_run_deg5_ring": 1.0, "max_run_const_degree_ring": 2.0, "n_triangles_deg5": 2.0, "n_diamonds_deg5": 0.0, "n_extendable": 644.0, "n_extendable_ratio": 0.032718589645887315, "n_consistent": 0.0}
- trace shape: rounds=6, survivor_counts=[9198, 1332, 1014, 623, 215, 52, 0], monotonic_nonincreasing=True, first_round_drop_ratio=0.8551859099804305, final_survivors=0
- set_trace (full raw per-round surviving-code-index lists, up to thousands of ints each round -- NOT reproduced here since it isn't human-legible as raw integers; the survivor_counts trajectory above IS the human-legible summary of it, and the full raw list is retrievable by ident from `data/v2/traces_r10.jsonl` (ident=gen-r10-n18-res62-30377) or `results/d1v2/digestion/error_set.json`)

### encoder_right_struct_wrong: ident=gen-r10-n18-res161-25540

- n=18, r=10, d_reducible=True, boundary=True
- source=plantri_new, canonical_key=1:3:2,11,10|2:3:1,3,11|3:4:2,4,12,11|4:5:3,5,13,14,12|5:3:4,6,13|6:4:5,7,15,13|7:4:6,8,16,15|8:4:7,9,17,16|9:4:8,10,14,17|10:5:1,11,12,14,9|11:5:1,2,3,12,10|12:5:3,4,14,10,11|13:6:4,5,6,15,18,14|14:7:4,13,18,17,9,10,12|15:5:6,7,16,18,13|16:5:7,8,17,18,15|17:5:8,9,14,18,16|18:5:13,15,16,17,14
- n_extendable=611, n_consistent=0
- degree sequence (v=1..n): [5, 4, 4, 4, 4, 3, 5, 4, 3, 3, 7, 5, 5, 5, 5, 6, 5, 5]
- adjacency:
  ```
  1: [2, 11, 12, 13, 10]
  2: [1, 3, 14, 11]
  3: [2, 4, 17, 14]
  4: [3, 5, 18, 17]
  5: [16, 18, 4, 6]
  6: [16, 5, 7]
  7: [11, 16, 6, 8, 12]
  8: [12, 7, 9, 13]
  9: [13, 8, 10]
  10: [1, 13, 9]
  11: [1, 2, 14, 15, 16, 7, 12]
  12: [1, 11, 7, 8, 13]
  13: [1, 12, 8, 9, 10]
  14: [2, 3, 17, 15, 11]
  15: [11, 14, 17, 18, 16]
  16: [11, 15, 18, 5, 6, 7]
  17: [3, 4, 18, 15, 14]
  18: [15, 17, 4, 5, 16]
  ```
- structural candidates: {"n_deg5_interior": 6.0, "n_deg5_total": 8.0, "max_run_deg5_ring": 1.0, "max_run_const_degree_ring": 4.0, "n_triangles_deg5": 3.0, "n_diamonds_deg5": 1.0, "n_extendable": 611.0, "n_extendable_ratio": 0.031042015952852716, "n_consistent": 0.0}
- trace shape: rounds=7, survivor_counts=[9231, 1451, 1153, 826, 425, 107, 12, 0], monotonic_nonincreasing=True, first_round_drop_ratio=0.8428122630267577, final_survivors=0
- set_trace (full raw per-round surviving-code-index lists, up to thousands of ints each round -- NOT reproduced here since it isn't human-legible as raw integers; the survivor_counts trajectory above IS the human-legible summary of it, and the full raw list is retrievable by ident from `data/v2/traces_r10.jsonl` (ident=gen-r10-n18-res161-25540) or `results/d1v2/digestion/error_set.json`)

### encoder_right_struct_wrong: ident=gen-r10-n18-res125-21698

- n=18, r=10, d_reducible=True, boundary=True
- source=plantri_new, canonical_key=1:3:2,11,10|2:3:1,3,11|3:4:2,4,12,11|4:6:3,5,13,14,15,12|5:3:4,6,13|6:3:5,7,13|7:5:6,8,16,14,13|8:5:7,9,17,18,16|9:3:8,10,17|10:5:1,11,12,17,9|11:5:1,2,3,12,10|12:7:3,4,15,18,17,10,11|13:5:4,5,6,7,14|14:5:4,13,7,16,15|15:5:4,14,16,18,12|16:5:7,8,18,15,14|17:5:8,9,10,12,18|18:5:8,17,12,15,16
- n_extendable=592, n_consistent=0
- degree sequence (v=1..n): [5, 3, 5, 5, 3, 3, 6, 4, 3, 3, 5, 7, 5, 5, 5, 5, 5, 5]
- adjacency:
  ```
  1: [2, 11, 12, 13, 10]
  2: [1, 3, 11]
  3: [2, 4, 16, 14, 11]
  4: [3, 5, 18, 17, 16]
  5: [4, 6, 18]
  6: [7, 18, 5]
  7: [12, 15, 17, 18, 6, 8]
  8: [12, 7, 9, 13]
  9: [13, 8, 10]
  10: [1, 13, 9]
  11: [1, 2, 3, 14, 12]
  12: [1, 11, 14, 15, 7, 8, 13]
  13: [1, 12, 8, 9, 10]
  14: [11, 3, 16, 15, 12]
  15: [12, 14, 16, 17, 7]
  16: [3, 4, 17, 15, 14]
  17: [15, 16, 4, 18, 7]
  18: [7, 17, 4, 5, 6]
  ```
- structural candidates: {"n_deg5_interior": 7.0, "n_deg5_total": 10.0, "max_run_deg5_ring": 2.0, "max_run_const_degree_ring": 2.0, "n_triangles_deg5": 7.0, "n_diamonds_deg5": 7.0, "n_extendable": 592.0, "n_extendable_ratio": 0.030076715947772188, "n_consistent": 0.0}
- trace shape: rounds=6, survivor_counts=[9250, 1493, 1124, 841, 413, 107, 0], monotonic_nonincreasing=True, first_round_drop_ratio=0.8385945945945946, final_survivors=0
- set_trace (full raw per-round surviving-code-index lists, up to thousands of ints each round -- NOT reproduced here since it isn't human-legible as raw integers; the survivor_counts trajectory above IS the human-legible summary of it, and the full raw list is retrievable by ident from `data/v2/traces_r10.jsonl` (ident=gen-r10-n18-res125-21698) or `results/d1v2/digestion/error_set.json`)

## Contrast: both_right (showing up to 3 of 15)

### both_right: ident=gen-r10-n17-515711

- n=17, r=10, d_reducible=True, boundary=True
- source=corpus:generated, canonical_key=1:3:2,11,10|2:3:1,3,11|3:5:2,4,12,13,11|4:3:3,5,12|5:4:4,6,14,12|6:4:5,7,15,14|7:3:6,8,15|8:4:7,9,16,15|9:3:8,10,16|10:6:1,11,13,17,16,9|11:5:1,2,3,13,10|12:5:3,4,5,14,13|13:6:3,12,14,17,10,11|14:6:5,6,15,17,13,12|15:6:6,7,8,16,17,14|16:5:8,9,10,17,15|17:5:10,13,14,15,16
- n_extendable=622, n_consistent=0
- degree sequence (v=1..n): [3, 4, 4, 3, 4, 3, 6, 3, 3, 5, 5, 6, 6, 5, 6, 5, 5]
- adjacency:
  ```
  1: [2, 11, 10]
  2: [1, 3, 12, 11]
  3: [2, 4, 15, 12]
  4: [3, 5, 15]
  5: [4, 6, 17, 15]
  6: [7, 17, 5]
  7: [13, 16, 17, 6, 8, 14]
  8: [14, 7, 9]
  9: [10, 14, 8]
  10: [1, 11, 13, 14, 9]
  11: [1, 2, 12, 13, 10]
  12: [2, 3, 15, 16, 13, 11]
  13: [11, 12, 16, 7, 14, 10]
  14: [10, 13, 7, 8, 9]
  15: [3, 4, 5, 17, 16, 12]
  16: [12, 15, 17, 7, 13]
  17: [15, 5, 6, 7, 16]
  ```
- structural candidates: {"n_deg5_interior": 4.0, "n_deg5_total": 5.0, "max_run_deg5_ring": 1.0, "max_run_const_degree_ring": 2.0, "n_triangles_deg5": 0.0, "n_diamonds_deg5": 0.0, "n_extendable": 622.0, "n_extendable_ratio": 0.03160087385053092, "n_consistent": 0.0}
- trace shape: rounds=6, survivor_counts=[9220, 1574, 1215, 765, 276, 39, 0], monotonic_nonincreasing=True, first_round_drop_ratio=0.8292841648590021, final_survivors=0
- set_trace (full raw per-round surviving-code-index lists, up to thousands of ints each round -- NOT reproduced here since it isn't human-legible as raw integers; the survivor_counts trajectory above IS the human-legible summary of it, and the full raw list is retrievable by ident from `data/v2/traces_r10.jsonl` (ident=gen-r10-n17-515711) or `results/d1v2/digestion/error_set.json`)

### both_right: ident=gen-r10-n18-res85-32784

- n=18, r=10, d_reducible=True, boundary=True
- source=plantri_new, canonical_key=1:3:2,11,10|2:3:1,3,11|3:4:2,4,12,11|4:4:3,5,13,12|5:3:4,6,13|6:3:5,7,13|7:4:6,8,14,13|8:5:7,9,15,16,14|9:3:8,10,15|10:5:1,11,17,15,9|11:6:1,2,3,12,17,10|12:6:3,4,13,18,17,11|13:7:4,5,6,7,14,18,12|14:5:7,8,16,18,13|15:5:8,9,10,17,16|16:5:8,15,17,18,14|17:6:10,11,12,18,16,15|18:5:12,13,14,16,17
- n_extendable=679, n_consistent=0
- degree sequence (v=1..n): [5, 3, 5, 4, 3, 3, 4, 4, 3, 3, 5, 6, 6, 5, 5, 6, 5, 7]
- adjacency:
  ```
  1: [2, 11, 12, 13, 10]
  2: [1, 3, 11]
  3: [2, 4, 17, 14, 11]
  4: [3, 5, 18, 17]
  5: [4, 6, 18]
  6: [18, 5, 7]
  7: [16, 18, 6, 8]
  8: [13, 16, 7, 9]
  9: [13, 8, 10]
  10: [1, 13, 9]
  11: [1, 2, 3, 14, 12]
  12: [1, 11, 14, 15, 16, 13]
  13: [1, 12, 16, 8, 9, 10]
  14: [11, 3, 17, 15, 12]
  15: [12, 14, 17, 18, 16]
  16: [12, 15, 18, 7, 8, 13]
  17: [3, 4, 18, 15, 14]
  18: [15, 17, 4, 5, 6, 7, 16]
  ```
- structural candidates: {"n_deg5_interior": 4.0, "n_deg5_total": 6.0, "max_run_deg5_ring": 1.0, "max_run_const_degree_ring": 2.0, "n_triangles_deg5": 3.0, "n_diamonds_deg5": 2.0, "n_extendable": 679.0, "n_extendable_ratio": 0.0344967738657725, "n_consistent": 0.0}
- trace shape: rounds=6, survivor_counts=[9163, 1286, 883, 478, 187, 9, 0], monotonic_nonincreasing=True, first_round_drop_ratio=0.8596529520899269, final_survivors=0
- set_trace (full raw per-round surviving-code-index lists, up to thousands of ints each round -- NOT reproduced here since it isn't human-legible as raw integers; the survivor_counts trajectory above IS the human-legible summary of it, and the full raw list is retrievable by ident from `data/v2/traces_r10.jsonl` (ident=gen-r10-n18-res85-32784) or `results/d1v2/digestion/error_set.json`)

### both_right: ident=gen-r10-n17-498034

- n=17, r=10, d_reducible=True, boundary=True
- source=corpus:generated, canonical_key=1:3:2,11,10|2:3:1,3,11|3:4:2,4,12,11|4:4:3,5,13,12|5:4:4,6,14,13|6:3:5,7,14|7:4:6,8,15,14|8:4:7,9,16,15|9:4:8,10,17,16|10:4:1,11,17,9|11:6:1,2,3,12,17,10|12:5:3,4,13,17,11|13:7:4,5,14,15,16,17,12|14:5:5,6,7,15,13|15:5:7,8,16,13,14|16:5:8,9,17,13,15|17:6:9,10,11,12,13,16
- n_extendable=613, n_consistent=0
- degree sequence (v=1..n): [4, 4, 3, 4, 4, 4, 4, 3, 3, 4, 7, 5, 5, 5, 5, 6, 6]
- adjacency:
  ```
  1: [2, 11, 12, 10]
  2: [1, 3, 13, 11]
  3: [2, 4, 13]
  4: [3, 5, 14, 13]
  5: [14, 4, 6, 15]
  6: [15, 5, 7, 16]
  7: [16, 6, 8, 17]
  8: [17, 7, 9]
  9: [10, 17, 8]
  10: [1, 12, 17, 9]
  11: [1, 2, 13, 14, 15, 16, 12]
  12: [1, 11, 16, 17, 10]
  13: [2, 3, 4, 14, 11]
  14: [11, 13, 4, 5, 15]
  15: [11, 14, 5, 6, 16]
  16: [11, 15, 6, 7, 17, 12]
  17: [12, 16, 7, 8, 9, 10]
  ```
- structural candidates: {"n_deg5_interior": 4.0, "n_deg5_total": 4.0, "max_run_deg5_ring": 0.0, "max_run_const_degree_ring": 4.0, "n_triangles_deg5": 0.0, "n_diamonds_deg5": 0.0, "n_extendable": 613.0, "n_extendable_ratio": 0.0311436264797033, "n_consistent": 0.0}
- trace shape: rounds=6, survivor_counts=[9229, 1480, 1089, 752, 400, 116, 0], monotonic_nonincreasing=True, first_round_drop_ratio=0.8396359302199589, final_survivors=0
- set_trace (full raw per-round surviving-code-index lists, up to thousands of ints each round -- NOT reproduced here since it isn't human-legible as raw integers; the survivor_counts trajectory above IS the human-legible summary of it, and the full raw list is retrievable by ident from `data/v2/traces_r10.jsonl` (ident=gen-r10-n17-498034) or `results/d1v2/digestion/error_set.json`)

## Contrast: both_wrong (showing up to 3 of 1)

### both_wrong: ident=gen-r10-n16-29491

- n=16, r=10, d_reducible=True, boundary=True
- source=corpus:generated, canonical_key=1:3:2,11,10|2:3:1,3,11|3:4:2,4,12,11|4:4:3,5,13,12|5:3:4,6,13|6:4:5,7,14,13|7:3:6,8,14|8:4:7,9,15,14|9:4:8,10,16,15|10:4:1,11,16,9|11:6:1,2,3,12,16,10|12:6:3,4,13,15,16,11|13:6:4,5,6,14,15,12|14:5:6,7,8,15,13|15:6:8,9,16,12,13,14|16:5:9,10,11,12,15
- n_extendable=536, n_consistent=0
- degree sequence (v=1..n): [4, 4, 4, 3, 4, 3, 4, 4, 3, 3, 5, 6, 6, 6, 5, 6]
- adjacency:
  ```
  1: [2, 11, 12, 10]
  2: [1, 3, 13, 11]
  3: [2, 4, 15, 13]
  4: [3, 5, 15]
  5: [4, 6, 16, 15]
  6: [16, 5, 7]
  7: [14, 16, 6, 8]
  8: [12, 14, 7, 9]
  9: [12, 8, 10]
  10: [1, 12, 9]
  11: [1, 2, 13, 14, 12]
  12: [1, 11, 14, 8, 9, 10]
  13: [2, 3, 15, 16, 14, 11]
  14: [11, 13, 16, 7, 8, 12]
  15: [3, 4, 5, 16, 13]
  16: [13, 15, 5, 6, 7, 14]
  ```
- structural candidates: {"n_deg5_interior": 2.0, "n_deg5_total": 2.0, "max_run_deg5_ring": 0.0, "max_run_const_degree_ring": 3.0, "n_triangles_deg5": 0.0, "n_diamonds_deg5": 0.0, "n_extendable": 536.0, "n_extendable_ratio": 0.027231621195955902, "n_consistent": 0.0}
- trace shape: rounds=9, survivor_counts=[9306, 1692, 1537, 1366, 1105, 809, 447, 141, 12, 0], monotonic_nonincreasing=True, first_round_drop_ratio=0.8181818181818182, final_survivors=0
- set_trace (full raw per-round surviving-code-index lists, up to thousands of ints each round -- NOT reproduced here since it isn't human-legible as raw integers; the survivor_counts trajectory above IS the human-legible summary of it, and the full raw list is retrievable by ident from `data/v2/traces_r10.jsonl` (ident=gen-r10-n16-29491) or `results/d1v2/digestion/error_set.json`)

## For completeness: struct_right_encoder_wrong (n=1)

### struct_right_encoder_wrong: ident=gen-r10-n17-527317

- n=17, r=10, d_reducible=True, boundary=True
- source=corpus:generated, canonical_key=1:3:2,11,10|2:3:1,3,11|3:4:2,4,12,11|4:4:3,5,13,12|5:4:4,6,14,13|6:3:5,7,14|7:4:6,8,15,14|8:5:7,9,16,17,15|9:3:8,10,16|10:5:1,11,12,16,9|11:5:1,2,3,12,10|12:7:3,4,13,17,16,10,11|13:6:4,5,14,15,17,12|14:5:5,6,7,15,13|15:5:7,8,17,13,14|16:5:8,9,10,12,17|17:5:8,16,12,13,15
- n_extendable=602, n_consistent=0
- degree sequence (v=1..n): [5, 3, 5, 4, 3, 4, 4, 4, 3, 3, 5, 7, 5, 5, 6, 5, 5]
- adjacency:
  ```
  1: [2, 11, 12, 13, 10]
  2: [1, 3, 11]
  3: [2, 4, 16, 14, 11]
  4: [3, 5, 17, 16]
  5: [4, 6, 17]
  6: [15, 17, 5, 7]
  7: [12, 15, 6, 8]
  8: [12, 7, 9, 13]
  9: [13, 8, 10]
  10: [1, 13, 9]
  11: [1, 2, 3, 14, 12]
  12: [1, 11, 14, 15, 7, 8, 13]
  13: [1, 12, 8, 9, 10]
  14: [11, 3, 16, 15, 12]
  15: [12, 14, 16, 17, 6, 7]
  16: [3, 4, 17, 15, 14]
  17: [15, 16, 4, 5, 6]
  ```
- structural candidates: {"n_deg5_interior": 5.0, "n_deg5_total": 7.0, "max_run_deg5_ring": 1.0, "max_run_const_degree_ring": 3.0, "n_triangles_deg5": 2.0, "n_diamonds_deg5": 1.0, "n_extendable": 602.0, "n_extendable_ratio": 0.030584768582025097, "n_consistent": 0.0}
- trace shape: rounds=8, survivor_counts=[9240, 1558, 1320, 1096, 845, 511, 213, 5, 0], monotonic_nonincreasing=True, first_round_drop_ratio=0.8313852813852813, final_survivors=0
- set_trace (full raw per-round surviving-code-index lists, up to thousands of ints each round -- NOT reproduced here since it isn't human-legible as raw integers; the survivor_counts trajectory above IS the human-legible summary of it, and the full raw list is retrievable by ident from `data/v2/traces_r10.jsonl` (ident=gen-r10-n17-527317) or `results/d1v2/digestion/error_set.json`)

## Feature means: encoder_right_struct_wrong vs rest of boundary

encoder_right_struct_wrong: n=4. Rest of VAL boundary (val boundary set minus this group): n=112. Rest of FULL CORPUS boundary (all 776 boundary configs minus this group): n=772.

| feature | encoder_right_struct_wrong mean | rest-of-val-boundary mean | rest-of-full-corpus-boundary mean |
|---|---|---|---|
| `n_deg5_interior` | 6.2500 | 4.8214 | 4.9534 |
| `n_deg5_total` | 8.7500 | 6.2500 | 6.3938 |
| `max_run_deg5_ring` | 1.2500 | 0.8929 | 0.9184 |
| `max_run_const_degree_ring` | 2.5000 | 2.3393 | 2.3044 |
| `n_triangles_deg5` | 4.0000 | 1.6607 | 1.8199 |
| `n_diamonds_deg5` | 2.7500 | 0.8750 | 0.9663 |
| `n_extendable` | 617.0000 | 632.5625 | 630.0518 |
| `n_extendable_ratio` | 0.0313 | 0.0321 | 0.0320 |
| `rounds` | 6.2500 | 6.7143 | 6.7008 |
| `monotonic_nonincreasing_frac` | 1.0000 | 1.0000 | 1.0000 |
| `first_round_drop_ratio` | 0.8449 | 0.8434 | 0.8437 |
| `final_survivors` | 0.0000 | 0.0000 | 0.0000 |

## Full raw records (including complete per-round `set_trace` code-index lists)

The exact configs dumped in summary form above, with EVERY field (including the full raw `set_trace`, omitted above for readability), are in `results/d1v2/digestion/error_set_full.json`, keyed by `ident`.

