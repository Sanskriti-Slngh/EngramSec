# Agent 1 run agent1-20261028T133311Z

- Code revision: `778bbbda008081c489afdaee836c6397c4cff93a+mapper-c159484a7625`
- Policy: `grouped`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 60.375 seconds
- Browser actions (including setup/replay): 46
- Replay-validated navigation categories: 4
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 5
- Replay navigation success: 9/9
- Replay failures / untested paths: 0/4
- Graph connections with complete evidence: 2321/2321
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_7fbc2fd964f3af20` — 立即下载 opens /
- `feature_8f920b22df292b84` — 联系我们 opens /index/contact.html
- `feature_f107262807d6fe62` — Observed link workflow to /index/honours/{instance}.html
- `feature_f253178968c62b36` — Observed link workflow to /index/product/{instance}.html?cate

## Functional path-instance outcomes

- `workflow_ba89336b1db55cb963` — Previous: `not_tested` (path length 1)
- `workflow_03d8e8c2c8d26ebea2` — Next: `unresolved` (path length 1)
- `workflow_f31d265408b8a3a82a` — 首 页: `navigation_only` (path length 1)
- `workflow_d0d2988f169fd812cf` — 铅笔盒: `navigation_only` (path length 1)
- `workflow_f30927b0ec40511afb` — 钢笔: `navigation_only` (path length 1)
- `workflow_15072a9c0f780b35cc` — 资质荣誉四: `navigation_only` (path length 1)
- `workflow_c3812eefff3749cdb7` — 资质荣誉六: `navigation_only` (path length 1)
- `workflow_543d647e2c11e2026c` — 资质荣誉五: `navigation_only` (path length 1)
- `workflow_ffa41e0b8483015561` — 资质荣誉: `not_tested` (path length 1)
- `workflow_1917f06ad845dd0fe9` — 资料下载: `not_tested` (path length 1)
- `workflow_0db6de08dd51e79c22` — 联系我们: `navigation_only` (path length 1)
- `workflow_2cc57bfaf741ddc3cf` — 立即下载: `not_tested` (path length 1)
- `workflow_13ca45c084baff92d0` — 立即下载: `navigation_only` (path length 1)

## Observed but not replay-validated

- `feature_653c8855e349ad43` — 资料下载 opens /index/download.html
- `feature_8439b81187224472` — 资质荣誉 opens /index/honours.html
- `feature_b88d821fe328230b` — 立即下载 opens /

## Failed or blocked transitions

- `tr_ab21f18d4d8b8faab11e` — 笔记本: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > div:nth-of-type(3) > div > div:nth-of-type(2) > div:nth-of-type(4) > div > div:nth-of-type(2) > h4 > a").first - locator resolved to <a href="/index/product/5.html?cate=9">笔记本</a> - attempting

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
