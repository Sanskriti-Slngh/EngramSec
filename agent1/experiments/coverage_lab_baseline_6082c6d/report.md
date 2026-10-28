# Agent 1 run agent1-20261028T192159Z

- Code revision: `6082c6df7fdb07b0cc0c13930f705c9f327e2a96+mapper-c2dedd335955`
- Policy: `grouped`
- Target: `http://127.0.0.1:53805/`
- Elapsed: 11.596 seconds
- Browser actions (including setup/replay): 142
- Replay-validated navigation categories: 3
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 20
- Replay navigation success: 19/19
- Replay failures / untested paths: 0/11
- Graph connections with complete evidence: 538/538
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_9bc71c26f88faa0a` — Load summary leads to Coverage Lab
- `feature_a277a7e12bffaee7` — Show tools leads to Coverage Lab
- `feature_a6fdfb0309a1ff7e` — Workspace opens /workspace

## Functional path-instance outcomes

- `workflow_795e4a50453ef0d136` — Enter member area: `unresolved` (path length 1)
- `workflow_1937f955180fdbf92a` — Show tools: `unresolved` (path length 1)
- `workflow_211feee11c20806d29` — Refresh status: `unresolved` (path length 1)
- `workflow_b70d30b9c2833ab4bc` — Load summary: `unresolved` (path length 1)
- `workflow_7fd5d38b24a7c05c0b` — Coverage Lab: `navigation_only` (path length 1)
- `workflow_06766beaa268f45524` — Beta customer: `navigation_only` (path length 1)
- `workflow_869624516e64efa6fd` — Alpha customer: `navigation_only` (path length 1)
- `workflow_df9de62bd18e248781` — Enter member area: `unresolved` (path length 2)
- `workflow_7df94845f885112b52` — Enter member area: `not_tested` (path length 2)
- `workflow_3f1c39166ade4c333a` — Load history: `not_tested` (path length 2)
- `workflow_6afd37e455fe1eb656` — Load history: `unresolved` (path length 2)
- `workflow_198f4bdbd73ff628de` — Show tools: `not_tested` (path length 2)
- `workflow_ff7e35e8f292a6868b` — Show tools: `not_tested` (path length 2)
- `workflow_10502833badc50d08a` — Refresh status: `not_tested` (path length 2)
- `workflow_df3e69d455394b0e86` — Refresh status: `unresolved` (path length 2)
- `workflow_08a5e71966832e3da9` — Load summary: `not_tested` (path length 2)
- `workflow_ecb99d7093028352a3` — Load summary: `unresolved` (path length 2)
- `workflow_44fbff42cd296bc87f` — Audit record: `unresolved` (path length 2)
- `workflow_883623c99d80a1bc60` — Member preferences: `not_tested` (path length 2)
- `workflow_9513398f59e03c0163` — Related customer: `navigation_only` (path length 2)
- `workflow_eaa57c31da27ac906f` — Related customer: `not_tested` (path length 2)
- `workflow_222120e3ce05dd6727` — Coverage Lab: `navigation_only` (path length 2)
- `workflow_ed28a356a8c0b7d654` — Workspace: `navigation_only` (path length 2)
- `workflow_3b1eab249c63b4187a` — Coverage Lab: `not_tested` (path length 2)
- `workflow_cac83ab85b5e95c42d` — Coverage Lab: `navigation_only` (path length 2)
- `workflow_b4e4a9ab417a85aca0` — Coverage Lab: `not_tested` (path length 2)
- `workflow_5f4804c4d5bc7de0bd` — Coverage Lab: `navigation_only` (path length 2)
- `workflow_d8b4266a432c58340e` — Beta customer: `not_tested` (path length 2)
- `workflow_909115c578092172a0` — Beta customer: `navigation_only` (path length 2)
- `workflow_d5c1ffe7b2c39185b7` — Alpha customer: `navigation_only` (path length 2)

## Observed but not replay-validated

- `feature_24eb9ef44b072359` — Observed link workflow to /records/{instance}
- `feature_476abf89e677a302` — Show tools leads to Coverage Lab
- `feature_50ed3e414fbc36fe` — Enter member area leads to Member
- `feature_5ce256c24795e4ad` — Coverage Lab opens /
- `feature_8381988dedc3fd61` — Member preferences opens /member/preferences
- `feature_ceaacf1bb2d2c619` — Load summary leads to Coverage Lab

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
