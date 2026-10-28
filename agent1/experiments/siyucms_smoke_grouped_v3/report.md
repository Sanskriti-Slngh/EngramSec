# Agent 1 run agent1-20261028T120646Z

- Code revision: `65b075ab8b339460dadb446c79b03fa6de03fa7c`
- Policy: `grouped`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 49.069 seconds
- Browser actions (including setup/replay): 58
- Validated feature workflows: 5
- Replay success: 14/14
- Unsupported connections: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 3
- Model calls / cost: 0 / $0.000000

## Replay-validated workflows

- `feature_01f9c0426d3a7cd0` — 资质荣誉 opens /index/honours.html
- `feature_64d15f6c5034b199` — 资料下载 opens /index/download.html
- `feature_79f37482630e2359` — 资质荣誉四 opens /index/honours/{instance}.html
- `feature_e793b769c930e6cb` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_f02aace3f33230ed` — 联系我们 opens /index/contact.html

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_5c95d8415a4a1de556a9` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
