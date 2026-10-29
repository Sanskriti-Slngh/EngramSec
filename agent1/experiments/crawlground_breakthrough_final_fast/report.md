# Agent 1 run agent1-20261029T011811Z

- Code revision: `2b8aa183db268243e36a76153407758ad6b218ff+mapper-4630211710e5`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:3456/`
- Elapsed: 61.185 seconds
- Browser actions (including setup/replay): 127
- Replay-validated navigation categories: 11
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 18
- Replay navigation success: 14/23
- Replay failures / untested paths: 9/7
- Graph connections with complete evidence: 527/528
- Graph connections missing evidence: 1
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_0355c7faf2d5da13` — Back to links opens /category/links
- `feature_19679822e5f2c979` — links opens /category/links
- `feature_19940a38217fb73c` — links opens /category/links
- `feature_2d33c3ce88630cf3` — other opens /category/other
- `feature_877004843b322fd0` — All results opens /results
- `feature_8bfb5cbdd854ffff` — navigation opens /category/navigation
- `feature_8f003f54e883778b` — Back to navigation opens /category/navigation
- `feature_cd38990d4bdcceb7` — Observed link workflow to /test/navigation/{instance}-window-open
- `feature_d7f49c9eb12b4267` — YAML export opens /results.yaml
- `feature_e0166645920169a5` — js-events opens /category/js-events
- `feature_e18b4cc98ecbeb4e` — Observed link workflow to /test/other/{instance}-bot-detection-globals

## Functional path-instance outcomes

- `workflow_a0b277547b8f56cf57` — other: `navigation_only` (path length 1)
- `workflow_433bd62b00554c9f71` — Bot-detection globals check: `navigation_only` (path length 2)
- `workflow_2af558a34f12816f1e` — other: `not_tested` (path length 3)
- `workflow_c9670aefa39f072eec` — navigation: `navigation_only` (path length 1)
- `workflow_b3d130cc0ef52c2474` — window.open() navigation: `navigation_only` (path length 2)
- `workflow_12eca33a17c98bd239` — Open popup: `unresolved` (path length 3)
- `workflow_012aae64f9da532d79` — Back to navigation: `navigation_only` (path length 4)
- `workflow_11114288c53fae4017` — window.open() navigation: `navigation_only` (path length 5)
- `workflow_ad71f6d953b7923f8e` — Scroll viewport: `unresolved` (path length 6)
- `workflow_b4d0245c1e6d1e6370` — Open popup: `not_tested` (path length 6)
- `workflow_0a43c11011202d88ea` — All results: `navigation_only` (path length 4)
- `workflow_242ebcca845798a274` — YAML export: `navigation_only` (path length 5)
- `workflow_98e4e799edcc9ad8d6` — Scroll viewport: `not_tested` (path length 6)
- `workflow_b3042d8b925c7b7fce` — links: `navigation_only` (path length 1)
- `workflow_e6e6012ab14d1277c9` — SVG <a> element: `failed` (path length 2)
- `workflow_30ee87d40d38afabc8` — unnamed link: `failed` (path length 3)
- `workflow_095f8b3c361d140ad3` — Back to links: `not_tested` (path length 4)
- `workflow_93f4681fed8dfee6bc` — SVG <a> element: `not_tested` (path length 5)
- `workflow_859c5a7e35e4d681ec` — Scroll viewport: `failed` (path length 3)
- `workflow_3a1fb14916deb9d227` — links: `navigation_only` (path length 3)
- `workflow_9f7da9cfcc8fcc0b59` — Plain anchor with href: `failed` (path length 4)
- `workflow_fd3273f8322a897bd7` — Click me: `failed` (path length 5)
- `workflow_82a51e8812b680f737` — Back to links: `navigation_only` (path length 6)
- `workflow_851a55f257699286f0` — SVG <a> element: `not_tested` (path length 7)
- `workflow_16e58077e7d8933736` — js-events: `navigation_only` (path length 1)
- `workflow_858bc4e1e09cd0dcfa` — Tab panel with JS-rendered content: `failed` (path length 2)
- `workflow_1615f4212cb6d01b51` — Tab 3: `failed` (path length 3)
- `workflow_7a43464dc8a82121e8` — Tab 3: `not_tested` (path length 4)
- `workflow_0101946e11ea545889` — frames: `failed` (path length 1)
- `workflow_c5344e9a89bcabbefc` — Link inside same-origin iframe (srcdoc): `failed` (path length 2)

## Observed but not replay-validated

- `feature_4d863dd9d9dc6aad` — Back to links opens /category/links
- `feature_6df0c892508e02b1` — Open popup leads to Scored
- `feature_b5705e53cbf5090e` — other opens /category/other

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
