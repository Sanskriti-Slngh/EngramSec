# Agent 1 run agent1-20261030T040217Z

- Code revision: `decc0a2788a8f8c91c4d65427ef36da8c2d581c5+mapper-ea5b01ebeb1f`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:49243/`
- Elapsed: 60.241 seconds
- Browser actions (including setup/replay): 67
- Replay-validated navigation categories: 3
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 24
- Replay navigation success: 7/7
- Replay failures / untested paths: 0/21
- Graph connections with complete evidence: 367/367
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 1
- Redundant raw states: 3
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_38abb14282d03e97` — News opens /shallow/b
- `feature_4e99c95dbd8a7ac6` — Load late reports leads to JavaScript Readiness Lab
- `feature_572196394a692cc5` — Overview opens /shallow/a

## Functional path-instance outcomes

- `workflow_be120c43c2a5707bf6` — Public alias area: `navigation_only` (path length 1)
- `workflow_c008832f6975602924` — Load alias data: `not_tested` (path length 2)
- `workflow_13b16a9bdd971dafba` — Overview: `not_tested` (path length 2)
- `workflow_28c5d05f532c3b72d2` — Refresh status: `unresolved` (path length 1)
- `workflow_0d1f0f4584e961fa10` — Open workflow: `unresolved` (path length 1)
- `workflow_657604085c0f754daa` — Continue setup: `not_tested` (path length 2)
- `workflow_774e5fc571f06e1a5f` — Open workspace: `not_tested` (path length 3)
- `workflow_86e25f393f278fe8f1` — Workspace detail: `not_tested` (path length 4)
- `workflow_68f64cc2afbc519eb8` — Load late reports: `unresolved` (path length 1)
- `workflow_f168d6aa56ff03002d` — Open reports: `not_tested` (path length 2)
- `workflow_12a3bcd418d838e6b4` — Overview: `navigation_only` (path length 1)
- `workflow_6af1ddbb9585be7a72` — News: `navigation_only` (path length 1)
- `workflow_75f88d8e245006cbc6` — JS Lab: `navigation_only` (path length 1)
- `workflow_5471ed40ca917b42e8` — Open workflow: `not_tested` (path length 2)
- `workflow_7f2dfef76034c8b5eb` — Load late reports: `not_tested` (path length 2)
- `workflow_752a2e04da72b22d61` — Continue setup: `not_tested` (path length 3)
- `workflow_186bbffed745670c1e` — Public alias area: `not_tested` (path length 4)
- `workflow_6b8e68fca13a5550a1` — News: `not_tested` (path length 2)
- `workflow_6ed7dcc7f8923e03b0` — Open workflow: `not_tested` (path length 2)
- `workflow_cbd8d85f5ef23e14c9` — Public alias area: `not_tested` (path length 3)
- `workflow_5dfe512e4a332ac1a0` — JS Lab: `not_tested` (path length 2)
- `workflow_7093d6672977ab9549` — Open workflow: `not_tested` (path length 3)
- `workflow_a515810ef1738893dc` — Public alias area: `not_tested` (path length 2)
- `workflow_a6fba792da1f7d015f` — Load late reports: `not_tested` (path length 3)
- `workflow_1f560e6526a769af16` — Open workspace: `not_tested` (path length 4)
- `workflow_eab24887ebf83a38aa` — Public alias area: `not_tested` (path length 2)
- `workflow_29ed7639d233c63251` — Public alias area: `not_tested` (path length 3)
- `workflow_51bb505dc575aa7c1d` — Open reports: `not_tested` (path length 3)

## Observed but not replay-validated

- `feature_1a030fea4681f1de` — JS Lab opens /
- `feature_21cb4c89afa576c2` — Overview opens /shallow/a
- `feature_3fdf7d4ac7486ad3` — Load late reports leads to JavaScript Readiness Lab
- `feature_57596745286f0170` — Continue setup leads to JavaScript Readiness Lab
- `feature_65aaa97a2117e3ad` — Open workspace opens /workspace
- `feature_66d712baf9e36c1c` — News opens /shallow/b
- `feature_6b4971396990b395` — Public alias area opens /alias-area
- `feature_805a5ea26d66d287` — Workspace detail opens /workspace/detail
- `feature_9c45708a2b4eccc1` — Open workflow leads to JavaScript Readiness Lab
- `feature_a1b7f7dfecb37603` — Open reports opens /reports
- `feature_a90ee4fc4b1202df` — Load late reports leads to JavaScript Readiness Lab
- `feature_c449436cb1de966e` — Continue setup leads to JavaScript Readiness Lab
- `feature_d321ac671fa5a6b9` — Open workflow leads to JavaScript Readiness Lab

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
