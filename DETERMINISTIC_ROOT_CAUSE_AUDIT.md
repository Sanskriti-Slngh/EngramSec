# Deterministic root-cause audit: response handling, frontier state, depth and extraction

**Scope.** This is an implementation-level investigation of Agent 1's deterministic discovery pipeline, starting from `21a0e2d`:
- reproduce each suspected defect with a synthetic fixture before changing code;
- explain why it happens;
- repair it with an established technique;
- measure the repair under the frozen matched budget.

No model calls, no LLM planning, and no use of benchmark answers by Agent 1. The Crawl Maze audit files were used offline only.

**Result.** Eleven implementation bugs (B1–B10b) were reproduced and repaired; two of them (B10, B10b) I introduced during this milestone and caught with tests. Three standards gaps were closed.

Under identical matched budgets (180 s, 300 browser actions, 1,000 shared HTTP requests, typed-resource total 100, class caps 70/20/10/20), the corrected combined candidate **E2 reaches 58/91 strict-2xx Crawl Maze paths** (supported-deployment 58/84). The frozen combined baseline scored 36 in this session (37 and 37 previously).
- It gains 22 markers and loses none.
- Browser behavior is unchanged: 103 transitions, 23/23 replays, 0 missing Graph A evidence, 0 false merges.
- It uses 678 of 1,000 HTTP requests.
- The JS-heavy lab and the shop fixture show no regressions.

E2's remaining 33 misses contain **no budget, depth or class-cap failures**. Every one is a testbed limitation, a scoring rule, a deliberate safety policy, a standards-correct non-match, or a runtime-interaction gap that the CDP probe confirms.

All repairs are opt-in; defaults reproduce the frozen behavior:
- `--response-body-reader bounded_stream`
- `--resource-frontier-model persistent`
- `--passive-document-max-depth`
- `--budget-aware-deepening`
- `--html-extraction standards`

The most important gain mechanism is **budget-aware use of idle capacity** (Phase 3, alternative D), not a raw depth increase.

## 1. Classification of findings

### 1.1 Confirmed implementation bugs (reproduced, repaired, tested)

| # | Bug | Minimal reproduction (test) | Repair |
|---|---|---|---|
| B1 | **Valid bodies without `Content-Length` are silently dropped.** Chunked, close-delimited and gzip+chunked 200 responses are recorded as "fetched" with 0 references, in both the spider and the browser recorder. | `test_legacy_reader_skips_valid_bodies_without_content_length`; localhost variants: 0 references vs 2 with `Content-Length` | Streaming reader `agent1/bounded_http.py` (`--response-body-reader bounded_stream`); browser path uses the transfer size before copying; an explicit `body_status` on every response |
| B2 | **The "memory bound" is not a bound.** Playwright's `APIResponse` buffers the entire body (3–3.9 MB in the reproduction) before the size check runs. | `test_oversized_bodies_are_read_only_to_the_bound` (wire bytes ≤ bound + 64 KiB) | Stream with `http.client`; stop at the bound and close the connection; bounded `zlib` decompression (`test_compressed_bodies_are_decoded_within_the_bound`, 50 MB gzip bomb) |
| B3 | **Invalid framing is not handled per RFC 9112 §6.3.** Playwright aborts with a parse error; `http.client` silently reads to close. | `test_empty_and_invalid_framing_are_explicit` | Discard and label `invalid_framing` |
| B4 | **An observed-only sighting blocks later explicit evidence.** Every reference, including POST `fetch()` targets, form actions and out-of-scope URLs, enters one `discovered_urls` set, so a later `<a href>` to the same URL is a "duplicate" and is never fetched. | `test_observed_only_reference_does_not_block_a_later_explicit_get_link` (reproduced on the old code: 0 requests) | Persistent frontier with an explicit per-URL state machine (`--resource-frontier-model persistent`) |
| B5 | **A speculative sighting blocks or slows explicit evidence.** With cap 0 the explicit link is never fetched; with cap > 0 it is fetched only through the 2-per-batch speculative lane. | `test_speculative_sighting_does_not_block_or_slow_a_later_explicit_reference` (old: 0 requests / speculative channel) | `promoted_explicit` transition |
| B6 | **No kind upgrade.** A URL first seen as `<img>` stays asset-class after an `<a href>` reference and is dropped by the asset cap even when documents have budget. | `test_kind_upgrade_from_asset_to_document_is_not_lost_to_the_asset_cap` | `upgraded_kind` / `readmitted_class` transitions |
| B7 | **Checkpoint resume loses work.** Query-bearing admitted references are filtered out, the speculative lane is dropped, and redirect hops are restored one level too deep (then depth-limited). | `test_checkpoint_resume_preserves_query_speculative_and_redirect_depth`, `test_redirect_hop_depth_is_restored_without_off_by_one` | Lossless persistent restore (own-depth vs child-depth records) |
| B8 | **Shorter routes do not propagate through fetched pages.** If page A is fetched first via a long chain, A's children are depth-capped. When A is later reached in one hop from a browser page, nothing is re-evaluated. In the frozen D run, 7 of the 17 never-fetched depth-capped URLs were 2 hops from an observed page. | `test_shorter_depth_propagates_through_already_fetched_pages` | BFS edge relaxation over recorded parent→child edges (`readmitted_propagated`) |
| B9 | **Method evidence is overwritten.** The AST extractor keyed methods by (literal, sink), so a second `fetch` of the same URL overwrote the first one's method, and `_dedupe` then collapsed them. | `test_references_with_different_methods_are_kept_distinct` | Per-occurrence method queue; method in the dedupe key |
| B10 | **(Introduced and caught in this milestone.)** Relaxation re-admitted speculative candidates into the typed queue, where they lost to the asset cap. Arm P lost two script-literal markers this way. | `test_relaxed_speculative_candidates_stay_in_their_own_lane` (verified to fail with the bug reinstated) | Lane-aware re-queue |
| B10b | **(Introduced and caught in this milestone.)** The speculative lane checked `depth > max_depth` at pop time, ignoring budget-aware deepening, and dropped instead of deferring. Arm PB recorded 57 speculative `depth_limited` discards, including the script-comment and conditional-comment markers. | `test_speculative_lane_honors_budget_deepening_and_defers_instead_of_dropping` (failed before the fix) | Lane uses the per-candidate depth limit, honors deepening, defers to the depth pool |

