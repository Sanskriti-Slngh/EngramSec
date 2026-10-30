# Agent 1 run agent1-20261030T040115Z

- Code revision: `decc0a2788a8f8c91c4d65427ef36da8c2d581c5+mapper-964d2a3ee260`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:65111/`
- Elapsed: 61.645 seconds
- Browser actions (including setup/replay): 70
- Replay-validated navigation categories: 4
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 24
- Replay navigation success: 8/8
- Replay failures / untested paths: 0/20
- Graph connections with complete evidence: 368/368
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 1
- Redundant raw states: 3
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_38abb14282d03e97` — News opens /shallow/b
- `feature_4e99c95dbd8a7ac6` — Load late reports leads to JavaScript Readiness Lab
- `feature_572196394a692cc5` — Overview opens /shallow/a
- `feature_c449436cb1de966e` — Continue setup leads to JavaScript Readiness Lab

## Functional path-instance outcomes

- `workflow_0b25173608f712f04b` — Public alias area: `navigation_only` (path length 1)
- `workflow_5ff5f160260b14a18b` — Load alias data: `not_tested` (path length 2)
- `workflow_e583f7a1e6caba948f` — Overview: `not_tested` (path length 2)
- `workflow_5c1386f79a4cc001d8` — Refresh status: `unresolved` (path length 1)
- `workflow_f3ae5d02316a852b4f` — Open workflow: `unresolved` (path length 1)
- `workflow_ed8bc970225200fa94` — Continue setup: `unresolved` (path length 2)
- `workflow_7cd2fcff68ddd9ef02` — Open workspace: `not_tested` (path length 3)
- `workflow_d37d74c9634cfae817` — Workspace detail: `not_tested` (path length 4)
- `workflow_de1eb8193d59c90ce1` — Load late reports: `unresolved` (path length 1)
- `workflow_476607f8f880780dcc` — Open reports: `not_tested` (path length 2)
- `workflow_295b7aa504a65fc263` — Overview: `navigation_only` (path length 1)
- `workflow_cd5316eeaf4f35a01a` — News: `navigation_only` (path length 1)
- `workflow_5ad3d3ae29f0164700` — JS Lab: `navigation_only` (path length 1)
- `workflow_b963a6e7b90a590a7f` — Open workflow: `not_tested` (path length 2)
- `workflow_ae7b2644cba67a7573` — Load late reports: `not_tested` (path length 2)
- `workflow_591d0ba0060bc73687` — Continue setup: `not_tested` (path length 3)
- `workflow_41573dcffda0b8d793` — Public alias area: `not_tested` (path length 4)
- `workflow_0ff844a90f6872d7e8` — News: `not_tested` (path length 2)
- `workflow_39b25c0d7157bbeb88` — Open workflow: `not_tested` (path length 2)
- `workflow_d73d8784e9f1a9a00a` — Public alias area: `not_tested` (path length 3)
- `workflow_ab59b816f4e2a53d61` — JS Lab: `not_tested` (path length 2)
- `workflow_4e7fe979418b126a0f` — Open workflow: `not_tested` (path length 3)
- `workflow_13f77068f35b6d4c9c` — Public alias area: `not_tested` (path length 2)
- `workflow_a37403b0d7f325bc5d` — Load late reports: `not_tested` (path length 3)
- `workflow_7ac81c8d22c5738f03` — Open workspace: `not_tested` (path length 4)
- `workflow_de933511a017e3d112` — Public alias area: `not_tested` (path length 2)
- `workflow_adcaea3351d6c6d094` — Public alias area: `not_tested` (path length 3)
- `workflow_80b7fcb76fab6ff352` — Open reports: `not_tested` (path length 3)

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
- `feature_d321ac671fa5a6b9` — Open workflow leads to JavaScript Readiness Lab

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
