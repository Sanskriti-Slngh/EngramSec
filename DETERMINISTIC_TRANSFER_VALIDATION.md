# Deterministic transfer validation: the repaired HTTP pipeline on an independent application

**Scope.** Phase 1 of the transfer/runtime milestone, starting from `b4a9a40`. I reviewed the bounded reader (`agent1/bounded_http.py`), the persistent frontier and the shared budget for:
- chunked and compressed responses;
- redirect chains and scope changes;
- decompression bounds and malformed framing;
- cookies and the authorized session;
- query parameters and request methods;
- checkpoint/resume;
- multiple discovery sources.

I then compared the old combined configuration (D0) with E2 on an independent localhost application. It was built for this purpose without reference to Crawl Maze paths. No model calls, no external targets.

**Result.** The review and the transfer run found **nine more defects (T1–T9)**. Each was reproduced first, then repaired and tested:
- the bounded reader dropped `Set-Cookie`, which broke the browser's authorized session on a server that renews session identifiers (T1);
- four framing and coding gaps (T2–T5);
- a redirect trap that consumed the whole HTTP budget (T6);
- replay starvation under a shared HTTP budget (T7, T7b);
- an audit rule that flagged correct evidence (T8);
- speculative GETs of computed request-target prefixes (T9).

On the independent application, E2 transfers: more references, documents reached passively, malformed responses labelled instead of misread, no off-scope or trap blow-up. But two properties that Crawl Maze could not exercise turned out to matter more than coverage: **session-cookie synchronization** and **an HTTP reserve for verification**.

## 1. Defects found in the transfer review

| # | Defect | Reproduction | Repair | Test |
|---|---|---|---|---|
| T1 | **Bounded reader dropped `Set-Cookie`.** It sent the browser context's cookies, but the response's `Set-Cookie` was discarded. When the server renewed the session identifier on a passive request, the browser kept an invalidated identifier. The legacy Playwright reader shared the browser's cookie jar, so this was a regression introduced at `b4a9a40`. | Localhost renewal server: browser `/whoami` → `expired` after one passive fetch. Fixture, E2 with old semantics (90 s): 20 invalid identifiers presented, 30 sessions issued vs 11 with sync | `agent1/cookies.py`: the reader returns all `Set-Cookie` headers; the spider applies them to the browser context per RFC 6265 §5.2–5.3 (domain-match, default-path, Secure-from-insecure, `__Host-`/`__Secure-` prefixes, `SameSite=None` requires Secure, Max-Age/Expires deletion). Evidence records cookie **names** sent and set, never values. `--no-passive-cookie-sync` reproduces the old behavior for ablation | `test_passive_fetch_keeps_the_browser_session_in_sync_after_server_rotation`, `test_set_cookie_parser_follows_rfc6265_scope_rules` |
| T2 | **Truncated compressed stream reported `complete`.** A gzip body whose trailer is missing was parsed and labelled complete. | Old reader: `complete` | `incomplete` unless the decompressor reached end of stream | `test_truncated_gzip_stream_is_incomplete_not_complete` |
| T3 | **Raw DEFLATE not decoded.** `Content-Encoding: deflate` without a zlib header, which browsers accept, was `unsupported_encoding`. | Old reader: 0 bytes | Fall back to raw DEFLATE on the first chunk | `test_raw_deflate_content_coding_is_decoded` |
| T4 | **A transfer coding other than a lone `chunked` was read as a body.** `http.client` decodes only `chunked`; on a persistent connection the old reader hung until the 5 s socket timeout and the fetch failed. | Old reader: `TimeoutError` after 5.0 s | `unsupported_transfer_coding`, no body parsed | `test_unsupported_transfer_coding_is_not_parsed_as_a_body` |
| T5 | **No wall-clock bound.** The 5 s timeout applied per socket read, and `read(64 KiB)` blocks until a full chunk arrives. A server trickling 64 bytes every 0.3 s held one passive fetch for **30.6 s**. | Old reader: 30.6 s | `read1` (returns available bytes) plus a total deadline (5 s for the spider); label `timeout`, partial body kept and labelled | `test_slow_trickle_is_bounded_by_a_total_deadline` |
| T6 | **Redirect chains were unbounded.** A followed hop also re-entered as an extracted `Location` "link" one level deeper (standards extraction), bypassing the hop's checks. An infinite `/r/n → /r/n+1` chain consumed **all 400 of 400** HTTP requests in the reproduction. | Old code: 400 fetches | At most 20 hops, as in Fetch/Chromium (`rejected_redirect_limit`). The `Location` of a followed 3xx is handled only by the hop logic | `test_redirect_chains_are_bounded_like_a_user_agent` |
| T7 | **Replay starvation under a shared HTTP budget.** The passive reserve protected the browser from the spider, but nothing protected *verification* from exploration. On the fixture every arm spent all 1,000 requests during exploration, and **68–69 of 77–78 replays failed at the start URL** (`ERR_BLOCKED_BY_CLIENT`). Crawl Maze never showed this because its pages have almost no subresources. | Fixture v1 (90 s): D0 10/78, E2 6/77 replays | `--http-verification-reserve F`: discovery (browser exploration and every passive source) stops at limit × (1 − F); only browser replay spends the reserve (`browser_verification` ledger entries). Default 0 keeps the old behavior; this milestone uses 0.3, matching the existing 30% time/action replay reserve | `test_http_verification_reserve_is_spent_only_by_browser_replay` |
| T7b | **Exploration crashed at the HTTP cap**, and replays that could not be sent were recorded as failures. The exploration loop checked time and actions but not HTTP, so the persistent root reload raised. The replay loop kept starting replays after the reserve was spent. | Fixture v2: both arms exited with an error after about 40 s | Exploration stops cleanly with a note. Replay stops when verification HTTP is spent, and a replay blocked mid-path is `not_tested`, not `failed` (`replays_untested_http_budget`) | `test_exploration_stops_cleanly_at_the_http_discovery_cap_and_replay_uses_the_reserve` |
| T8 | **Graph A audit rule.** An `unresolved_candidate` (a computed `fetch` target) has no URL by definition, yet the audit required one and reported missing evidence. | Fixture smoke run: 1 missing claim | Its evidence is the expression fingerprint | covered by every fixture run (0 missing) |
| T9 | **Speculative GET of a computed request-target prefix.** `fetch('/api/shelf/' + id)`: the literal `'/api/shelf/'` was not a *direct* sink argument, so the speculative lane issued a GET to it. For a non-GET `fetch` this is a GET to part of the request target. | Fixture: 1 passive GET each to `/api/shelf/`, `/api/hidden/` in every arm | Literals nested anywhere inside a request-sink URL argument (`fetch`, `Request`, `new Request`, XHR `open`) are never speculative candidates | `test_literal_prefix_of_a_computed_request_target_is_not_a_speculative_get` |

