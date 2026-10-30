# Hierarchical exploration, external discovery and state reuse: implementation report

This milestone was taken over mid-implementation from a previous agent whose run ended while it was editing HTTP redirect accounting. This report covers the recovered state, the fixes, the finished architecture, and why it is not adopted as the default. Measured results are in [ARCHITECTURE_COMPARISON.md](ARCHITECTURE_COMPARISON.md).

## 1. Recovery

Starting point: commit `5710c01` plus uncommitted work in `agent1/{cli,explorer,exporter,resource_spider,schema}.py`, the ablation runner and tests, the new `agent1/hierarchical.py`, `agent1/zap_adapter.py` and `tests/test_hierarchical_zap.py`, and four interrupted experiment folders. All were preserved. No experiment process was running. An idle Codex CLI session was left untouched. The Crawl Maze server on `127.0.0.1:3460` was reused.

### Redirect-budget failure: root cause and fix

`test_http_budget_counts_redirect_requests` failed with `used == 1` for a two-request redirect. A probe (Playwright 1.64.1) showed that a context route handler is called **only for the first request of a redirect chain**. Every later hop is followed by the browser outside the router, whether the handler continues or fulfills. Consequences of the interrupted code:

1. Redirect hops were never charged (≈ 95 per 180 s Crawl Maze run, about 19% of browser traffic).
2. Only the first hop's `Location` was scope-checked. A second hop could leave scope unseen.
3. Charging hops inside the handler (prepaying) would over-count whenever the browser does not follow.

Fix (`HttpBudget` and `BrowserSession.__enter__` in `agent1/explorer.py`):

- The first request is charged pre-flight and refused once the budget is exhausted (as before).
- For a 3xx with `Location`, the handler refuses the response **before** the browser can follow it if the target is out of scope or no budget remains. The hop itself is not charged there.
- Every hop is charged exactly once from the context `request` event (`redirected_from is not None`). Hops that could not be refused are counted as `http_redirect_budget_overrun` when over the limit, and unroutable out-of-scope hops as `http_redirect_scope_violations` (both 0 in all runs).
- The ledger keeps per-source totals (`browser`, `browser_redirect`, `resource_spider`, `zap_traditional_spider`), exported to `metrics.http_budget_by_source` and restored on checkpoint resume.
- ZAP's cost is charged through `charge_external` and refused if it exceeds the remaining budget. The typed spider charges `resource_spider`. Its GETs use `max_redirects=0`, so one fetch is one request.

The original test passes unchanged. A new test covers a two-hop chain (exactly 3 charges: 1 routed + 2 unrouted, no double count), refusal of a redirect when one request remains, and per-source totals.

## 2. Component audit

| Component | At handoff | Now |
|---|---|---|
| A. ZAP Traditional Spider evidence adapter (`zap_adapter.py`) | Implemented and working: explicit origin mapping, rejects traversal/protocol-relative/query/control characters, no bodies, provenance (run, record, export digest) | Unchanged; used in arms B/D/E |
| B. Shared HTTP budget and origin mapping | Broken (redirect hops uncharged and unscoped past the first hop; ZAP charge overwrote the counter) | Fixed, auditable per source |
| C. Hierarchical global/local exploration (`hierarchical.py`) | Partially implemented: planner integrated but never evaluated; its travel-cost model assumed free movement up the tree, which the executor cannot do | Cost model matches the executor; evaluated |
| D. Live-state reuse / restoration | Existing same-state live reuse; prefix reuse not started; root reloads not split by purpose | Discovery vs verification reloads split; verified prefix reuse and one-step history return added (`--state-reuse prefix`) |
| E. Graph A external-evidence provenance | Implemented and working: `external_discovery_run` nodes, `external_report` edges, `external_seed_candidate` vs `agent_seed_fetch`, `external_observation` connection evidence | Unchanged; audited in every run (0 promotions to replay) |
| F. Experimental runner and scoring | Partially: CLI flags only; earlier "tournament" folders hold baseline arms only | `experiments/run_architecture_comparison.sh`, `experiments/summarize_architecture_comparison.py` |

