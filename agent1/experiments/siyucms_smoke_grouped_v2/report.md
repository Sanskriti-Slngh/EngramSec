# Agent 1 run agent1-20261028T115244Z

- Code revision: `65b075ab8b339460dadb446c79b03fa6de03fa7c`
- Policy: `grouped`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 0.351 seconds
- Browser actions (including setup/replay): 46
- Validated feature workflows: 9
- Replay success: 11/11
- Unsupported connections: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 2
- Model calls / cost: 0 / $0.000000

## Replay-validated workflows

- `feature_3134afa016d05982` — Previous leads to SIYUCMS 官网
- `feature_9d1c417faecae0c8` — 钢笔 opens /index/product/{instance}.html?cate
- `feature_adaada0ffa924b58` — 资料下载 opens /index/download.html
- `feature_c794ea4232cc0d0f` — Next leads to SIYUCMS 官网
- `feature_df42b62bf2d13cc4` — 资质荣誉 opens /index/honours.html
- `feature_e0b1ee5e0db3eed1` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_eb1e9c5d08c01879` — 资质荣誉四 opens /index/honours/{instance}.html
- `feature_f43516ede2749372` — 联系我们 opens /index/contact.html
- `feature_fc30d5490e285ded` — 资质荣誉六 opens /index/honours/{instance}.html

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_fa61bfb2172494c797ee` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- Resumed from checkpoint saved at 2026-10-28T11:53:25.620696+00:00.
