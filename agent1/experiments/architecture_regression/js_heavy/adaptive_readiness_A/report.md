# Agent 1 run agent1-20261030T215217Z

- Code revision: `5710c01fbcd2b09fab0886cbc0eedf65b0b1510e+mapper-9b4b25920aaf`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:50242/`
- Elapsed: 61.200 seconds
- Browser actions (including setup/replay): 87
- Replay-validated navigation categories: 6
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 26
- Replay navigation success: 10/10
- Replay failures / untested paths: 0/21
- Graph connections with complete evidence: 531/531
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 1
- Redundant raw states: 3
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_21cb4c89afa576c2` — Overview opens /shallow/a
- `feature_38abb14282d03e97` — News opens /shallow/b
- `feature_3fdf7d4ac7486ad3` — Load late reports leads to JavaScript Readiness Lab
- `feature_4e99c95dbd8a7ac6` — Load late reports leads to JavaScript Readiness Lab
- `feature_572196394a692cc5` — Overview opens /shallow/a
- `feature_c449436cb1de966e` — Continue setup leads to JavaScript Readiness Lab

## Functional path-instance outcomes

- `workflow_2287fbe9ee0b9b242e` — Public alias area: `navigation_only` (path length 1)
- `workflow_de4db9a11afd521d78` — Load alias data: `not_tested` (path length 2)
- `workflow_3431b7ddb875fae950` — Overview: `navigation_only` (path length 2)
- `workflow_d1016800617ccf8ea0` — Refresh status: `unresolved` (path length 1)
- `workflow_c72c3a6a1c30512329` — Open workflow: `unresolved` (path length 1)
- `workflow_5aa5873e3d322d8099` — Continue setup: `unresolved` (path length 2)
- `workflow_b00420dd08c97fa167` — Open workspace: `not_tested` (path length 3)
- `workflow_9d429c02317135c013` — Workspace detail: `not_tested` (path length 4)
- `workflow_9e5c0a1ede7ada914a` — Load late reports: `unresolved` (path length 1)
- `workflow_4537e2d01b2cc0b052` — Open reports: `not_tested` (path length 2)
- `workflow_ff19aa518c28521355` — Overview: `navigation_only` (path length 1)
- `workflow_db1a0deb78cad9806d` — News: `navigation_only` (path length 1)
- `workflow_57d1305073b0dbb412` — JS Lab: `navigation_only` (path length 1)
- `workflow_576a96f9b6cf199ac6` — Open workflow: `not_tested` (path length 2)
- `workflow_8a86f8c296e768e33e` — Load late reports: `unresolved` (path length 2)
- `workflow_acaa6f1a2db682868a` — Continue setup: `not_tested` (path length 3)
- `workflow_6f3d2875111791f1b0` — Public alias area: `not_tested` (path length 4)
- `workflow_4327576e149f99ae55` — News: `not_tested` (path length 2)
- `workflow_ed24ba5c04e915aa07` — Open workflow: `not_tested` (path length 2)
- `workflow_51bff5cb7aaec7e820` — Public alias area: `not_tested` (path length 3)
- `workflow_24aacac3df4e523284` — JS Lab: `not_tested` (path length 2)
- `workflow_73e69c97cb71dec612` — Open workflow: `not_tested` (path length 3)
- `workflow_983ded6ab61c47417d` — Public alias area: `not_tested` (path length 2)
- `workflow_2e68057efe53c0bd35` — Load late reports: `not_tested` (path length 3)
- `workflow_b3067fd7e459c34841` — Open workspace: `not_tested` (path length 4)
- `workflow_da264db8b6f9d23deb` — Public alias area: `not_tested` (path length 2)
- `workflow_9c434d9e531b61472e` — Public alias area: `not_tested` (path length 3)
- `workflow_9c7adde4aa4fb57915` — Open reports: `not_tested` (path length 3)
- `workflow_bec39bf07838deab6d` — Open reports: `not_tested` (path length 4)
- `workflow_367bed487c929e9022` — Refresh status: `not_tested` (path length 2)
- `workflow_05fabbcc00fff49ac6` — Refresh status: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_1a030fea4681f1de` — JS Lab opens /
- `feature_57596745286f0170` — Continue setup leads to JavaScript Readiness Lab
- `feature_65aaa97a2117e3ad` — Open workspace opens /workspace
- `feature_66d712baf9e36c1c` — News opens /shallow/b
- `feature_6b4971396990b395` — Public alias area opens /alias-area
- `feature_805a5ea26d66d287` — Workspace detail opens /workspace/detail
- `feature_9c45708a2b4eccc1` — Open workflow leads to JavaScript Readiness Lab
- `feature_a1b7f7dfecb37603` — Open reports opens /reports
- `feature_a90ee4fc4b1202df` — Load late reports leads to JavaScript Readiness Lab
- `feature_d321ac671fa5a6b9` — Open workflow leads to JavaScript Readiness Lab

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
