# Discovery bottleneck fixes: shared-HTTP document allocation and standards-based extraction

**Result.** Both changes improve coverage at the same browser budget, and they are complementary. On Crawl Maze (180 s, 300 browser actions, 1,000 shared HTTP requests):

| Arm | Raw 2xx /91 | vs frozen A |
|---|---:|---:|
| A frozen baseline | 25 | — |
| B allocation only | 30 | +5 / −0 |
| C extraction only | 32 | +7 / −0 |
| D both | **37** | +14 / −2 |

D's 37/91 at 180 s equals the earlier 300 s serious run. Browser exploration is unchanged in every arm: 103 transitions, 23/23 replays, 89 of 113 safe controls executed. The extra coverage comes entirely from passive GETs: +123 HTTP requests, all counted in the shared budget. D was repeated and reproduced exactly (37, same gains and losses). There are no regressions on the JS-heavy lab or the shop fixture.

The first implementation of allocation (B v1) made coverage **worse** (22/91). Two defects explained it, both fixed and covered by tests, and both are reported below as negative findings.

Inputs used offline only: [CRAWLMAZE_64_MISSING_ROOT_CAUSES.md](CRAWLMAZE_64_MISSING_ROOT_CAUSES.md) and its CSV. Nothing in `agent1/` reads evaluator paths or testbed names (checked with `grep`), and every new mechanism is tested on independently constructed fixtures ([tests/test_discovery_extensions.py](tests/test_discovery_extensions.py)).

## What was implemented (all opt-in; defaults reproduce the frozen baseline)

### 1. `--resource-allocation shared_http`: a separate passive-document channel

- **Eligibility.** Only same-origin, explicit (non-speculative), input-free GET references whose resource class is *document* (`navigation`/`asset` kinds) qualify. Sensitive-query, dangerous-path (`DANGEROUS_ACTION`), out-of-scope and every observed-only request surface are refused.
- **Budget.** These documents draw on the shared HTTP ledger (source `passive_document`) instead of the fixed document class cap.
  - The passive channels together may use at most `limit − reserve` requests. `--passive-document-http-reserve` defaults to half the total, so browser, redirect, replay and typed-resource traffic always keep the reserve.
  - An optional hard cap is available: `--max-passive-document-fetches`.
  - Scripts, stylesheets and other assets keep the independent typed-resource total (100) and class caps (20/10/20), which preserves fairness between classes.
- **Redirects.** Each hop is charged and scope-checked. An in-scope `Location` is followed at the *same* depth (it is the same logical document).
- **Minimum-depth re-admission.** A never-fetched reference that is rediscovered on a shorter path (for example, observed directly by the browser) is re-queued at that depth.
- **Separation.** Passive fetches produce resource evidence only, never UI transitions or workflows. Browser exploration and fresh-context replay are untouched.

### 2. `--html-extraction extended`: standards-based extraction

| Mechanism | Treatment |
|---|---|
| Additional URL attributes: `body`/`td`/`th`/`tr[background]`, `img[lowsrc,dynsrc,longdesc]`, `iframe`/`frame[longdesc]`, `object[codebase,archive,classid]`, `html[manifest]`, SVG `script[href, xlink:href]`, `IMPORT[implementation]`, `head[profile]`, `command`/`menuitem[icon]`, `a[xlink:href]`, URL-valued `meta` names (Open Graph/Twitter/msapplication) | Explicit references |
| `<!DOCTYPE … SYSTEM "…">` system identifier; `<base href>` (emitted as well as applied) | Explicit references |
| `iframe[srcdoc]` | Nested document, parent base URL, nesting bound 2 |
| `<!--[if …]> … <![endif]-->` | Nested document labelled `conditional_comment` (speculative channel) |
| Text nodes, ordinary comments, `data-*`, non-URL `meta[content]` | Conservative URL-shaped tokens (absolute, protocol-relative, or path ending in an extension or `/`), labelled `speculative` |
| JS: literals not at a sink, folded constants, comments | `speculative` (`script-literal`, `script-constant`, `script-comment`). Any literal used as a request-sink argument is excluded, so a POST endpoint can never become a GET candidate. |
| JS `fetch`/`Request`/XHR | The HTTP method is recorded; still observed-only |

Speculative candidates are fetched only under `--max-speculative-fetches` (default 0 = record only), at most 2 per batch, from the shared ledger (source `speculative_candidate`), within the same reserve.

### 3. Request semantics (extended mode)

- Typed, observed-only surfaces are never fetched and never method-substituted:
  - `form_action` (method from `form`/`formmethod`; also `isindex`)
  - `ping` (POST)
  - `security_report` (CSP `report-uri`, in `meta` or header; POST)
  - `api` (with method)
- Graph A gains `request_surfaces` and `request_surface_summary`. Each (method, path, parameter-names) surface gets one outcome: `successful_resource`, `sent_non_2xx`, `sent_no_response` or `observed_not_sent`. Each also records `sent_by` (browser action / navigation / restoration / replay / spider channel), `observed_as`, and `in_replay_validated_workflow`. A browser POST answered 405 is a `sent_non_2xx` surface. It is not a fetched resource and not a workflow (tested).
- Effective budgets are written to every run (`metrics.effective_resource_budgets`).

