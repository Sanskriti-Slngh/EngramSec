# Agent 1 run agent1-20261031T051321Z

- Code revision: `b4a9a40a9d6715b0c1184b1555a722f12e047e3a+mapper-bd4b9ac71756`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:59757/`
- Elapsed: 60.686 seconds
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

- `feature_21cb4c89afa576c2` — Overview opens /shallow/a
- `feature_38abb14282d03e97` — News opens /shallow/b
- `feature_4e99c95dbd8a7ac6` — Load late reports leads to JavaScript Readiness Lab
- `feature_572196394a692cc5` — Overview opens /shallow/a
- `feature_66d712baf9e36c1c` — News opens /shallow/b

## Functional path-instance outcomes

- `workflow_1294c4f101612ae349` — Public alias area: `navigation_only` (path length 1)
- `workflow_61c56b6431fac03d63` — Load alias data: `unresolved` (path length 2)
- `workflow_553546e66051dc1e02` — Overview: `navigation_only` (path length 2)
- `workflow_24196d709a40ef1e10` — Refresh status: `unresolved` (path length 1)
- `workflow_8eb9c97a84ed288031` — Open workflow: `unresolved` (path length 1)
- `workflow_bd4720975e7796d48a` — Continue setup: `not_tested` (path length 2)
- `workflow_13c88909a6b19da095` — Open workspace: `not_tested` (path length 3)
- `workflow_ace6d53fbd92a13f59` — Workspace detail: `not_tested` (path length 4)
- `workflow_21e54695f702c85c0d` — Load late reports: `unresolved` (path length 1)
- `workflow_348e55c24be474e72b` — Open reports: `not_tested` (path length 2)
- `workflow_700bfaded80e9c8fde` — Overview: `navigation_only` (path length 1)
- `workflow_adcbf7d124877c9699` — News: `navigation_only` (path length 1)
- `workflow_4fcd8a7f09ccecca1b` — JS Lab: `navigation_only` (path length 1)
- `workflow_59fe39016ac0d4041a` — Open workflow: `not_tested` (path length 2)
- `workflow_255ff5003fa2b3e538` — Load late reports: `not_tested` (path length 2)
- `workflow_797f6157542f7e211a` — Continue setup: `not_tested` (path length 3)
- `workflow_639ac99ae487093fd3` — Public alias area: `not_tested` (path length 4)
- `workflow_4f48af539f07d8152e` — News: `navigation_only` (path length 2)
- `workflow_c786079a7fc11d797f` — Open workflow: `not_tested` (path length 2)
- `workflow_f4fa00bb4a47ddd8ae` — Public alias area: `not_tested` (path length 3)
- `workflow_165e4e0b2180a8ad0c` — JS Lab: `not_tested` (path length 2)
- `workflow_8d6c3dbddde50930f6` — Open workflow: `not_tested` (path length 3)
- `workflow_9b1cd16a1343427f16` — Public alias area: `not_tested` (path length 2)
- `workflow_3cda64ecd908a10692` — Load late reports: `not_tested` (path length 3)
- `workflow_cb699635f21a6c73e6` — Open workspace: `not_tested` (path length 4)
- `workflow_39657eec8552003bb1` — Public alias area: `not_tested` (path length 2)
- `workflow_6b08041358a970a880` — Public alias area: `not_tested` (path length 3)
- `workflow_b11d7e361c64c21c58` — Open reports: `not_tested` (path length 3)
- `workflow_b2647af70389da2fb7` — Open reports: `not_tested` (path length 4)
- `workflow_88cb7ea99d40fbb661` — Refresh status: `not_tested` (path length 2)
- `workflow_19d4f4d60fada3874a` — Refresh status: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_1a030fea4681f1de` — JS Lab opens /
- `feature_3fdf7d4ac7486ad3` — Load late reports leads to JavaScript Readiness Lab
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