Reviewed and found correct, or unchanged by design:
- **Chunked, gzip+chunked and `Content-Length` bodies, and the 50 MB gzip bomb** are read within the bound (previous milestone's tests still pass).
- **Invalid `Content-Length`** is discarded (`invalid_framing`), and so are a body that ends early (`incomplete`) and an oversized body (`truncated` at 1 MB).
- **Scope:** an out-of-scope redirect target is never followed. The off-scope sentinel received 0 requests in every run.
- **Redirect loops** stop at the first repeated URL.
- **Query values** are deduplicated by parameter name, values redacted, as intended. Sensitive keys are rejected.
- **Methods:** non-GET sinks are observed-only. The method is kept per occurrence (B9 fix).
- **Checkpoint/resume** is lossless for queue, lane and hop depth (previous tests). One known gap: the redirect-hop *counter* is not restored, so a chain resumed mid-way gets up to 20 more hops.
- **Multiple discovery sources** — browser responses, passive documents, typed resources, speculative candidates and ZAP seeds — keep separate ledger entries and `channel` labels. 0 spider attempts lacked a channel.

**Session isolation.** The spider is shared across the browser contexts of one run (exploration, restores, replays). Every passive fetch now uses the cookies of the context that drains it and records which cookie *names* it carried. The frontier itself is still URL-keyed, not context-keyed: a URL first fetched in one context is not re-fetched in another. This matters only for multi-context runs (`context_label` is single-valued today). It is recorded as a limitation, not changed.

## 2. Independent application

`development_apps/transfer_library.py` (Larkspur Library) contains:
- 107 content documents and 64 static resources:
  - five ~126 KB catalog pages sent chunked (gzip when accepted);
  - 60 ~24 KB item pages with CSS, a deferred script with a `fetch`, an SVG cover, and a POST "Add to reading list";
  - chunked author pages.
- Duplicate URLs: `?ref=`, `#reviews`, trailing-slash 301s, a `&sort=` variant.
- Two-hop redirect chains, an off-scope redirect to a sentinel origin, and an infinite redirect trap.
- A 3.5 MB chunked annual report (one link at the start and one past 1 MB), an invalid `Content-Length`, a truncated gzip feed, and a 30 s trickle.
- A cookie session renewed every 25th request; the old identifier is valid for a 2 s grace, as in common implementations. Session-scoped state is a reading list.
- A "reading room" of runtime-only interactions, used in `RUNTIME_INTERACTION_ABLATION.md`.

The server logs every request with client kind, by User-Agent: the bounded reader identifies itself, while the legacy Playwright reader looks like the browser. Evaluator truth: `experiments/evaluate_transfer_library.py`.

## 3. Old combined configuration (D0) vs E2

Matched: 1 worker, 300 actions, 120 transitions, 1,000 HTTP, typed total 100, caps 70/20/10/20, shared-HTTP allocation, 25 speculative fetches, multidimensional policy, start `/`. Final runs are 60 s with a 30% HTTP verification reserve. The v1 runs (90 s, no reserve) are kept for the session comparison, which the reserve does not affect.

| Metric | D0 (frozen combined) | E2 |
|---|---:|---:|
| References discovered (distinct) | 263 | **291** |
| Content documents reached, 2xx (of 107) | 96 | **98** |
| …by the passive reader | 0 (legacy reader skips chunked bodies) | 98 |
| Static resources fetched (of 64) | 63 | 64 |
| Passive bodies: complete / skipped for unknown length | 100 / 20 | 187 / 0 |
| Browser bodies copied / skipped for unknown length | 397 / 116 | 469 / 0 |
| Malformed responses labelled (`incomplete`, `invalid_framing`, `timeout`, `truncated`) | 0 (2 errors) | 1 / 1 / 1 / 1 |
| Links beyond a response bound or in malformed bodies found | 0 of 4 | 2 of 4 (truncated-gzip prefix; trickle prefix) |
| HTTP requests (server-side) / bytes | 1,000 / 7.56 MB | 1,000 / 6.30 MB |
| …passive wire bytes (agent ledger) | — (the legacy reader buffered the whole 3.5 MB report) | 3.17 MB |
| Redirect-trap requests / off-scope sentinel hits | 21 / 0 | 21 / 0 |
| Browser actions / transitions / grouped states | 117 / 66 / 60 | 108 / 57 / 52 |
| Designed functionality executed (of the 9 reading-room behaviors) | 2 | 2 |
| Replays validated | 9/9 | 9/9 validated, then 16 blocked by the spent reserve (T7b; repaired after this run) |
| Graph A connections missing evidence | 0 / 2,906 | 16 / 3,509 (exactly the 16 budget-blocked replays) |
| Incorrect state merges | 0 | 0 |
| Wall time / Python peak RSS | 62.6 s / 76.8 MB | 60.0 s / 79.2 MB |

**Authorized session context (v1, 90 s, no reserve; passive and browser traffic otherwise identical):**

| Arm | Passive `Set-Cookie` | Invalid session identifiers presented | Sessions issued |
|---|---|---:|---:|
| D0 (legacy reader, shared jar) | applied by Playwright | 1 (browser) | 17 |
| E2 with `b4a9a40` semantics | **20 dropped** | **20** (17 passive, 3 browser) | **30** |
| E2 (T1 repaired) | 7 applied | 0 | 11 |

**Reading.**
- **E2 transfers to a realistic application on the discovery side.** The bounded reader is the only way passive discovery sees chunked or compressed documents. D0's passive reader parsed none of the five catalog pages, and the browser skipped 116 bodies without `Content-Length`. E2 reaches the same document set with fewer browser actions.
- **The memory bound holds and costs nothing:**
  - Python peak RSS is 77–79 MB in both arms;
  - the 3.5 MB report is read to 1 MB;
  - the trickle is cut at 5 s;
  - malformed responses are labelled, not misread.
- **E2 is not free.** The passive channel spends its 50% share. With realistic per-page subresources, *browser* exploration was the scarce resource: both arms stopped exploration on the HTTP discovery cap, not on time or actions.
- **The decisive transfer findings are T1 and T7, not a coverage number.** Crawl Maze has no cookies and no subresource-heavy pages, so neither was measurable there. Without T1, E2 silently broke the session it was meant to observe. Without T7, almost no workflow was independently verified.

**Interaction coverage** (2 of 9 designed behaviors from `/` in 60 s) is limited by the exploration policy, not the pipeline. The multidimensional scheduler favors the 60 novel item links over the header-navigation "Reading room" link (navigation is penalized as global chrome). The runtime ablation therefore starts at `/desk`.

## 4. Files

- `agent1/bounded_http.py`: T2–T5, Set-Cookie return.
- `agent1/cookies.py`: T1, new.
- `agent1/resource_spider.py`: T1 evidence, T6, T9.
- `agent1/explorer.py`: T7/T7b, T8, cookie bridge.
- `development_apps/transfer_library.py`, `experiments/evaluate_transfer_library.py`, `experiments/run_runtime_ablation.sh`.
- `tests/test_transfer_hardening.py`.
- Results:
  - `agent1/experiments/transfer_validation/` (final);
  - `transfer_validation_v1_no_replay_reserve/` (T7 evidence and the session comparison);
  - `transfer_validation_v2_discovery_cap_crash/` (T7b evidence).
