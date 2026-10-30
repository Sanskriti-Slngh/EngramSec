# Agent 1 run agent1-20261030T210917Z

- Code revision: `5710c01fbcd2b09fab0886cbc0eedf65b0b1510e+mapper-3262f58a7ee6`
- Policy: `hierarchical`
- Target: `http://127.0.0.1:3460/`
- Elapsed: 40.226 seconds
- Browser actions (including setup/replay): 89
- Replay-validated navigation categories: 11
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 17
- Replay navigation success: 11/11
- Replay failures / untested paths: 0/17
- Graph connections with complete evidence: 1174/1174
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_09b360029d057bf8` — font-face.html opens /css/font-face.html
- `feature_2e19750bfe9e891e` — misc/ opens /javascript/misc/
- `feature_3531dbd3511a8d44` — content-location/ opens /headers/content-location/
- `feature_4719d72f368a294c` — refresh/ opens /headers/refresh/
- `feature_6f6ffbd2a0199e3e` — CSS opens /css/
- `feature_7d1756ba5d7cb6e4` — HTML opens /html/
- `feature_93ea1e291784ce15` — JavaScript opens /javascript/
- `feature_9fe133e4cf904946` — Misc opens /misc/
- `feature_c06bd8289171ed68` — Response headers opens /headers/
- `feature_df5f963876e079ed` — link/ opens /headers/link/
- `feature_ec82d30050a88157` — head/ opens /html/head/

## Functional path-instance outcomes

- `workflow_339dade3446f1e033d` — Response headers: `navigation_only` (path length 1)
- `workflow_3ded5ce4dbf57eb9eb` — Misc: `navigation_only` (path length 1)
- `workflow_43ff0c135a59008017` — JavaScript: `navigation_only` (path length 1)
- `workflow_aee41e7ceff347f546` — HTML: `navigation_only` (path length 1)
- `workflow_c2e3c9880882661a76` — CSS: `navigation_only` (path length 1)
- `workflow_1ac9ded933d012e8ce` — font-face.html: `navigation_only` (path length 2)
- `workflow_98e8988870dc3c5098` — refresh/: `navigation_only` (path length 2)
- `workflow_a5a0f14ca38a68f9d4` — location/: `not_tested` (path length 2)
- `workflow_42ac20abdaf28c6519` — link/: `navigation_only` (path length 2)
- `workflow_b631e5548eaaa4200b` — content-location/: `navigation_only` (path length 2)
- `workflow_2575705b97a0ff5ab6` — manifest.html: `not_tested` (path length 2)
- `workflow_cf4dbb666492a21b64` — head/: `navigation_only` (path length 2)
- `workflow_d4ca620eaa0ecb8d45` — profile.html: `not_tested` (path length 3)
- `workflow_77b3f29c0bdfd6251c` — doctype.html: `not_tested` (path length 2)
- `workflow_6eee27846893a305fa` — body/: `not_tested` (path length 2)
- `workflow_1fe6a4387091ea8942` — video/: `not_tested` (path length 3)
- `workflow_b99d530f45768329ca` — track/: `not_tested` (path length 4)
- `workflow_5704c886bf20f0af9a` — src.html: `not_tested` (path length 5)
- `workflow_3676cfdf7959742f7d` — misc/: `navigation_only` (path length 2)
- `workflow_b8f48198612518d4b9` — string-variable.html: `not_tested` (path length 3)
- `workflow_a48a777d4d2721170d` — interactive/: `not_tested` (path length 2)
- `workflow_301e9e6754423905dc` — two-listeners.html: `not_tested` (path length 3)
- `workflow_42f5d6312b123c3115` — Submit: `not_tested` (path length 4)
- `workflow_77f2c33f8498f9b65c` — frameworks/: `not_tested` (path length 2)
- `workflow_85a610f7425a0c4283` — react/: `not_tested` (path length 3)
- `workflow_1a40a0f006e0aa44f3` — multi-step-request-redefine-event-attribute.html: `not_tested` (path length 3)
- `workflow_d6d8ba229eaac0969a` — known-files/: `not_tested` (path length 2)
- `workflow_2686ebc9e8053bb675` — sitemap.xml.html: `not_tested` (path length 3)

## Observed but not replay-validated

- `feature_14ff0e53dc96656c` — frameworks/ opens /javascript/frameworks/
- `feature_3699dc387e5599e0` — known-files/ opens /misc/known-files/
- `feature_41ba3209725933d5` — manifest.html opens /html/manifest.html/
- `feature_4f48554801804ce5` — location/ opens /test/headers/location.found
- `feature_5948979f1136ede8` — two-listeners.html opens /javascript/interactive/two-listeners.html/
- `feature_7612ac371200f1dd` — multi-step-request-redefine-event-attribute.html opens /javascript/interactive/multi-step-request-redefine-event-attribute.html/
- `feature_807aa56a6e29d871` — react/ opens /javascript/frameworks/react/
- `feature_83e6c54fbb203956` — src.html opens /html/body/video/track/src.html/
- `feature_8751b0e546498d3b` — video/ opens /html/body/video/
- `feature_a272edaa1ef4a316` — sitemap.xml.html opens /misc/known-files/sitemap.xml.html/
- `feature_bf52dfcdbf7d0b39` — profile.html opens /html/head/profile.html/
- `feature_bfc743e866906a70` — doctype.html opens /html/doctype.html/
- `feature_c31a67b4e402254b` — Submit leads to CrawlMaze - Testbed for Web Crawlers - two EventListeners on same action
- `feature_db7621f5f224af8f` — body/ opens /html/body/
- `feature_e1efb4ee365f95fc` — string-variable.html opens /javascript/misc/string-variable.html/
- `feature_e483f0482c47ab24` — interactive/ opens /javascript/interactive/
- `feature_ef56eeb5fdfd2965` — track/ opens /html/body/video/track/

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- ZAP evidence is externally reported and does not prove a UI transition or replay.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
