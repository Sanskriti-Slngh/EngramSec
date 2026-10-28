# Agent 1 run agent1-20261028T121348Z

- Code revision: `65b075ab8b339460dadb446c79b03fa6de03fa7c`
- Policy: `exact`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 602.279 seconds
- Browser actions (including setup/replay): 529
- Validated feature workflows: 36
- Replay success: 77/77
- Unsupported connections: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 5
- Model calls / cost: 0 / $0.000000

## Replay-validated workflows

- `feature_01ac5bffe7aa8aa3` — 资质荣誉 opens /index/honours.html
- `feature_01f9c0426d3a7cd0` — 资质荣誉 opens /index/honours.html
- `feature_06bf170fd944acde` — unnamed link opens /index.html
- `feature_15ab4a6d3a504efa` — 首页 opens /
- `feature_18306b3e2ce685bb` — 首页 opens /
- `feature_2fdca4a22834026c` — 关于我们 opens /index/about.html
- `feature_30511c7f0163a002` — 首页 opens /
- `feature_388e81cd888d9029` — 首页 opens /
- `feature_3bd443e3870e2849` — 优秀团队 opens /index/team.html
- `feature_3bfa44d4085f446e` — 招聘表格下载 opens /uploads/{instance}/{instance}6d08f0{instance}8e54d9ac4eae3d0a6d53cff7.rar
- `feature_4be88c03e0f1d8fd` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_598e9cbd5aba1aa2` — 首页 opens /
- `feature_6492536e4d8871f9` — 国内网络总监 opens /index/team/{instance}.html
- `feature_64d15f6c5034b199` — 资料下载 opens /index/download.html
- `feature_70554e786b5dc95a` — 查看更多 opens /index/information.html
- `feature_768df5617575fc75` — 资质荣誉四 opens /index/honours/{instance}.html
- `feature_79f37482630e2359` — 资质荣誉四 opens /index/honours/{instance}.html
- `feature_80a4689558b44c68` — 首页 opens /
- `feature_89c9c73afdb69ef3` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_8f7efb2a900b79cd` — 首页 opens /
- `feature_9596fe5c7b73302a` — 查看详细 opens /index/Article/info.html?cate&id
- `feature_a4a5372118547327` — 新闻中心 opens /index/news.html
- `feature_ad05dac3ebe07144` — 注 册 opens /index/User/register.html
- `feature_b663dfa34184143f` — 首 页 opens /
- `feature_c86986b0365c4d30` — 首页 opens /
- `feature_c937b62eba145d00` — 产品中心 opens /index/product.html
- `feature_cb5d0a4f69ba23e1` — 首页 opens /
- `feature_d095f4659f93847d` — 首页 opens /
- `feature_d48f21e65d2df33e` — 首页 opens /
- `feature_e6e60c728fa93264` — 首页 opens /
- `feature_e793b769c930e6cb` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_e7f4ba16fbb5944d` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_e903782cb27ce644` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_eaca7bcc690707fa` — 首页 opens /
- `feature_eeb89a0507d5d5ba` — 用户中心 opens /index/user/login
- `feature_f02aace3f33230ed` — 联系我们 opens /index/contact.html

## Observed but not replay-validated

- `feature_3c730f24e3d9243d` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_3efb6dbec2646e69` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_540099e5ed33dd10` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_6712edc4e7e6b65f` — 资质荣誉 opens /index/honours.html
- `feature_6c1c9c8d738c65a5` — 首页 opens /
- `feature_82ed5531b6878c93` — 首页 opens /
- `feature_93728ac0f3fc39c7` — 首页 opens /
- `feature_9e11994b0f5b3dbd` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_af8808e6ce62dc85` — 首页 opens /
- `feature_c2920c765eee9e62` — 资质荣誉 opens /index/honours.html
- `feature_c39f70c4023c6731` — 铅笔盒 opens /index/product/{instance}.html?cate
- `feature_eb01957442da45d2` — 铅笔盒 opens /index/product/{instance}.html?cate

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
