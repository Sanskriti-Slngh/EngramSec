# Runtime interaction ablation: bounded DevTools listener observation and behavior revisions

**Scope.** Phases 2–4 of the transfer/runtime milestone, starting from `b4a9a40` (E2). Work in this phase:
- an opt-in Chromium DevTools listener observer;
- a behavior-revision identity for handlers that change behind an unchanged DOM;
- Graph A behavior evidence;
- a matched ablation on an independent fixture, plus a limited Crawl Maze check.

No model calls, no paid APIs, no crawler-proposed JavaScript, no method substitution, no off-scope requests. Agent 1 never reads evaluator truth. Transfer-pipeline findings (Phase 1) are in `DETERMINISTIC_TRANSFER_VALIDATION.md`.

**Result in one paragraph.** Listener observation makes behavior that was invisible to the DOM snapshot executable and recordable as evidence. It never treats a listener as authorization, and costs about 9.5 ms per observation (0.9% of runtime).

On the independent fixture's reading room (60 s, matched budgets):

| Arm | Designed behaviors executed | Action-triggered request structures |
|---|---:|---:|
| A (E2) | 3/9 | 3 |
| B (+ listener observation) | 7/9 | 7 |
| C (+ revision re-exploration) | 8/9 | 8 |

B adds 5 new interaction types and C adds a 6th. Graph A shows 0 missing evidence, 0 DOM merges and 0 unsafe or delegated executions in every arm.

Two results limit the claim:
1. **Replay coverage barely moved** (0/9 → 2/9 → 1/9). The fixed 30% replay reserve, ordered shallowest-first, spent its 14 replays on depth-1/2 navigation, while listener behaviors sit at depth 2–3.
2. **On Crawl Maze**, the effect is +3 strict-2xx markers (56 → 59 /91 at 120 s), exactly the three runtime cases the earlier probe predicted.

Listener observation is retained **opt-in** (`--runtime-listener-observation observe|revisit`). Default adoption should wait on replay prioritization and a second independent application.

## 1. What was built

### 1.1 Bounded DevTools observer (`agent1/listeners.py`)

After every browser observation, when enabled, the observer does the following:
1. **Collect listeners.** One `DOMDebugger.getEventListeners(document, depth: -1, pierce: true)` call returns every listener in the document, including same-process frames and shadow roots, keyed by `backendNodeId` and handler location (script, line, column).
2. **Detect delegation.** A second call on `window` counts delegated window listeners.
3. **Describe listener nodes.** Click-family listeners (click, mouse/pointer down/up, dblclick, contextmenu) are kept. Each listener-bearing node is described once per document, up to `max_listener_nodes` (300): tag, rendered/hit-test, label, frame-relative CSS path, and shadow chain (`host >> inner`).
4. **Compare with the prior observation of the same document.** Document identity is `performance.timeOrigin`, never function code:
   - a new node is `created_after_action`, attributed to the last executed action;
   - a changed handler set on an existing node is a **handler revision**;
   - the first observation of a document marks nodes `present_at_first_observation`.
5. **Classify, in order, and count every skip by reason:**
   - document/html/body/main → `delegation_host`;
   - already a snapshot control → `represented_by_snapshot` (tracked for revisions only);
   - containing controls, more than 12 descendants or more than half the viewport → `possible_delegation_host`;
   - closed shadow root → `closed_shadow_root` (Playwright cannot address it);
   - not rendered or occluded → `not_rendered`;
   - disabled → `disabled`;
   - more than 2 per handler location → `family_limit`;
   - more than 12 per observation → `candidate_limit`;
   - beyond the node budget → `node_budget`.

Candidates become ordinary `button` controls with `provenance: observed_listener`. They pass the same `_unsafe_reason` safety filter as every other control: a "Delete my reading list" div is recorded but marked unsafe and never clicked. They also share the same action budget, scope routing and replay requirement. A listener is evidence that an element is actionable, never authorization to act.

Unsupported: Firefox and WebKit (no `DOMDebugger` through Playwright; the observer reports `unsupported_engine`), cross-origin frames (separate targets; not pierced), and closed shadow roots (counted, not executed).

### 1.2 Behavior revision identity (Phase 3)

**Investigation.** I reproduced, with Explorer-level tests, four ways the existing visible-DOM identity hid changed behavior:

| # | Defect | Reproduction | Repair |
|---|---|---|---|
| I1 | Frontier `tried` key = group signature + control signature. A handler replaced behind the same DOM is "already tried" forever. | `test_state_identity_suppressed_the_changed_handler_and_revisit_recovers_it`: the off arm never issues the second request | In revisit mode, the tried key includes the control's evidence-derived `behavior_revision`, so the old action stops suppressing the new behavior |
| I2 | Return paths keyed by group signature. A state whose behavior was created by a click (a revised handler, or a listener `<div>` appended outside `<main>`) shares the root's group, so its recorded workflow lost the creating click. | Debug runs: revisit workflow length 1 instead of 2; listener workflow `[Open details]` instead of `[Show, Open details]` | `behavior_signature` = group + active revisions + available listener-only actions; return paths are also kept per behavior signature |
| I3 | Replay de-duplication by (result URL, group, interaction). A network-only workflow ending on the same screen as another action was never replayed. | Revised-handler transition dropped from replay | Key also includes the revision, and the request structures for network-only transitions |
| I4 | A transition whose only effect is a fetch/XHR or non-GET request (same DOM, no dialog) was replay-validated on DOM checks alone, even if the replayed click did nothing. | Same tests | New required replay check `request_structures`: the final replayed step must issue the same (method, route, parameter names) |

**Design.**
- The state signature and group signature are unchanged (visible DOM only); listener controls are excluded from them.
- Handler revisions are identified by (CSS path, causing action, portable handler locations). No function body is read or hashed.
- `behavior_signature` is a separate field.
- `find_current` requires the recorded revision to match, so restore and replay must re-create the revised behavior. In observe mode (B), revisions are recorded as evidence only.

Kept distinct in Graph A: visible DOM (`group_signature`), handler behavior (`behavior_signature` and `handler_revisions`), application state (result group and requests), and session/record identity (`session_context`, session markers, cookie *names* on passive fetches).

**Identity uncertainty (not solved).**
- Location-based handler identity cannot see a replacement created at the same source location: a factory closure re-bound with new captured state counts as "unchanged".
- Script identifiers are per-document, so cross-load comparison uses line and column only.
- Delegated handlers are not attributed to targets.

### 1.3 Graph A behavior evidence

`graph_a.json → behavior_evidence` contains:
- `listener_observations`: nodes inspected, candidates, revisions, skips by reason, CDP time and calls, errors;
- `listener_candidates`: provenance, handler locations, control ids, safety;
- `handler_revisions`: before/after locations and causing action;
- `behavior_executions`: provenance, revision, visible-DOM change, request structures and replay status.

Two new connection-evidence claims:
- `listener_candidate`: the executed element appears in the source observation's DevTools evidence;
- `handler_revision`: the exercised revision is active in the source observation.

## 2. Independent fixture ablation (reading room, 60 s)

**Fixture.** `development_apps/transfer_library.py`, built without reference to Crawl Maze. The run starts at `/desk` so that the 60 s run reaches the runtime-only section. Nine designed behaviors (F1–F9) and four that must not occur (X1–X4). Truth is held in `experiments/evaluate_transfer_library.py` and the server log, both used after the run only.

**Matched settings for all arms:** 60 s, 300 actions, 120 transitions, 1 worker, 1,000 HTTP of which 30% is held for replay, typed total 100, caps 70/20/10/20, E2 discovery configuration. The fixture arms ran before repair T9, which stops speculative GETs of computed request-target prefixes (`DETERMINISTIC_TRANSFER_VALIDATION.md`). T9 changes only one passive request per arm (see X1/X4 below).

| Metric | A (E2) | B (+observe) | C (+revisit) |
|---|---:|---:|---:|
| Designed behaviors executed (of 9) | 3 | 7 | **8** |
| …replay-validated with the request reproduced | 0 | 2 | 1 |
| Action-triggered request structures | 3 | 7 | 8 |
| …per 100 browser actions | 3.03 | 7.37 | 8.42 |
| Listener candidates recorded / listener actions executed | — | 10 / 13 | 10 / 13 |
| Handler revisions observed / revisits executed | — | 1 / 0 | 1 / 1 |
| Browser actions / transitions | 99 / 54 | 95 / 45 | 95 / 45 |
| Replays validated | 14/14 | 14/14 | 14/14 |
| CDP time per observation (share of runtime) | — | 9.6 ms (0.93%) | 9.4 ms (0.92%) |
| CDP calls / observations / errors | — | 1,089 / 59 / 0 | 1,087 / 59 / 0 |
| Graph A connections missing evidence | 0 / 3,509 | 0 / 3,052 | 0 / 3,037 |
| Incorrect (DOM) state merges | 0 | 0 | 0 |
| Behavior-divergent groups (same DOM, different behavior) | 0 | 1 | 1 |
| Python peak RSS (MB) | 78.5 | 80.0 | 78.9 |
| HTTP requests | 678 | 524 | 521 |

