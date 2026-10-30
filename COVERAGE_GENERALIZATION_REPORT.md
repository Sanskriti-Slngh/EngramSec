# Coverage and generalization report

## Result

This iteration adds bounded typed reference discovery, faster resource-aware readiness, and explicit prerequisite request provenance to Agent 1. The strongest combined Crawl Maze run reached **16/91** independent marker URLs in the server request log (17.6%), up from a contemporaneous legacy-knob control at **3/91**. This is meaningful progress, but remains below the 20-marker initial target and is not comparable to ZAP's published 45/59 result: target version, configuration, budget, and scoring context differ. The frozen-code re-run varied from 2/91 to the historical report's 4/91, so report the control range rather than pretending the baseline is a stable point estimate.

The combined final run began at the application root, used a single browser worker and a 180-second wall budget, 120 transitions, 300 browser-action cap, 100 typed GET fetches, no model, no credentials, and no paid APIs. The marker list was retrieved only after exploration through Crawl Maze's public evaluator interface, then independently checked against the local server request log. The mapper did not read evaluator paths. No protected WebExploitBench material was accessed.

## Crawl Maze measurements

| Variant | Expected marker URLs reached | References discovered | Spider fetched | Browser fetched | Replay attempts/successes | Transitions | Browser actions | Elapsed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen decc0a2 | 2/91 | 0 | 0 | 2 | 12/12 | 36 | 101 | 181.9 s |
| P0 legacy settings | 3/91 | 0 | 0 | 3 | 12/12 | 36 | 101 | 184.1 s |
| Typed spider only | 8/91 | 13 | 7 | 3 | 12/12 | 36 | 101 | 183.3 s |
| Readiness only | 11/91 | 0 | 0 | 11 | 32/32 | 85 | 285 | 181.7 s |
| Replay-diversity only | 3/91 | 0 | 0 | 3 | 11/11 | 36 | 102 | 184.3 s |
| Combined, diversity replay | 16/91* | 22 | 8 | 11 | 29/30 | 85 | 278 | 180.1 s |
| Combined, shallow replay, final | **16/91** | **22** | **8** | **11** | **32/32** | **85** | **285** | **181.5 s** |

`*` The diversity-combined row's 16/91 is the union of post-run Graph evidence; it was not scored against an independently retained server log. The final row's 16/91 is independently supported by the local server request log. Browser fetched and spider fetched sets overlap; do not add them. References, fetches, UI transitions, and replayed paths are distinct quantities.

Final per-category marker hits from the server log: HTML 10/57, JavaScript 3/27, HTTP headers 3/4, CSS 0/1, miscellaneous 0/2. The final graph recorded 22 expected references (post-run intersection), 11 browser-fetched expected URLs, 8 spider-fetched expected URLs, and one UI-state route match. These are not vulnerability coverage scores. The 85 observed transitions include ordinary navigation and do not equal 85 unique functions.

The final run recorded 74 grouped states, 162 typed resource references, 100/100 successful bounded spider GETs, 392 browser network events with 392 events represented, and 2,198/2,198 graph connections with evidence. It attempted 32/85 replayable paths and left 53 untested. The replay success rate is 32/32 for attempted paths, not 100% coverage. Its run metric reports zero incorrect state merges, but that is a mapper-side audit, not an independent proof of state equivalence.

The largest remaining gap is discovery/priority, especially HTML and JavaScript references: only 16/91 marker paths were fetched in the entire run, despite 100 safe GETs. Passive readiness consumed about 81 seconds and interactive readiness about 60 seconds; root reloads numbered 71 and restoration used 56 actions. The mapper spent measurable effort restoring and replaying while a large fraction of category paths remained unvisited. Thus low marker coverage is not just an action-support issue; breadth and revisit/restoration overhead remain important. The 100 spider fetches include ordinary resources and are not 100 new markers.

## Independent development cases

