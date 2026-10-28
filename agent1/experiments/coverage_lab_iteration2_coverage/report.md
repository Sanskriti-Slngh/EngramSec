# Agent 1 run agent1-20261028T192510Z

- Code revision: `6082c6df7fdb07b0cc0c13930f705c9f327e2a96+mapper-9c116cade9ea`
- Policy: `coverage`
- Target: `http://127.0.0.1:55304/`
- Elapsed: 11.302 seconds
- Browser actions (including setup/replay): 140
- Replay-validated navigation categories: 7
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 26
- Replay navigation success: 17/17
- Replay failures / untested paths: 0/13
- Graph connections with complete evidence: 645/645
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_126608ed79b7ddeb` — Show tools leads to Coverage Lab
- `feature_2028df292483a3bf` — Advanced settings leads to Coverage Lab
- `feature_229d40c5953629cb` — Help center leads to Help
- `feature_306e9ece746fa9a8` — Load summary leads to Coverage Lab
- `feature_7f1a16ad48d3390c` — Analytics leads to Coverage Lab
- `feature_a6fdfb0309a1ff7e` — Workspace opens /workspace
- `feature_ed2908593a00fd37` — Show tools leads to Coverage Lab

## Functional path-instance outcomes

- `workflow_215b426226ffb8b9c0` — Enter member area: `unresolved` (path length 1)
- `workflow_5e0c9d12f0beed00b3` — Show tools: `unresolved` (path length 1)
- `workflow_467d012da7af9cec5a` — Refresh status: `unresolved` (path length 1)
- `workflow_33978da5fe6060fc60` — Load summary: `unresolved` (path length 1)
- `workflow_61a8a66cb56a4a621f` — Help center: `unresolved` (path length 1)
- `workflow_b4cf84d8048c1809c0` — Analytics: `unresolved` (path length 1)
- `workflow_ae23da8c4b11116a8d` — Advanced settings: `unresolved` (path length 1)
- `workflow_83f34d7bd70b75612f` — Audit record: `not_tested` (path length 2)
- `workflow_adeb236490fe6595a2` — Export analytics: `unresolved` (path length 2)
- `workflow_2b2eb05081394e4d36` — Member preferences: `not_tested` (path length 2)
- `workflow_a201cdcb05cdced4c4` — Coverage Lab: `navigation_only` (path length 1)
- `workflow_d8dcb12493d4b965fd` — Beta customer: `navigation_only` (path length 1)
- `workflow_3c1bf8e36439b9f150` — Load history: `unresolved` (path length 2)
- `workflow_d23a64d3227919dd94` — Related customer: `not_tested` (path length 2)
- `workflow_1c14970d799bf0540f` — Open settings: `not_tested` (path length 2)
- `workflow_6c066816e13aa4f967` — Workspace: `navigation_only` (path length 2)
- `workflow_9a24acb063a85a6202` — Prepare workspace: `not_tested` (path length 3)
- `workflow_452e88154f9218e23d` — Alpha customer: `navigation_only` (path length 1)
- `workflow_bbdf5decc4b0d20f39` — Open reports: `not_tested` (path length 4)
- `workflow_f22d3c4a4d04158889` — Enter member area: `not_tested` (path length 2)
- `workflow_6d504de51dd5ba9b4a` — Enter member area: `unresolved` (path length 2)
- `workflow_e1a6a8f3d9db1949be` — Enter member area: `unresolved` (path length 2)
- `workflow_476b3f9c265c6c5e53` — Enter member area: `not_tested` (path length 2)
- `workflow_6f9413ad10745fb95f` — Show tools: `unresolved` (path length 2)
- `workflow_a4c66c4fb46b17b5f1` — Show tools: `not_tested` (path length 2)
- `workflow_705a2c3679b64780df` — Enter member area: `not_tested` (path length 3)
- `workflow_268b64250fd5d48db9` — Show tools: `not_tested` (path length 2)
- `workflow_f63ed9c658c6d4f2c8` — Enter member area: `not_tested` (path length 3)
- `workflow_13d5ffcd4560c5c9d2` — Show tools: `unresolved` (path length 2)
- `workflow_ebf30e644e694d318f` — Enter member area: `not_tested` (path length 3)

## Observed but not replay-validated

- `feature_06c43a65adbc76d0` — Open settings opens /settings
- `feature_24eb9ef44b072359` — Observed link workflow to /records/{instance}
- `feature_50ed3e414fbc36fe` — Enter member area leads to Member
- `feature_6dcd32b59045751c` — Open reports opens /workspace/reports
- `feature_8381988dedc3fd61` — Member preferences opens /member/preferences
- `feature_a888279d5d7f576d` — Show tools leads to Coverage Lab
- `feature_d7e96a98931a1e0a` — Prepare workspace leads to Workspace
- `feature_ecfca57997aa6842` — Show tools leads to Coverage Lab

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