**Per behavior.**

| Behavior | Wiring | A | B | C |
|---|---|---|---|---|
| F1 reading-list save | snapshot button, POST fetch | ✓ | – | – |
| F2 catalog search | snapshot GET form | ✓ | ✓ | ✓ |
| F3 loan status | snapshot button, first handler | ✓ | ✓ (replayed) | ✓ |
| F4 loan eligibility | same button, handler replaced, DOM unchanged | – | – (revision recorded only) | **✓ revisit** |
| F5 study-slot reserve | `<div>` listener created by an action | – | ✓ | ✓ |
| F6 exhibit card | `<div>` listener present at load, navigates | – | ✓ | ✓ |
| F7 branch holdings | listener in an open shadow root | – | ✓ | ✓ |
| F8 citation | listener in a same-origin frame | – | ✓ | ✓ (replayed) |
| F9 call-number row | 400 rows, one handler location | – | ✓ (replayed) | ✓ |

**Must not occur, by browser action, in any arm (0 everywhere):**
- X1: document-delegated shelf item (not attributed);
- X2: closed-shadow listener;
- X3: dangerous "Delete my reading list" listener (recorded, marked unsafe, never clicked);
- X4: hidden or zero-size listeners (`not_rendered`).

The safe-labelled "Open partner catalogue" listener was clicked in B and C. The route blocked its off-scope navigation; the off-scope sentinel saw 0 requests. The transition is recorded as failed ("action left the configured origin").

Separately, every arm sent 1 passive speculative GET each to the `/api/shelf/` and `/api/hidden/` prefixes. Those literals sit inside computed `fetch` targets; the cause was found here and repaired as T9.

**Skips (B, summed over 59 observations):**
- `family_limit` 1,194 and `node_budget` 400 (the 400-row table: 2 rows exposed per observation);
- `represented_by_snapshot` 26;
- `closed_shadow_root` 2, `not_rendered` 2, `delegation_host` 1.

**Missed or misclassified controls.**
- No listener action lacked an observable effect.
- No candidate came from a delegation host.
- The dangerous listener was classified unsafe.
- Misses:
  - F1 was not reached in B or C. Exploration order: listener candidates on the reading-room pages took the actions that A spent reaching item pages.
  - X1 and X2 are designed limitations.
  - In B, F4 is recorded as a revision but not executed, by design.

**Reading.** Listener observation is the only route to F5–F9, which are ordinary implementation patterns: `addEventListener` on non-semantic elements, custom elements, frames, and table rows. These show B is not a Crawl Maze-specific gain. Revision re-exploration (C) adds exactly the one designed case (F4) for one extra action.

The cost is attention, not time. B and C execute 13 listener actions and observe 9 fewer transitions than A within the same budget.

Replay coverage of the new behaviors is the weak point. The 14 replays covered only paths of length 1–2: the run reserves 30% of time for replay, and the shallow replay order puts navigation first. Most listener behaviors are at depth 2–3, so they remain observed-but-not-replayed. This is a replay-scheduling limit, not an observation failure. Every replay that ran reproduced its request structure.

## 3. Limited Crawl Maze check

Limited by the 20-minute live-browser cap: arms A and C at 120 s each, otherwise the matched configuration of §2 (start `/`). B was not run separately on Crawl Maze. C contains B's mechanism, and the fixture already separates B from C. Raw scores are not comparable with the 180 s E2 = 58 of the previous milestone.

| Metric | A (E2) | C (+listeners, +revisit) |
|---|---:|---:|
| Strict-2xx /91 (secondary) | 56 | **59** (+3, −0) |
| Supported-deployment /84 | 56 | 59 |
| Any-status request surfaces /91 | 58 | 61 |
| Action-triggered request structures | 4 | 7 |
| Listener actions executed / revisits executed | 0 / 0 | 2 / 1 |
| …of those replay-validated | — | 0 / 0 |
| Browser actions / transitions / grouped states | 225 / 71 / 63 | 223 / 71 / 60 |
| Replays validated | 25/25 | 26/26 |
| CDP time per observation (share of runtime) / calls | — | 4.7 ms (0.39%) / 729 |
| Listener skips | — | `represented_by_snapshot` 27 |
| Graph A missing evidence / incorrect merges / behavior-divergent groups | 0 / 0 / 0 | 0 / 0 / 1 |
| HTTP requests / Python peak RSS | 582 / 57.7 MB | 571 / 57.5 MB |

