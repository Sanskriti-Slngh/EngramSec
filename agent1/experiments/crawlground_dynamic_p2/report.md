# Agent 1 run agent1-20261029T000703Z

- Code revision: `1551947368901f25afa5879442c1680bbc9d511b+mapper-8e56e6cfeb1e`
- Policy: `coverage`
- Target: `http://127.0.0.1:3456/category/dynamic-content`
- Elapsed: 39.427 seconds
- Browser actions (including setup/replay): 141
- Replay-validated navigation categories: 14
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 18
- Replay navigation success: 18/28
- Replay failures / untested paths: 10/2
- Graph connections with complete evidence: 701/701
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
- `feature_b8672fe8de95e5fe` — Observed link workflow to /test/navigation/{instance}-window-open
- `feature_ca75e9682bbe5618` — Submit via XHR leads to XMLHttpRequest POST
- `feature_d24cf3bba4ed2688` — Observed link workflow to /score/dynamic-content/{instance}-template-element
- `feature_d46829cf85b40872` — Observed link workflow to /test/dynamic-content/{instance}-details-toggle
- `feature_fa5336044cb1ec2a` — Observed link workflow to /score/dynamic-content/{instance}-localstorage

## Functional path-instance outcomes

- `workflow_50069e77f469cd6c86` — Score link inside <template> element: `navigation_only` (path length 1)
- `workflow_05326f2b46ad5aa602` — Load content: `unresolved` (path length 2)
- `workflow_c83efff78698368778` — Click me: `navigation_only` (path length 3)
- `workflow_9cec662e44d19625c8` — Back to dynamic-content: `not_tested` (path length 4)
- `workflow_c4621ef593bfe62559` — Score link inside <template> element: `not_tested` (path length 5)
- `workflow_1ff5745a960d4566a5` — dynamic-content: `failed` (path length 2)
- `workflow_dd51d8af6f2a6e4bb5` — results.json: `failed` (path length 3)
- `workflow_3f5d745edd405eb8df` — results.json: `failed` (path length 1)
- `workflow_8ba2f7cdb17da6b256` — Results: `failed` (path length 1)
- `workflow_1caae1f15a47e544f7` — YAML export: `failed` (path length 2)
- `workflow_5228f95b5d24641f91` — localStorage token gates score link: `navigation_only` (path length 1)
- `workflow_9dfe1fb9d04930bef5` — Set flag: `unresolved` (path length 2)
- `workflow_81b3906872fae3ebd7` — Click me: `navigation_only` (path length 3)
- `workflow_cf0882eb51ac3ff1d5` — results.json: `failed` (path length 4)
- `workflow_89f9cd92395faf170a` — XMLHttpRequest POST: `navigation_only` (path length 2)
- `workflow_faccb836aaa8b7d1ae` — Submit via XHR: `unresolved` (path length 3)
- `workflow_554bc24067cf299a95` — Submit via XHR: `unresolved` (path length 4)
- `workflow_674fdaaf8ceedf3a56` — results.json: `failed` (path length 4)
- `workflow_411ac6db9f91cd3eaf` — window.open() navigation: `navigation_only` (path length 2)
- `workflow_09236d18c39ea5075b` — Open popup: `unresolved` (path length 3)
- `workflow_c5aa12a838aa041343` — navigation: `navigation_only` (path length 3)
- `workflow_daaf17e2d087e2c116` — window.open() navigation: `navigation_only` (path length 4)
- `workflow_1f5b3a21cf3ab5de10` — results.json: `failed` (path length 3)
- `workflow_0b377948a85e632bda` — window.location.replace() navigation: `navigation_only` (path length 2)
- `workflow_f2c81eb24f136bd1b8` — results.json: `failed` (path length 3)
- `workflow_7141acc2ac6c53aa0d` — window.location assigned in setTimeout: `navigation_only` (path length 2)
- `workflow_8fbadcbe733ae3a95e` — results.json: `failed` (path length 3)
- `workflow_9605c9fba64733427d` — Link injected when <details> is opened: `navigation_only` (path length 1)
- `workflow_365dad0c2c1707ad12` — Click to expand: `unresolved` (path length 2)
- `workflow_75d03d2fb093c30063` — Click me: `navigation_only` (path length 3)

## Observed but not replay-validated

- `feature_8ceebd43e189a84e` — Observed link workflow to /test/dynamic-content/{instance}-template-element

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
