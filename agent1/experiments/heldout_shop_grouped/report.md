# Agent 1 run agent1-20261028T192704Z

- Code revision: `6082c6df7fdb07b0cc0c13930f705c9f327e2a96+mapper-4027cddaacc1`
- Policy: `grouped`
- Target: `http://127.0.0.1:56407/`
- Elapsed: 12.422 seconds
- Browser actions (including setup/replay): 140
- Replay-validated navigation categories: 14
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 22
- Replay navigation success: 21/21
- Replay failures / untested paths: 0/9
- Graph connections with complete evidence: 498/498
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_1c371d89019dbc3f` — Browse categories leads to Northstar Shop
- `feature_25205dbbdb5c7078` — Shipping and returns leads to Northstar Shop
- `feature_3350a1876a89b23c` — Add sample to cart leads to Cart
- `feature_44b0ad8a5aa09fb8` — Returns guide opens /returns
- `feature_62b5a8db896ad5d8` — Current deals leads to Northstar Shop
- `feature_6da69594c7e00dd1` — Current deals leads to Northstar Shop
- `feature_b1b3c8cb25cb1492` — Current deals leads to Northstar Shop
- `feature_d02729b742f69d70` — Load customer reviews leads to Trail lantern
- `feature_d2968497ddab58b3` — Outdoor collection opens /category/outdoors
- `feature_d7f66c81a8f3ce1a` — Load customer reviews leads to Camp kettle
- `feature_e055a1b51043262f` — Browse categories leads to Northstar Shop
- `feature_e1339e56e0487e08` — Shipping and returns leads to Northstar Shop
- `feature_e9626787060ef50f` — Shipping and returns leads to Northstar Shop
- `feature_f291a1e8518590e9` — Cart opens /cart

## Functional path-instance outcomes

- `workflow_e7511c9bc60d36751d` — Shipping and returns: `unresolved` (path length 1)
- `workflow_59cc5c538f9d0bfb7e` — Current deals: `unresolved` (path length 1)
- `workflow_55be9cf31defc0f2a8` — Browse categories: `unresolved` (path length 1)
- `workflow_44b8af4d3ff01b4ae2` — Trail lantern: `navigation_only` (path length 1)
- `workflow_f4731ac7406dd7cf6a` — Northstar Shop: `navigation_only` (path length 1)
- `workflow_70598bf188dccccd89` — Cart: `navigation_only` (path length 1)
- `workflow_f5c1720891c69fdf96` — Camp kettle: `navigation_only` (path length 1)
- `workflow_d885a8fe5ea1e61e25` — Add sample to cart: `unresolved` (path length 2)
- `workflow_5d8d5809f21fba6b6c` — Add sample to cart: `unresolved` (path length 2)
- `workflow_b59d8978d21642435f` — Shipping and returns: `not_tested` (path length 2)
- `workflow_94ea68148afd6d98eb` — Shipping and returns: `unresolved` (path length 2)
- `workflow_5d6e5d018bd7bd6c68` — Shipping and returns: `unresolved` (path length 2)
- `workflow_cf83bff1e3e7087092` — Current deals: `unresolved` (path length 2)
- `workflow_52a028483539b5c973` — Current deals: `unresolved` (path length 2)
- `workflow_8eb4f9234d7f38c6dc` — Current deals: `unresolved` (path length 2)
- `workflow_0c1b476a05d4ba2141` — Browse categories: `unresolved` (path length 2)
- `workflow_01ae730aeadc26e7fc` — Browse categories: `not_tested` (path length 2)
- `workflow_e6694e8e97258c6a35` — Browse categories: `not_tested` (path length 2)
- `workflow_b216d428ec0efc71de` — Load customer reviews: `unresolved` (path length 2)
- `workflow_f0a8a5617482c7a3cd` — Load customer reviews: `unresolved` (path length 2)
- `workflow_226a55b44ec1090d48` — Northstar Shop: `navigation_only` (path length 2)
- `workflow_a64e2f37624ffbf4be` — Trail lantern: `not_tested` (path length 2)
- `workflow_2e8180b6be4371e0f3` — Trail lantern: `not_tested` (path length 2)
- `workflow_673cf581e134cd7f1f` — Trail lantern: `not_tested` (path length 2)
- `workflow_57594c89533f908ef6` — See all deals: `not_tested` (path length 2)
- `workflow_32f91aa4ddb0c592a5` — Outdoor collection: `navigation_only` (path length 2)
- `workflow_306014f8cd29e21443` — Returns guide: `navigation_only` (path length 2)
- `workflow_b6074a8d9b95ead8bb` — Cart: `not_tested` (path length 2)
- `workflow_963973372fd5cb9551` — Northstar Shop: `navigation_only` (path length 2)
- `workflow_b6a364b031b683f0d4` — Northstar Shop: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_090bde44a0425c63` — See all deals opens /deals
- `feature_5ce256c24795e4ad` — Northstar Shop opens /
- `feature_b2949974b790acaf` — Shipping and returns leads to Northstar Shop
- `feature_cd0c03b5a603de8f` — Observed link workflow to /products/{instance}
- `feature_efbf4c0f047ecd8c` — Browse categories leads to Northstar Shop

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