### 1.2 Standards-correctness gaps (repaired; `--html-extraction standards`)

| Gap | Standard | Test |
|---|---|---|
| `Content-Location` not extracted | RFC 9110 §8.7 | `test_content_location_header_is_an_explicit_reference` |
| Hyperlinks before `<base>` resolved against the document URL | HTML: hyperlinks are parsed against the document base URL when used; fetched-on-insertion subresources keep the base at that time | `test_hyperlinks_before_base_resolve_against_the_document_base` |
| Missing `Content-Type` never sniffed | WHATWG MIME Sniffing (unknown type only; an explicit `text/plain` is honored) | `test_missing_content_type_html_is_sniffed_only_when_unknown` |

Kept as-is after review: query-bearing URLs are deduplicated by parameter *names* (values redacted). That is an intentional bound on parameter spaces, not a bug. The resume path that dropped query URLs was a bug (B7).

### 1.3 Inefficient but correct design choices

- **Fixed per-class caps are zero-sum.** Once document coverage improved, the 20-request asset cap decided *which* markers were fetched, not how many. Arm P fetched 9 more parent pages and lost 6 markers to the cap while using 27 of the 100-request typed budget. The budget-aware frontier (reclaim class-deferred work only when nothing better is pending, within the typed total and HTTP) addresses this without removing fairness during competition.
- **The FIFO order of assets** decides which candidates win under a cap. It was not changed.
- **Depth-by-hop counts redirect and index levels.** It was corrected for redirects in the previous milestone; separately bounded passive document depth (arm PC) is the general alternative to a blanket depth increase.

### 1.4 Intentional safety limitations (unchanged)

- The dangerous-path filter on passive fetches (3 Crawl Maze test pages whose paths contain "delete"/"remove").
- Observed-only request surfaces: no GET substitution for POST/PUT/DELETE, form actions, pings or CSP report endpoints.
- Same-origin route enforcement (blocks third-party CDN code).
- Passive fetches never write cookies into the browser session. This is a deliberate semantic change of the bounded reader; the old Playwright request context did store `Set-Cookie`.
  **Revised in the next milestone** (`DETERMINISTIC_TRANSFER_VALIDATION.md`, defect T1): dropping `Set-Cookie` desynchronizes the browser from a server that renews session identifiers. The bounded reader now applies `Set-Cookie` to the browser context under RFC 6265, as the legacy reader did.
- Speculative candidates are capped and labelled.

### 1.5 Testbed and evaluator limitations

- 6 framework cases are unsupported on plain Flask.
- Non-GET marker requests get 405 under the strict 2xx scorer.
- AngularJS needs a CDN plus hashbang interpretation.
- All Crawl Maze responses carry `Content-Length`, so B1–B3 cannot change its score even though they are real bugs.

### 1.6 Falsified or narrowed hypotheses