## Matched evaluation

Every arm used the same target, 180 s, 300 browser actions, 120 transitions, 1 worker, 1,000 shared HTTP requests, a typed-resource total of 100 with class caps of 70 document / 20 script / 10 stylesheet / 20 asset, depth 3, multidimensional policy, adaptive readiness and no models. The B and D effective budgets show `document_class_cap: None`, a passive share of 500 and a reserve of 500. C and D add `speculative_fetch_cap: 25`.

| | A | B | C | D (r1 = r2) |
|---|---:|---:|---:|---:|
| **Raw strict-2xx recall /91** (historical definition) | 25 | 30 | 32 | **37** |
| Supported-deployment recall /84 | 25 | 30 | 32 | 37 |
| Request surface sent, any status /91 | 31 | 36 | 38 | 43 |
| Observed or sent /91 | 38 | 43 | 51 | 60 |
| HTML /57 · JS /27 · CSS /1 · headers /4 · misc /2 | 19·3·0·3·0 | 23·3·1·3·0 | 23·6·0·3·0 | 27·6·1·3·0 |
| Parents (80 supported containers): discovered / admitted / fetched-or-loaded / browser-visited | 62/44/48/35 | 76/73/58/35 | 62/40/48/35 | 76/73/58/35 |
| HTTP total | 493 | 609 | 504 | 616 |
| HTTP by source: browser + redirect / passive doc / typed / speculative | 402/0/91/0 | 406/176/27/0 | 403/0/95/6 | 405/178/27/6 |
| Transitions · safe controls executed/unexecuted | 103 · 89/24 | 103 · 89/24 | 103 · 89/24 | 103 · 89/24 |
| Restoration actions · discovery / verification root reloads | 76 · 49/23 | 76 · 49/23 | 76 · 49/23 | 76 · 49/23 |
| Replays validated · untested transitions | 23/23 · 80 | 23/23 · 80 | 23/23 · 80 | 23/23 · 80 |
| Request surfaces: successful / sent non-2xx / observed only | 121/64/38 | 142/74/37 | 128/65/39 | 149/75/42 |
| Graph A missing evidence · false merges | 0 · 0 | 0 · 0 | 0 · 0 | 0 · 0 |

The raw score keeps the historical denominator (91) and the historical 2xx definition. Supported recall and any-status surfaces are separate columns. A reproduces the earlier frozen baseline exactly: 25/91, 103 transitions, 91 typed GETs, 22 class-limited, 23/23 replays.

