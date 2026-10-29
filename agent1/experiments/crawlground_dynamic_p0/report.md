# Agent 1 run agent1-20261029T000530Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-8e56e6cfeb1e`
- Policy: `coverage`
- Target: `http://127.0.0.1:3456/category/dynamic-content`
- Elapsed: 42.818 seconds
- Browser actions (including setup/replay): 103
- Replay-validated navigation categories: 11
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 7
- Replay navigation success: 11/14
- Replay failures / untested paths: 3/0
- Graph connections with complete evidence: 1579/1579
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

- `workflow_8ea40a7b0e5ac9bac7` — Score link inside <template> element: `navigation_only` (path length 1)
- `workflow_624bf6e5e235bfd530` — Load content: `unresolved` (path length 2)
- `workflow_29f4db7f708df456b1` — results.json: `failed` (path length 1)
- `workflow_d902632cabde80198a` — Results: `failed` (path length 1)
- `workflow_d45690e821e4acebe1` — localStorage token gates score link: `navigation_only` (path length 1)
- `workflow_80487c318fbea389b9` — Set flag: `unresolved` (path length 2)
- `workflow_e5c9ffae389c751aac` — YAML export: `failed` (path length 2)
- `workflow_e1d08c51cdcf42c658` — XMLHttpRequest POST: `navigation_only` (path length 2)
- `workflow_f3291a0b1719dcd42e` — Submit via XHR: `unresolved` (path length 3)
- `workflow_4fc853f5cdae123ccc` — Link injected when <details> is opened: `navigation_only` (path length 1)
- `workflow_8becef07e1d348e0a0` — Click to expand: `unresolved` (path length 2)
- `workflow_d4acfeefcf28e9cd36` — Link delivered via WebSocket: `navigation_only` (path length 1)
- `workflow_3d2b7a9c0e270f12ac` — Link delivered via Server-Sent Events: `navigation_only` (path length 1)
- `workflow_81dff3912165e0c59c` — Link appears on scroll (IntersectionObserver): `navigation_only` (path length 1)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_bac559e7e12592574e5c` — window.open() navigation: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_17fbe6f57afbe2405ae9` — window.location.replace() navigation: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_eb2e29c3b1a6b6563e24` — window.location assigned in setTimeout: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_49ebd614d64301694457` — Tab panel with JS-rendered content: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_d75a746abbea582e3e0e` — SVG <a> element: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_f1b6c817c28838e3c47a` — Single-level CSS :hover dropdown: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_8646fdab6b542bfc2056` — Right-click (contextmenu) link injection: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_7205000e0d4fc68b3f24` — POST form with submit button: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_bf2802aedad3b24807a1` — Popover API — link injected on open: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_0eadba4eea76105f043c` — pointerup event triggers navigation: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_4f7c39d65bd1731e1b9f` — Plain anchor with href: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_ce08aeb9885d892567ce` — onclick with preventDefault — JS-only navigation: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_5431c013c8995a046dd8` — Multi-step form wizard: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_5dc3602d4d1a7235d8e2` — Multi-level JS dropdown menu: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_c7892757e3a43b7a2059` — Meta refresh redirect: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f
- `tr_713c08bf4e8015fc702e` — Long press (mousedown hold) triggers navigation: RuntimeError: saved return path restored b0a4b64cf3062721, expected 5b18c834b50ef25f

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
