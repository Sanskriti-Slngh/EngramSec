# Agent 1 run agent1-20261028T121348Z

- Code revision: `65b075ab8b339460dadb446c79b03fa6de03fa7c`
- Policy: `exact`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 602.279 seconds
- Browser actions (including setup/replay): 529
- Validated feature workflows: 16
- Replay success: 77/77
- Unsupported connections: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 5
- Model calls / cost: 0 / $0.000000

## Replay-validated workflows

- `feature_2d2e4683da6149c0` — 优秀团队 opens /index/team.html
- `feature_300f7f2b64e8fbb8` — 用户中心 opens /index/user/login
- `feature_383ce999c91ed6c5` — 注 册 opens /index/User/register.html
- `feature_3b5d756f5c33435d` — 国内网络总监 opens /index/team/{instance}.html
- `feature_44d6e6cbf254c554` — 关于我们 opens /index/about.html
- `feature_4d6f5501f417b343` — 查看更多 opens /index/information.html
- `feature_5ce256c24795e4ad` — 首页 opens /
- `feature_653c8855e349ad43` — 资料下载 opens /index/download.html
- `feature_8439b81187224472` — 资质荣誉 opens /index/honours.html
- `feature_8f920b22df292b84` — 联系我们 opens /index/contact.html
- `feature_9243568d32b4dcd5` — 产品中心 opens /index/product.html
- `feature_9710f969516b98ac` — 查看详细 opens /index/Article/info.html?cate&id
- `feature_98ad47ac95cc8d75` — 招聘表格下载 opens /uploads/{instance}/{instance}6d08f0{instance}8e54d9ac4eae3d0a6d53cff7.rar
- `feature_a8c5fe083783ade1` — 新闻中心 opens /index/news.html
- `feature_f107262807d6fe62` — 资质荣誉四 opens /index/honours/{instance}.html
- `feature_f253178968c62b36` — 铅笔盒 opens /index/product/{instance}.html?cate

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_77e292d2a46130e0278c` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_16a5ffafe917b5a6a7f8` — 盒子: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(2) > div > div:nth-of-type(1) > a:nth-of-type(1)").first - locator resolved to <a href="#" class="ec-boxed">…</a> - attempting click action 2 × waiting for element to be visible, enabled and stable - elem
- `tr_cf5e97b96d526c0a3914` — 国外销售总监: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > div:nth-of-type(7) > div > div > div > div:nth-of-type(2) > div > div > div:nth-of-type(3) > h2 > a").first - locator resolved to <a tabindex="-1" href="/index/team/14.html">国外销售总监</a> - attemp
- `tr_4a9b22f3baebdb80de06` — 国内技术总监: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > div:nth-of-type(7) > div > div > div > div:nth-of-type(2) > div > div > div:nth-of-type(2) > h2 > a").first - locator resolved to <a tabindex="-1" href="/index/team/15.html">国内技术总监</a> - attemp
- `tr_f15f687d7e4d6ff1f891` — 国内保密设计师: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > div:nth-of-type(7) > div > div > div > div:nth-of-type(2) > div > div > div:nth-of-type(4) > h2 > a").first - locator resolved to <a tabindex="-1" href="/index/team/13.html">国内保密设计师</a> - attem
- `tr_ecab7346c207d6b71f22` — 全屏: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(2) > div > div:nth-of-type(1) > a:nth-of-type(2)").first - locator resolved to <a href="#" class="ec-wide">…</a> - attempting click action 2 × waiting for element to be visible, enabled and stable - eleme
- `tr_58a5d9c7036c143be275` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_1ff337b4be78d38a3aeb` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_380b191c1ed02c7ceb25` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_ea1b82efd46f90bea07e` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_b6b9783f0740ae9e9b33` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_96e7d803826abd5b47f4` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_34b1f84cf9e5b7501cc0` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_c74dd82fc863178c78f1` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_cbe901a08343ee7e7084` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_b34accf6c46f1974f6d0` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_3c5325853c26700246b8` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_8db58aaa9237c941ae86` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_6b4f6584f3ecd7ad86a7` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_062c293195652639120b` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_dcf28f6e0ee966f3b844` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_861c0713389f38866917` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_2d7151f506cdd435186b` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_8b27cfbd419a0bcf95b0` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_3fb7d8b213313b1eb6c7` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_4a63cf471370b5120373` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_8265b3e46d4cbd2466bc` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a
- `tr_58157f452ff87a27ff14` — unnamed button: TimeoutError: Locator.click: Timeout 5000ms exceeded. Call log: - waiting for locator("body > div:nth-of-type(1) > div > header > div:nth-of-type(2) > div > div > div:nth-of-type(2) > div > div:nth-of-type(2) > div > form > button").first - locator resolved to <button type="submit">…</button> - attempting click a

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- Post-run feature-identity audit: repeated site-wide links were collapsed across source states; raw observations, transitions, replays, and the original run directory remain unchanged.
