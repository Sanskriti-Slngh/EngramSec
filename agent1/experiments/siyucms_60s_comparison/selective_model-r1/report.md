# Agent 1 run agent1-20261028T121012Z

- Code revision: `65b075ab8b339460dadb446c79b03fa6de03fa7c`
- Policy: `selective_model`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 56.192 seconds
- Browser actions (including setup/replay): 46
- Validated feature workflows: 3
- Replay success: 11/11
- Unsupported connections: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 1
- Model calls / cost: 2 / $0.000000

## Replay-validated workflows

- `feature_79f37482630e2359` — 查看详细 opens /index/honours/{instance}.html
- `feature_9596fe5c7b73302a` — php整型就是整数 opens /index/Article/info.html?cate&id
- `feature_e793b769c930e6cb` — 一支笔 opens /index/product/{instance}.html?cate

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_3ac3b5a5e7a393cc72bc` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- Model decision failed for obs_b3f805f5e0069d2e2b88: JSONDecodeError; deterministic order used.
- Model decision failed for obs_6b65771508021ae6c32b: JSONDecodeError; deterministic order used.
- Model decision failed for obs_0153323aed5136813c2c: JSONDecodeError; deterministic order used.
- Model decision failed for obs_c672f0cad6557b02dae7: JSONDecodeError; deterministic order used.
- Model decision failed for obs_ce56095a769e9a74fbb6: JSONDecodeError; deterministic order used.
- Model decision failed for obs_614dd9041056dd6ada89: JSONDecodeError; deterministic order used.
- Model decision failed for obs_98f3ea47509af394df88: JSONDecodeError; deterministic order used.
- Model decision failed for obs_d47925debbdbe293977c: JSONDecodeError; deterministic order used.
- Model decision failed for obs_c686c0f4d51db7c12850: JSONDecodeError; deterministic order used.
