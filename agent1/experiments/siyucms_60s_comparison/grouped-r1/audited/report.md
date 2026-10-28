# Agent 1 run agent1-20261028T120911Z

- Code revision: `65b075ab8b339460dadb446c79b03fa6de03fa7c`
- Policy: `grouped`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 60.112 seconds
- Browser actions (including setup/replay): 67
- Validated feature workflows: 7
- Replay success: 14/14
- Unsupported connections: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 3
- Model calls / cost: 0 / $0.000000

## Replay-validated workflows

- `feature_300f7f2b64e8fbb8` — 用户中心 opens /index/user/login
- `feature_653c8855e349ad43` — 资料下载 opens /index/download.html
- `feature_8439b81187224472` — 资质荣誉 opens /index/honours.html
- `feature_8f920b22df292b84` — 联系我们 opens /index/contact.html
- `feature_9710f969516b98ac` — 查看详细 opens /index/Article/info.html?cate&id
- `feature_f107262807d6fe62` — Observed link workflow to /index/honours/{instance}.html
- `feature_f253178968c62b36` — Observed link workflow to /index/product/{instance}.html?cate

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_c49ffe020b66d0a45644` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_d4d86fd5dbb613f1051a` — 盒子: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(2) > div > div:nth-of-type(1) > a:nth-of-type(1)").first - locator resolved to <a href="#" class="ec-boxed">…</a> - attempting click action 2 × waiting for element to be visible, enabled and stable - elem

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- Post-run feature-identity audit: repeated site-wide links were collapsed across source states; raw observations, transitions, replays, and the original run directory remain unchanged.