The three gained markers:
- `multi-step-request-event-listener-div` and `…-div-dom`: listener `<div>`s created by a click, executed as listener candidates;
- `multi-step-request-redefine-event-attribute`: the `Submit` button's `onclick` replaced in place, executed as a revision.

None was lost. Remaining limitations on Crawl Maze are unchanged: delegation, the 5 s timer, the AngularJS CDN, and the testbed and safety boundaries listed in `DETERMINISTIC_ROOT_CAUSE_AUDIT.md`. As on the fixture, the newly executed actions were observed but not replayed within the replay reserve.

Graph A evidence audit (Crawl Maze): 0 spider attempts without a channel, 0 passive documents as UI transitions, 0 spider GETs for non-GET surfaces, 0 observed-only records with a spider attempt.

## 4. Generalization regressions

Arm C (the most permissive configuration), 60 s, matched to the previous milestone's E2 regression runs:

| Lab | Areas / controls / request structures | Replays | Missing evidence | Self-audited merges | Contexts / distinct instances | Prerequisite paths | Listener candidates | CDP ms/obs |
|---|---|---:|---:|---:|---|---:|---:|---:|
| JS-heavy (previous E2) | 9 / 12 / 8 | 10/10 | 0 | 1 | 0.5 / no | 6 of 11 | — | — |
| JS-heavy (C) | 9 / 12 / 8 | 10/10 | 0 | 1 | 0.5 / no | 5 of 11 | 0 (98 listener nodes, all snapshot controls) | 6.2 |
| Shop (previous E2) | 8 / 11 / 8 | 16/16 | 0 | 0 | 1.0 / yes | 0.75 | — | — |
| Shop (C) | 8 / 11 / 8 | 16/16 | 0 | 0 | 1.0 / yes | 0.75 | 0 (104 nodes, all snapshot controls) | 5.0 |

No regression in any coverage or replay count. The JS-heavy merge and context recall are pre-existing and identical to the previous milestone.

The only difference is one JS-heavy prerequisite path (5 vs 6 of 11). The observer exposed no candidate there, so it did not change the frontier. The cause is not isolated: candidates are run-to-run variation, as seen before on the shop (0.75 vs 0.875), or this milestone's replay de-duplication change (I3).

On both labs every listener-bearing element is already a semantic control. Listener observation adds 0.5–0.6% runtime and nothing else there. That is the expected and correct outcome for applications whose interactive elements are well-formed.

## 5. Graph A behavior-evidence integrity audit

`experiments/summarize_runtime_ablation.py → integrity`, per run. All values are 0 unless stated:

| Check | Fixture A | Fixture B | Fixture C | Crawl Maze A | Crawl Maze C | JS-heavy C | Shop C |
|---|---:|---:|---:|---:|---:|---:|---:|
| Listener / revision claims incomplete | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Listener actions without a `listener_candidate` claim | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Revisits without a `handler_revision` claim | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Unsafe listener elements executed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Skipped (delegated / hidden / closed-shadow) elements executed | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Revisits in observe mode | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Validated network-only replays without the request check | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Mixed session contexts within a run | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Cookie values in passive evidence (schema stores names only) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Replays validated against an exploration observation (must be independent) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Same-DOM, different-behavior transitions (informational) | 0 | 1 | 1 | 0 | 1 | 0 | 0 |
| Graph A connections missing evidence | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Incorrect (DOM) state merges | 0 | 0 | 0 | 0 | 0 | 1 (pre-existing) | 0 |

The informational row counts exactly the expected cases:
- the fixture's loan button, whose handler is revised without a DOM change;
- Crawl Maze's redefined `onclick`.

Those are the states that the old identity would have treated as already explored. Graph A now keeps them distinct through `behavior_signature`; the visible-DOM group is not split.

## 6. Decision

**Retain listener observation as an opt-in capability; do not enable it by default yet.**

Evidence that it adds generalizable functionality:
- **Fixture.** Five of the nine designed behaviors are reachable only through it. They use ordinary patterns: `addEventListener` on `<div>` cards and table rows, an action-created element, an open shadow root, a same-origin frame.
- **Crawl Maze.** It adds exactly the predicted runtime cases.
- **Cost and safety:**
  - under 1% runtime;
  - no Graph A integrity loss;
  - no unsafe, hidden, closed-shadow or delegated execution;
  - no regression on the two labs.

Revision re-exploration (C) is separately justified, but narrowly: one designed fixture behavior (F4) and one Crawl Maze marker, each for a single extra action and with complete `handler_revision` evidence. It needs B's observer and costs nothing further. Run it together with B, and treat it as supported by two cases, not a general measurement.