- **"The 14 depth misses need a higher depth."** False as stated. Of 17 never-fetched depth-capped URLs in frozen D: 7 were 2 hops from an observed page (bug B8), 2 were re-admitted but still queued at the end, and only 8 were genuinely 4 hops away.
- **"Most depth-capped references are lost."** False. 60 of 77 depth-capped *records* were later fetched or loaded by another route; record counts overstated losses.
- **"Missing response-body extraction contributes to Crawl Maze misses."** False for this testbed: Flask always sends `Content-Length` (verified: 0 `skipped_unknown_length` in the matched runs). B1 is a general bug only.
- **"Exploration is deterministic."** Narrowed. The frozen configuration scored 37, 37 earlier and 36 now (one fewer browser transition skipped a listing page). Single markers move run to run, and the legacy frontier's coverage depends on which listing pages the browser happens to visit.

## 2. Runtime interaction probe

`experiments/probe_runtime_interaction.py` (6 synthetic pages; first advertised click, then compare):

| Case | Existing snapshot | CDP `DOMDebugger.getEventListeners` |
|---|---|---|
| Click creates a `<button>` | ✓ | ✓ |
| Click creates a `<div>` with a click listener | ✗ | ✓ new listener on the `div` |
| Click redefines the same button's `onclick` | ✗ (state signature unchanged) | ✓ handler location changed |
| Delegation through `document` | ✗ | ✗ only the ancestor listener; targets not attributable |
| Listener added then removed | — | — (correctly nothing) |
| Control added after 1.2 s | ✓ | ✓ |

**Decision.** Do not integrate a listener framework in this milestone. CDP metadata adds exactly two capabilities the snapshot lacks: listener-bearing non-semantic elements created by an executed action, and handler replacement on an existing control. Delegation needs heuristics neither approach provides. A narrow next step is justified: after each executed action, query click listeners on a bounded node set (≤ 300). Expose only *new or changed* listeners as candidate controls, with provenance `observed_listener`, through the existing safety filters. On Crawl Maze this addresses 3 GET cases (two `<div>` variants and one redefinition).

## 3. Matched evaluation

All arms: Crawl Maze `2a0dd0a`; 180 s, 300 browser actions, 120 transitions, 1 worker; 1,000 shared HTTP (passive share 500, reserve 500); typed total 100; class caps document 70 / script 20 / stylesheet 10 / asset 20; `max_resource_depth` 3; shared-HTTP allocation, 25 speculative fetches; multidimensional policy; no models. Browser evaluation used about 19 of the 20 minutes. One run per arm; the frozen configuration has varied by ±1 across sessions (§1.6).

| Arm | Change over frozen D0 | Raw 2xx /91 | Supported /84 | Any-status /91 | HTML /57 | JS /27 | Headers /4 | Parents fetched (80) | HTTP (passive / typed / spec) | Depth-limited · class-limited · admitted-never-attempted |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| D0 | frozen combined baseline | 36 | 36 | 42 | 26 | 6 | 3 | 57 | 616 (175/27/6) | 0 · 10 · 18 |
| P | persistent frontier (B4–B8; before the lane fix) | 35 | 35 | 41 | 27 | 4 | 3 | 66 | 633 (198/27/3) | 0 · 16 · 28 |
| PC | P + passive document depth 6 | 37 | 37 | 43 | 29 | 4 | 3 | 74 | 648 (216/27/1) | 0 · 22 · 19 |
| PB | P + budget-aware frontier (lane fix in relaxation; speculative-lane bug B10b still present) | 52 | 52 | 58 | 44 | 4 | 3 | 74 | 669 (216/44/1) | 57 · 17 · 0 |
| E | PB + passive depth 6 + standards extraction + bounded reader (B10b present) | 53 | 53 | 59 | 44 | 4 | **4** | 74 | 670 (216/45/1) | 9 · 18 · 0 |
| **E2** | **E with all fixes** | **58** | **58** | **64** | **47** | **6** | **4** | 74 | **678** (218/45/10) | **0 · 18 · 0** |

Every arm had 102–104 transitions, 23–24/24 replays, 88–90 distinct UI states, 88–90 safe controls executed (23–24 unexecuted), 0 missing Graph A evidence, and 0 false merges. The Graph A evidence audit was clean in all arms:
- 0 spider attempts without a channel;
- 0 passive documents as UI transitions;
- 0 spider GETs for non-GET surfaces;
- 0 observed-only records with a spider attempt.

Body status: Crawl Maze always sends `Content-Length`, so every arm had 0 skipped bodies (E2: spider 272 complete / 1 empty; browser 289 / 2). References per parsed response: 1.8–1.95. Successful spider paths: D0 140 → E2 183.

