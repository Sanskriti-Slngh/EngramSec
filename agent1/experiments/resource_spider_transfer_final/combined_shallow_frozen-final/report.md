# Agent 1 run agent1-20261030T042336Z

- Code revision: `decc0a2788a8f8c91c4d65427ef36da8c2d581c5+mapper-fb926c713753`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:59792/`
- Elapsed: 42.520 seconds
- Browser actions (including setup/replay): 94
- Replay-validated navigation categories: 13
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 22
- Replay navigation success: 18/18
- Replay failures / untested paths: 0/12
- Graph connections with complete evidence: 839/839
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_254421de94dc97e8` — Shipping and returns leads to Northstar Shop
- `feature_2efe36f4b58d9a99` — Shipping and returns leads to Northstar Shop
- `feature_35164de97e539f33` — Outdoor collection opens /category/outdoors
- `feature_3964ff48467ad2bd` — Browse categories leads to Northstar Shop
- `feature_4c2ead82cd3ed97d` — Begin checkout opens /checkout
- `feature_60d26fcc6bdd2ff7` — Cart opens /cart
- `feature_7c450395fe9c3714` — Shipping and returns leads to Northstar Shop
- `feature_8ddd6e6547a96c8f` — Current deals leads to Northstar Shop
- `feature_aa9c1fd4d82b6aa0` — Shipping and returns leads to Northstar Shop
- `feature_b37fc01cde74d80a` — Returns guide opens /returns
- `feature_c4a51635e5bd4e32` — Browse categories leads to Northstar Shop
- `feature_ca7b1aa330133e4f` — Current deals leads to Northstar Shop
- `feature_d11c52de045209fd` — Load customer reviews leads to Trail lantern

## Functional path-instance outcomes

- `workflow_78b6371bd58de61adc` — Trail lantern: `navigation_only` (path length 1)
- `workflow_b7010e0c073857d8d3` — Add sample to cart: `unresolved` (path length 2)
- `workflow_5f17cf0ce8a3b700e3` — Begin checkout: `navigation_only` (path length 3)
- `workflow_41d56380b87b2d96f5` — Camp kettle: `navigation_only` (path length 1)
- `workflow_2381e1e12b87e560d8` — Add sample to cart: `not_tested` (path length 2)
- `workflow_726c34e579425be8c4` — Shipping and returns: `unresolved` (path length 1)
- `workflow_c42645bcba8eb14c48` — Returns guide: `navigation_only` (path length 2)
- `workflow_43715158b97b0a63fe` — Current deals: `unresolved` (path length 1)
- `workflow_3c856a4829d385a3ef` — See all deals: `navigation_only` (path length 2)
- `workflow_0b06a0d8d3c37f7c39` — Browse categories: `unresolved` (path length 1)
- `workflow_8c2af8d09d9f0f0d03` — Outdoor collection: `navigation_only` (path length 2)
- `workflow_0da38a4a35dfb7fa72` — Featured lantern: `not_tested` (path length 3)
- `workflow_0f5431bbd886882ead` — Load customer reviews: `unresolved` (path length 2)
- `workflow_1844a2ef60acbe4911` — Add sample to cart: `not_tested` (path length 3)
- `workflow_b0d54e8784a9dae717` — Northstar Shop: `navigation_only` (path length 1)
- `workflow_89b61cc213babb0d6b` — Cart: `navigation_only` (path length 1)
- `workflow_68e7aaac4ca2c3131d` — Shipping and returns: `unresolved` (path length 2)
- `workflow_c58f99567d258d0755` — Shipping and returns: `not_tested` (path length 2)
- `workflow_cc451bb6017f2fb7b1` — Shipping and returns: `not_tested` (path length 3)
- `workflow_77ce140c3b49f82393` — Current deals: `not_tested` (path length 2)
- `workflow_75b3408106a6259195` — Browse categories: `unresolved` (path length 2)
- `workflow_34f81811dad713469d` — Shipping and returns: `unresolved` (path length 3)
- `workflow_03c76720c591355e29` — Shipping and returns: `not_tested` (path length 4)
- `workflow_1befd77b422d918635` — Browse categories: `not_tested` (path length 3)
- `workflow_a174fb2543526b907f` — Trail lantern: `not_tested` (path length 3)
- `workflow_5618d8ed00ee6855bd` — Shipping and returns: `unresolved` (path length 2)
- `workflow_f4a89f1beba07e1bbb` — Shipping and returns: `not_tested` (path length 3)
- `workflow_b94c157c0a246ff3bf` — Current deals: `not_tested` (path length 2)
- `workflow_77e7d5dec2ff6a3ec2` — See all deals: `not_tested` (path length 3)
- `workflow_303ed99aa3e7146366` — Current deals: `unresolved` (path length 2)

## Observed but not replay-validated

- `feature_021ad0eb06993524` — Current deals leads to Northstar Shop
- `feature_0dc4a03638f2a9a5` — Observed link workflow to /products/{instance}
- `feature_136e6295e2a62b42` — Shipping and returns leads to Northstar Shop
- `feature_38ca310b4c0d5375` — Shipping and returns leads to Northstar Shop
- `feature_3edb247e76a55a05` — Add sample to cart leads to Cart
- `feature_4056f0fa4206a366` — Observed link workflow to /products/{instance}
- `feature_4f835e9f2421f157` — Shipping and returns leads to Northstar Shop
- `feature_5e9176137cfa6445` — See all deals opens /deals
- `feature_c3ce8e58be5c5fb8` — Shipping and returns leads to Northstar Shop

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
