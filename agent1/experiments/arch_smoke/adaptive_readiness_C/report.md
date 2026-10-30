# Agent 1 run agent1-20261030T210836Z

- Code revision: `5710c01fbcd2b09fab0886cbc0eedf65b0b1510e+mapper-3262f58a7ee6`
- Policy: `hierarchical`
- Target: `http://127.0.0.1:3460/`
- Elapsed: 40.487 seconds
- Browser actions (including setup/replay): 88
- Replay-validated navigation categories: 11
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 16
- Replay navigation success: 11/11
- Replay failures / untested paths: 0/16
- Graph connections with complete evidence: 470/470
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_09b360029d057bf8` — font-face.html opens /css/font-face.html
- `feature_14ff0e53dc96656c` — frameworks/ opens /javascript/frameworks/
- `feature_3699dc387e5599e0` — known-files/ opens /misc/known-files/
- `feature_41ba3209725933d5` — manifest.html opens /html/manifest.html/
- `feature_4719d72f368a294c` — refresh/ opens /headers/refresh/
- `feature_6f6ffbd2a0199e3e` — CSS opens /css/
- `feature_7d1756ba5d7cb6e4` — HTML opens /html/
- `feature_93ea1e291784ce15` — JavaScript opens /javascript/
- `feature_9fe133e4cf904946` — Misc opens /misc/
- `feature_c06bd8289171ed68` — Response headers opens /headers/
- `feature_ec82d30050a88157` — head/ opens /html/head/

## Functional path-instance outcomes

- `workflow_06e44a3faa84e5333a` — Response headers: `navigation_only` (path length 1)
- `workflow_bd9fdde72dc589d7db` — Misc: `navigation_only` (path length 1)
- `workflow_c1c45ba8ba4a309810` — JavaScript: `navigation_only` (path length 1)
- `workflow_2067cf117f0ff33d28` — HTML: `navigation_only` (path length 1)
- `workflow_57dd1b54c501dbb261` — CSS: `navigation_only` (path length 1)
- `workflow_7e9176a226e615e11a` — font-face.html: `navigation_only` (path length 2)
- `workflow_bc22086d423e8ea9fd` — refresh/: `navigation_only` (path length 2)
- `workflow_a320f0508773653cc6` — location/: `not_tested` (path length 2)
- `workflow_90ce72f1b41fffc4ac` — link/: `not_tested` (path length 2)
- `workflow_2b001eb8b4ec23926e` — content-location/: `not_tested` (path length 2)
- `workflow_6065e4aecec1258731` — manifest.html: `navigation_only` (path length 2)
- `workflow_dd2d5d954a1e083adc` — head/: `navigation_only` (path length 2)
- `workflow_f8b297bb8243fbd99d` — profile.html: `not_tested` (path length 3)
- `workflow_a3a9dc12d524a0a341` — doctype.html: `not_tested` (path length 2)
- `workflow_f6a92d2f56d188b0fd` — body/: `not_tested` (path length 2)
- `workflow_2c8a339f6abc62fe60` — video/: `not_tested` (path length 3)
- `workflow_e5515ec3034730c402` — track/: `not_tested` (path length 4)
- `workflow_1b64b53ae262e602aa` — src.html: `not_tested` (path length 5)
- `workflow_2c9d3df625d9a69403` — misc/: `not_tested` (path length 2)
- `workflow_84a674a1bc6f2b8bfd` — string-variable.html: `not_tested` (path length 3)
- `workflow_c2bccdb9fc733fe356` — interactive/: `not_tested` (path length 2)
- `workflow_544a17b16c3a92b10c` — two-listeners.html: `not_tested` (path length 3)
- `workflow_592d5654e1e59044b0` — Submit: `not_tested` (path length 4)
- `workflow_0678973dfbe00e25ec` — frameworks/: `navigation_only` (path length 2)
- `workflow_14eccfc81e341c864b` — react/: `not_tested` (path length 3)
- `workflow_37650b611fc860a795` — multi-step-request-redefine-event-attribute.html: `not_tested` (path length 3)
- `workflow_8dd1ed469457d8a287` — known-files/: `navigation_only` (path length 2)

## Observed but not replay-validated

- `feature_2e19750bfe9e891e` — misc/ opens /javascript/misc/
- `feature_3531dbd3511a8d44` — content-location/ opens /headers/content-location/
- `feature_4f48554801804ce5` — location/ opens /test/headers/location.found
- `feature_5948979f1136ede8` — two-listeners.html opens /javascript/interactive/two-listeners.html/
- `feature_7612ac371200f1dd` — multi-step-request-redefine-event-attribute.html opens /javascript/interactive/multi-step-request-redefine-event-attribute.html/
- `feature_807aa56a6e29d871` — react/ opens /javascript/frameworks/react/
- `feature_83e6c54fbb203956` — src.html opens /html/body/video/track/src.html/
- `feature_8751b0e546498d3b` — video/ opens /html/body/video/
- `feature_bf52dfcdbf7d0b39` — profile.html opens /html/head/profile.html/
- `feature_bfc743e866906a70` — doctype.html opens /html/doctype.html/
- `feature_c31a67b4e402254b` — Submit leads to CrawlMaze - Testbed for Web Crawlers - two EventListeners on same action
- `feature_db7621f5f224af8f` — body/ opens /html/body/
- `feature_df5f963876e079ed` — link/ opens /headers/link/
- `feature_e1efb4ee365f95fc` — string-variable.html opens /javascript/misc/string-variable.html/
- `feature_e483f0482c47ab24` — interactive/ opens /javascript/interactive/
- `feature_ef56eeb5fdfd2965` — track/ opens /html/body/video/track/

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
