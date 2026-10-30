# Agent 1 run agent1-20261030T202530Z

- Code revision: `5710c01fbcd2b09fab0886cbc0eedf65b0b1510e+mapper-fe94def219a5`
- Policy: `hierarchical`
- Target: `http://127.0.0.1:3460/`
- Elapsed: 20.851 seconds
- Browser actions (including setup/replay): 46
- Replay-validated navigation categories: 9
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 1
- Replay navigation success: 9/9
- Replay failures / untested paths: 0/1
- Graph connections with complete evidence: 969/969
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_09b360029d057bf8` — font-face.html opens /css/font-face.html
- `feature_3531dbd3511a8d44` — content-location/ opens /headers/content-location/
- `feature_4f48554801804ce5` — location/ opens /test/headers/location.found
- `feature_6f6ffbd2a0199e3e` — CSS opens /css/
- `feature_7d1756ba5d7cb6e4` — HTML opens /html/
- `feature_93ea1e291784ce15` — JavaScript opens /javascript/
- `feature_9fe133e4cf904946` — Misc opens /misc/
- `feature_c06bd8289171ed68` — Response headers opens /headers/
- `feature_df5f963876e079ed` — link/ opens /headers/link/

## Functional path-instance outcomes

- `workflow_ba74baa922326e5217` — Response headers: `navigation_only` (path length 1)
- `workflow_991a2d86bbc89f2f71` — Misc: `navigation_only` (path length 1)
- `workflow_8b2c9c71c7f8154a79` — JavaScript: `navigation_only` (path length 1)
- `workflow_431858e9cb2d630235` — HTML: `navigation_only` (path length 1)
- `workflow_7353eed265097f81bf` — CSS: `navigation_only` (path length 1)
- `workflow_bf146b39f013796004` — font-face.html: `navigation_only` (path length 2)
- `workflow_5d4f38f77fb59511ea` — refresh/: `not_tested` (path length 2)
- `workflow_eff56a44618d55a081` — location/: `navigation_only` (path length 2)
- `workflow_dd579ea8cdd792fc42` — link/: `navigation_only` (path length 2)
- `workflow_121466386618344d92` — content-location/: `navigation_only` (path length 2)

## Observed but not replay-validated

- `feature_4719d72f368a294c` — refresh/ opens /headers/refresh/

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- ZAP evidence is externally reported and does not prove a UI transition or replay.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
