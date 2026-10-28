# Agent 1 run agent1-20261028T124731Z

- Code revision: `65b075ab8b339460dadb446c79b03fa6de03fa7c+mapper-05ff253ad3fb`
- Policy: `grouped`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 46.501 seconds
- Browser actions (including setup/replay): 44
- Validated feature workflows: 2
- Replay success: 6/6
- Unsupported connections: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 3
- Model calls / cost: 0 / $0.000000

## Replay-validated workflows

- `feature_8f920b22df292b84` — 联系我们 opens /index/contact.html
- `feature_f107262807d6fe62` — Observed link workflow to /index/honours/{instance}.html

## Observed but not replay-validated

- `feature_653c8855e349ad43` — 资料下载 opens /index/download.html
- `feature_8439b81187224472` — 资质荣誉 opens /index/honours.html
- `feature_f253178968c62b36` — Observed link workflow to /index/product/{instance}.html?cate

## Failed or blocked transitions

- `tr_c75bd81283d2a2b688bb` — 盒子: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(2) > div > div:nth-of-type(1) > a:nth-of-type(1)").first - locator resolved to <a href="#" class="ec-boxed">…</a> - attempting click action 2 × waiting for element to be visible, enabled and stable - elem

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
