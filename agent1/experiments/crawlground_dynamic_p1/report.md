# Agent 1 run agent1-20261029T000623Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-8e56e6cfeb1e`
- Policy: `coverage`
- Target: `http://127.0.0.1:3456/category/dynamic-content`
- Elapsed: 28.683 seconds
- Browser actions (including setup/replay): 103
- Replay-validated navigation categories: 11
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 7
- Replay navigation success: 11/14
- Replay failures / untested paths: 3/0
- Graph connections with complete evidence: 1577/1577
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_20376372b346fc88` — Click to expand leads to Link injected when <details> is opened
- `feature_37331aef26931b1d` — Observed link workflow to /test/forms/{instance}-xhr-post
- `feature_627ffbd129e0ee3e` — Observed link workflow to /test/dynamic-content/{instance}-localstorage
- `feature_725090f669e3de5d` — Observed link workflow to /test/dynamic-content/{instance}-sse-injected
- `feature_8ceebd43e189a84e` — Observed link workflow to /test/dynamic-content/{instance}-template-element
- `feature_8da319e14420faed` — Observed link workflow to /test/dynamic-content/{instance}-websocket-injected
- `feature_97d6f7760d013871` — Load content leads to Score link inside <template> element
- `feature_a2b72eef5a863ca2` — Set flag leads to localStorage token gates score link
- `feature_c05d1b3839726e68` — Observed link workflow to /test/dynamic-content/{instance}-intersection-observer
- `feature_ca75e9682bbe5618` — Submit via XHR leads to XMLHttpRequest POST
- `feature_d46829cf85b40872` — Observed link workflow to /test/dynamic-content/{instance}-details-toggle

## Functional path-instance outcomes

- `workflow_a93b66f9f7e95a9420` — Score link inside <template> element: `navigation_only` (path length 1)
- `workflow_72dda8907f60261c3c` — Load content: `unresolved` (path length 2)
- `workflow_bf921e2da32fbd14cd` — results.json: `failed` (path length 1)
- `workflow_cc039d6d3832ba609c` — Results: `failed` (path length 1)
- `workflow_c4cfcc5a650498ff78` — localStorage token gates score link: `navigation_only` (path length 1)
- `workflow_1a5abaac71f4a32531` — Set flag: `unresolved` (path length 2)
- `workflow_dd61f193096c112aab` — YAML export: `failed` (path length 2)
- `workflow_df966818885852f51d` — XMLHttpRequest POST: `navigation_only` (path length 2)
- `workflow_f7824db6f1846b2ae6` — Submit via XHR: `unresolved` (path length 3)
- `workflow_cb28c84435d57e16ed` — Link injected when <details> is opened: `navigation_only` (path length 1)
- `workflow_8d73244fd7498ec061` — Click to expand: `unresolved` (path length 2)
- `workflow_fccd1cab022ae8f645` — Link delivered via WebSocket: `navigation_only` (path length 1)
- `workflow_81a7fd2bdaade66789` — Link delivered via Server-Sent Events: `navigation_only` (path length 1)
- `workflow_2f2c0725dda0149cb9` — Link appears on scroll (IntersectionObserver): `navigation_only` (path length 1)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_a6b59f06cf38d06f2efc` — window.open() navigation: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_3fa3bdce3ce674cbb95b` — window.location.replace() navigation: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_84be9d14e0e809c3c876` — window.location assigned in setTimeout: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_70368c7c08266abc27ea` — Tab panel with JS-rendered content: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_6824875e0a79d706a50e` — SVG <a> element: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_1bc02c06debe45123c3a` — Single-level CSS :hover dropdown: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_21a121c951e790036df3` — Right-click (contextmenu) link injection: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_f542c00434942dbb553c` — POST form with submit button: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_26f58cd66c2655b2a973` — Popover API — link injected on open: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_05067002b19be5bdc591` — pointerup event triggers navigation: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_9e77db996f9113bbc668` — Plain anchor with href: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_9cbb7184f65e0f2f7052` — onclick with preventDefault — JS-only navigation: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_8327d6ce81a58504157f` — Multi-step form wizard: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_d390dd7f938693027aa6` — Multi-level JS dropdown menu: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_58f5e680b3f5d80f108b` — Meta refresh redirect: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a
- `tr_68777272bdda03a80dea` — Long press (mousedown hold) triggers navigation: RuntimeError: saved return path restored 6f70bd4535855da7, expected 82c70558c50c968a

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