**Graph A evidence audit** (all arms, from each run's Graph A):
- 0 spider attempts without a channel label
- 0 passive-only documents appearing as UI transitions
- 0 spider GETs for a surface observed only as non-GET
- 0 observed-only records with a spider attempt
- 0 missing connection evidence
- `in_replay_validated_workflow` is set only on requests issued inside validated replays

## Which stages and mechanisms improved

**Allocation (B).**
- Parents discovered rose 62 → 76, admitted 44 → 73, and fetched-or-loaded 48 → 58. Browser-visited is unchanged (35), as intended.
- The 5 gains are all markers on newly fetched parents, extracted by the existing extractor: `<iframe>[src]`, `<img>[src]`, `<param>[value]`, `<track>[src]`, and a stylesheet `url()`.
- Coverage per request fell slightly (5.1 → 4.9 per 100), and per browser action rose 25 → 30 per 300.

**Extraction (C).** 7 gains, none lost:
- 2 via explicit attributes: `object[codebase]`, `IMPORT[implementation]`.
- 5 via the speculative channel: conditional-comment `<link href>`, a URL inside `meta[content]`, a JS comment, a folded JS constant, a non-sink JS literal.
- Only 6 speculative candidates were recorded in the whole run, and 5 of the 6 fetches hit expected paths. That precision reflects a benchmark that deliberately embeds such strings. Expect far lower precision on real applications, which is why the channel is capped, labelled, and off by default.

**Combined (D).** 14 gains:
- B's allocation gains plus C's extraction gains.
- Mechanisms that need *both* changes, because their parents were only reached through the passive channel: `<!DOCTYPE>` system identifier, `html[manifest]`, SVG `script[xlink:href]`, `img[longdesc]`, `<base href>`.
- 2 losses (`<blockquote>[cite]`, `<frame>[src]` markers): in D they were extracted, then `class_budget_limited`. More admitted documents produce more asset candidates competing for the unchanged 20-asset cap.

## Negative findings

1. **Allocation v1 reduced coverage (B 22/91, D 29/91; kept in `discovery_ablation/v1_before_depth_and_reserve_fix/`).** The passive channel fetched 110 documents in the first ~3.5 s, then stopped. Two defects:
   - *Depth by first discovery.* References keep the depth of their first discovery path. The fast channel stamped listing pages deep, so when the browser later observed them directly they were treated as duplicates and never re-queued, leaving 146 references stranded at the depth limit. Fix: minimum-depth re-admission under `shared_http` (48 re-admissions in D).
   - *Reserve counted browser traffic.* The first reserve rule ("stop once total use reaches limit − reserve") let ordinary browser traffic close the passive channel early. Fix: the reserve bounds the passive channels' own share.

   B and D were rerun after both fixes. A and C do not use this code path and were not rerun. Both fixes are opt-in; the frozen baseline is unchanged (tested).
2. **Allocation alone is not "fetch everything".** Even after the fixes, D used only 178 of its 500-request passive share. The binding limits moved elsewhere (next section).
3. **`button[formaction]` is now a form action, not a passive link.** This cost nothing: in every arm the formaction marker is reached because the browser clicks the submit button (an authorized interaction).
4. **No change in interaction coverage.** Every JavaScript gain in C/D is static. The runtime-created-control, timer and non-GET cases are untouched, as expected.

## The true remaining bottleneck (D, 54 misses, classified with the offline audit)

| Remaining cause | Misses |
|---|---:|
| Parent beyond `max_resource_depth = 3` from any browser-observed page (discovered and admitted, never rediscovered shallower) | 14 |
| Marker extracted, then the asset class cap (20) was exhausted (includes D's 2 losses vs A) | 7 |
| Unsupported in this deployment (unbuilt frameworks) | 6 |
| Non-GET request sent by the browser, answered 405 (scoring/testbed) | 6 |
| Observed-only by design: form actions (GET, POST, `isindex`), `ping`, CSP `report-uri` | 5 |
| Parent never discovered (2 pages in one unreached listing; `/robots.txt`, `/sitemap.xml` are never probed) | 5 |
| Parent refused by the passive channel's dangerous-path filter ("delete"/"remove" in the path) | 3 |
| Runtime-created listener on a `<div>`, or redefined handler | 3 |
| Other: AngularJS CDN, 5 s timer, POST listener page not browser-visited, `data:` URI, `Content-Location` header not extracted | 5 |
| **Total** | **54** |

This is a summary of `experiments/audit_crawlmaze_missing.py` run on D_r1.

**Conclusion.** The next limits are two configurable budgets: spider depth relative to browser-observed pages, and the 20-request asset class cap. Behind them sit policy-bounded cases (dangerous paths, observed-only surfaces, non-GET) that should stay bounded. Raising depth or asset caps is budget tuning, not a new mechanism. If pursued, it should be a declared sensitivity sweep at equal total HTTP, not folded into a headline score. The one new general extraction gap found is the `Content-Location` response header. It was not added, to keep the matched runs valid.

## Regression and generalization (60 s; A vs D)

| Fixture | Arm | Areas | Controls | Request structures | Contexts | Records distinct | Replays | Missing evidence |
|---|---|---:|---:|---:|---:|---|---:|---:|
| JS-heavy lab (11/14/12) | A | 9 | 12 | 8 | 0.5 | – | 10/10 | 0 |
| JS-heavy lab | D | 9 | 12 | 8 | 0.5 | – | 10/10 | 0 |
| Shop (8/11/8, 2 contexts, 2 records) | A | 8 | 11 | 8 | 1.0 | yes | 16/16 | 0 |
| Shop | D | 8 | 11 | 8 | 1.0 | yes | 16/16 | 0 |

There are no regressions. Session identity, record identity, functional interactions and replay are preserved. On these small apps D adds 8 passive document fetches and no speculative fetches. JS-lab prerequisite-path coverage was 0.45 (A) vs 0.64 (D) in single runs. I don't claim this as an effect.

Independent fixtures (synthetic names and structure, none from Crawl Maze) cover:
- every new attribute;
- `base` resolution, `srcdoc` nesting and its bound, conditional comments;
- typed request surfaces with methods, conservative text tokens (rejecting prose such as "and/or" and "1/2"), and JS non-sink literals/constants/comments with sink exclusion;
- class-cap lifting, the reserve share, redirect same-depth, the dangerous-path and sensitive-query filters, the speculative cap, minimum-depth re-admission (and its absence in the frozen baseline), checkpoint channel counters, and config validation;
- the Graph A 405 semantics;
- a live browser integration on a small local site (more documents reached, no new UI transitions, POST 405 recorded as `sent_non_2xx` from a browser action, never as a GET).

Full suite: 92 passed.

## Cost and reproduction

Browser evaluation: about 24 minutes. That covers 1 smoke run, 4 matched arms, 2 re-runs after the fixes, 1 repeat of D, and 4 fixture regressions. $0; no models, no external scanning.

```sh
experiments/run_discovery_ablation.sh agent1/experiments/discovery_ablation 180 A_r1 B_r1 C_r1 D_r1
cd experiments && ../.venv/bin/python summarize_discovery_ablation.py \
  --root ../agent1/experiments/discovery_ablation --out ../agent1/experiments/discovery_ablation/discovery_summary.json
```

The summarizer and the audit are offline evaluators. They read the testbed's public expected-results file after runs finish, and are never imported by Agent 1.