**Reading the arms.**
- *P alone looked like a regression.* It fetched 9 more parent pages, but the fixed 20-request asset cap is zero-sum: P fetched a different 20 assets (+4 / −6 markers). It also exposed bug B10 (speculative re-admission into the typed lane). Taken alone, P supports the frontier repair at the *discovery* stage (parents 57 → 66), not at the score.
- *PC* (separately bounded passive depth) raised parents fetched to 74 without touching typed or browser budgets. Score +1, still asset-cap-bound.
- *PB* (budget-aware frontier) is where coverage moves (+16 over D0). It reclaims class-deferred work only once nothing better is pending, within the typed total (44/100 used) and the HTTP budget. It also deepens depth-deferred work up to depth 8, shallowest first. The 57 depth-limited records were speculative candidates discarded by bug B10b, found from this run's evidence, reproduced and fixed.
- *E* added the standards extraction (+1 header via `Content-Location`) and the bounded reader (no score effect on Crawl Maze, as expected).
- *E2* (all fixes) recovered the speculative script/comment markers: JS 4 → 6, total 58.

**What produced E2's 22 gains over D0 (offline attribution):**
- 9 asset-class deferrals reclaimed with idle budget;
- 8 parent pages reached through the frontier and depth repairs (relaxation, separately bounded passive depth);
- 3 markers class-capped in D0 but fetched in E2;
- 1 `Content-Location` header;
- 1 budget-aware deepening.

**Cost.** E2 uses 62 more HTTP requests than D0 (678 vs 616): +43 passive documents, +18 typed resources, +4 speculative. Browser requests and actions are equal. Marker yield is 8.6 per 100 requests (D0: 5.8).

**Regressions (60 s, E2 configuration):**
- **JS-heavy lab:** 9 areas, 12 controls, 8 request structures, 10/10 replays, 0 missing evidence (same as the baseline).
- **Shop:** 8/8 areas, 11/11 controls, 8/8 request structures, 2/2 contexts, distinct records, 16/16 replays, 0 missing evidence. Prerequisite-path coverage was 0.75; earlier baseline runs measured 0.75 and 0.875, so this is within observed variation.

## 4. Remaining-failure funnel

E2's 33 misses, classified with `experiments/audit_crawlmaze_missing.py`:

| Category | Misses | Nature |
|---|---:|---|
| Unbuilt framework cases (Angular ×2, React ×2, Polymer ×2) | 6 | testbed |
| Browser sent the exact non-GET request; testbed answered 405 | 6 | scorer/testbed |
| Observed-only surfaces: form actions (GET, POST, `isindex`), 2 pings, CSP `report-uri` | 6 | intentional safety semantics |
| Parent page refused by the dangerous-path filter ("delete"/"remove") | 3 | intentional safety |
| `/robots.txt`, `/sitemap.xml` never requested (no well-known-file probing) | 2 | design choice (not implemented) |
| URL-like text whose standard resolution differs from the testbed's expectation (`./…`, `../…`, base + `/x.pdf`), and a reference inside a `data:` SVG image | 4 | standards-correct non-match |
| Runtime-created `<div>` listener ×2, redefined `onclick` | 3 | runtime interaction (CDP probe: detectable) |
| 5 s timer; non-GET listener page never browser-visited; AngularJS CDN | 3 | policy / dwell / testbed |
| **Total** | **33** | |

No miss is attributable to depth, class caps, HTTP budget, frontier state or body handling.

## 5. Recommendation

1. **Adopt the repaired deterministic pipeline as the recommended configuration**, while keeping the frozen defaults for comparability:
   ```
   --resource-allocation shared_http --html-extraction standards --response-body-reader bounded_stream
   --resource-frontier-model persistent --passive-document-max-depth 6 --budget-aware-deepening
   ```
   Confirm on a second, independently built multi-page fixture with realistic page sizes and some chunked responses. Crawl Maze cannot measure B1–B3, and its tiny pages flatter idle-budget reclaim. Report whether reclaimed work stays useful when pages are large.
2. **Next milestone: narrow runtime listener observation**, because it is the only remaining *discovery* gap with direct evidence (3 misses plus the probe). After each executed action, read click listeners for ≤ 300 nodes via CDP. Expose only new or changed listeners as `observed_listener` candidate controls through the existing safety filters and action budget, and re-click a control whose handler changed. Do not attempt delegation inference.
3. **Do not loosen the safety boundaries** to raise the benchmark score. That covers the dangerous-path filter, GET substitution for non-GET surfaces, and third-party scripts: 10 of the 33 misses come from these boundaries by design.
4. **Evaluator decision (not a crawler change).** Alongside the strict-2xx score, keep reporting the any-status surface count (E2: 64) for the 6 non-GET cases.
5. **Well-known-file probing** (`/robots.txt` `Disallow`/`Allow`, `/sitemap.xml`) is a standards-based option for a later milestone. Only 2 examples here, so below the evidence bar for now.
6. **Stop tuning depth or caps.** The remaining funnel has no budget-bound misses.
