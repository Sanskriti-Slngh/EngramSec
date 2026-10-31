# Runtime discovery: large-DOM cost, React, and an unfamiliar application

This is the companion to `REPLAY_VALIDATION_REPORT.md`. It covers three things:
- the measured cost of the listener enumeration on large documents;
- how React registers events, and what that means for direct-listener discovery;
- the strongest configuration on an application Agent 1 had never seen.

It ends with a ranking of the next architectural improvement.

## 1. Large-DOM cost of `DOMDebugger.getEventListeners`

Measured with `experiments/measure_listener_cdp_cost.py` (results in `agent1/experiments/listener_cdp_cost/`). The setup:
- Chromium 156, local, headless, with the guard disabled to measure the mechanism itself;
- synthetic nested pages;
- a share of elements with click listeners, plus a `mouseover` listener on every 7th element;
- enumeration latency is the median of 5 calls, and Python allocation is the tracemalloc peak while the response is parsed.

| Elements | Click share | Listener records | Enumeration (ms) | Response | Python alloc peak | First observe (ms) | Unchanged repeat (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 107 | 1% | 14 | 0.7 | 6 KB | 0.3 MB | 9 | 2.5 |
| 107 | 10% | 23 | 0.9 | 10 KB | 0.3 MB | 13 | 2.7 |
| 1,007 | 1% | 139 | 3.3 | 58 KB | 0.5 MB | 11 | 3.8 |
| 1,007 | 10% | 229 | 4.9 | 95 KB | 0.8 MB | 64 | 4.7 |
| 10,007 | 1% | 1,386 | 31 | 584 KB | 4.5 MB | 97 | 35 |
| 10,007 | 10% | 2,286 | 51 | 961 KB | 7.5 MB | 202 | 219* |
| 50,007 | 1% | 6,929 | 160 | 2.9 MB | 22 MB | 311 | 283* |
| 50,007 | 10% | 11,429 | 265 | 4.8 MB | 37 MB | 318 | 331* |
| 10,007 | 100% (worst) | 10,286 | 236 | 4.3 MB | 34 MB | 349 | 358* |
| 50,007 | 100% (worst) | 51,429 | 1,886 | 21.5 MB | 167 MB | 1,547 | 1,459* |

\* At most 300 nodes are described per observation. With more click-listener nodes than that, each repeat observation describes the next 300 nodes not yet inspected. Repeat cost therefore equals first-observation cost until every node has been described; after that only the enumeration remains.

**Findings.**
- **Enumeration** is a single native call, linear in DOM size: about 3–5 µs per element at realistic listener densities.
- **Response size and Python memory** grow with the number of listener *records*, about 420 bytes per record. Listener density, not element count, is what makes very large pages expensive.
- **Practical range.** Up to about 10,000 elements, enumeration costs at most about 50 ms per observation. The real targets measured were far smaller:
  - Crawl Maze: 6.3 ms per observation in total, 0.6% of runtime;
  - the whiteboard app: see §3.

  At 50,000 elements and realistic density, enumeration costs 160–265 ms per observation. At 50,000 elements with a listener on every element, it costs 1.9 s, a 21 MB response and 167 MB of Python allocation, which is impractical per observation.
- **No incremental replacement.** An incremental enumeration driven by DOM mutations would miss exactly the two target behaviors: replacing `onclick` and calling `addEventListener` on an existing element are not DOM mutations. The measurements do not justify replacing the mechanism.

  Instead, the observer now:
  - records each document's element count (`dom_elements`, run metric `listener_dom_elements_max`);
  - skips the enumeration when the document exceeds `max_listener_dom_elements`, default 20,000, recording `dom_too_large`. In the measurements, 20,000 elements cost about 60–100 ms at realistic density and about 470 ms in the worst case.

  The guard costs one native element count; it is tested by `test_dom_size_guard_skips_enumeration_and_keeps_the_snapshot`.

## 2. How React registers events

React 19.2.4 was investigated in the whiteboard client (§3), signed in, on the canvas list and on a canvas page.

- **Root registration.** `createRoot` registers its listeners on the root container. `getEventListeners` reports about 85 listener records on `div#root` and almost none on descendants.
- **Handlers as props.** Each element's handlers are stored in an own property `__reactProps$<random>` (for example `onClick`, `onSubmit`, `onPointerDown`). For some elements React also sets a no-op `onclick`.
- **Observer behavior.** The direct-listener observer correctly classifies `#root` as a `possible_delegation_host`. It attributes the root listener to no descendant and creates 0 listener candidates on these pages.
- **What the props contain.** A bounded, read-only scan of the handler *names* in `__reactProps$*` found:
  - home: 4 handler-bearing elements (3 `<button>` and 1 `<form onSubmit>`), all already snapshot controls;
  - canvas page: 13, of which 12 are buttons, forms and inputs.

  The only element outside the snapshot is the SVG drawing surface, with `onPointerDown/Move/Up/Leave/Cancel` and `onLostPointerCapture` handlers. That is a drag gesture that creates shapes, not a click target.

**Safe, bounded discovery.** The evidence-only **framework probe** (`--framework-handler-probe N`, off by default) runs only on pages where a delegation host was found. It reads handler names from at most N elements and records in each observation's listener evidence:
- the framework, how many elements were scanned, and whether the scan was truncated;
- how many elements carry handlers;
- how many of those are outside the snapshot;
- counts per handler prop;
- five examples (tag, handler names, ARIA label).

It never calls a handler and **never creates a candidate**. A root listener plus a prop is reported, not acted on.

Turning such props into click candidates was not implemented, because the measurement shows no benefit on this application:
- every React click handler here sits on an element the snapshot already executes;
- the one element outside the snapshot carries a gesture that changes state.

It is tested by `test_framework_probe_reports_delegated_handlers_without_creating_candidates`, on a simulated React page.

## 3. Unfamiliar application: collaborative whiteboard

**Application.** A real-time collaborative whiteboard: `~/takehome-sanskriti-singh` at revision `989ec3e`. It is the user's own local project, and Agent 1 had never run against it.
- React 19.2.4 and Vite client (about 1,800 lines);
- FastAPI server with Postgres;
- accounts, canvases as records, a shape toolbar, invites, and a WebSocket.

**Stack.** An isolated copy separate from the project's own Docker setup:
- `postgres:16-alpine` with no volume, and the existing server image (`takehome-sanskriti-singh-server`, `8a8ed37…`), both on a private Docker network;
- the Vite dev server on `127.0.0.1:45173`.

Before every run the database is recreated. An operator script (`experiments/seed_whiteboard_session.py`, not part of Agent 1) creates a throwaway account and two canvases, then saves the authenticated Playwright storage state outside the repository.

Agent 1 receives that state through the new `RunConfig.storage_state_path` (`--storage-state`). It never sees or enters a credential. Every exploration and replay context starts from the same session identity (context label `authenticated`), and Graph A records cookie names only.

**Configuration.** Each run used 150 s; the same budgets as Crawl Maze (300 actions, 1,000 HTTP requests with 30% held for replay); and the E2 flags.
- W0: listener discovery off, shallow replay.
- W2: listener `revisit`, structure replay, framework probe (5,000 elements).

### 3.1 First attempt (kept as `runtime_generalization_whiteboard_v1_uuid_fragmentation`)

It exposed a generalization bug in `route_pattern`. Digits were tried before UUIDs, so a canvas id starting with a digit became `{instance}5efb7a-{instance}3b4-…`. Each canvas then looked like a new route, which inflated states, request structures and exploration.

W0 used the full 1,000-request budget in 54 s. The Vite dev server serves unbundled modules, so every page load costs dozens of requests. The fix tries whole UUIDs first (`test_route_pattern_normalizes_whole_uuids`). Crawl Maze has no UUID paths, so it is unaffected.

### 3.2 Results after the UUID fix

| | W0: control | W2: strongest config | W2 final code |
|---|---:|---:|---:|
| Transitions observed | 13 | 13 | 13 |
| Browser actions (exploration + replay) | 94 | 107 | 67 |
| Elapsed (s; exploration exhausted the app) | 34 | 41 | 25 |
| Listener observations / candidates / handler revisions | – | 24 / 0 / 0 | 24 / 0 / 0 |
| DevTools time per observation | – | 18.7 ms (largest DOM 85 elements) | 19.1 ms |
| Framework probe: React handler elements / outside snapshot | – | 13 / 3 | 13 / 3 |
| Request structures observed | 5 | 5 | 5 |
| Replays attempted / validated | 6 / 0 | 8 / 0 | **0 / 0** |
| Replay failures | 6 × `state_mismatch` | 8 × `state_mismatch` | none (13 workflows not replayed: state-changing) |
| Canvases in the database after the run (2 seeded) | 17 | 19 | 11 |
| Missing Graph A evidence / incorrect merges | 0 / 2 | 0 / 2 | 0 / 2 |

**What generalized.**
- Exploration covered both screens (canvas list, canvas editor), the toolbar, canvas navigation, the create and invite forms, and their API calls: 5 distinct request structures, including `POST /api/canvases [name] json` and `POST /api/canvases/{instance}/invite [identifier] json`.
- Session identity held: every observation was in the authenticated context.
- `Log out` and the toolbar's `Delete` were never executed. The safety pattern now matches the two-word "Log out" as well as "logout" and "sign out", closing a gap found during this setup.
- The listener observer was cheap (85-element pages). As §2 predicts for React, it found **no** direct-listener candidates and attributed nothing to the root.

**What did not generalize.**
- **No replay reproduced anything.** Every recorded workflow begins with `+ Create canvas`: exploration's first action created a canvas and navigated into it. The form has no `method`, so Agent 1 classifies it as a GET form, but React's `onSubmit` sends a `POST`.

  Replaying any workflow therefore created another canvas with a new id. The replay failed `exact_url` honestly, and each attempt added a canvas (W0 17, W2 19).
- **The fix in this milestone.** Under the structure policy, a workflow is not replayed by either lane, without `allow_post_forms`, if any of its exact recorded prefixes issued a non-GET request. The check is keyed by the workflow path, not the action label: on Crawl Maze a read-only "Submit" shares its label with POST-issuing ones.

  With the final code, W2 replays nothing on this app. It reports all 5 structures as `not_attempted` / `state_changing_workflow`, and replay creates no records (the database ends with 11 canvases, 9 created by exploration).

  An offline check of the three R2 Crawl Maze runs confirms the rule excludes none of their 21 replays each, so those results are unchanged.
- **Exploration still changes state.** The first submission of a GET-looking form that actually POSTs cannot be predicted from the DOM. Exploration also re-submitted these forms from new states: 9 canvases and several invites per run in an isolated database.
- **Merge audit.** It flags 2 state groups, each merging several canvas records under one template: the same route pattern, title and 8 safe controls. This was not diagnosed further in the time available.

## 4. Live browser time

| Activity | Minutes |
|---|---:|
| Replay-lab probes (4 runs) | 2.0 |
| React and CDP-cost probes | 0.6 |
| Crawl Maze 3 × 3 (16:49:39–17:14:46) | 25.1 |
| Whiteboard: v1 (2 runs), v2 (2 runs), final (1 run) | 3.3 |
| **Total** | **≈31** of 35 |

Deterministic test runs are additional:
- replay-lab end-to-end tests: about 1.5 min per run;
- the full suite: about 10 min.

## 5. Next architectural improvement: ranked

Ranked by measured impact and how far it generalizes.

1. **Stateful prerequisites and state-changing actions.** This had the highest measured impact on the unfamiliar app: 0 of 5 structures reproducible, and data created on every replay before the fix.
   - Replay cannot reproduce a workflow whose prerequisite creates a record.
   - Exploration cannot tell a GET-looking form that POSTs until it has submitted it.

   Smallest next steps:
   - after one observed non-GET effect, treat that exact workflow step as state-changing for exploration too (not only replay);
   - verify read-only behaviors from a restored *existing* record. For example, open an existing canvas rather than creating one, using record identity from Graph A.

   This applies to any CRUD application.
2. **Replay scheduling.** Partly done: 0 → 3 of 3 runtime transitions and 0 → 6 of 11 structures on Crawl Maze.
   - The remaining Crawl Maze gap is the five POST/PUT structures.
   - Its value now depends on item 1: on real applications most interesting structures sit behind state-changing steps.
3. **Framework-specific interaction discovery.** Measured impact on React was 0 here: every click handler was on a semantic control, and the only gap was a drawing gesture. The probe now records the gap per page. Revisit it when an application shows a large `outside_snapshot` count.
4. **Delegated event discovery** (non-React, document-level). Not measured on a real application in this milestone. On the fixtures it is correctly reported and never attributed.
5. **Large-DOM observation cost.** It is bounded by the new guard and is negligible on all real targets measured (at most about 19 ms per observation).
6. **Closed shadow roots and cross-origin frames.** Not encountered on any real target. They remain reported as skipped.
