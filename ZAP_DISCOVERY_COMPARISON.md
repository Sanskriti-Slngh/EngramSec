# ZAP discovery comparison

The traditional ZAP Spider found useful complementary resources, but this milestone stopped before integration. Its Client Spider ran with the real browser extension and populated a Client Map; the official map export was not valid YAML when parsed after shutdown and after a second export. A trustworthy Client Map adapter and a live Agent 1 plus ZAP comparison therefore remain blocked. No Agent 1 architecture change or partial adapter was retained.

## Setup and boundary

- Agent 1 began at commit `e69c7a6`; target was Google Security Crawl Maze revision `2a0dd0a75e39925ded887bcd25016e8b3ce0f2b3`, running Flask 3.1.3 in a disposable container. Agent 1 accessed its loopback-published port; ZAP accessed the same server through a dedicated internal Docker network. The target port was published only on `127.0.0.1`.
- The official `ghcr.io/zaproxy/zaproxy:weekly` image was version `D-2026-10-29`, image ID `sha256:42ed9f5219f4301c39f0c88141e074513422e9507bd51da421bbdd6c1fa2d86a`. The ARM64 image contained about 1.05 GB of compressed layers; the resulting local testbed image occupied about 405 MB. Installed add-ons: Spider 0.21.0, Client 0.35.0, Selenium 15.60.0.
- ZAP had one traditional spider thread and one Firefox browser, strict context scope, no POST forms in the traditional spider, and robots/sitemap guessing disabled. No active scanner was started. The Docker network prevented ZAP from reaching the external internet.
- The first 25-second diagnostic exposed a ZAP default: PTK SAST and IAST instrumentation were enabled automatically; DAST was disabled. We did not inspect findings. The diagnostic was stopped and not scored. The measured runs used explicit `MANUAL` run locations and disabled SAST, IAST, DAST, and the PTK active scan rule. ZAP logs confirmed all three engines disabled. ZAP documentation states that its SAST/IAST instrumentation adds no extra traffic; it is still disclosed here because it was not intended for this evaluation. [PTK options](https://www.zaproxy.org/docs/desktop/addons/owasp-ptk/ptk-options/), [ZAP PTK design](https://www.zaproxy.org/blog/2026-06-29-even-more-owasp-ptk-integration-with-zap/).
- Evaluation paths were fetched by a separate scorer only after the relevant crawl stopped. They were never supplied to Agent 1 or ZAP as crawl inputs. Query and form values were not retained in the sanitized ZAP request records.

## Shared-server results

All runs started at the application root with a nominal 180-second cap. Agent 1 had 300 browser actions and 100 typed-resource GETs; ZAP does not provide the same action or global request limits. ZAP history contains status-zero discovery placeholders, so response-bearing messages are reported separately. They are a lower bound on transport attempts; the total history entry count is a conservative upper bound, not an exact request count.

| Run | Elapsed | Successful unique paths | Expected paths fetched | ZAP response-bearing / status-zero history | Replays |
|---|---:|---:|---:|---:|---:|
| Agent 1 | 165.855 s | 121 | 25/91 | 409 browser events + 91 typed GET attempts | 24/24; 79 transitions untested |
| ZAP traditional | 2.043 s, completed | 135 | 13/91 | 212 / 132 | Not independently replayed |
| ZAP Client Spider | 180.336 s, stopped at cap | 58 | 7/91 | 78 / 64 | Not independently replayed |
| ZAP traditional then Client | 180.987 s, Client stopped at cap | 141 | 16/91 | 287 / 140 | Not independently replayed |

All recorded ZAP history entries used GET. The traditional run generated 212 candidate URLs; a discovered candidate is not counted as a fetched response. The standalone Client Spider generated a 52,192-byte Client Map with 143 `nodeType` DOM component records. ZAP's Client Spider documentation identifies its browser extension and Client Map as the mechanism; the exported component records demonstrate that this was a Client Spider run, not a substituted traditional scan. [Client Spider](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/spider/), [Client Map](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/).

Traditional ZAP's successful paths included 43 paths absent from Agent 1's successful-path set, eight of which were independently scored expected paths. Client Spider had nine unique paths, one independently scored expected path. The combined ZAP run had 45 unique paths, ten independently scored expected paths. The post-run set unions with Agent 1 were 33/91, 26/91, and 35/91 respectively. These are **set unions**, not results of a live integrated crawl, and they do not establish replayable workflows. Across separate ZAP runs, the two spiders shared 45 successful paths; traditional-only had 90 and client-only had 13. Their union was 19/91 expected paths.

A preliminary run against an equivalent separate container reached 13/91 traditional, 3/91 client, and 22/91 combined; the shared-server client/combined values above were 7/91 and 16/91. This variation and unequal request limits preclude a superiority claim. ZAP's fast traditional spider nevertheless supplies nonduplicate resource evidence worth further investigation.

## Client Map blocker and Graph A audit

The Client Map was exported through the documented `client/action/exportClientMap` API. Python's standard safe YAML loader raised `ParserError` for the standalone export. A second export after the combined scan had stopped also raised `ParserError` (55,291 bytes, 143 DOM component records). A textual component count establishes extension activity, but does not safely reconstruct the Client Map, its node hierarchy, fragments, or session context. Guessing indentation or treating extracted strings as a valid map would lose provenance.

The existing Agent 1 graph on the shared target has 1,294/1,294 complete evidence connections under its internal audit and 0 missing connections. This is a structural completeness check, not independent semantic verification. ZAP resources have not been imported into Graph A, and no ZAP URL is represented as an Agent 1 transition or replay. The raw baseline Graph A, sanitized ZAP history records, and Client Maps are retained locally in ignored paths; the committed [aggregate results](agent1/experiments/zap_comparison_local/zap_aggregate.json) contain no expected path list.

## Decision and next step

Do not force a ZAP adapter while its Client Map export cannot be parsed reliably. The narrow HTTP history comparison supports a future integration experiment: traditional ZAP produced eight scored paths absent from Agent 1, but under a different request budget, and its paths do not yet have Agent 1 prerequisite or replay evidence. Client Spider's standalone score was below Agent 1 and varied between runs. The next step is to reproduce the invalid export with the pinned ZAP/add-on versions, establish whether an official structured export or fixed release preserves the Client Map hierarchy, then implement an external-evidence adapter with explicit origin mapping and path-level replay. Only after that can the requested live A/B/C and browser-heavy regression comparison be run.

## Reproduction

The locally prepared testbed is `/private/tmp/security-crawl-maze` at the revision above. From the repository root, the following commands recreate the loopback-only target and internal ZAP network. They create only the named disposable resources:

```sh
mkdir -p /private/tmp/engramsec-zap-eval
printf 'FROM python:3.11\nRUN pip install --no-cache-dir Flask==3.1.3\nWORKDIR /app\nCMD ["flask", "--app", "app", "run", "--host", "0.0.0.0", "--port", "3460"]\n' > /private/tmp/engramsec-zap-eval/Dockerfile
docker build -t engramsec-crawlmaze-eval:local /private/tmp/engramsec-zap-eval
docker network create --internal engramsec-zap-eval-net
docker run -d --name engramsec-zap-maze --network bridge \
  -p 127.0.0.1:3460:3460 -v /private/tmp/security-crawl-maze:/app:ro \
  engramsec-crawlmaze-eval:local
docker network connect --alias crawlmaze engramsec-zap-eval-net engramsec-zap-maze
docker run -d --name engramsec-zap-eval --network engramsec-zap-eval-net \
  ghcr.io/zaproxy/zaproxy@sha256:42ed9f5219f4301c39f0c88141e074513422e9507bd51da421bbdd6c1fa2d86a \
  zap.sh -daemon -host 0.0.0.0 -port 8090 \
  -config api.disablekey=true -config 'api.addrs.addr.name=.*' -config api.addrs.addr.regex=true \
  -config ptk.engine.SAST.runLocation=MANUAL -config ptk.engine.IAST.runLocation=MANUAL \
  -config ptk.engine.DAST.runLocation=MANUAL -config ptk.useRecommendedDefaults=false \
  -config ptk.scanrules.SAST.enabled=false -config ptk.scanrules.IAST.enabled=false \
  -config ptk.scanrules.DAST.enabled=false -config ptk.activescan.rule.enabled=false
docker cp experiments/run_zap_spider_comparison.py engramsec-zap-eval:/tmp/run_spiders.py
docker exec engramsec-zap-eval python3 /tmp/run_spiders.py traditional 180
docker exec engramsec-zap-eval python3 /tmp/run_spiders.py client 180
docker exec engramsec-zap-eval python3 /tmp/run_spiders.py combined 180
docker exec engramsec-zap-eval python3 -c 'import yaml; yaml.safe_load(open("/tmp/engramsec-combined-map.yaml", encoding="utf-8"))'
```

Wait for the ZAP API to finish starting before the first `docker exec`. Each invocation starts a fresh ZAP session and contacts the local expected-path evaluator only after its spider stops. Use the existing `experiments/run_resource_spider_ablation.py` command from [COVERAGE_ABLATIONS.md](COVERAGE_ABLATIONS.md) for the Agent 1 180-second baseline. Stop and remove only these two named containers and the named network when finished.

No paid APIs or models were used. The created test containers and internal network were stopped and removed after the comparison; the downloaded ZAP image remains available locally.

The image and add-on setup completed within the 15-minute installation limit. The experiment script passed `py_compile`. Four existing focused tests passed for observation evidence, session differences, typed-spider scope, and fresh-context prerequisite replay. No adapter-specific tests are claimed because the incomplete adapter was removed when the Client Map export blocker reproduced.
