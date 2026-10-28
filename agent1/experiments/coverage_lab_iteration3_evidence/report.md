# Agent 1 run agent1-20261028T193155Z

- Code revision: `3012ce6d393ee7f373c03c69789d5918abc95abc+mapper-1cc5c02a0a12`
- Policy: `coverage`
- Target: `http://127.0.0.1:58900/`
- Elapsed: 10.930 seconds
- Browser actions (including setup/replay): 140
- Replay-validated navigation categories: 10
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 24
- Replay navigation success: 17/17
- Replay failures / untested paths: 0/13
- Graph connections with complete evidence: 645/645
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_24eb9ef44b072359` — Observed link workflow to /records/{instance}
- `feature_48be9d4ddbb75a2a` — Show tools leads to Coverage Lab
- `feature_6c94ddb8eda63167` — Show tools leads to Coverage Lab
- `feature_8381988dedc3fd61` — Member preferences opens /member/preferences
- `feature_9be32f67e10e87e8` — Show tools leads to Coverage Lab
- `feature_a6fdfb0309a1ff7e` — Workspace opens /workspace
- `feature_c903a3d643767fde` — Help center leads to Help
- `feature_dc8ed1eec6d70ca9` — Advanced settings leads to Coverage Lab
- `feature_e47efdaab6398315` — Analytics leads to Coverage Lab
- `feature_eecf897e0ac4e0a5` — Load summary leads to Coverage Lab

## Functional path-instance outcomes

- `workflow_a124292a32a248f7cc` — Enter member area: `unresolved` (path length 1)
- `workflow_979bbf341da8d71f2d` — Show tools: `unresolved` (path length 1)
- `workflow_6752388aba5e4f72c7` — Refresh status: `unresolved` (path length 1)
- `workflow_a6ed623982e4642f6a` — Load summary: `unresolved` (path length 1)
- `workflow_6b411676d3ea08ffb7` — Help center: `unresolved` (path length 1)
- `workflow_5ec45449e552a1c219` — Analytics: `unresolved` (path length 1)
- `workflow_2f5fe609e27fe4727f` — Advanced settings: `unresolved` (path length 1)
- `workflow_e04d3a2e431884575d` — Audit record: `not_tested` (path length 2)
- `workflow_520a36b5a804fc38f7` — Export analytics: `not_tested` (path length 2)
- `workflow_41a0701e02d1ae0449` — Member preferences: `navigation_only` (path length 2)
- `workflow_9cf0f3768391749d9a` — Coverage Lab: `navigation_only` (path length 1)
- `workflow_bc24ad3e6ede40adf3` — Beta customer: `navigation_only` (path length 1)
- `workflow_99229ac917a3dc048c` — Load history: `not_tested` (path length 2)
- `workflow_752559ea63d93db3bc` — Related customer: `navigation_only` (path length 2)
- `workflow_b95f1ffbb07d559750` — Open settings: `not_tested` (path length 2)
- `workflow_db53d95fab150f9576` — Workspace: `navigation_only` (path length 2)
- `workflow_3fa4d6d4cd9bda7d8c` — Prepare workspace: `not_tested` (path length 3)
- `workflow_7d53faba5f33002000` — Alpha customer: `navigation_only` (path length 1)
- `workflow_a7f8fc9872aef579f5` — Open reports: `not_tested` (path length 4)
- `workflow_58884963e4baa9656b` — Enter member area: `not_tested` (path length 2)
- `workflow_ef58710dbb925ce78c` — Enter member area: `not_tested` (path length 2)
- `workflow_c9fdb7cb22a35f18ff` — Enter member area: `not_tested` (path length 2)
- `workflow_192ba48341c9726859` — Enter member area: `unresolved` (path length 2)
- `workflow_42eaa62a7017f2a2a1` — Show tools: `unresolved` (path length 2)
- `workflow_6287f40dd620c0d27c` — Show tools: `unresolved` (path length 2)
- `workflow_591e0bca8fa7c5258a` — Enter member area: `not_tested` (path length 3)
- `workflow_75e4c146ff53399ccf` — Show tools: `not_tested` (path length 2)
- `workflow_5f610c75007d4f4609` — Enter member area: `not_tested` (path length 3)
- `workflow_3da172bc3665a4e7d6` — Show tools: `unresolved` (path length 2)
- `workflow_5ab32bc8a278262e30` — Enter member area: `not_tested` (path length 3)

## Observed but not replay-validated

- `feature_06c43a65adbc76d0` — Open settings opens /settings
- `feature_32b0ee5511b2895d` — Prepare workspace leads to Workspace
- `feature_418ff3806f9ef233` — Show tools leads to Coverage Lab
- `feature_6dcd32b59045751c` — Open reports opens /workspace/reports
- `feature_c026acc28579ea13` — Enter member area leads to Member

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
