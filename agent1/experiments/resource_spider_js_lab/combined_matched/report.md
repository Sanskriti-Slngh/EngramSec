# Agent 1 run agent1-20261030T040522Z

- Code revision: `decc0a2788a8f8c91c4d65427ef36da8c2d581c5+mapper-ea5b01ebeb1f`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:50912/`
- Elapsed: 60.729 seconds
- Browser actions (including setup/replay): 89
- Replay-validated navigation categories: 5
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 24
- Replay navigation success: 9/9
- Replay failures / untested paths: 0/22
- Graph connections with complete evidence: 426/426
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 1
- Redundant raw states: 3
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_38abb14282d03e97` — News opens /shallow/b
- `feature_4e99c95dbd8a7ac6` — Load late reports leads to JavaScript Readiness Lab
- `feature_572196394a692cc5` — Overview opens /shallow/a
- `feature_805a5ea26d66d287` — Workspace detail opens /workspace/detail
- `feature_c449436cb1de966e` — Continue setup leads to JavaScript Readiness Lab

## Functional path-instance outcomes

- `workflow_49abd9746088decac3` — Public alias area: `navigation_only` (path length 1)
- `workflow_3c2a9c8648a7ee076a` — Load alias data: `not_tested` (path length 2)
- `workflow_3eb2302bbebc28f4c7` — Overview: `not_tested` (path length 2)
- `workflow_13085443f4902851bd` — Refresh status: `not_tested` (path length 1)
- `workflow_e8a686a6a4fd59a1e8` — Open workflow: `not_tested` (path length 1)
- `workflow_6d9bd17a11405d96f8` — Continue setup: `unresolved` (path length 2)
- `workflow_ab507e03237be47a72` — Open workspace: `navigation_only` (path length 3)
- `workflow_0361bfca855819749e` — Workspace detail: `navigation_only` (path length 4)
- `workflow_514c130798d1483d34` — Load late reports: `unresolved` (path length 1)
- `workflow_ca561f83cf464b038b` — Open reports: `navigation_only` (path length 2)
- `workflow_3ee55b2460c7547931` — Overview: `navigation_only` (path length 1)
- `workflow_6ac739c7a710ca60bb` — News: `navigation_only` (path length 1)
- `workflow_157d2aace2859de194` — JS Lab: `navigation_only` (path length 1)
- `workflow_e9cf114ae2e0ff09f7` — Open workflow: `not_tested` (path length 2)
- `workflow_20c07b48c827551ca0` — Load late reports: `not_tested` (path length 2)
- `workflow_5e0bad6a5373cdc5c1` — Continue setup: `not_tested` (path length 3)
- `workflow_15f625b443da03f72d` — Public alias area: `not_tested` (path length 4)
- `workflow_688d5fa52bb04665aa` — News: `not_tested` (path length 2)
- `workflow_00a1201c090dd10f0c` — Open workflow: `not_tested` (path length 2)
- `workflow_60df29a2759b46a724` — Public alias area: `not_tested` (path length 3)
- `workflow_5001aa35a92bf63f29` — JS Lab: `not_tested` (path length 2)
- `workflow_109b00708bc9511c0a` — Open workflow: `not_tested` (path length 3)
- `workflow_9de5887a8a6503fc81` — Public alias area: `not_tested` (path length 2)
- `workflow_a2d070214fdaa32e9d` — Load late reports: `not_tested` (path length 3)
- `workflow_11d78a106e765d3bed` — Open workspace: `not_tested` (path length 4)
- `workflow_d562700c52a0a7943b` — Public alias area: `not_tested` (path length 2)
- `workflow_11881ac2f6a498305f` — Public alias area: `not_tested` (path length 3)
- `workflow_3b7eab0bbb54719469` — Open reports: `not_tested` (path length 3)
- `workflow_b432c39ff16f93d0fe` — Open reports: `not_tested` (path length 4)
- `workflow_3248466887ab9d0d30` — Refresh status: `not_tested` (path length 2)
- `workflow_e1c50dacb5130d72d5` — Refresh status: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_1a030fea4681f1de` — JS Lab opens /
- `feature_21cb4c89afa576c2` — Overview opens /shallow/a
- `feature_3fdf7d4ac7486ad3` — Load late reports leads to JavaScript Readiness Lab
- `feature_57596745286f0170` — Continue setup leads to JavaScript Readiness Lab
- `feature_65aaa97a2117e3ad` — Open workspace opens /workspace
- `feature_66d712baf9e36c1c` — News opens /shallow/b
- `feature_6b4971396990b395` — Public alias area opens /alias-area
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