The local JavaScript-heavy lab was run under matched 60-second configurations. Its independent evaluator labels 11 applicable areas, 14 controls, and 12 request structures. P0, typed-spider-only, readiness-only, replay-only, and combined all found 9/11 areas, 12/14 controls, and 8/12 request structures. All recorded replays succeeded (P0 8/8; spider 7/7; readiness 10/10; replay 7/7; combined 9/9). The strongest depth was combined at four steps; replay-only reached three. Readiness increased transitions from 28 to 31 and unique replayed paths from 8 to 10, but not labeled-area recall. Spider increased passive resource references/fetches but did not improve this fixture's labeled UI or request recall. Critical false merges and sensitive-value leaks were independently scored at zero. This is a small controlled case, not broad generalization.

A separate held-out shop fixture repeat yielded 8/8 applicable areas, 11/11 controls, 8/8 request structures, 8/8 labeled paths, 2/2 records distinguished, and 2/2 context markers; 18/18 replay attempts succeeded. One admin area was inaccessible and excluded from the applicable denominator. This shop has appeared in earlier development work, so call this a separate-app transfer repeat, not a fresh unseen holdout.

## Conclusions and limits

- Readiness is the best measured contributor on Crawl Maze: transitions increased from 36 to 85 and replay attempts from 12 to 32 at the same wall budget. Three readiness runs were similar (11/91 each; 31–32 replays; roughly 281–285 browser actions).
- Typed discovery adds a complementary route to resources: it found seven expected URLs by direct fetch that the browser did not fetch, and raises the final union. It does not establish navigability or application behavior.
- Diverse replay scheduling did not help: it produced one replay failure and fewer successful replay validations than shallow scheduling. Shallow remains the default.
- The final implementation is not near the independent 90% coverage target on Crawl Maze. HTML and JS categories dominate the miss count, and the resource parser does not yet traverse enough discovered script/module structures or schedule long-tail references efficiently.
- ZAP's public 45/59 is a different denominator and experiment. No superiority or parity claim is supported.
- Crawl Maze marker URLs are a resource-discovery proxy. Route similarity or a fetched URL is not evidence of vulnerability coverage or successful application functionality.

## Reproduction

Use a clean isolated Crawl Maze checkout/venv and empty output directory. Start the local server on loopback, then run:

```sh
PYTHONPATH=. .venv/bin/python experiments/run_resource_spider_ablation.py \
  --root agent1/experiments/reproduction_run --seconds 180 \
  --max-transitions 120 --max-browser-actions 300 \
  --variants p0 spider readiness replay combined combined_shallow
```

After the crawl only, score the saved graph and server log with:

```sh
PYTHONPATH=. .venv/bin/python experiments/score_crawlmaze_posthoc.py \
  --root agent1/experiments/reproduction_run \
  --url http://127.0.0.1:3460/ --out agent1/experiments/reproduction_score.json
```

See `agent1/experiments/resource_spider_ablation/` for per-run metrics and `combined_shallow_final/graph_a.mmd` for the standard Graph A diagram. Raw trace/checkpoint JSON remains in the ignored local experiment cache to avoid committing application content.

## Research sources

The implementation follows the complementary roles of [ZAP Traditional Spider](https://www.zaproxy.org/docs/desktop/addons/spider/) and [ZAP Client Spider](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/spider/), Google's guidance that crawlable links use observed anchors with `href` ([Google Search Central](https://developers.google.com/search/docs/crawling-indexing/links-crawlable)), reference resolution and resource semantics in the [HTML Living Standard](https://html.spec.whatwg.org/) and [CSS Syntax](https://www.w3.org/TR/css-syntax/), and HTTP `Link` metadata in [RFC 8288](https://www.rfc-editor.org/rfc/rfc8288). Bounded actionability/readiness is informed by [Playwright's actionability model](https://playwright.dev/docs/actionability). Archive-and-return is inspired by [Go-Explore](https://arxiv.org/abs/2004.12919), but the diversity replay ablation did not improve results here.
