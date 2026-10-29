# Agent 1 run agent1-20261029T001347Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-a787d6fa301e`
- Policy: `coverage`
- Target: `http://127.0.0.1:3456/category/dynamic-content`
- Elapsed: 37.210 seconds
- Browser actions (including setup/replay): 136
- Replay-validated navigation categories: 13
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 19
- Replay navigation success: 17/27
- Replay failures / untested paths: 10/3
- Graph connections with complete evidence: 700/700
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_1cc16589cb2f7764` — Observed link workflow to /score/dynamic-content/{instance}-details-toggle
- `feature_20376372b346fc88` — Click to expand leads to Link injected when <details> is opened
- `feature_370ad83af12aa507` — navigation opens /category/navigation
- `feature_37331aef26931b1d` — Observed link workflow to /test/forms/{instance}-xhr-post
- `feature_461d92080e24b75c` — Observed link workflow to /test/navigation/{instance}-window-replace
- `feature_627ffbd129e0ee3e` — Observed link workflow to /test/dynamic-content/{instance}-localstorage
- `feature_7334cf8c864ccf38` — Observed link workflow to /test/navigation/{instance}-window-location-timeout
- `feature_97d6f7760d013871` — Load content leads to Score link inside <template> element
- `feature_a2b72eef5a863ca2` — Set flag leads to localStorage token gates score link
- `feature_ca75e9682bbe5618` — Submit via XHR leads to XMLHttpRequest POST
- `feature_d24cf3bba4ed2688` — Observed link workflow to /score/dynamic-content/{instance}-template-element
- `feature_d46829cf85b40872` — Observed link workflow to /test/dynamic-content/{instance}-details-toggle
- `feature_fa5336044cb1ec2a` — Observed link workflow to /score/dynamic-content/{instance}-localstorage

## Functional path-instance outcomes

- `workflow_9997c85a9bba62f853` — Score link inside <template> element: `navigation_only` (path length 1)
- `workflow_1e44dce31814d1788c` — Load content: `unresolved` (path length 2)
- `workflow_2c9fec919b390eed14` — Click me: `navigation_only` (path length 3)
- `workflow_056c3b4de5c964c0de` — Back to dynamic-content: `not_tested` (path length 4)
- `workflow_40cdb7fccbf639e102` — Score link inside <template> element: `not_tested` (path length 5)
- `workflow_c276219796f8efc2a0` — dynamic-content: `failed` (path length 2)
- `workflow_b5c714a226d56852c5` — results.json: `failed` (path length 3)
- `workflow_c229b31a6b4ce66a40` — results.json: `failed` (path length 1)
- `workflow_2be3c1869a34cde415` — Results: `failed` (path length 1)
- `workflow_914746070a2d0d2ad1` — YAML export: `failed` (path length 2)
- `workflow_8a1f323682e649e3e8` — localStorage token gates score link: `navigation_only` (path length 1)
- `workflow_b306afa1df924ff7b7` — Set flag: `unresolved` (path length 2)
- `workflow_c9cffcf17f2c4616c2` — Click me: `navigation_only` (path length 3)
- `workflow_25f76914ffb192a0b2` — results.json: `failed` (path length 4)
- `workflow_12de9a71cf5760246b` — XMLHttpRequest POST: `navigation_only` (path length 2)
- `workflow_c4eafeb3a7336b3871` — Submit via XHR: `unresolved` (path length 3)
- `workflow_71ed8bdb1d6d706b39` — Submit via XHR: `unresolved` (path length 4)
- `workflow_397eb44fbce1532246` — results.json: `failed` (path length 4)
- `workflow_519e4d87794d083068` — window.open() navigation: `navigation_only` (path length 2)
- `workflow_2444e92aa70208ce51` — Open popup: `unresolved` (path length 3)
- `workflow_dafba96d880fd66e0d` — navigation: `navigation_only` (path length 3)
- `workflow_732f9aee3d01e893a6` — window.open() navigation: `not_tested` (path length 4)
- `workflow_c92a99e25a9d76b390` — results.json: `failed` (path length 3)
- `workflow_d70b4f9a9b81542cfc` — window.location.replace() navigation: `navigation_only` (path length 2)
- `workflow_816f38aa63fadc8f5f` — results.json: `failed` (path length 3)
- `workflow_8ca751053f7d1c925a` — window.location assigned in setTimeout: `navigation_only` (path length 2)
- `workflow_92ca5fd4945cbc8c17` — results.json: `failed` (path length 3)
- `workflow_2e393b17efd0c4212a` — Link injected when <details> is opened: `navigation_only` (path length 1)
- `workflow_e9f5eb03a0b8aff544` — Click to expand: `unresolved` (path length 2)
- `workflow_97c031443a2b5c7f8e` — Click me: `navigation_only` (path length 3)

## Observed but not replay-validated

- `feature_8ceebd43e189a84e` — Observed link workflow to /test/dynamic-content/{instance}-template-element
- `feature_b8672fe8de95e5fe` — Observed link workflow to /test/navigation/{instance}-window-open

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- Restoration content signature differed, but the independently compared interaction shape remained usable for c2bd957d51ef690e.
- Restoration content signature differed, but the independently compared interaction shape remained usable for cec6c06975c13d42.
- Restoration content signature differed, but the independently compared interaction shape remained usable for 674201e1576f60e2.
- Restoration content signature differed, but the independently compared interaction shape remained usable for 53bd02a6792f5197.
- Restoration content signature differed, but the independently compared interaction shape remained usable for 3f14bbc12e0b8b3b.
- Restoration content signature differed, but the independently compared interaction shape remained usable for 189d70ecb0c379a0.
- Restoration content signature differed, but the independently compared interaction shape remained usable for eebf928afa64c36e.
- Restoration content signature differed, but the independently compared interaction shape remained usable for 1580b3c4dc8fe68a.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
