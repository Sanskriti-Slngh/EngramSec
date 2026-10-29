# Agent 1 run agent1-20261029T010859Z

- Code revision: `2b8aa183db268243e36a76153407758ad6b218ff+mapper-b73d22f4aa48`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:3456/`
- Elapsed: 61.713 seconds
- Browser actions (including setup/replay): 123
- Replay-validated navigation categories: 8
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 18
- Replay navigation success: 12/25
- Replay failures / untested paths: 13/4
- Graph connections with complete evidence: 815/815
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_19679822e5f2c979` — links opens /category/links
- `feature_2d33c3ce88630cf3` — other opens /category/other
- `feature_8f003f54e883778b` — Back to navigation opens /category/navigation
- `feature_b5705e53cbf5090e` — other opens /category/other
- `feature_cd38990d4bdcceb7` — Observed link workflow to /test/navigation/{instance}-window-open
- `feature_d2bbeac31f107071` — Link injected on input focus opens /category/js-events
- `feature_e0166645920169a5` — js-events opens /category/js-events
- `feature_e18b4cc98ecbeb4e` — Observed link workflow to /test/other/{instance}-bot-detection-globals

## Functional path-instance outcomes

- `workflow_54f78da27fe8dbf514` — View results →: `failed` (path length 1)
- `workflow_5ec348fcb51305fb2e` — YAML export: `failed` (path length 2)
- `workflow_fadfe8b88c37c59374` — Scroll viewport: `failed` (path length 3)
- `workflow_352cb4b1715d918ddd` — other: `navigation_only` (path length 1)
- `workflow_e700d0dd3c6b1e265c` — Bot-detection globals check: `navigation_only` (path length 2)
- `workflow_526c8c6517e98b4560` — other: `navigation_only` (path length 3)
- `workflow_968d2506b25c4ae34b` — navigation: `failed` (path length 1)
- `workflow_3ffe0596cb21e07ee3` — Scroll viewport: `failed` (path length 2)
- `workflow_7c6e4874011d9d741b` — window.open() navigation: `navigation_only` (path length 2)
- `workflow_86e4a18f3801034879` — Open popup: `unresolved` (path length 3)
- `workflow_107d6e04a481ce9273` — Back to navigation: `navigation_only` (path length 4)
- `workflow_e7a238ba86f8354c60` — window.open() navigation: `navigation_only` (path length 5)
- `workflow_2478ee80284b353a28` — Open popup: `not_tested` (path length 6)
- `workflow_8b1043a0933cfa19d1` — All results: `failed` (path length 4)
- `workflow_07ed2c6b7a99e1ba47` — Single-level CSS :hover dropdown: `failed` (path length 5)
- `workflow_d538744dbe24ba8376` — Link injected on mouseover: `not_tested` (path length 6)
- `workflow_f1857fdd97df25469a` — Single-level CSS :hover dropdown: `not_tested` (path length 7)
- `workflow_650c06b803a4190d38` — YAML export: `not_tested` (path length 6)
- `workflow_27d1dab77716c0d38d` — links: `navigation_only` (path length 1)
- `workflow_7fd3f9ccd1539aa488` — SVG <a> element: `failed` (path length 2)
- `workflow_1cd893a57fca63b0b3` — js-events: `navigation_only` (path length 1)
- `workflow_a364934367b8097455` — Single-level CSS :hover dropdown: `navigation_only` (path length 2)
- `workflow_4071bb0225bdca09b8` — Link injected on mouseover: `failed` (path length 2)
- `workflow_0f9c58f025dae2d3c4` — Link injected on mouseover: `failed` (path length 3)
- `workflow_6da6726584da1276e6` — Link injected on input focus: `navigation_only` (path length 3)
- `workflow_4000b2683c4559ad85` — Link injected on input focus: `navigation_only` (path length 2)
- `workflow_bbc03483e40ea74766` — Tab panel with JS-rendered content: `failed` (path length 2)
- `workflow_6df0ff82b9df275a38` — Tab 3: `failed` (path length 3)
- `workflow_26873d6452b7bbe258` — Tab 3: `failed` (path length 4)

## Observed but not replay-validated

- `feature_6df0c892508e02b1` — Open popup leads to Scored
- `feature_ff5a03a1846bc2fa` — Link injected on mouseover opens /results

## Failed or blocked transitions

- `tr_16cd202ec218b7d4a493` — unnamed link: RuntimeError: navigation candidate has no observed target

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
