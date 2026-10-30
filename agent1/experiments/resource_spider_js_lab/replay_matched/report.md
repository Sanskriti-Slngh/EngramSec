# Agent 1 run agent1-20261030T040419Z

- Code revision: `decc0a2788a8f8c91c4d65427ef36da8c2d581c5+mapper-ea5b01ebeb1f`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:50392/`
- Elapsed: 62.264 seconds
- Browser actions (including setup/replay): 70
- Replay-validated navigation categories: 3
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 22
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

- `workflow_2d54827696ebf83d8e` — Public alias area: `navigation_only` (path length 1)
- `workflow_e745d791a9ab70678f` — Load alias data: `not_tested` (path length 2)
- `workflow_c5bb836b0c33a15369` — Overview: `not_tested` (path length 2)
- `workflow_1416fa41b7de2b16c0` — Refresh status: `not_tested` (path length 1)
- `workflow_41a6bbeee0bcec90fe` — Open workflow: `not_tested` (path length 1)
- `workflow_7fb4f6ef4635fcf57f` — Continue setup: `not_tested` (path length 2)
- `workflow_15f37c7bf3f84f6aa9` — Open workspace: `navigation_only` (path length 3)
- `workflow_0307f8580b1258cbff` — Workspace detail: `not_tested` (path length 4)
- `workflow_05c1c31b7d6ac39d74` — Load late reports: `unresolved` (path length 1)
- `workflow_237940f9243ac8e2b6` — Open reports: `navigation_only` (path length 2)
- `workflow_1f1d9df5d096bcb50c` — Overview: `navigation_only` (path length 1)
- `workflow_5a126be2a7a8338549` — News: `navigation_only` (path length 1)
- `workflow_384fd4832a26eef1e9` — JS Lab: `navigation_only` (path length 1)
- `workflow_4f73dfc161efb6f37f` — Open workflow: `not_tested` (path length 2)
- `workflow_7a80013f23546eb1c3` — Load late reports: `not_tested` (path length 2)
- `workflow_34e6f6b5efa00b00bd` — Continue setup: `not_tested` (path length 3)
- `workflow_1d360cf2052074566f` — Public alias area: `not_tested` (path length 4)
- `workflow_93c941924dbb78395b` — News: `not_tested` (path length 2)
- `workflow_23f1322cbffe7a8a85` — Open workflow: `not_tested` (path length 2)
- `workflow_c424d9e53a0d25a60b` — Public alias area: `not_tested` (path length 3)
- `workflow_8ce748d8f8429e2154` — JS Lab: `not_tested` (path length 2)
- `workflow_a7b654e59939cbab68` — Open workflow: `not_tested` (path length 3)
- `workflow_62dc19ebdc744ef69f` — Public alias area: `not_tested` (path length 2)
- `workflow_832bbd8c8ab835ce89` — Load late reports: `not_tested` (path length 3)
- `workflow_4f5a7efab82be99ac4` — Open workspace: `not_tested` (path length 4)
- `workflow_d625b396bad1adbd23` — Public alias area: `not_tested` (path length 2)
- `workflow_29fb6339398c21d477` — Public alias area: `not_tested` (path length 3)
- `workflow_a65ed1fefddfee7edd` — Open reports: `not_tested` (path length 3)

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
