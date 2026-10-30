# Agent 1 run agent1-20261030T041432Z

- Code revision: `decc0a2788a8f8c91c4d65427ef36da8c2d581c5+mapper-e9af1058031e`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:55174/`
- Elapsed: 43.137 seconds
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

- `feature_021ad0eb06993524` — Current deals leads to Northstar Shop
- `feature_254421de94dc97e8` — Shipping and returns leads to Northstar Shop
- `feature_2efe36f4b58d9a99` — Shipping and returns leads to Northstar Shop
- `feature_35164de97e539f33` — Outdoor collection opens /category/outdoors
- `feature_4c2ead82cd3ed97d` — Begin checkout opens /checkout
- `feature_60d26fcc6bdd2ff7` — Cart opens /cart
- `feature_7c450395fe9c3714` — Shipping and returns leads to Northstar Shop
- `feature_8ddd6e6547a96c8f` — Current deals leads to Northstar Shop
- `feature_aa9c1fd4d82b6aa0` — Shipping and returns leads to Northstar Shop
- `feature_b37fc01cde74d80a` — Returns guide opens /returns
- `feature_c3ce8e58be5c5fb8` — Shipping and returns leads to Northstar Shop
- `feature_c4a51635e5bd4e32` — Browse categories leads to Northstar Shop
- `feature_d11c52de045209fd` — Load customer reviews leads to Trail lantern

## Functional path-instance outcomes

- `workflow_8e87d21ab24f5e542a` — Trail lantern: `navigation_only` (path length 1)
- `workflow_d172e13e44dbd8ac7b` — Add sample to cart: `unresolved` (path length 2)
- `workflow_381e2404c7c56e246a` — Begin checkout: `navigation_only` (path length 3)
- `workflow_f4851063b857264063` — Camp kettle: `navigation_only` (path length 1)
- `workflow_473f0eb83c1f45fe54` — Add sample to cart: `not_tested` (path length 2)
- `workflow_177d1ca0e7b8120a77` — Shipping and returns: `unresolved` (path length 1)
- `workflow_4ead709bbb4b99c368` — Returns guide: `navigation_only` (path length 2)
- `workflow_98709d419bc1b27cb0` — Current deals: `unresolved` (path length 1)
- `workflow_e45f1a9a56d39d33b1` — See all deals: `navigation_only` (path length 2)
- `workflow_67581605ae1b642753` — Browse categories: `unresolved` (path length 1)
- `workflow_b9b9fb52f034141c31` — Outdoor collection: `navigation_only` (path length 2)
- `workflow_95170e011e953c0f29` — Featured lantern: `not_tested` (path length 3)
- `workflow_63bb931af20ab93fa7` — Load customer reviews: `unresolved` (path length 2)
- `workflow_6e6eb6fa1f094a3904` — Add sample to cart: `not_tested` (path length 3)
- `workflow_7f88a29b3293283e10` — Northstar Shop: `navigation_only` (path length 1)
- `workflow_86e4f0a6306fc50340` — Cart: `navigation_only` (path length 1)
- `workflow_def2bab6acb97cb87e` — Shipping and returns: `unresolved` (path length 2)
- `workflow_5b7772796bdd75a2bc` — Shipping and returns: `unresolved` (path length 2)
- `workflow_dad87632d686e93220` — Shipping and returns: `not_tested` (path length 3)
- `workflow_04086e8dcb4fa6a024` — Current deals: `not_tested` (path length 2)
- `workflow_4cdf052cf07d0220ab` — Browse categories: `not_tested` (path length 2)
- `workflow_1d23c06c693523b0ec` — Shipping and returns: `unresolved` (path length 3)
- `workflow_5899f80726b8fc9276` — Shipping and returns: `not_tested` (path length 4)
- `workflow_c34e0e69e91a121d6c` — Browse categories: `not_tested` (path length 3)
- `workflow_bacb6027220559145d` — Trail lantern: `not_tested` (path length 3)
- `workflow_648f25d8750242e35d` — Shipping and returns: `unresolved` (path length 2)
- `workflow_ab8f601faaae1f7f95` — Shipping and returns: `not_tested` (path length 3)
- `workflow_4335821a8579ade04d` — Current deals: `unresolved` (path length 2)
- `workflow_287536736decf1c327` — See all deals: `not_tested` (path length 3)
- `workflow_c4dd4e6ca89f0e9a2a` — Current deals: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_0dc4a03638f2a9a5` — Observed link workflow to /products/{instance}
- `feature_136e6295e2a62b42` — Shipping and returns leads to Northstar Shop
- `feature_38ca310b4c0d5375` — Shipping and returns leads to Northstar Shop
- `feature_3964ff48467ad2bd` — Browse categories leads to Northstar Shop
- `feature_3edb247e76a55a05` — Add sample to cart leads to Cart
- `feature_4056f0fa4206a366` — Observed link workflow to /products/{instance}
- `feature_4f835e9f2421f157` — Shipping and returns leads to Northstar Shop
- `feature_5e9176137cfa6445` — See all deals opens /deals
- `feature_ca7b1aa330133e4f` — Current deals leads to Northstar Shop

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
