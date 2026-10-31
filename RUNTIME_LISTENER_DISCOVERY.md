# Runtime listener discovery: integration, tests and matched benchmark

This builds on `RUNTIME_INTERACTION_ABLATION.md` (commit 5db85c5), which introduced the opt-in Chromium listener observer. This milestone does three things:
- closes the gaps the development brief identified;
- adds focused regression tests and bounded instrumentation;
- runs the requested matched 180 s A/B experiment on the pinned Crawl Maze.

It changes no frontier, budget or graph architecture.

## 0. Baseline and reproducibility

| Item | State |
|---|---|
| Branch / HEAD before this work | `agent1-browser-mapper-20261028` at 5db85c5. That commit was not yet pushed: the remote was at b4a9a40, so the branch was one commit ahead. The tree was clean. |
| b4a9a40 is an ancestor of HEAD | yes |
| Target | Crawl Maze at `http://127.0.0.1:3460/`, revision `2a0dd0a75e39925ded887bcd25016e8b3ce0f2b3` |
| Browser | Chromium 156.0.8078.4 via Playwright 1.64.1, Python 3.12.13 |

**`E_DEPTH_FLAGS` defect.** `experiments/run_root_cause_ablation.sh` expanded `${=E_DEPTH_FLAGS}`, which nothing defined, so the value came from the caller's shell. The saved E2 run's `experiment_config.json` shows the value used: `--passive-document-max-depth 6 --budget-aware-deepening --hard-max-resource-depth 8`. The script now defaults to that value and prints it.

**Provenance.** Every run's `experiment_config.json` now also records:
- the exact command line;
- the target's git revision;
- whether the source tree was clean;
- browser, Playwright and Python versions.

`run.json` records `browser_version`.

**Limits on reproducing the historical 58/91.** The saved E2 run reports source revision `21a0e2d…+mapper-734e3e65c2d2`. That is an uncommitted working tree which later became b4a9a40, so its exact code is not recoverable. Arm A below uses E2's flags, with these differences:
- the 30% HTTP verification reserve;
- passive `Set-Cookie` sync, which is on by default since 5db85c5;
- the 5db85c5 reader and redirect fixes.

Browser timing is not deterministic. A scored 58/91, the same number as E2, but this is a matched control, not a reproduction of the historical run.

Matched configuration, identical for both arms (from `experiments/run_runtime_ablation.sh`):

```
--seconds 180 --max-transitions 120 --max-browser-actions 300 --max-resource-fetches 100
--document-budget 70 --script-budget 20 --stylesheet-budget 10 --asset-budget 20
--max-total-http-requests 1000 --http-verification-reserve 0.3 --exploration-policy multidimensional
--resource-allocation shared_http --max-speculative-fetches 25 --resource-frontier-model persistent
--passive-document-max-depth 6 --budget-aware-deepening --hard-max-resource-depth 8
--html-extraction standards --response-body-reader bounded_stream   (resource seed 0, 1 worker)
```

The two arms differ only in `--runtime-listener-observation` (`off` for A, `revisit` for B). `revisit` is the mode that lets the existing policy reconsider a control whose handler was replaced. The brief requires that, so it is the treatment. In the runner the treatment arm is tagged `C`.

## 1. How discovery works

`agent1/listeners.py` runs after each browser observation. It inspects page state only:
- it never dispatches events or calls handlers;
- the only page code it runs is a fixed describe function.

1. **Inventory.** One `DOMDebugger.getEventListeners(document, depth: -1, pierce: true)` call returns every listener with its node's `backendNodeId`. A second call returns the window's listeners. Click-family listeners are kept: `click`, `mousedown`, `mouseup`, `pointerdown`, `pointerup`, `dblclick`, `contextmenu`.
2. **Bounded, prioritized, incremental inspection.** At most `max_listener_nodes` (300) nodes are resolved and described per observation. Each describe is two DevTools calls. The order is:
   1. nodes new or changed since the previous observation of the same document;
   2. unchanged nodes already described, served from cache at no DevTools cost;
   3. nodes never inspected.

   Reaching the limit sets `truncated` and counts `node_budget` skips. A later observation of the same document inspects the remainder.
3. **Change classification.** Within one document, against the previous inventory, each node is one of:
   - `created_after_action`;
   - `listener_attached_after_action`;
   - `listener_appeared_after_action`, when history is unknown (shadow tree or frame);
   - `handler_changed`;
   - `unchanged`;
   - `present_at_first_observation`.

   To tell a created element from an attached one, the observer keeps a weak set of the main document's elements. The DevTools session holds the set, not a page global. A new document (navigation or reload, keyed by `performance.timeOrigin` and URL) starts a new inventory.
4. **Handler identity.** A handler is identified by its listener type and source location (script, line, column), never by its code. When a node's identity set changes, it gets a behavior revision token derived from the element path, the causing action and the new locations.
5. **Candidate filter.** A node becomes a candidate only if:
   - it has a direct listener;
   - it is rendered (not hidden, not zero-size, not occluded);
   - it is enabled and not in a closed shadow root;
   - it is not already a snapshot control;
   - it is not a likely delegation host (document, body, main, a container of other controls, more than 12 descendants, or more than half the viewport).

   Per handler location (`family_limit` 2) and per observation (`max_candidates` 12), excess candidates are counted and dropped.

