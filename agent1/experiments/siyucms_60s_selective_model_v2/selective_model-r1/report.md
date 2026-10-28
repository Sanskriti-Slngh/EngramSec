# Agent 1 run agent1-20261028T121234Z

- Code revision: `65b075ab8b339460dadb446c79b03fa6de03fa7c`
- Policy: `selective_model`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 56.534 seconds
- Browser actions (including setup/replay): 34
- Validated feature workflows: 2
- Replay success: 8/8
- Unsupported connections: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 2
- Model calls / cost: 9 / $0.000000

## Replay-validated workflows

- `feature_79f37482630e2359` — 资质荣誉四 opens /index/honours/{instance}.html
- `feature_e793b769c930e6cb` — 铅笔盒 opens /index/product/{instance}.html?cate

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_1d4576cb7ec47c24fd53` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- Model decision failed for obs_3a39a4cdb0faefdd2826: ModelProviderError; deterministic order used.
- Model decision failed for obs_ab999cb06df229766b68: ModelProviderError; deterministic order used.
- Model decision failed for obs_04b27d58986296387102: ModelProviderError; deterministic order used.
- Model decision failed for obs_256b748302f94568c7de: ModelProviderError; deterministic order used.
- Model decision failed for obs_1de7487c2d6c27536e69: ModelProviderError; deterministic order used.
- Model decision failed for obs_7d0ad220b2ae8a8b0467: ModelProviderError; deterministic order used.
- Model decision failed for obs_89849838dc2dfeeada07: ModelProviderError; deterministic order used.
- Model decision failed for obs_eeab6b69385f6375fb68: ModelProviderError; deterministic order used.
