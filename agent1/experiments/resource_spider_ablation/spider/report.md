# Agent 1 run agent1-20261030T034233Z

- Code revision: `decc0a2788a8f8c91c4d65427ef36da8c2d581c5+mapper-0da88053cdec`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:3460/`
- Elapsed: 183.312 seconds
- Browser actions (including setup/replay): 101
- Replay-validated navigation categories: 12
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 24
- Replay navigation success: 12/12
- Replay failures / untested paths: 0/24
- Graph connections with complete evidence: 288/288
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_09b360029d057bf8` — font-face.html opens /css/font-face.html
- `feature_2e19750bfe9e891e` — misc/ opens /javascript/misc/
- `feature_3699dc387e5599e0` — known-files/ opens /misc/known-files/
- `feature_41ba3209725933d5` — manifest.html opens /html/manifest.html/
- `feature_4f48554801804ce5` — location/ opens /test/headers/location.found
- `feature_6f6ffbd2a0199e3e` — CSS opens /css/
- `feature_7d1756ba5d7cb6e4` — HTML opens /html/
- `feature_93ea1e291784ce15` — JavaScript opens /javascript/
- `feature_9fe133e4cf904946` — Misc opens /misc/
- `feature_bfc743e866906a70` — doctype.html opens /html/doctype.html/
- `feature_c06bd8289171ed68` — Response headers opens /headers/
- `feature_db7621f5f224af8f` — body/ opens /html/body/

## Functional path-instance outcomes

- `workflow_2a5c638945b90f9036` — Response headers: `navigation_only` (path length 1)
- `workflow_f04f0ddb4207a008c7` — refresh/: `not_tested` (path length 2)
- `workflow_59c495861337354c99` — Misc: `navigation_only` (path length 1)
- `workflow_c0288061dca74ba41f` — known-files/: `navigation_only` (path length 2)
- `workflow_6d68e70e93c42b2589` — sitemap.xml.html: `not_tested` (path length 3)
- `workflow_fbf4430c161317279b` — JavaScript: `navigation_only` (path length 1)
- `workflow_daaa0a56a664b45495` — misc/: `navigation_only` (path length 2)
- `workflow_7d455014dff04bb1a3` — string-variable.html: `not_tested` (path length 3)
- `workflow_817ded1a807f9be22d` — HTML: `navigation_only` (path length 1)
- `workflow_6d8ea5034c74d2a06f` — manifest.html: `navigation_only` (path length 2)
- `workflow_ffabafc0f45b625396` — CSS: `navigation_only` (path length 1)
- `workflow_96e9a68c1705fca193` — font-face.html: `navigation_only` (path length 2)
- `workflow_01e6e2acdfdd69086c` — location/: `navigation_only` (path length 2)
- `workflow_80576d38a83b03df2f` — interactive/: `not_tested` (path length 2)
- `workflow_6e6bf809537ccd386e` — two-listeners.html: `not_tested` (path length 3)
- `workflow_68468981c6fb5fa64a` — Submit: `not_tested` (path length 4)
- `workflow_6046744eb425762b1c` — head/: `not_tested` (path length 2)
- `workflow_55fce3b16d6290d72f` — profile.html: `not_tested` (path length 3)
- `workflow_d0f85dca68479fcc62` — link/: `not_tested` (path length 2)
- `workflow_4623b2b5b1feeee9fa` — doctype.html: `navigation_only` (path length 2)
- `workflow_cbdf47fdada1e0367d` — frameworks/: `not_tested` (path length 2)
- `workflow_c5dbceee7952901de6` — react/: `not_tested` (path length 3)
- `workflow_80c8a3855c3a1e0221` — multi-step-request-redefine-event-attribute.html: `not_tested` (path length 3)
- `workflow_92645c532dcd8433eb` — Submit: `not_tested` (path length 4)
- `workflow_9e56d8ca7428b9e265` — content-location/: `not_tested` (path length 2)
- `workflow_3862ecf0f6412d0800` — meta/: `not_tested` (path length 3)
- `workflow_f91270e30cc0cf3ede` — content-redirect.html: `not_tested` (path length 4)
- `workflow_c8d3504b94113d9bae` — multi-step-request-event-listener.html: `not_tested` (path length 3)
- `workflow_660a5e51a291058d3b` — show secret button: `not_tested` (path length 4)
- `workflow_b5292cae4a5f756d14` — click this secret button: `not_tested` (path length 5)
- `workflow_53962640ceca98c545` — show secret button: `not_tested` (path length 5)
- `workflow_e11d88133a361044c3` — body/: `navigation_only` (path length 2)
- `workflow_b16378cd804c68e340` — video/: `not_tested` (path length 3)
- `workflow_5f47056ffd3c11aaff` — track/: `not_tested` (path length 4)
- `workflow_48806a74172cb338a0` — src.html: `not_tested` (path length 5)
- `workflow_dffff44e940e260109` — table/: `not_tested` (path length 3)

## Observed but not replay-validated

- `feature_0fcd9d80ee606842` — multi-step-request-event-listener.html opens /javascript/interactive/multi-step-request-event-listener.html/
- `feature_1279b6c074418cbb` — show secret button leads to CrawlMaze - Testbed for Web Crawlers - multi-step request with EventListener
- `feature_14ff0e53dc96656c` — frameworks/ opens /javascript/frameworks/
- `feature_1e9ad45c7719697f` — meta/ opens /html/head/meta/
- `feature_3531dbd3511a8d44` — content-location/ opens /headers/content-location/
- `feature_420c4957c820f430` — content-redirect.html opens /html/head/meta/content-redirect.html/
- `feature_4719d72f368a294c` — refresh/ opens /headers/refresh/
- `feature_5948979f1136ede8` — two-listeners.html opens /javascript/interactive/two-listeners.html/
- `feature_7612ac371200f1dd` — multi-step-request-redefine-event-attribute.html opens /javascript/interactive/multi-step-request-redefine-event-attribute.html/
- `feature_807aa56a6e29d871` — react/ opens /javascript/frameworks/react/
- `feature_83e6c54fbb203956` — src.html opens /html/body/video/track/src.html/
- `feature_8751b0e546498d3b` — video/ opens /html/body/video/
- `feature_a272edaa1ef4a316` — sitemap.xml.html opens /misc/known-files/sitemap.xml.html/
- `feature_bf52dfcdbf7d0b39` — profile.html opens /html/head/profile.html/
- `feature_c31a67b4e402254b` — Submit leads to CrawlMaze - Testbed for Web Crawlers - two EventListeners on same action
- `feature_df5f963876e079ed` — link/ opens /headers/link/
- `feature_e1efb4ee365f95fc` — string-variable.html opens /javascript/misc/string-variable.html/
- `feature_e483f0482c47ab24` — interactive/ opens /javascript/interactive/
- `feature_ec82d30050a88157` — head/ opens /html/head/
- `feature_ee054aa9c31d2457` — table/ opens /html/body/table/
- `feature_ef56eeb5fdfd2965` — track/ opens /html/body/video/track/

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
