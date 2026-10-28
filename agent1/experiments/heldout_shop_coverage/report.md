# Agent 1 run agent1-20261028T193210Z

- Code revision: `3012ce6d393ee7f373c03c69789d5918abc95abc+mapper-1cc5c02a0a12`
- Policy: `coverage`
- Target: `http://127.0.0.1:59106/`
- Elapsed: 10.965 seconds
- Browser actions (including setup/replay): 141
- Replay-validated navigation categories: 12
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 25
- Replay navigation success: 19/19
- Replay failures / untested paths: 0/11
- Graph connections with complete evidence: 504/504
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_090bde44a0425c63` — See all deals opens /deals
- `feature_1c371d89019dbc3f` — Browse categories leads to Northstar Shop
- `feature_62b5a8db896ad5d8` — Current deals leads to Northstar Shop
- `feature_6da69594c7e00dd1` — Current deals leads to Northstar Shop
- `feature_b1b3c8cb25cb1492` — Current deals leads to Northstar Shop
- `feature_b2949974b790acaf` — Shipping and returns leads to Northstar Shop
- `feature_d7f66c81a8f3ce1a` — Load customer reviews leads to Camp kettle
- `feature_e055a1b51043262f` — Browse categories leads to Northstar Shop
- `feature_e1339e56e0487e08` — Shipping and returns leads to Northstar Shop
- `feature_e9626787060ef50f` — Shipping and returns leads to Northstar Shop
- `feature_efbf4c0f047ecd8c` — Browse categories leads to Northstar Shop
- `feature_f291a1e8518590e9` — Cart opens /cart

## Functional path-instance outcomes

- `workflow_1eb1f9840fdbc26763` — Shipping and returns: `unresolved` (path length 1)
- `workflow_431bef9ae1564170b1` — Current deals: `unresolved` (path length 1)
- `workflow_e78a7f63a01865b3de` — Browse categories: `unresolved` (path length 1)
- `workflow_08d4015bc77aa8c70b` — Trail lantern: `navigation_only` (path length 1)
- `workflow_937862dab90ab961b7` — Add sample to cart: `unresolved` (path length 2)
- `workflow_50c404c6db4b609d56` — Load customer reviews: `not_tested` (path length 2)
- `workflow_25723cb523732c7850` — Northstar Shop: `navigation_only` (path length 1)
- `workflow_1893edd44f60ee75d3` — See all deals: `navigation_only` (path length 2)
- `workflow_ced7c9633c1f26b494` — Outdoor collection: `not_tested` (path length 2)
- `workflow_eafef9325d4f26ee44` — Returns guide: `not_tested` (path length 2)
- `workflow_9cdfa5a7ec90d9073c` — Cart: `navigation_only` (path length 1)
- `workflow_63368e09a36b983a5f` — Featured lantern: `not_tested` (path length 3)
- `workflow_718f08e0026616342f` — Camp kettle: `navigation_only` (path length 1)
- `workflow_1187706ece03170180` — Begin checkout: `not_tested` (path length 3)
- `workflow_8a0fafad569b3a6f38` — Add sample to cart: `unresolved` (path length 2)
- `workflow_5b1e8f4dc23b189d7d` — Add sample to cart: `not_tested` (path length 3)
- `workflow_4ad45fbd6a62d0a7cb` — Shipping and returns: `unresolved` (path length 2)
- `workflow_2baacc7d02780791e1` — Shipping and returns: `unresolved` (path length 2)
- `workflow_e6a3d28d227f8a471e` — Shipping and returns: `not_tested` (path length 2)
- `workflow_2cca9607cecf4dbd16` — Current deals: `unresolved` (path length 2)
- `workflow_aa1a44660a81e901a2` — Current deals: `unresolved` (path length 2)
- `workflow_2524380eec0e617d94` — Current deals: `unresolved` (path length 2)
- `workflow_b91e3de45465ab350f` — Shipping and returns: `not_tested` (path length 3)
- `workflow_0916902c33ece366b1` — Shipping and returns: `not_tested` (path length 3)
- `workflow_20fc505c30c041241f` — Shipping and returns: `not_tested` (path length 3)
- `workflow_673dc8640edc3bd837` — Browse categories: `unresolved` (path length 2)
- `workflow_9933af73303bb9a650` — Browse categories: `unresolved` (path length 2)
- `workflow_235b50542c6d1bcd30` — Browse categories: `unresolved` (path length 2)
- `workflow_dc774fb177dc8c5254` — Load customer reviews: `unresolved` (path length 2)
- `workflow_dadf271fc6c4f4b086` — Add sample to cart: `not_tested` (path length 3)

## Observed but not replay-validated

- `feature_25205dbbdb5c7078` — Shipping and returns leads to Northstar Shop
- `feature_3350a1876a89b23c` — Add sample to cart leads to Cart
- `feature_44b0ad8a5aa09fb8` — Returns guide opens /returns
- `feature_52a02b7468930573` — Begin checkout opens /checkout
- `feature_5a0852d2ceaa06b1` — Shipping and returns leads to Northstar Shop
- `feature_8c09e8a1816510ba` — Shipping and returns leads to Northstar Shop
- `feature_cd0c03b5a603de8f` — Observed link workflow to /products/{instance}
- `feature_d02729b742f69d70` — Load customer reviews leads to Trail lantern
- `feature_d2968497ddab58b3` — Outdoor collection opens /category/outdoors
- `feature_df00bee78f341f41` — Shipping and returns leads to Northstar Shop

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
