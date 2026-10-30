# Agent 1 run agent1-20261030T234816Z

- Code revision: `fb43810ba3d837f0c9190087425eede19964fa18+mapper-fae05bd19c4b`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:54340/`
- Elapsed: 60.390 seconds
- Browser actions (including setup/replay): 87
- Replay-validated navigation categories: 5
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

- `feature_38abb14282d03e97` — News opens /shallow/b
- `feature_4e99c95dbd8a7ac6` — Load late reports leads to JavaScript Readiness Lab
- `feature_572196394a692cc5` — Overview opens /shallow/a
- `feature_9c45708a2b4eccc1` — Open workflow leads to JavaScript Readiness Lab
- `feature_c449436cb1de966e` — Continue setup leads to JavaScript Readiness Lab

## Functional path-instance outcomes

- `workflow_fc0186ff4e91f74f28` — Public alias area: `navigation_only` (path length 1)
- `workflow_14e01ce383401ff7de` — Load alias data: `not_tested` (path length 2)
- `workflow_0c2420beb159a8fc8c` — Overview: `not_tested` (path length 2)
- `workflow_d14613ad76e2a8634d` — Refresh status: `unresolved` (path length 1)
- `workflow_9431077d73af692428` — Open workflow: `unresolved` (path length 1)
- `workflow_2517e9b9b593cc43ed` — Continue setup: `unresolved` (path length 2)
- `workflow_6a4b818b6b811ba73c` — Open workspace: `not_tested` (path length 3)
- `workflow_de63843c9c3a000c16` — Workspace detail: `not_tested` (path length 4)
- `workflow_1ffdb24cb113c9e983` — Load late reports: `unresolved` (path length 1)
- `workflow_83ed54b99f1343d5b9` — Open reports: `navigation_only` (path length 2)
- `workflow_9dd119d5f005d00aea` — Overview: `navigation_only` (path length 1)
- `workflow_6f33570480882742a6` — News: `navigation_only` (path length 1)
- `workflow_0ff3e6048764321fba` — JS Lab: `navigation_only` (path length 1)
- `workflow_7f119c4a30798b9963` — Open workflow: `not_tested` (path length 2)
- `workflow_496875214b11d08020` — Load late reports: `not_tested` (path length 2)
- `workflow_6b0039dfbfa65e879b` — Continue setup: `not_tested` (path length 3)
- `workflow_38e616e8ebded1eb4b` — Public alias area: `not_tested` (path length 4)
- `workflow_a5b217a2c7679c19cd` — News: `not_tested` (path length 2)
- `workflow_1cbece26cb4216bfbe` — Open workflow: `unresolved` (path length 2)
- `workflow_fc6f4e9e9f62e059ba` — Public alias area: `not_tested` (path length 3)
- `workflow_c4f92a8e0131ac6660` — JS Lab: `not_tested` (path length 2)
- `workflow_7fdec7efff4fda57b6` — Open workflow: `not_tested` (path length 3)
- `workflow_e30c3825cf5041ff65` — Public alias area: `not_tested` (path length 2)
- `workflow_f180bf37af6319b4ea` — Load late reports: `not_tested` (path length 3)
- `workflow_e4d24002744d4959e5` — Open workspace: `not_tested` (path length 4)
- `workflow_996edf51b3e46cbeb0` — Public alias area: `not_tested` (path length 2)
- `workflow_df7b76bd2138621549` — Public alias area: `not_tested` (path length 3)
- `workflow_fde8a3eb094d894d8c` — Open reports: `not_tested` (path length 3)
- `workflow_2b995b9ffc47f96a72` — Open reports: `not_tested` (path length 4)
- `workflow_a51b9dff051b3d807c` — Refresh status: `not_tested` (path length 2)
- `workflow_e5a91e3dc72d74dd7f` — Refresh status: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_1a030fea4681f1de` — JS Lab opens /
- `feature_21cb4c89afa576c2` — Overview opens /shallow/a
- `feature_3fdf7d4ac7486ad3` — Load late reports leads to JavaScript Readiness Lab
- `feature_57596745286f0170` — Continue setup leads to JavaScript Readiness Lab
- `feature_65aaa97a2117e3ad` — Open workspace opens /workspace
- `feature_66d712baf9e36c1c` — News opens /shallow/b
- `feature_6b4971396990b395` — Public alias area opens /alias-area
- `feature_805a5ea26d66d287` — Workspace detail opens /workspace/detail
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
