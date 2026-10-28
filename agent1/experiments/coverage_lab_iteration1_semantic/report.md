# Agent 1 run agent1-20261028T192422Z

- Code revision: `6082c6df7fdb07b0cc0c13930f705c9f327e2a96+mapper-6b5fa795c675`
- Policy: `grouped`
- Target: `http://127.0.0.1:54881/`
- Elapsed: 11.200 seconds
- Browser actions (including setup/replay): 143
- Replay-validated navigation categories: 7
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 27
- Replay navigation success: 21/21
- Replay failures / untested paths: 0/9
- Graph connections with complete evidence: 731/731
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_126608ed79b7ddeb` — Show tools leads to Coverage Lab
- `feature_2028df292483a3bf` — Advanced settings leads to Coverage Lab
- `feature_24eb9ef44b072359` — Observed link workflow to /records/{instance}
- `feature_306e9ece746fa9a8` — Load summary leads to Coverage Lab
- `feature_7f1a16ad48d3390c` — Analytics leads to Coverage Lab
- `feature_ecfca57997aa6842` — Show tools leads to Coverage Lab
- `feature_ed2908593a00fd37` — Show tools leads to Coverage Lab

## Functional path-instance outcomes

- `workflow_e8abd489e418292c6f` — Enter member area: `unresolved` (path length 1)
- `workflow_df5e355eaecc09fd5f` — Show tools: `unresolved` (path length 1)
- `workflow_4319d8ebdfa76eb8c4` — Refresh status: `unresolved` (path length 1)
- `workflow_f988fb4396ac6cc82d` — Load summary: `unresolved` (path length 1)
- `workflow_deb754ee2b856fa24a` — Help center: `unresolved` (path length 1)
- `workflow_47a2b8351397a2e39e` — Analytics: `unresolved` (path length 1)
- `workflow_d7f5b32231402d7d5b` — Advanced settings: `unresolved` (path length 1)
- `workflow_ac9c121e3b36629b6e` — Coverage Lab: `navigation_only` (path length 1)
- `workflow_5004a28ccd501d344e` — Beta customer: `navigation_only` (path length 1)
- `workflow_184e222366591fbf7a` — Alpha customer: `navigation_only` (path length 1)
- `workflow_8509c4f94557fdcb0d` — Enter member area: `unresolved` (path length 2)
- `workflow_989c0fa99f319691bb` — Enter member area: `not_tested` (path length 2)
- `workflow_0e155696f4a61f63ce` — Enter member area: `unresolved` (path length 2)
- `workflow_46d9f2dac6912a7de1` — Enter member area: `unresolved` (path length 2)
- `workflow_d3568a37ccd521750e` — Load history: `not_tested` (path length 2)
- `workflow_b01012d1b522451524` — Load history: `not_tested` (path length 2)
- `workflow_0dc7bcb267caec67ff` — Show tools: `unresolved` (path length 2)
- `workflow_3716cc134761f77590` — Show tools: `unresolved` (path length 2)
- `workflow_fb3b94e289ac32eea4` — Show tools: `not_tested` (path length 2)
- `workflow_45a8533aadd39a10e4` — Show tools: `unresolved` (path length 2)
- `workflow_d01555cc5022bb80d1` — Refresh status: `unresolved` (path length 2)
- `workflow_4a5075602c6ad2897e` — Refresh status: `unresolved` (path length 2)
- `workflow_57444089b01cbcf16d` — Refresh status: `unresolved` (path length 2)
- `workflow_4ffef087dfda9b96fe` — Refresh status: `unresolved` (path length 2)
- `workflow_8c3c73d62e408b8a18` — Load summary: `not_tested` (path length 2)
- `workflow_e9ba00802a3a51678f` — Load summary: `not_tested` (path length 2)
- `workflow_abee0cd152a1ffe8ca` — Load summary: `not_tested` (path length 2)
- `workflow_5706390933ac01fe02` — Load summary: `unresolved` (path length 2)
- `workflow_91f2be17996694514e` — Help center: `not_tested` (path length 2)
- `workflow_16746793f4660ac476` — Help center: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_229d40c5953629cb` — Help center leads to Help
- `feature_50ed3e414fbc36fe` — Enter member area leads to Member
- `feature_75e2f1f1844a33ec` — Load summary leads to Coverage Lab
- `feature_8281d059de0b052a` — Load summary leads to Coverage Lab
- `feature_a888279d5d7f576d` — Show tools leads to Coverage Lab
- `feature_f7efba166ae5908d` — Load summary leads to Coverage Lab

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
