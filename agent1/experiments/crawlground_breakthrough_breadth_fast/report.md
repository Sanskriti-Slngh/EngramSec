# Agent 1 run agent1-20261029T011929Z

- Code revision: `2b8aa183db268243e36a76153407758ad6b218ff+mapper-4630211710e5`
- Policy: `breadth`
- Target: `http://127.0.0.1:3456/`
- Elapsed: 38.808 seconds
- Browser actions (including setup/replay): 75
- Replay-validated navigation categories: 14
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 16
- Replay navigation success: 16/16
- Replay failures / untested paths: 0/14
- Graph connections with complete evidence: 703/703
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_02ddb2707d3ca8b7` — Results opens /results
- `feature_0d027f56db388620` — Observed link workflow to /test/links/{instance}-target-blank
- `feature_16dde48efdb31889` — frames opens /category/frames
- `feature_19679822e5f2c979` — links opens /category/links
- `feature_4b2ed0ea192f9132` — Next → leads to Multi-step form wizard
- `feature_51c4b595d472e498` — forms opens /category/forms
- `feature_60809bf3720fc549` — Observed link workflow to /test/dynamic-content/{instance}-details-toggle
- `feature_6249d01ddb790c04` — dynamic-content opens /category/dynamic-content
- `feature_7c358f1606586bb3` — Observed link workflow to /test/forms/{instance}-multistep-wizard
- `feature_8bfb5cbdd854ffff` — navigation opens /category/navigation
- `feature_cc29e7c6623cfd86` — Observed link workflow to /test/js-events/{instance}-tab-panel
- `feature_cd90470a0e14dd0e` — Observed link workflow to /test/forms/{instance}-fetch-get
- `feature_dfb923657558e2e9` — results.json opens /results.json
- `feature_e0166645920169a5` — js-events opens /category/js-events

## Functional path-instance outcomes

- `workflow_f550cb782efde2eccc` — frames: `navigation_only` (path length 1)
- `workflow_b6fc81ca4d366cf23e` — Categories: `not_tested` (path length 2)
- `workflow_8bd23168149517a6e1` — dynamic-content: `navigation_only` (path length 1)
- `workflow_911e387052288a6b8c` — Link injected when <details> is opened: `not_tested` (path length 2)
- `workflow_e729f6e1bd40385179` — Categories: `not_tested` (path length 3)
- `workflow_294c7d1f24d57aed97` — navigation: `navigation_only` (path length 1)
- `workflow_f4167d653201823132` — Categories: `not_tested` (path length 2)
- `workflow_68252f2d5e7be7470e` — Results: `navigation_only` (path length 1)
- `workflow_d8d93b56d2384b0bcf` — Tab panel with JS-rendered content: `not_tested` (path length 2)
- `workflow_ea1938ab0c56cd406c` — Categories: `not_tested` (path length 3)
- `workflow_e1d15e1a22088804f0` — View results →: `not_tested` (path length 1)
- `workflow_56a1eb926b0e8d5855` — Multi-step form wizard: `not_tested` (path length 2)
- `workflow_b45ad8a8c92ffcd4de` — Next →: `unresolved` (path length 3)
- `workflow_b8ebda10c08818c4aa` — Categories: `not_tested` (path length 4)
- `workflow_e573a62dff8d2ef6a6` — links: `navigation_only` (path length 1)
- `workflow_2627a1420e10e0c992` — Anchor with target="_blank": `navigation_only` (path length 2)
- `workflow_8a551e55ae80ccd0be` — Categories: `not_tested` (path length 3)
- `workflow_41a2a2c45e2f684f23` — Crawlground: `not_tested` (path length 1)
- `workflow_894b528610f5197780` — Categories: `navigation_only` (path length 1)
- `workflow_013e3ac133e7b93bbc` — js-events: `navigation_only` (path length 1)
- `workflow_c6dabfab21ad1bad97` — Tab panel with JS-rendered content: `navigation_only` (path length 2)
- `workflow_965b482f3057235933` — Results: `not_tested` (path length 3)
- `workflow_59061fd73c8465ded6` — Link injected when <details> is opened: `navigation_only` (path length 2)
- `workflow_4485eba2fe05d26058` — Results: `not_tested` (path length 3)
- `workflow_0b3c2dd6ced77ac133` — AJAX fetch() GET — no <form> element: `navigation_only` (path length 2)
- `workflow_8b9df9690e26c636a1` — Categories: `not_tested` (path length 3)
- `workflow_07f1f80dcdcd2848b5` — results.json: `navigation_only` (path length 1)
- `workflow_6af2da2dbbfb3f6732` — Scroll viewport: `unresolved` (path length 2)
- `workflow_91a88e7075853b3024` — forms: `navigation_only` (path length 1)
- `workflow_39bb6b6deb568b30ca` — Multi-step form wizard: `navigation_only` (path length 2)

## Observed but not replay-validated

- `feature_1e6109cb24db6228` — Categories opens /
- `feature_4c904ca9c09628ca` — View results → opens /results
- `feature_5e2a21b08c63d14c` — Categories opens /
- `feature_65a9095d7add88a6` — Categories opens /
- `feature_7cbe58bde42fec86` — Observed link workflow to /test/forms/{instance}-multistep-wizard
- `feature_962af4edcdbab6b9` — Categories opens /
- `feature_a6da4955dacb9043` — Categories opens /
- `feature_a7a275f6e4bebe07` — Categories opens /
- `feature_b927ac02b78ab674` — Observed link workflow to /test/dynamic-content/{instance}-details-toggle
- `feature_d19bf45c19d54338` — Categories opens /
- `feature_d21f53264ff8328e` — Results opens /results
- `feature_e587d812d3df6ae4` — Observed link workflow to /test/js-events/{instance}-tab-panel
- `feature_fe979309b8a2acdb` — Results opens /results

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
