# Agent 1 run agent1-20261029T003607Z

- Code revision: `2b8aa183db268243e36a76153407758ad6b218ff+mapper-a787d6fa301e`
- Policy: `coverage`
- Target: `http://127.0.0.1:3456/`
- Elapsed: 37.124 seconds
- Browser actions (including setup/replay): 135
- Replay-validated navigation categories: 9
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 15
- Replay navigation success: 17/27
- Replay failures / untested paths: 10/0
- Graph connections with complete evidence: 830/830
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_1031e8c76f431515` — Observed link workflow to /test/js-events/{instance}-tab-panel
- `feature_2b9002120dc2c497` — Observed link workflow to /test/links/{instance}-svg-anchor
- `feature_370ad83af12aa507` — navigation opens /category/navigation
- `feature_37331aef26931b1d` — Observed link workflow to /test/forms/{instance}-xhr-post
- `feature_747a88432fa2845c` — Tab 3 leads to Tab panel with JS-rendered content
- `feature_b8672fe8de95e5fe` — Observed link workflow to /test/navigation/{instance}-window-open
- `feature_c07dc08199596715` — other opens /category/other
- `feature_ca75e9682bbe5618` — Submit via XHR leads to XMLHttpRequest POST
- `feature_fbdfde0e0e8274c7` — js-events opens /category/js-events

## Functional path-instance outcomes

- `workflow_d26238ffa17f328c43` — View results →: `failed` (path length 1)
- `workflow_c6a767d1874b045c1e` — YAML export: `failed` (path length 2)
- `workflow_cfc73f84d49ac16110` — results.json: `failed` (path length 1)
- `workflow_bf39674277bb308a43` — Results: `failed` (path length 1)
- `workflow_9bd2bbaca97167a9c7` — XMLHttpRequest POST: `navigation_only` (path length 2)
- `workflow_ca2d9285004e1e2d20` — Submit via XHR: `unresolved` (path length 3)
- `workflow_0ceb4c0da325d7d165` — Submit via XHR: `unresolved` (path length 4)
- `workflow_4e962522ab95c519c8` — results.json: `failed` (path length 4)
- `workflow_9bc4cb3c39a3a3f57e` — other: `navigation_only` (path length 1)
- `workflow_182b8c4ea2bd57cdf0` — results.json: `failed` (path length 2)
- `workflow_3d7e8ec287adae6383` — window.open() navigation: `navigation_only` (path length 2)
- `workflow_0b1c9fdadf6b229094` — Open popup: `unresolved` (path length 3)
- `workflow_647a98785b714f8562` — results.json: `failed` (path length 3)
- `workflow_094e45ca8c05b46bce` — navigation: `navigation_only` (path length 1)
- `workflow_f94acccdecfbb1a3e2` — window.open() navigation: `navigation_only` (path length 2)
- `workflow_d20acb153e1b84e146` — Results: `failed` (path length 3)
- `workflow_8dbacefbc567b07f07` — YAML export: `failed` (path length 2)
- `workflow_7fd98b17da525a8e03` — links: `failed` (path length 1)
- `workflow_ab1b9b8648bbe76a56` — SVG <a> element: `navigation_only` (path length 2)
- `workflow_8a16d5cd00307d00f4` — unnamed link: `navigation_only` (path length 3)
- `workflow_e53d62924d90a76ded` — Back to links: `navigation_only` (path length 4)
- `workflow_a6cf9a05f7eaaa2df5` — SVG <a> element: `navigation_only` (path length 5)
- `workflow_ee505469ef30e50a39` — results.json: `navigation_only` (path length 3)
- `workflow_1c9b1d7bba0bebee75` — js-events: `navigation_only` (path length 1)
- `workflow_3778724f689bc9383e` — Tab panel with JS-rendered content: `navigation_only` (path length 2)
- `workflow_488987e1b43603e5e0` — Tab 3: `unresolved` (path length 3)
- `workflow_b51feabb7d9924569f` — Tab 3: `unresolved` (path length 4)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_6b171a1717a1645942b0` — window.location.replace() navigation: RuntimeError: saved return path restored be582a34a3d5fe92, expected 7b37d4d1894c7916
- `tr_010903137b135352f27d` — window.location assigned in setTimeout: RuntimeError: saved return path restored be582a34a3d5fe92, expected 7b37d4d1894c7916
- `tr_f8eb24aa40e0d8a7b2b6` — Tab panel with JS-rendered content: RuntimeError: saved return path restored 3828ddb3bbe64b03, expected 7b37d4d1894c7916

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- Restoration content signature differed, but the independently compared interaction shape remained usable for 3f14bbc12e0b8b3b.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