What blocks default adoption:
1. **Verification lags discovery.**
   - Fixture: 2 of 9 listener or revision behaviors replay-validated in B, 1 of 9 in C.
   - Crawl Maze: 0 of 3.

   The replay reserve is ordered shallowest-first. A deterministic replay prioritization that covers each distinct action-triggered request structure once, before repeating navigation, should come first. It needs no new budget and is directly measurable.
2. **Attention cost.** In the same budget, B and C observed 9 fewer transitions than A and missed F1. Listener candidates compete for actions with ordinary links. The family limit (2 per handler location) contained the 400-row table, but the trade-off has to be measured on applications with many listener-bearing elements.
3. **Framework coverage is unmeasured.** React 17+ attaches its listeners to the root container, so the observer correctly sees only a delegation host there and adds nothing. Libraries that bind directly to non-semantic elements benefit. A second independent application built with a mainstream framework is needed before generalizing.
4. **Limits that remain by design:**
   - delegated listeners are not attributed;
   - closed shadow roots;
   - cross-origin frames;
   - location-based handler identity: a re-bound factory closure is invisible;
   - Chromium only.

Path to default: (1) replay prioritization by request structure; (2) a second independent app (framework-built) under matched A/B/C; (3) a listener-heavy stress page to set the family and candidate limits from evidence; then make `observe` the default for Chromium runs if (1)–(3) show verification parity with no attention loss.

**Is the deterministic crawler ready for LLM-guided planning?** Conditionally, for a narrow experiment; not as the next default.

For:
- The deterministic layer now gives a planner trustworthy inputs and guardrails:
  - **Pipeline transfer:** the HTTP pipeline transfers to an independent application.
  - **Session safety:** the session is kept intact.
  - **Discovery boundaries:** malformed and hostile responses are bounded; the off-scope sentinel and redirect trap are contained.
  - **Execution safety:** every executed action passes the same safety filter, scope router and evidence audit.
  - **Evidence:** Graph A shows 0 missing evidence in every final run except the transfer E2 run. Its 16 missing claims are exactly the replays blocked by the spent reserve (T7b), repaired after that run and verified on the regression runs. DOM merges are 0 everywhere except the pre-existing JS-heavy one.
- The remaining losses on both applications are *allocation* decisions, which is what a planner could improve:
  - which of many novel actions to spend the budget on (the reading room never reached from `/`; F1 lost to listener candidates);
  - which workflows to verify (deep behaviors unreplayed).

Against:
- Both of those decisions have cheap deterministic baselines that have not been tried yet:
  - request-structure-aware replay ordering;
  - navigation-chrome penalties that do not hide whole sections.
- An LLM planner measured before them would be credited with gains a deterministic rule can deliver.

Recommendation:
1. Implement the deterministic replay prioritization and re-run the fixture A/B/C.
2. Then run a matched experiment in which a local model only **reorders existing frontier and replay items**. It proposes no URLs, no JavaScript and no methods. It is scored on designed behaviors replay-validated per browser action, against the improved deterministic ordering.

Planning should be adopted only if it beats that baseline on two independent applications with unchanged evidence integrity.

## 7. Live-browser time and artifacts

Cumulative live-browser experiment time was about 19.5 minutes, against a 20-minute cap:
- fixture smoke runs, 1.6 min;
- transfer v1 (no reserve), 4.3 min;
- an aborted queue, 0.9 min;
- transfer v2 (cap crash), 1.3 min;
- runtime fixture A/B/C, 3.1 min;
- final transfer D0/E2, 2.2 min;
- Crawl Maze A/C, 4.1 min;
- regressions, 2.0 min.

Unit and integration tests are not counted. One run per arm. The earlier milestone measured ±1 marker of run-to-run variation on Crawl Maze.

Results:
- `agent1/experiments/runtime_fixture/` (`transfer_evaluation.json`, `runtime_summary.json`);
- `agent1/experiments/runtime_crawlmaze/runtime_summary.json`;
- `agent1/experiments/runtime_regression/{js-heavy,heldout-shop}/`.

Code:
- `agent1/listeners.py`;
- behavior identity and the replay request check in `agent1/explorer.py` and `agent1/state.py`;
- `build_behavior_evidence` in `agent1/exporter.py`;
- `experiments/summarize_runtime_ablation.py`.

Tests: `tests/test_runtime_listeners.py` (9 session-level) and `tests/test_runtime_listener_runs.py` (3 Explorer-level).
