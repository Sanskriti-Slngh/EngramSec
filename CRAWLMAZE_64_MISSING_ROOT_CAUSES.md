# Crawl Maze: root causes of the 64 missed paths

**Diagnostic only.** No crawls, no Agent 1 changes. Inputs: existing artifacts for run B (`architecture_comparison/adaptive_readiness_B_r1`, best matched 180 s run, 27/91), run A (`…_A_r1`, 25/91) and the earlier serious run S300 (`serious_budget/adaptive_readiness_adaptive_ast_fifo_300s`, 37/91); the pinned testbed `/private/tmp/security-crawl-maze` @ `2a0dd0a`. The per-path data is in [CRAWLMAZE_91_PATH_AUDIT.csv](CRAWLMAZE_91_PATH_AUDIT.csv). It is produced by [experiments/audit_crawlmaze_missing.py](experiments/audit_crawlmaze_missing.py), an offline evaluator that Agent 1 never imports.

## Bottom line

1. **The largest cause is budget starvation, not missing capability.** 35 of the 64 misses are on test pages Agent 1 had already *discovered* (21 as advertised links, 14 as spider references) but never visited or fetched. Every one of those references is marked `class_budget_limited`: the 70-document spider allowance ran out, and the 300 browser actions were spent elsewhere. Another 3 markers were extracted and then dropped for the same reason.
2. **The static extractors have verified gaps.** I ran Agent 1's own extractors on every test file. 27 mechanisms produce no reference at all (23 HTML, 3 JavaScript, robots.txt). 20 of the misses need an extractor change whatever the budget: 14 HTML-mechanism cases and 6 text/JS-literal cases.
3. **The scoring and the HTTP-method policy hide 11 cases.** The testbed's `/test/<path>` route answers only GET, so the 11 cases whose intended request is POST/PUT/DELETE can never produce a 2xx. In 6 of them Agent 1's browser did send the exact request (and got 405). Its static parser also extracts all JS `fetch()` URLs but never fetches them, because they are typed `api`.
4. **Runtime interaction gaps are real but small:** 2 listener-on-`<div>` cases, 1 redefined-handler case and 1 five-second timer.
5. **6 cases are untestable on this deployment** (unbuilt Angular, React and Polymer). A 7th, AngularJS, depends on a third-party CDN and a hashbang route.

## 1. Test environment audit