The previous agent's `hierarchical_smoke`, `hierarchy_smoke_v2`, `hierarchy_tournament` and `hierarchy_tournament_v2` folders were produced before the accounting fix. Their HTTP totals undercount redirects. They are retained as history only.

## 3. Architecture

**External discovery (H1).** A sanitized ZAP Traditional Spider history (`zap-http-history-1`) is validated and mapped from its explicit source origin to the Agent 1 target origin. Every record becomes `ExternalDiscoveryEvidence` with status `external_response` (ZAP saw a status) or `external_candidate` (status 0). Only parameterless 2xx GETs whose path does not match the dangerous-action pattern are queued into Agent 1's own typed-resource spider. Agent 1 then fetches them under its own budget and records them as `agent_seed_fetch`. An imported URL is never a UI transition, a workflow or a replay. The Client Map is not used.

**Hierarchical exploration (H2).** `AreaTourPlanner` groups frontier items by functional area, which is `(session-context digest, first URL path segment)` of the item's source observation. Exact states, record identities and sessions are never merged; areas are only a scheduling key. Global layer: a tour over areas, ordered by an exact permutation search over the 5 nearest areas (the rest in distance order). The cost between areas is the executor's real restore cost from the live path to each area's cheapest representative. Local layer: within the current area, the cheapest item first (same live state, then restore cost, then the existing novelty priority). The planner rotates to the next area after 8 consecutive actions, so it cannot camp in one area.

**State reuse (H4).** With `--state-reuse prefix`, before falling back to a root reload the executor tries, in order:
1. **Live prefix:** the live return path is a strict prefix of the item's path. Run only the suffix.
2. **History return:** the item's path extends the live state's parent. Take one browser-history step, re-observe, and accept only if the next required control is present. Then run the suffix.

Both require identical session markers and an input-free `navigate`/`click` as the undone step. Neither assumes cookies or storage restore server state: the page is re-observed and the final source signature is still verified as before. Steps skipped through reuse were executed earlier in the same live context. They are recorded as `reused_prefix_steps`, and the Graph A prerequisite-evidence check requires evidence for exactly the remaining steps. Fresh-context independent replay is unchanged.

## 4. What the experiments showed

- The hierarchical planner moved between areas 61% less often than the baseline, but this did not reduce cost. On a tree of dead-end pages, sibling-to-sibling travel without a way back up costs a root reload plus the full path, the same as any jump. Area locality and cost locality are different things.
- Live-prefix reuse is structurally vacuous in persistent single-session exploration: it fired 0 times. The live page is always the newest, deepest state.
- One-step history return is the mechanism that creates locality: 30 verified returns per run, 0 rejected, discovery root reloads 53 → 31. It only fires under the locality-seeking planner (0 times under the baseline scheduler).
- None of this moved the JavaScript category (3/27 in every arm), and the HTML category stayed at 16–19/57. Every arm exhausted its 300 actions. Scheduling changed what those actions were spent on (fewer reloads, more transitions), not how much of the application was observable.

## 5. Next hypothesis: channel split, then event-driven instrumentation

