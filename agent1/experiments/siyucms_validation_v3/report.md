# Agent 1 run agent1-20261028T133045Z

- Code revision: `778bbbda008081c489afdaee836c6397c4cff93a+mapper-6e41e2f822b1`
- Policy: `grouped`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 61.054 seconds
- Browser actions (including setup/replay): 59
- Replay-validated navigation categories: 3
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 15
- Replay navigation success: 3/10
- Replay failures / untested paths: 7/8
- Graph connections with complete evidence: 3168/3168
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_300f7f2b64e8fbb8` — 用户中心 opens /index/user/login
- `feature_653c8855e349ad43` — 资料下载 opens /index/download.html
- `feature_8f920b22df292b84` — 联系我们 opens /index/contact.html

## Functional path-instance outcomes

- `workflow_ba85ca427f199554f1` — Previous: `failed` (path length 1)
- `workflow_652e8c75c20f73183e` — Next: `failed` (path length 1)
- `workflow_3813f5b47ad75c5e25` — 首 页: `not_tested` (path length 1)
- `workflow_304c0b9d3ea55f30bf` — 铅笔盒: `not_tested` (path length 1)
- `workflow_e7319f2e91cb5dd449` — 钢笔: `not_tested` (path length 1)
- `workflow_a7f20a9e9a018dbffa` — 资质荣誉四: `not_tested` (path length 1)
- `workflow_54c946fb5734526986` — 资质荣誉六: `failed` (path length 1)
- `workflow_644225436d76aee06c` — 资质荣誉五: `not_tested` (path length 1)
- `workflow_0ef9a298339c09bbde` — 资质荣誉: `not_tested` (path length 1)
- `workflow_0329106dea8ee6ceb0` — 资料下载: `navigation_only` (path length 1)
- `workflow_d603b0811b3fcb1674` — 联系我们: `navigation_only` (path length 1)
- `workflow_f662c5df9f5730e688` — 笔记本: `not_tested` (path length 1)
- `workflow_975c19bc240b867a75` — 立即下载: `failed` (path length 1)
- `workflow_09efea98aeefb268ba` — 立即下载: `failed` (path length 1)
- `workflow_299661379a30c1d969` — 立即下载: `not_tested` (path length 1)
- `workflow_ddcadbff9ea879c800` — 用户中心: `navigation_only` (path length 1)
- `workflow_7a96615952ade87735` — 查看详细: `failed` (path length 1)
- `workflow_a362a0ab80d8a17ad0` — 查看详细: `failed` (path length 1)

## Observed but not replay-validated

- `feature_8439b81187224472` — 资质荣誉 opens /index/honours.html
- `feature_98ad47ac95cc8d75` — 立即下载 opens /

## Failed or blocked transitions

- `tr_3260c645ff98e2aa34fe` — 盒子: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(2) > div > div:nth-of-type(1) > a:nth-of-type(1)").first - locator resolved to <a href="#" class="ec-boxed">…</a> - attempting click action 2 × waiting for element to be visible, enabled and stable - elem
- `tr_d652be25fd3060680148` — 查看详细: RuntimeError: saved return path restored 34f97677a9f53e9e, expected 34db875431bb0aba

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