### Integration with existing Agent 1 behavior

- **Ordinary controls.** Candidates become `Control(provenance="observed_listener")` in the same observation. They pass `_unsafe_reason`, the same filter as every other control, and enter the same frontier and action budget. They execute through `BrowserSession.execute`. Their transitions get the usual state, network, replay and connection evidence.
- **Group signatures unchanged.** Visible-DOM group signatures exclude listener controls. Listener actions and active revisions refine `behavior_signature` only, so states with listeners but no new behavior are not split.
- **Replaced handlers.** In `revisit` mode a snapshot control whose handler changed gets `behavior_revision`. The frontier's tried key and return paths include it, so the same unchanged button is offered again once per new revision. An unchanged handler keeps its tried key and is not re-executed. Replay of a revision action with no visible DOM change must reproduce its request structure.
- **Scope.** A listener candidate has no static target, so the cross-origin check on link targets cannot apply to it. With observation on, the browser scope router is now installed even when no HTTP budget is configured (see §5).
- **Failure.** Any DevTools error, or a non-Chromium engine, is recorded in `listener_evidence.error`. That observation then contributes no listener controls, and the snapshot pipeline continues unchanged.

## 2. Evidence and instrumentation

- **Per observation:** `listener_evidence` records:
  - node counts (`listener_nodes`, `described_nodes`, `reused_nodes`);
  - `changes` by class and `truncated`;
  - candidates, with change class, handler locations, listener count, family, revision, control ids and safety verdict;
  - revisions (before/after locations and causing action);
  - skips by reason, elapsed ms, DevTools call count, and any error.
- **Graph A `behavior_evidence`:** each candidate now also carries `caused_by_action` and `executed_transition_ids`. The summary counts candidates by change class and records how many were executed.
- **Run metrics** (all 0 when off):
  - DevTools activity: `listener_nodes_inspected`, `listener_nodes_reused`, `listener_bearing_nodes_max`, `listener_scans_truncated`, `listener_changes`, `listener_observation_errors`, `listener_observation_ms`;
  - candidates: `listener_candidates_new`, `listener_candidates_deduplicated`, `listener_candidates_safe`, `listener_candidates_rejected`;
  - actions: `listener_actions_executed`, `listener_transitions_with_effect`;
  - handler revisions: `handler_revision_candidates`, `handler_revisions_observed`, `handler_revisits_executed`.
- **Not stored:** handler source, argument values, form values, cookie values.

The schema is extended only, with defaulted fields, so older artifacts still load.

## 3. Tests

`tests/test_runtime_listeners.py` holds the session-level tests on synthetic localhost pages: 9 existing and 8 new. `tests/test_runtime_listener_fixture.py` is new and runs the Explorer end to end on the Larkspur Library reading room.

| Brief case | Test |
|---|---|
| 1 click creates a listener `<div>` | `test_listener_div_created_by_an_action_becomes_a_candidate_with_provenance`; end to end: `test_created_listener_divs_become_executed_and_evidenced_controls` (the slot `<div>` is invisible with the observer off, then executed and evidenced with it on) |
| 2 replaced handler reconsidered | `test_handler_revision_is_evidence_in_observe_mode_and_a_revision_in_revisit_mode`, `test_state_identity_suppressed_the_changed_handler_and_revisit_recovers_it`; end to end: `test_replaced_handler_is_reconsidered_on_the_same_unchanged_button` |
| 3 unchanged listener deduplicated | `test_unchanged_listener_is_deduplicated_and_not_reinspected` (stable control id; 0 DevTools describes on repeat) |
| 4 hidden or disabled | `test_hidden_and_zero_size_listener_elements_are_skipped`, `test_disabled_listener_element_is_not_promoted` |
| 5 more than 300 listener elements | `test_default_inspection_limit_on_a_large_page_prioritizes_new_nodes` (401 nodes at the default 300; truncation recorded; a node created after the click is inspected first) |
| 6 multiple listeners on one element | `test_multiple_listeners_on_one_element_yield_one_control` |
| 7 no relevant listeners | `test_page_without_listeners_is_unchanged_by_the_observer` (identical control ids and signatures for off, observe and revisit) |
| 8 DevTools unavailable | `test_devtools_failure_falls_back_to_the_snapshot`, `test_observer_is_off_by_default_and_reports_unsupported_engines` |
| 9 dangerous candidate | `test_listener_alone_never_authorizes_an_unsafe_action`; end to end: `test_dangerous_and_off_scope_listeners_are_still_refused` (no `POST /api/reading-list/clear`, no sentinel request) |
| 10 navigation | `test_navigation_starts_a_new_listener_inventory` (navigation and reload) |
| Created vs attached | `test_existing_element_with_a_newly_attached_listener_is_distinguished_from_a_created_one` |

