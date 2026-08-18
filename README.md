# four_color_digestion

Machine digestion of the Four Color Theorem's computer proof. Two sub-goals:
(A) a smaller unavoidable set of reducible configurations than the known
records; (B) extraction of the organizing invariant behind reducibility via
process-supervised models + mechanistic interpretability.

- Plan: `00-ATTACK-PLAN.md`. Research dossiers: `sources/`.
- Primary artifacts (pinned, sha256 in `third_party/CHECKSUMS.sha256`):
  RSST arXiv:1401.6481 (reduce.c + 633 configs), arXiv:1401.6485
  (discharge.c + rules + presenters), Steinberger arXiv:0905.0043
  (2822 D-reducible configs, ring <= 16).
- `make oracle` re-verifies reducibility of all 633 RSST configurations
  (~1 min on an M4); `make discharge` replays the unavoidability proof for
  hub degrees 7-11 (seconds). `make test` runs the parser test suite.

Status ledger and evidence discipline are lightweight for now: committed
`results/` transcripts with checksums; failures preserved as results.