| Case | Evidence (this deployment, plain Flask) | Verdict |
|---|---|---|
| `angular/event-handler`, `angular/router-outlet` | Source tree has no `index.html`; the catch-all route `serve_framework_root` → **404 for every path**, including the expected ones (verified with `curl`) | Unsupported: no crawler can obtain a 2xx |
| `react/route-path`, `react/index.html/search` | Same: no root `index.html`, **404 for every path** (verified) | Unsupported |
| `polymer/event-handler`, `polymer/polymer-router` | Catch-all returns `index.html` (200) for any path. But the page loads `/node_modules/@webcomponents/…/webcomponents-loader.js` and `/src/my-app.js` (both **404**, verified, because `<base href="/">`), and `my-app.js` uses bare module specifiers that need the Polymer build. The app cannot render, and no reachable resource references either marker. | Unsupported |
| `angularjs/ng-href` | No build needed, but AngularJS loads from `ajax.googleapis.com`. In B (HTTP budget set → Agent 1's route aborts cross-origin requests; 2 blocked), the page was observed with **0 controls**. In S300 (no route) AngularJS rendered an "ng-href navigation" link and Agent 1 clicked it twice. The link is the hashbang route `index.html#!ng-href.found`, so the expected **server** path is never requested. | Conditionally supported: needs third-party code, and the expected path needs a hashbang-to-path interpretation |

README line 37: *"Run locally as a Flask app (Does not support JS frameworks)"*. The Dockerfile builds Angular, Polymer and React; AngularJS is not built.

**Denominators.**

| Denominator | Size | A | B | S300 |
|---|---:|---:|---:|---:|
| Raw expected list | 91 | 25 | 27 | 37 |
| Excluding the 6 cases proven unsupported | 85 | 25 | 27 | 37 |
| Also excluding conditional AngularJS (third-party CDN + hashbang semantics) | **84** | 25 | 27 | 37 |

**Scoring note (not a deployment defect, but it affects every run).** `/test/<path:path>` is a Flask route with default methods, so POST/PUT/DELETE get **405** (verified). 11 expected paths are exercised by a non-GET request in the test case: 7 interactive JS, `automatic-post`, `form/action-post`, `area/ping`, and DELETE/PUT among them. Under the 2xx `any_fetch` scorer used in all prior reports, they can only count if something issues a GET for the literal. Sensitivity for B: **27** (strict 2xx) · **33** (any request sent, including 405) · **40** (request sent *or* exact reference extracted). A: 25 / 31 / 38. S300: 37 / 44 / 56. All other numbers in this report use the strict 2xx definition.

## 2. Root-cause frequency (B, 64 misses; mutually exclusive primary cause)

Primary cause = the first failed stage on the route the test case is designed to exercise: static reference for static cases, browser interaction for interactive ones. Blockers on alternative routes are listed as secondary causes in the CSV (`secondary_causes`, `route_blockers`). All 64 primary assignments are **confirmed** by recorded evidence. None needed the "unknown" class.

| # | Primary cause | HTML | JS | Misc | **Total** |
|---:|---|---:|---:|---:|---:|
| 1 | Unsupported test case (framework not built) | 0 | 6 | 0 | **6** |
| 2 | Parent page not discovered or visited | 31 | 4 | 2 | **37** |
| 3 | Parent reached, reference not extracted | 4 | 3 | 0 | **7** |
| 4 | Reference extracted but excluded/misclassified | 0 | 0 | 0 | **0** |
| 5 | Candidate admitted, not fetched (budget) | 3 | 0 | 0 | **3** |
| 6 | Interaction/behavior available, never executed | 0 | 1 | 0 | **1** |
| 7 | Prerequisite executed, follow-up interaction not observed | 0 | 3 | 0 | **3** |
| 8 | Blocked by safety/origin policy | 0 | 1 | 0 | **1** |
| 9 | Attempted, failed / unexpected response | 0 | 0 | 0 | **0** |
| 10 | Evaluator/evidence-accounting mismatch | 0 | 6 | 0 | **6** |
| 11 | Unknown | 0 | 0 | 0 | **0** |
| | **Total** | **38** | **24** | **2** | **64** |

Cause 4 is 0 *as a primary cause* only because of the rule above. Offline, the extractor types 19 expected-path references as `api` (17 JS `fetch()` literals and 2 form actions; 9 GET, 10 non-GET), and `api` references are never fetched. 16 of them are B misses: 10 are recorded in B as `queue_decision = observed_only_api`; the other 6 sit on pages B never visited. The 3 reached ones were reached by clicking.

### Cause 2 (37): what the unvisited parents were

| Sub-group | n | Evidence |
|---|---:|---|
| Statically extractable marker; parent discovered but never visited or fetched | 16 | Agent 1's extractor emits the marker from the test file (verified offline). Parent reference `class_budget_limited`. S300, with 2× actions and 2× spider budget, reached 14 of these 16. |
| Parent not visited **and** extractor gap | 13 | Would still fail if visited (e.g. `img[lowsrc]`, `body[background]`, text strings, `iframe[srcdoc]`) |
| Interactive JS page (needs a click) not visited | 4 | `js-delete`, `js-post-event-listener` (non-GET → 405 anyway), and the two decoy-button multi-step pages |
| Form page not visited (form action typed `api`; no submit button) | 2 | `form/action-get`, `form/action-post` |
| Well-known file never requested | 2 | `/robots.txt` and `/sitemap.xml` are not linked from anywhere; Agent 1 does not probe well-known paths. ZAP was configured with robots/sitemap parsing off. |

Of the 35 known-but-unvisited parents, 21 were advertised links on pages the browser had observed, and 14 were only spider references from fetched listing pages.

**Run A vs B.** A reached 8 markers that B did not; their B causes are 2 (×5) and 5 (×3). B's 100 typed GETs were partly spent on ZAP seeds, which pushed these parents and markers past the class budget. B reached 10 markers A did not, 4 of them only through ZAP seeds (`doctype`, `manifest`, `url-string`, `content-location`), which covers mechanisms Agent 1 cannot extract itself.

### The other 27

| Cause | Paths | Specific evidence |
|---|---|---|
| 3 not extracted (7) | `isindex/action`, `map/area/ping`, `head/comment-conditional`, `head/import/implementation`, `javascript/misc/comment`, `…/string-concat-variable`, `…/string-variable` | Parent reached by browser (and spider for the `.js`). Offline extractor run: **NOT extracted**. Reasons: `isindex`, `ping` and `IMPORT` are not in the attribute table; the HTML parser ignores comments; the AST parser ignores comments and emits literals only at recognized sinks, so `var url = "…"` and a folded `domain + path` that is never passed to a sink are dropped. `area/ping`: the "unnamed link" click was executed (status failed) and no ping request was recorded. |
| 5 budget (3) | `blockquote/cite`, `frameset/frame/src`, `meta/content-redirect` | Parent visited; marker extracted (`<blockquote>[cite]`, `<frame>[src]`, `<meta>[content]`), then `class_budget_limited`. S300 reached `cite` and `content-redirect`; A reached `cite` and `frame`. |
| 10 accounting (6) | `js-post`, `js-put`, `listener-and-event-attribute-first/second`, `two-listeners-first/second` | Agent 1 clicked **Submit**; its browser sent the exact `POST`/`PUT` to the marker; the testbed answered **405**. The literal was also extracted by the AST parser (`call:fetch`, `observed_only_api`). Agent 1 found the URL; the strict 2xx scorer cannot count it. |
| 7 follow-up not observed (3) | `multi-step-…-listener-div`, `…-listener-div-dom`, `…-redefine-event-attribute` | "show secret button" was clicked (×2: exploration and replay), but the created `<div>` with `addEventListener` was **not detected as a control** (no new controls in the result observation). For `redefine`, the first click only rebinds `onclick` on the same button, with no DOM change, and the same control was never clicked again. **Contrast:** the three variants that create a `<button>` (`event-attribute`, `event-listener`, `event-listener-dom`) were all reached in A, B and S300; Agent 1 executed "click this secret button". |
| 6 behavior never exercised (1) | `javascript/misc/automatic-post` | The POST fires 5 s after load. B navigated at 21:17:35.9, observed at 38.09 and left by 39.35: about 3.5 s, so the timer never fired. Even if it had, the POST would get 405. |
| 8 policy (1) | `angularjs/ng-href` | See section 1. |
| 1 unsupported (6) | Angular ×2, React ×2, Polymer ×2 | See section 1. |

## 3. Verified extraction gaps (Agent 1 extractors run offline on the testbed sources)

| Mechanism | Verified result | Paths |
|---|---|---|
| Missing HTML attributes: `a[ping]`, `area[ping]`, `body[background]`, `td[background]`, `img[dynsrc]`, `img[lowsrc]`, `img[longdesc]`, `object[codebase]`, `isindex[action]`, `svg script[xlink:href]`, `html[manifest]`, `IMPORT[implementation]` | NOT extracted | 12 |
| Declarations and metadata: `<!DOCTYPE … SYSTEM "…">`, `<base href>` (used only to resolve other URLs), CSP `report-uri`, HTML inside `meta[content]` | NOT extracted | 4 |
| Embedded documents: `iframe[srcdoc]`, `data:` SVG in `img[src]` | NOT extracted | 2 |
| Conditional comment `<!--[if true]><link href>` | NOT extracted | 1 |
| URL-like text nodes (`./…`, `../…`, absolute URL, base + `.pdf`) | NOT extracted (no text-node candidates) | 4 |
| JS: URL in comment; literal not at a sink; folded concatenation not at a sink | NOT extracted | 3 |
| `robots.txt` `Disallow:` line | NOT extracted (parser reads only `Sitemap:`) | 1 |
| `sitemap.xml` `<loc>` | **Extracted** when the file is parsed; the file is never requested | 1 |
| JS `fetch()` literals, all methods | Extracted as `kind=api` → `observed_only_api`, never fetched | 17 |
| `form[action]` (GET and POST) | Extracted as `kind=api` → never fetched; neither form has a submit button | 2 |
| All other static mechanisms (`a[href]`, `img[src]`, `srcset`, `applet`, `param`, `track`, `meta` refresh/msapplication, `formaction`, …) | Extracted | 34 |

Other aspects the brief asked to check:
- **Multi-step clicks** work when the created element is a semantic control (3/3 reached).
- **Dynamic listeners** on non-semantic elements are not seen (0/2).
- **Methods other than GET:** the browser sends them and they are recorded, but the testbed returns 405.
- **POST form submission** is disabled by policy (`allow_post_forms=False`).
- **The framework cases** are unsupported by the deployment, not by the crawler.

## 4. Five highest-leverage verified failure mechanisms

Ranked by confirmed misses each explains in B. Every one has at least 3 independent test pages as examples.

1. **Discovered pages starved of budget (35 parents + 3 markers).** Agent 1 knew about these pages and never reached them. The spider's fixed 70-document class allowance and the 300 browser actions (about 40% of which went to restoration, per the previous milestone) are the binding constraints. S300's larger budget reached 16 of the 21 misses that need nothing else.
2. **HTML extractor coverage (23 not-extracted mechanisms; 14 misses need this whatever the budget).** All verified by running the extractor.
3. **Typed-`api` literals are never fetched (16 of B's misses; 19 expected paths overall).** These are JS `fetch()` literals and form actions. 6 of the missed ones are GET. For 4 of them this classification is the only static blocker besides allocation (2 `<div>` multi-step pages, `redefine`, `form/action-get`). The 2 decoy-button pages are already covered by allocation through the click route. The other 10 are non-GET.
4. **Non-GET intended requests (11 cases, 6 already sent by Agent 1 and answered 405).** This is a scorer/testbed property plus a safety-policy question, not a discovery failure.
5. **Text-node and non-sink JS literals (7 mechanisms, 6 B misses).** These are `./`, `../`, absolute-URL and base-relative text strings, plus the comment, variable and concatenation scripts.

Below the 3-example threshold as separate mechanisms:
- listener-only `<div>` controls: 2 examples
- handler redefinition: 1
- timer dwell: 1
- well-known files: 2 (robots, sitemap)
- AngularJS CDN/hashbang: 1

## 5. Opportunity by fix family (upper bounds on misses unblocked, not predicted score gains)

A fix is **sufficient** for a miss if it clears every recorded blocker on at least one route to a scorer-countable 2xx. These are counts of B misses, using the blockers in `route_blockers`.

| Area | Fix family | Sufficient alone | Extra when combined with A1 | Required on every route | ≥3 independent examples? |
|---|---|---:|---:|---:|---|
| Browser-action allocation | **A1** visit/fetch every discovered parent page (shared document/HTTP budget instead of a fixed class cap; plain GET links over HTTP) | **21** | – | **38** | Yes: 20 distinct pages; 16/21 empirically reached by S300 |
| Resource discovery | **R1** HTML attribute, declaration, comment and `srcdoc` coverage | 4 | **+14** | 14 | Yes (14 pages) |
| Resource discovery | **R2** text-node and non-sink JS literal candidates | 3 | +6 | 6 | Yes (6 pages) |
| Resource discovery | **R3** well-known files (`/robots.txt` Disallow, `/sitemap.xml`) | 2 | +2 | 2 | No (2) |
| Safety policy | **P1** fetch GET-method `api` literals (fetch GET, GET form action) | 3 | +4 | 0 | Yes (4), narrow |
| Safety policy | **P2** GET re-check of non-GET `api` literals | 7 | +10 | 0 | Yes, but semantically questionable: it requests a POST endpoint with GET |
| Runtime interaction discovery | **I1** listener-bearing elements, re-click after handler change, timer dwell | 3 | +3 | 0 | Borderline: 4 pages across 3 different sub-mechanisms |
| Stateful prerequisites | **S1** implicit form submit; executing created controls | 0 | +1 | 0 | No. Created *button* controls are already executed (3/3). |
| Evaluator | **E1** count observed non-2xx requests to marker URLs | 6 | +8 | 0 | Yes, but this is a scoring decision, not a crawler improvement |
| Testbed configuration | **T1** run the Docker image with built frameworks | 6 become *eligible* | – | 6 | Yes, but crawler success on them is untested |
| Safety policy | **C1** allow-listed third-party scripts + hashbang route semantics | 1 | – | 1 | No (1) |

**Combined resource-discovery opportunity (A1 + R1 + R2 + R3): up to 43 of the 64 misses unblocked.** That is an upper bound. It assumes every discovered parent is fetched within a budget the run can afford, and it does not predict a score.

## 6. Recommended next milestone

**"Discovery completeness under a fixed budget": allocation first, then extractor coverage.** Runtime instrumentation is deprioritized.

1. **Allocation (A1, 21 sufficient alone; required for 38).** Replace the fixed 70-document class cap with a draw on the shared, already-audited HTTP budget. B used 847 of 1,000 requests, 344 of them ZAP's upper bound; A used 496. Fetch statically discovered same-origin GET document links over HTTP instead of spending browser actions on them. Reserve browser actions for non-navigate controls. Provenance stays `agent_seed_fetch`/resource evidence, never a UI transition or replay. Measure at equal browser actions and equal total HTTP.
2. **Extractor coverage (R1 + R2, +20 beyond A1).** Add the verified missing attributes, declarations, `srcdoc` and conditional-comment parsing. Add text-node and non-sink JS literal candidates, typed as low-confidence `candidate` references and admitted under the same budget. These are generic HTML/JS semantics, not maze answers. Every gap above maps to a documented HTML/HTTP mechanism.
3. **Make the evaluation decision explicit before the next comparison.** Report strict-2xx, any-status-request and reference-or-request scores side by side, and state the supported denominator (84). Decide separately whether GET-method `api` literals (P1) may be fetched. That is a safety-policy call, and it only affects 4 misses.

Event-driven instrumentation, recommended last milestone as a second step, is supported here by only 2–4 cases. It should wait until allocation and extractor coverage stop being the binding constraints.

## Method and limitations

- One matched run per configuration (the repeats in [ARCHITECTURE_COMPARISON.md](ARCHITECTURE_COMPARISON.md) were deterministic). S300 is an older code revision with 2× budgets and no HTTP route. It is used as corroborating evidence, not as a matched comparison.
- "Reached" is the strict 2xx definition from `score_crawlmaze_posthoc.py`, recomputed from Graph A. The audit reproduces 25/27/37.
- Container/parent reachability counts a browser observation, a 2xx browser response or a 2xx spider fetch. Interaction facts come from `run.json` observations (all controls with `safe`/`skip_reason`) and transitions. "Created controls" are controls in a click's result observation that were absent from its source.
- Extractor verdicts come from running `agent1.resource_spider` extractors on the testbed's files on disk, with Jinja `url_for` rendered locally. Header cases are not covered by this check; their markers were all reached.
- Opportunity counts assume a fix removes only the blockers listed. They do not model budget competition between newly unblocked candidates, so they are upper bounds.
- **Repository-policy note.** `.gitignore` says per-case evaluator expectations should stay local. The CSV and appendix list exact expected paths, as this milestone requested. They are diagnostic outputs, never Agent 1 input. Whether to commit them is left to you. Nothing was committed in this milestone.

Reproduce:

```sh
.venv/bin/python experiments/audit_crawlmaze_missing.py \
  --best agent1/experiments/architecture_comparison/adaptive_readiness_B_r1 \
  --baseline agent1/experiments/architecture_comparison/adaptive_readiness_A_r1 \
  --serious agent1/experiments/serious_budget/adaptive_readiness_adaptive_ast_fifo_300s \
  --csv CRAWLMAZE_91_PATH_AUDIT.csv --json /tmp/crawlmaze_audit.json
```

## Appendix: all 91 expected paths

✓ = reached (strict 2xx). "Static extractor" is the offline extractor result on the case's container. Full evidence columns (queue decisions, spider attempts, browser requests, advertised/executed/created controls, route blockers, evidence references) are in the CSV.

| # | Expected path | Cat. | A | B | S300 | Supported | Static extractor (verified) | Interaction / method | B parent | B primary cause | Secondary |
|---:|---|---|:-:|:-:|:-:|---|---|---|---|---|---|
| 1 | `/javascript/frameworks/angular/event-handler.found` | javascript | · | · | · | no | n/a (header or unsupported) | click/GET | reached | 1 unsupported |  |
| 2 | `/javascript/frameworks/angular/router-outlet.found` | javascript | · | · | · | no | n/a (header or unsupported) | none/GET | reached | 1 unsupported |  |
| 3 | `/javascript/frameworks/angularjs/ng-href.found` | javascript | · | · | · | conditional | n/a (header or unsupported) | click/GET | reached | 8 policy | AngularJS loads from third-party CDN; Agent 1 aborts cross-origin requests when an HTTP budget is set; hashban |
| 4 | `/javascript/frameworks/polymer/event-handler.found` | javascript | · | · | · | no | n/a (header or unsupported) | click/GET | reached | 1 unsupported |  |
| 5 | `/javascript/frameworks/polymer/polymer-router.found` | javascript | · | · | · | no | n/a (header or unsupported) | none/GET | reached | 1 unsupported |  |
| 6 | `/javascript/frameworks/react/index.html/search.found` | javascript | · | · | · | no | n/a (header or unsupported) | form_enter/GET | reached | 1 unsupported |  |
| 7 | `/javascript/frameworks/react/route-path.found` | javascript | · | · | · | no | n/a (header or unsupported) | click/GET | reached | 1 unsupported |  |
| 8 | `/test/css/font-face.found` | css | · | ✓ | · | yes | asset:url() | none/GET | reached | reached |  |
| 9 | `/test/headers/content-location.found` | headers | · | ✓ | · | yes | n/a (header or unsupported) | none/GET | reached | reached |  |
| 10 | `/test/headers/link.found` | headers | ✓ | ✓ | ✓ | yes | n/a (header or unsupported) | none/GET | reached | reached |  |
| 11 | `/test/headers/location.found` | headers | ✓ | ✓ | ✓ | yes | n/a (header or unsupported) | navigate_header/GET | known, unvisited | reached |  |
| 12 | `/test/headers/refresh.found` | headers | ✓ | ✓ | ✓ | yes | n/a (header or unsupported) | none/GET | reached | reached |  |
| 13 | `/test/html/body/a/href.found` | html | · | · | ✓ | yes | navigation:<a>[href] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 14 | `/test/html/body/a/ping.found` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 15 | `/test/html/body/applet/archive.found` | html | · | · | ✓ | yes | asset:<applet>[archive] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 16 | `/test/html/body/applet/codebase.found` | html | · | · | ✓ | yes | asset:<applet>[codebase] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 17 | `/test/html/body/audio/source/src.found` | html | · | · | ✓ | yes | asset:<source>[src] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 18 | `/test/html/body/audio/source/srcset1x.found` | html | · | · | · | yes | asset:<source>[srcset] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 19 | `/test/html/body/audio/source/srcset2x.found` | html | · | · | · | yes | asset:<source>[srcset] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 20 | `/test/html/body/audio/src.found` | html | · | · | ✓ | yes | asset:<audio>[src] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 21 | `/test/html/body/background.found` | html | ✓ | ✓ | ✓ | yes | NOT extracted | none/GET | reached | reached |  |
| 22 | `/test/html/body/blockquote/cite.found` | html | ✓ | · | ✓ | yes | asset:<blockquote>[cite] | none/GET | reached | 5 budget |  |
| 23 | `/test/html/body/embed/src.found` | html | ✓ | ✓ | ✓ | yes | asset:<embed>[src] | none/GET | reached | reached |  |
| 24 | `/test/html/body/form/action-get.found` | html | · | · | · | yes | api:<form>[action] | form_enter/GET | known, unvisited | 2 parent not visited | requires interaction (form_enter) ; 5: parent page reference was class_budget_limited (70-document spider budg |
| 25 | `/test/html/body/form/action-post.found` | html | · | · | · | yes | api:<form>[action] | form_enter/POST | known, unvisited | 2 parent not visited | requires interaction (form_enter) ; 5: parent page reference was class_budget_limited (70-document spider budg |
| 26 | `/test/html/body/form/button/formaction.found` | html | ✓ | ✓ | ✓ | yes | navigation:<button>[formaction] | click/GET | reached | reached |  |
| 27 | `/test/html/body/frameset/frame/src.found` | html | ✓ | · | · | yes | asset:<frame>[src] | none/GET | reached | 5 budget |  |
| 28 | `/test/html/body/iframe/src.found` | html | · | · | ✓ | yes | asset:<iframe>[src] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 29 | `/test/html/body/iframe/srcdoc.found` | html | ✓ | ✓ | ✓ | yes | NOT extracted | none/GET | reached | reached |  |
| 30 | `/test/html/body/img/dynsrc.found` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 31 | `/test/html/body/img/longdesc.found` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 32 | `/test/html/body/img/lowsrc.found` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 33 | `/test/html/body/img/src-data.found` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 34 | `/test/html/body/img/src.found` | html | · | · | ✓ | yes | asset:<img>[src] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 35 | `/test/html/body/img/srcset1x.found` | html | ✓ | ✓ | ✓ | yes | asset:<img>[srcset] | none/GET | reached | reached |  |
| 36 | `/test/html/body/img/srcset2x.found` | html | ✓ | ✓ | ✓ | yes | asset:<img>[srcset] | none/GET | reached | reached |  |
| 37 | `/test/html/body/input/src.found` | html | ✓ | ✓ | ✓ | yes | asset:<input>[src] | none/GET | reached | reached |  |
| 38 | `/test/html/body/isindex/action.found` | html | · | · | · | yes | NOT extracted | none/GET | reached | 3 not extracted |  |
| 39 | `/test/html/body/map/area/ping.found` | html | · | · | · | yes | NOT extracted | click/POST | reached | 3 not extracted |  |
| 40 | `/test/html/body/object/codebase.found` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 41 | `/test/html/body/object/data.found` | html | ✓ | · | ✓ | yes | asset:<object>[data] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 42 | `/test/html/body/object/param/value.found` | html | · | ✓ | · | yes | asset:<param>[value] | none/GET | reached | reached |  |
| 43 | `/test/html/body/script/src.found` | html | ✓ | ✓ | ✓ | yes | asset:<script>[src] | none/GET | reached | reached |  |
| 44 | `/test/html/body/svg/image/xlink.found` | html | ✓ | ✓ | ✓ | yes | asset:<image>[xlink:href] | none/GET | reached | reached |  |
| 45 | `/test/html/body/svg/script/xlink.found` | html | · | · | ✓ | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 46 | `/test/html/body/table/background.found` | html | ✓ | · | ✓ | yes | asset:<table>[background] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 47 | `/test/html/body/table/td/background.found` | html | ✓ | ✓ | ✓ | yes | NOT extracted | none/GET | reached | reached |  |
| 48 | `/test/html/body/video/poster.found` | html | ✓ | · | ✓ | yes | asset:<video>[poster] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 49 | `/test/html/body/video/src.found` | html | ✓ | · | ✓ | yes | asset:<video>[src] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 50 | `/test/html/body/video/track/src.found` | html | · | ✓ | · | yes | asset:<track>[src] | none/GET | reached | reached |  |
| 51 | `/test/html/doctype.found` | html | · | ✓ | · | yes | NOT extracted | none/GET | reached | reached |  |
| 52 | `/test/html/head/base/href.found` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 53 | `/test/html/head/comment-conditional.found` | html | · | · | · | yes | NOT extracted | none/GET | reached | 3 not extracted |  |
| 54 | `/test/html/head/import/implementation.found` | html | · | · | · | yes | NOT extracted | none/GET | reached | 3 not extracted |  |
| 55 | `/test/html/head/link/href.found` | html | · | · | ✓ | yes | asset:<link>[href] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 56 | `/test/html/head/meta/content-csp.found` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 57 | `/test/html/head/meta/content-pinned-websites.found` | html | ✓ | · | ✓ | yes | asset:<meta>[content] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 58 | `/test/html/head/meta/content-reading-view.found` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 59 | `/test/html/head/meta/content-redirect.found` | html | ✓ | · | ✓ | yes | navigation:<meta>[content] | none/GET | reached | 5 budget |  |
| 60 | `/test/html/head/profile.found` | html | ✓ | ✓ | ✓ | yes | asset:<video>[poster] | none/GET | reached | reached |  |
| 61 | `/test/html/manifest.found` | html | · | ✓ | · | yes | NOT extracted | none/GET | reached | reached |  |
| 62 | `/test/html/misc/string/dot-dot-slash-prefix.found` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 63 | `/test/html/misc/string/dot-slash-prefix.found` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 64 | `/test/html/misc/string/string-known-extension.pdf` | html | · | · | · | yes | NOT extracted | none/GET | known, unvisited | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched ; 5: parent page reference |
| 65 | `/test/html/misc/string/url-string.found` | html | · | ✓ | · | yes | NOT extracted | none/GET | reached | reached |  |
| 66 | `/test/html/misc/url/full-url.found` | html | · | ✓ | ✓ | yes | navigation:<a>[href] | none/GET | reached | reached |  |
| 67 | `/test/html/misc/url/path-relative-url.found` | html | · | ✓ | ✓ | yes | navigation:<a>[href] | none/GET | reached | reached |  |
| 68 | `/test/html/misc/url/protocol-relative-url.found` | html | · | ✓ | ✓ | yes | navigation:<a>[href] | none/GET | reached | reached |  |
| 69 | `/test/html/misc/url/root-relative-url.found` | html | · | · | ✓ | yes | navigation:<a>[href] | none/GET | known, unvisited | 2 parent not visited | 5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action  |
| 70 | `/test/javascript/interactive/js-delete.found` | javascript | · | · | · | yes | api:call:fetch | click/DELETE | known, unvisited | 2 parent not visited | requires interaction (click) ; 5: parent page reference was class_budget_limited (70-document spider budget ex |
| 71 | `/test/javascript/interactive/js-post-event-listener.found` | javascript | · | · | · | yes | api:call:fetch | click/POST | known, unvisited | 2 parent not visited | requires interaction (click) ; 5: parent page reference was class_budget_limited (70-document spider budget ex |
| 72 | `/test/javascript/interactive/js-post.found` | javascript | · | · | · | yes | api:call:fetch | click/POST | reached | 10 accounting | 4: fetch() literal was extracted but classified kind=api (observed_only_api), so never fetched by the spider ; |
| 73 | `/test/javascript/interactive/js-put.found` | javascript | · | · | · | yes | api:call:fetch | click/PUT | reached | 10 accounting | 4: fetch() literal was extracted but classified kind=api (observed_only_api), so never fetched by the spider ; |
| 74 | `/test/javascript/interactive/listener-and-event-attribute-first.found` | javascript | · | · | · | yes | api:call:fetch | click/POST | reached | 10 accounting | 4: fetch() literal was extracted but classified kind=api (observed_only_api), so never fetched by the spider ; |
| 75 | `/test/javascript/interactive/listener-and-event-attribute-second.found` | javascript | · | · | · | yes | api:call:fetch | click/POST | reached | 10 accounting | 4: fetch() literal was extracted but classified kind=api (observed_only_api), so never fetched by the spider ; |
| 76 | `/test/javascript/interactive/multi-step-request-event-attribute.found` | javascript | ✓ | ✓ | ✓ | yes | api:call:fetch | multi_click/GET | reached | reached |  |
| 77 | `/test/javascript/interactive/multi-step-request-event-listener-div-dom.found` | javascript | · | · | · | yes | api:call:fetch | multi_click/GET | reached | 7 follow-up not observed | 4: fetch() literal was extracted but classified kind=api (observed_only_api), so never fetched by the spider |
| 78 | `/test/javascript/interactive/multi-step-request-event-listener-div.found` | javascript | · | · | · | yes | api:call:fetch | multi_click/GET | reached | 7 follow-up not observed | 4: fetch() literal was extracted but classified kind=api (observed_only_api), so never fetched by the spider |
| 79 | `/test/javascript/interactive/multi-step-request-event-listener-dom.found` | javascript | ✓ | ✓ | ✓ | yes | api:call:fetch | multi_click/GET | reached | reached |  |
| 80 | `/test/javascript/interactive/multi-step-request-event-listener.found` | javascript | ✓ | ✓ | ✓ | yes | api:call:fetch | multi_click/GET | reached | reached |  |
| 81 | `/test/javascript/interactive/multi-step-request-redefine-event-attribute.found` | javascript | · | · | · | yes | api:call:fetch | multi_click/GET | reached | 7 follow-up not observed | 4: fetch() literal was extracted but classified kind=api (observed_only_api), so never fetched by the spider |
| 82 | `/test/javascript/interactive/multi-step-request-remove-button.found` | javascript | · | · | · | yes | api:call:fetch | multi_click/GET | known, unvisited | 2 parent not visited | requires interaction (multi_click) ; 5: parent page reference was class_budget_limited (70-document spider bud |
| 83 | `/test/javascript/interactive/multi-step-request-remove-event-listener.found` | javascript | · | · | · | yes | api:call:fetch | multi_click/GET | known, unvisited | 2 parent not visited | requires interaction (multi_click) ; 5: parent page reference was class_budget_limited (70-document spider bud |
| 84 | `/test/javascript/interactive/two-listeners-first.found` | javascript | · | · | · | yes | api:call:fetch | click/POST | reached | 10 accounting | 4: fetch() literal was extracted but classified kind=api (observed_only_api), so never fetched by the spider ; |
| 85 | `/test/javascript/interactive/two-listeners-second.found` | javascript | · | · | · | yes | api:call:fetch | click/POST | reached | 10 accounting | 4: fetch() literal was extracted but classified kind=api (observed_only_api), so never fetched by the spider ; |
| 86 | `/test/javascript/misc/automatic-post.found` | javascript | · | · | · | yes | api:call:fetch | timer/POST | reached | 6 not executed | 4: fetch() literal was extracted but classified kind=api (observed_only_api), so never fetched by the spider ; |
| 87 | `/test/javascript/misc/comment.found` | javascript | · | · | · | yes | NOT extracted | none/GET | reached | 3 not extracted |  |
| 88 | `/test/javascript/misc/string-concat-variable.found` | javascript | · | · | · | yes | NOT extracted | none/GET | reached | 3 not extracted |  |
| 89 | `/test/javascript/misc/string-variable.found` | javascript | · | · | · | yes | NOT extracted | none/GET | reached | 3 not extracted |  |
| 90 | `/test/misc/known-files/robots.txt.found` | misc | · | · | · | yes | NOT extracted | none/GET | not discovered | 2 parent not visited | 3: static extractor would not recognize the mechanism even if the page were fetched |
| 91 | `/test/misc/known-files/sitemap.xml.found` | misc | · | · | · | yes | navigation:loc | none/GET | not discovered | 2 parent not visited |  |