**Claim.** Snapshot-based exploration misses behavior that never appears as a semantic control or literal URL. The extractor (`explorer.py`, control selector) sees `a[href]`, form controls, ARIA roles and inline `on*` attributes. It does not see handlers attached with `addEventListener` on non-semantic elements, or URLs computed at runtime and handed to `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, workers, `window.open`, `location.assign/replace` or `history.pushState`. The AST resource parser only recovers string literals.

**Proposed mechanism.**
1. An init script (`context.add_init_script`) wraps `EventTarget.prototype.addEventListener` and the JS network/navigation APIs. It records element paths plus event types, and the API plus URL, with initiator stacks attached to the current action ID.
2. Listener-bearing elements become frontier controls with provenance `observed_listener`, distinct from `advertised_control`.
3. API-initiated URLs become typed-spider candidates with provenance `runtime_api_url`. Network requests are attributed causally to the action that triggered them, instead of by time window.
4. Readiness waits on the hooked counter of pending fetch/XHR calls instead of polling DOM stability.

**Preliminary evidence: the probe changes the priority.** `experiments/probe_event_instrumentation.py` re-opened all 84 states baseline run A_r1 reached, including 22 under `/javascript/`, with only the hooks installed (no clicks). It found **0 listener-only elements and 0 JS-API URL calls at page load** (the hook was validated on a synthetic page first). The reason is visible in the pages themselves. Crawl Maze's interactive cases attach the hidden listener or issue the `fetch` only **after** a first click ("show secret button"). That first button is an ordinary `<input type=button>`, which the snapshot extractor already sees.

The Graph A of the same run shows why those markers were missed. At the end of the 300-action run, **504 safe controls were advertised but never executed: 483 plain links and 20 clicks**, including every "show secret button"/"click this secret button" on the interactive pages. The frontier is ≈ 1.7× the whole action budget, and ≈ 40% of actions went to root reloads and restoration.

**Revised assessment.**
1. The first-order bottleneck is **browser-action allocation**, not observation. Plain GET links compete for the same 300 browser actions as the multi-step clicks that only a browser can perform, while ≈ 500 of the 1,000 HTTP budget goes unused.
2. Event-driven instrumentation is the right **second step** for this target: once the first click is executed, a listener on a non-semantic `div` and a computed `fetch` are exactly what the snapshot misses. It is not the first lever, because the first clicks are not even being reached.

**Next fundamentally different experiment (two channels, then instrumentation).**
- *Channel split:* safe, input-free `navigate` controls whose targets are in-scope GET URLs go to the HTTP channel. That is the existing typed spider, with provenance kept as `advertised_control` → `agent_seed_fetch`, never a UI transition or replay. Browser actions are reserved for non-navigate interactions and for states whose fetched HTML shows scripts or forms. This is an allocation change between budgets, not a scoring heuristic. It also answers the open H1 equal-cost question: the spider gets the HTTP budget B spent on ZAP.
- *Then instrumentation:* keep the hooks active **during** exploration. Listener-bearing elements created by an executed action become `observed_listener` controls, and API URLs become `runtime_api_url` candidates attributed to the action that caused them.
- *Decision rule:* proceed with instrumentation only if the channel split first reaches the interactive pages' first-step buttons within budget, and the hooks then report listener-only controls created by those clicks. Measure the gain at equal browser actions and equal HTTP requests.

## 6. Regression checks (60 s, same budgets; scored with `experiments/score_resource_transfer.py`)

| Fixture | Config | Areas | Controls | Request structures | Contexts | Replays | Missing evidence |
|---|---|---:|---:|---:|---:|---:|---:|
| JS-heavy lab (11 / 14 / 12) | A, default explorer | 9 | 12 | 8 | 0.5 | 10/10 | 0 |
| JS-heavy lab | hierarchical + state reuse | 8 | 12 | 6 | 0.5 | 10/10 | 0 |
| Shop (8 / 11 / 8, 2 contexts) | A, default explorer | 8 | 11 | 8 | 1.0 | 16/16 | 0 |
| Shop | hierarchical + state reuse | 7 | 10 | 5 | 0.5 | 15/15 | 0 |

The default configuration reproduces the historical results (JS lab 9/12/8; shop 8/8 areas, 11/11 controls, 8/8 requests), so the accounting fix did not regress the default path. The hierarchical + state-reuse configuration **regresses both fixtures**. On the shop it never executed the stateful add-to-cart POST → checkout chain or the review POST. Its cheapest-first local ordering keeps choosing cheap navigations in the current area, while the baseline's novelty priority pulls rare interaction kinds (forms) forward. The ZAP arms were not run on these fixtures because the ZAP evidence belongs to Crawl Maze. History return fired 10 times (2 rejected and safely fell back to root) on the JS lab and 17 times on the shop, with 0 missing evidence. This is a second, independent reason not to make the hierarchical policy the default.

## 7. Tests

Full suite: 62 passed (`.venv/bin/python -m pytest`). New or changed tests: redirect-chain and exhaustion accounting, per-source ledger, ZAP import scope and provenance, shared budget with seed scope, area separation by session context, planner cost model, prefix-reuse guards, and history-return evidence completeness on the fixture app.
