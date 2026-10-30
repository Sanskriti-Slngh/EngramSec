# Agent 1 run agent1-20261030T234715Z

- Code revision: `fb43810ba3d837f0c9190087425eede19964fa18+mapper-fae05bd19c4b`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:53795/`
- Elapsed: 60.854 seconds
- Browser actions (including setup/replay): 87
- Replay-validated navigation categories: 6
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

- `feature_21cb4c89afa576c2` — Overview opens /shallow/a
- `feature_38abb14282d03e97` — News opens /shallow/b
- `feature_3fdf7d4ac7486ad3` — Load late reports leads to JavaScript Readiness Lab
- `feature_4e99c95dbd8a7ac6` — Load late reports leads to JavaScript Readiness Lab
- `feature_572196394a692cc5` — Overview opens /shallow/a
- `feature_66d712baf9e36c1c` — News opens /shallow/b

## Functional path-instance outcomes

- `workflow_30e0fe456cadb8d8d5` — Public alias area: `navigation_only` (path length 1)
- `workflow_daaafcd902bd48b640` — Load alias data: `not_tested` (path length 2)
- `workflow_ad00677a084c5778c5` — Overview: `navigation_only` (path length 2)
- `workflow_30a0c9df18d96cf8b4` — Refresh status: `unresolved` (path length 1)
- `workflow_4b0f86e34d0fc2be80` — Open workflow: `unresolved` (path length 1)
- `workflow_8ebdd84ea7d408d48c` — Continue setup: `not_tested` (path length 2)
- `workflow_178604fe33e363ecec` — Open workspace: `not_tested` (path length 3)
- `workflow_40432238f8cf748921` — Workspace detail: `not_tested` (path length 4)
- `workflow_8150387a1d9a18a73c` — Load late reports: `unresolved` (path length 1)
- `workflow_43798444474a15658c` — Open reports: `not_tested` (path length 2)
- `workflow_8ac6f695a82831d3be` — Overview: `navigation_only` (path length 1)
- `workflow_4a3dd786c63fc7e7a7` — News: `navigation_only` (path length 1)
- `workflow_3b20224296fd0e5ae4` — JS Lab: `navigation_only` (path length 1)
- `workflow_2d7af0356b7f027e44` — Open workflow: `not_tested` (path length 2)
- `workflow_7f51a9f5d978813878` — Load late reports: `unresolved` (path length 2)
- `workflow_e860836fe0f1be2bea` — Continue setup: `not_tested` (path length 3)
- `workflow_f3f12c45a9de564d89` — Public alias area: `not_tested` (path length 4)
- `workflow_978ba019b3ac20bf15` — News: `navigation_only` (path length 2)
- `workflow_d48fbfd2f6c51b9db5` — Open workflow: `not_tested` (path length 2)
- `workflow_2cb95cb66880d29257` — Public alias area: `not_tested` (path length 3)
- `workflow_995ec6a5654a944674` — JS Lab: `not_tested` (path length 2)
- `workflow_ab06b81a14c27611db` — Open workflow: `not_tested` (path length 3)
- `workflow_c68e402a6095c378fa` — Public alias area: `not_tested` (path length 2)
- `workflow_4f0efca2df883417bd` — Load late reports: `not_tested` (path length 3)
- `workflow_1f498cc53b0ba8397c` — Open workspace: `not_tested` (path length 4)
- `workflow_44ffe626d1bcfd1fca` — Public alias area: `not_tested` (path length 2)
- `workflow_6de22c0e0acf37a5c0` — Public alias area: `not_tested` (path length 3)
- `workflow_fedc249fa7155907af` — Open reports: `not_tested` (path length 3)
- `workflow_d47bf196cc2c3ce044` — Open reports: `not_tested` (path length 4)
- `workflow_3b4263ed1c7f41b398` — Refresh status: `not_tested` (path length 2)
- `workflow_5a76b22e161e0ae1c3` — Refresh status: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_1a030fea4681f1de` — JS Lab opens /
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
