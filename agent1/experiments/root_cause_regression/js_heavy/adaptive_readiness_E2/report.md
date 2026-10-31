# Agent 1 run agent1-20261031T004304Z

- Code revision: `21a0e2d3188221b35babc7b25b369369849987d8+mapper-734e3e65c2d2`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:51096/`
- Elapsed: 60.795 seconds
- Browser actions (including setup/replay): 87
- Replay-validated navigation categories: 5
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 25
- Replay navigation success: 10/10
- Replay failures / untested paths: 0/21
- Graph connections with complete evidence: 531/531
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 1
- Redundant raw states: 3
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_38abb14282d03e97` — News opens /shallow/b
- `feature_3fdf7d4ac7486ad3` — Load late reports leads to JavaScript Readiness Lab
- `feature_4e99c95dbd8a7ac6` — Load late reports leads to JavaScript Readiness Lab
- `feature_572196394a692cc5` — Overview opens /shallow/a
- `feature_66d712baf9e36c1c` — News opens /shallow/b

## Functional path-instance outcomes

- `workflow_a93232f1e12c80130d` — Public alias area: `navigation_only` (path length 1)
- `workflow_47b01b325fb7495220` — Load alias data: `not_tested` (path length 2)
- `workflow_21cb5bfdb6628b50c5` — Overview: `not_tested` (path length 2)
- `workflow_fc46de9cf9370675d9` — Refresh status: `unresolved` (path length 1)
- `workflow_ad62c4765b789efe9b` — Open workflow: `unresolved` (path length 1)
- `workflow_fab24b1b0612f3667b` — Continue setup: `not_tested` (path length 2)
- `workflow_4f0394c5e11ae11be1` — Open workspace: `not_tested` (path length 3)
- `workflow_0c919be370b59aa6d5` — Workspace detail: `not_tested` (path length 4)
- `workflow_2a0e1d64f908bd3d17` — Load late reports: `unresolved` (path length 1)
- `workflow_39b592820856eb4f79` — Open reports: `navigation_only` (path length 2)
- `workflow_c872613418a3505596` — Overview: `navigation_only` (path length 1)
- `workflow_6c9f51cccd01eda6c6` — News: `navigation_only` (path length 1)
- `workflow_3df9b51d654e363538` — JS Lab: `navigation_only` (path length 1)
- `workflow_ab1b8d1f0f3a243b24` — Open workflow: `not_tested` (path length 2)
- `workflow_d12e5a3d4e38ec30f5` — Load late reports: `unresolved` (path length 2)
- `workflow_a1bfb762cad18e5d4a` — Continue setup: `not_tested` (path length 3)
- `workflow_7be070d19e7d364f7a` — Public alias area: `not_tested` (path length 4)
- `workflow_1344099a9f9c6814d4` — News: `navigation_only` (path length 2)
- `workflow_8efed269fe0f001a17` — Open workflow: `not_tested` (path length 2)
- `workflow_f011096a985980362e` — Public alias area: `not_tested` (path length 3)
- `workflow_95ff813b1f6d4af080` — JS Lab: `not_tested` (path length 2)
- `workflow_6ae4235f5c248ed1c7` — Open workflow: `not_tested` (path length 3)
- `workflow_9c0d7724662f4f9792` — Public alias area: `not_tested` (path length 2)
- `workflow_a5819023858ee9fe6f` — Load late reports: `not_tested` (path length 3)
- `workflow_6371541da2f5c02d21` — Open workspace: `not_tested` (path length 4)
- `workflow_4606dee605d8b3dede` — Public alias area: `not_tested` (path length 2)
- `workflow_de92d3de09cfe2e286` — Public alias area: `not_tested` (path length 3)
- `workflow_593fa4004c8c028d7d` — Open reports: `not_tested` (path length 3)
- `workflow_14d5e9e4d94114e649` — Open reports: `not_tested` (path length 4)
- `workflow_8551689ea74dd1dce6` — Refresh status: `not_tested` (path length 2)
- `workflow_0b256f0c80809bb40f` — Refresh status: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_1a030fea4681f1de` — JS Lab opens /
- `feature_21cb4c89afa576c2` — Overview opens /shallow/a
- `feature_57596745286f0170` — Continue setup leads to JavaScript Readiness Lab
- `feature_65aaa97a2117e3ad` — Open workspace opens /workspace
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