Full suite: **150 passed**.

## 4. Matched Crawl Maze benchmark (180 s per arm, one run each)

Artifacts are in `agent1/experiments/runtime_crawlmaze_180/`. They were summarized offline by `experiments/summarize_runtime_ablation.py --crawlmaze`. The strict-2xx /91 score uses the existing offline scorer, and runtime attribution is computed offline after the run. Agent 1 never sees expected paths.

| | A: control (off) | B: treatment (revisit) |
|---|---:|---:|
| Markers, strict 2xx /91 | 58 | **61** |
| Gained / lost vs A | – | +3 / −0 |
| Markers reached through runtime-discovered actions | 0 | 3 (all 3 reached by no other means) |
| Distinct listener candidates (safe / rejected) | – | 1 / 0 |
| Handler revisions observed / offered / executed | – | 1 / 1 / 1 |
| Listener actions executed / with observable effect | – | 2 / 2 |
| Candidate sightings deduplicated | – | 5 |
| Listener-node sightings already represented by snapshot controls | – | 38 (no duplicate controls created) |
| Transitions observed | 102 | 103 |
| Browser actions (cap 300) | 297 | 299 |
| Action request structures | 9 | 11 |
| Replays validated | 24/24 | 25/25 |
| Runtime-discovered actions replay-validated | – | 0/3 |
| HTTP requests (cap 1000) | 679 | 683 |
| Elapsed (s) | 163.8 | 167.4 |
| DevTools time: total / per observation / share of runtime | – | 0.99 s / 6.6 ms / 0.6% |
| DevTools calls; nodes inspected / reused; truncated scans; errors | – | 1,376; 15 / 29; 0; 0 |
| Python peak RSS (MB) | 66.3 | 66.4 |
| Missing Graph A evidence / incorrect merges | 0 / 0 | 0 / 0 |
| Unsafe or skipped listener elements executed | – | 0 |

The three gains are:
- `multi-step-request-event-listener-div.found` and `…-event-listener-div-dom.found`: a click creates a `<div>` with a click listener. Its change class was `created_after_action`, it was executed as a listener candidate, and it issued the request.
- `multi-step-request-redefine-event-attribute.found`: the second handler of the same Submit button. Its change class was `handler_changed`, and it ran as a revision revisit with the visible DOM unchanged.

Actions per additional marker: the three markers took three runtime-discovered actions (two listener clicks, one revisit), so one browser action each. Total actions stayed at the shared cap: 299 vs 297. Wall-clock cost was +3.6 s (2.2%), of which DevTools accounted for 1.0 s; memory was unchanged.

**Graph quality.** No candidate was unsafe, executed without an observable effect, or missing its connection claim. No incorrect merges occurred, and one same-DOM, different-behavior transition was correctly kept separate.

The two 2xx counts above come from one run per arm and are not significance-tested. In the earlier 120 s check (5db85c5) the same arm gained the same three markers: 56 → 59, −0.

## 5. Issue found and smallest correction

The new end-to-end safety test caught a gap that predates this work. The browser scope router was installed only when `max_total_http_requests` was set. Without an HTTP budget, clicking the fixture's "Open partner catalogue" listener `<div>` (`location.href = <off-scope origin>`) reached the sentinel server.

Snapshot links are protected by the static cross-origin target check. Listener candidates have no target to check, so they need the router. The fix installs the router whenever listener observation is on, enforcing scope only when there is no budget. Behavior with listener observation off is unchanged. Every benchmark configuration already set a budget, so no reported result was affected: the fixture runs in 5db85c5 recorded 0 sentinel hits.

## 6. Remaining limitations

- **Replay coverage.** None of the three runtime-discovered behaviors on Crawl Maze was replay-validated (0/3). Replay is shallow-first, and these actions sit two or three steps deep. The deterministic fix is replay prioritization that covers each distinct request structure once; it was not attempted here.
- **Delegated listeners.** Delegated listeners (document, body or container), closed shadow roots, cross-origin frames, and handlers rebound to the same source location are still not attributable or distinguishable. A framework that attaches only at the root (e.g. React) gains nothing.
- **Native traversal.** `getEventListeners(depth: -1)` traverses the whole DOM inside the browser in one native call. The 300-node bound applies to per-node DevTools inspection, not to that traversal.
- **Created vs attached.** The distinction is available only for main-document light-DOM elements. Elsewhere the class is `listener_appeared_after_action`.
- **Single run.** Only one run per arm, and only one benchmark target with runtime cases. A framework-built application has not been evaluated.
- **Chromium only.**

## 7. Configuration

```bash
--runtime-listener-observation off|observe|revisit   # default off
--max-listener-nodes 300 --max-listener-candidates 12   # RunConfig.listener_family_limit = 2
```

Reproduce the benchmark with:

```bash
experiments/run_runtime_ablation.sh crawlmaze ROOT 180 A C
cd experiments && ../.venv/bin/python summarize_runtime_ablation.py --root ../ROOT --crawlmaze --out ../ROOT/runtime_summary.json
```
