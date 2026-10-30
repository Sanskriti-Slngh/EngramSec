# Agent 1 run agent1-20261030T033928Z

- Code revision: `decc0a2788a8f8c91c4d65427ef36da8c2d581c5+mapper-0da88053cdec`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:3460/`
- Elapsed: 184.062 seconds
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

- `feature_2e19750bfe9e891e` — misc/ opens /javascript/misc/
- `feature_3531dbd3511a8d44` — content-location/ opens /headers/content-location/
- `feature_41ba3209725933d5` — manifest.html opens /html/manifest.html/
- `feature_4719d72f368a294c` — refresh/ opens /headers/refresh/
- `feature_4f48554801804ce5` — location/ opens /test/headers/location.found
- `feature_6f6ffbd2a0199e3e` — CSS opens /css/
- `feature_7d1756ba5d7cb6e4` — HTML opens /html/
- `feature_93ea1e291784ce15` — JavaScript opens /javascript/
- `feature_9fe133e4cf904946` — Misc opens /misc/
- `feature_bfc743e866906a70` — doctype.html opens /html/doctype.html/
- `feature_c06bd8289171ed68` — Response headers opens /headers/
- `feature_ec82d30050a88157` — head/ opens /html/head/

## Functional path-instance outcomes

- `workflow_f2b97f24f0e51e3ff1` — Response headers: `navigation_only` (path length 1)
- `workflow_1dd8169c9c7f7c3969` — refresh/: `navigation_only` (path length 2)
- `workflow_8c1c65bd048208219b` — Misc: `navigation_only` (path length 1)
- `workflow_01a137e18e6f128515` — known-files/: `not_tested` (path length 2)
- `workflow_0e163b5e7903020577` — sitemap.xml.html: `not_tested` (path length 3)
- `workflow_0cee6d2be181bacc5a` — JavaScript: `navigation_only` (path length 1)
- `workflow_d8735a097725f2858b` — misc/: `navigation_only` (path length 2)
- `workflow_16ed1b3fe8a0f9707c` — string-variable.html: `not_tested` (path length 3)
- `workflow_49b804a4daa0642f29` — HTML: `navigation_only` (path length 1)
- `workflow_242222b298bcb85a0f` — manifest.html: `navigation_only` (path length 2)
- `workflow_5c99bc11345fc685f2` — CSS: `navigation_only` (path length 1)
- `workflow_1080a73a526c1f0ac1` — font-face.html: `not_tested` (path length 2)
- `workflow_c7ab25f83a0f3afa1b` — location/: `navigation_only` (path length 2)
- `workflow_54df6016904948ff3b` — interactive/: `not_tested` (path length 2)
- `workflow_90501ec4975b6f1eae` — two-listeners.html: `not_tested` (path length 3)
- `workflow_6ea1561e7d07050573` — Submit: `not_tested` (path length 4)
- `workflow_9e04b8b1305d0cb8cd` — head/: `navigation_only` (path length 2)
- `workflow_1fb3e7127d0e27f0fc` — profile.html: `not_tested` (path length 3)
- `workflow_1749d0a438bb710e1d` — link/: `not_tested` (path length 2)
- `workflow_727cb7f9cec4634451` — doctype.html: `navigation_only` (path length 2)
- `workflow_0c8a890a14411c89fe` — frameworks/: `not_tested` (path length 2)
- `workflow_de059361bea053d00d` — react/: `not_tested` (path length 3)
- `workflow_7f0665d06191055907` — multi-step-request-redefine-event-attribute.html: `not_tested` (path length 3)
- `workflow_90ea4676262fd31b03` — Submit: `not_tested` (path length 4)
- `workflow_a5b21823b87b435394` — content-location/: `navigation_only` (path length 2)
- `workflow_c9fecaf85d4883faa6` — meta/: `not_tested` (path length 3)
- `workflow_443402a8e18250d869` — content-redirect.html: `not_tested` (path length 4)
- `workflow_5a0e432bae275ba478` — multi-step-request-event-listener.html: `not_tested` (path length 3)
- `workflow_202b5e06d9aaf78092` — show secret button: `not_tested` (path length 4)
- `workflow_b81cefc8ea94f2702d` — click this secret button: `not_tested` (path length 5)
- `workflow_562d0ffb21696510ef` — show secret button: `not_tested` (path length 5)
- `workflow_a060b8eb4923128393` — body/: `not_tested` (path length 2)
- `workflow_58ebdaa45b4d13a2d9` — video/: `not_tested` (path length 3)
- `workflow_c49462f327a68c71f9` — track/: `not_tested` (path length 4)
- `workflow_63f80ae170b122fda0` — src.html: `not_tested` (path length 5)
- `workflow_af945d9bf3ce15cdd4` — table/: `not_tested` (path length 3)

## Observed but not replay-validated

- `feature_09b360029d057bf8` — font-face.html opens /css/font-face.html
- `feature_0fcd9d80ee606842` — multi-step-request-event-listener.html opens /javascript/interactive/multi-step-request-event-listener.html/
- `feature_1279b6c074418cbb` — show secret button leads to CrawlMaze - Testbed for Web Crawlers - multi-step request with EventListener
- `feature_14ff0e53dc96656c` — frameworks/ opens /javascript/frameworks/
- `feature_1e9ad45c7719697f` — meta/ opens /html/head/meta/
- `feature_3699dc387e5599e0` — known-files/ opens /misc/known-files/
- `feature_420c4957c820f430` — content-redirect.html opens /html/head/meta/content-redirect.html/
- `feature_5948979f1136ede8` — two-listeners.html opens /javascript/interactive/two-listeners.html/
- `feature_7612ac371200f1dd` — multi-step-request-redefine-event-attribute.html opens /javascript/interactive/multi-step-request-redefine-event-attribute.html/
- `feature_807aa56a6e29d871` — react/ opens /javascript/frameworks/react/
- `feature_83e6c54fbb203956` — src.html opens /html/body/video/track/src.html/
- `feature_8751b0e546498d3b` — video/ opens /html/body/video/
- `feature_a272edaa1ef4a316` — sitemap.xml.html opens /misc/known-files/sitemap.xml.html/
- `feature_bf52dfcdbf7d0b39` — profile.html opens /html/head/profile.html/
- `feature_c31a67b4e402254b` — Submit leads to CrawlMaze - Testbed for Web Crawlers - two EventListeners on same action
- `feature_db7621f5f224af8f` — body/ opens /html/body/
- `feature_df5f963876e079ed` — link/ opens /headers/link/
- `feature_e1efb4ee365f95fc` — string-variable.html opens /javascript/misc/string-variable.html/
- `feature_e483f0482c47ab24` — interactive/ opens /javascript/interactive/
- `feature_ee054aa9c31d2457` — table/ opens /html/body/table/
- `feature_ef56eeb5fdfd2965` — track/ opens /html/body/video/track/

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
