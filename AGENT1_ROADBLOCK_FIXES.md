# Agent 1 — General-traversal roadblock fixes (Stage 3)

Written for: the EngramSec research owner. Branch `agent1-browser-mapper-20261028`.
**No model tokens. Opt-in flags, default-off (frozen WebExploitBench baseline byte-for-byte preserved).
No safety/scope/replay-floor relaxation.**

## TL;DR — the "poor WebExploitBench performance" was largely a *protocol configuration*, not missing capability

The guiding question was whether Agent 1 does poorly on the WebExploitBench (Track B) real apps, or
whether the evaluation was unfair. Diagnosed on the **one measurable SPA fixture** (`js_heavy_lab`,
ground-truth recall), the answer is mostly **the evaluation under-configured the agent**:

| configuration | recall | what it recovered | lever |
|---|---|---|---|
| frozen WebExploitBench protocol | **3/13 (0.21)** | static nav links only | — |
| + `robust_readiness` | **8/13** | the entire chained-JS SPA chain | **existing flag, was OFF** |
| + `loopback_origin_equivalence` | **10/13** | cross-spelling (`localhost`↔`127.0.0.1`) links | **new (15 lines)** |
| + authorized-write login | **13/13** | the POST-login → authenticated surface | **existing path, not provisioned** |

Two of the three levers were **capabilities the frozen protocol disabled** (`robust_readiness` off;
no authenticated session / no writes). Only one small piece was genuinely new code. This confirms the
hypothesis that the headline Track-B numbers understated the agent.

## Roadblock #1 (client-rendered SPA) — diagnosed, fixed, measured

### Root causes (empirical, on `js_heavy_lab`)
The server-side request oracle showed the frozen run only ever hit `/`, `/shallow/a`, `/shallow/b`.
Three independent causes, each general:

1. **Hydration is never awaited.** Readiness waiting is gated behind `robust_readiness`, which defaults
   **off** and is off in the frozen protocol — so every page gets a flat `settle_ms` (350 ms) wait.
   `js_heavy_lab` enables its controls via a **650 ms** bootstrap fetch and injects a late button at
   **800 ms**. Proof: `/api/bootstrap` is **never** requested under the frozen config, but a plain
   1200 ms Playwright wait fires it and enables everything. The agent was observing every page
   *before it hydrated*, seeing only disabled controls, and tearing the page down.
2. **Origin canonicalization gap.** The one alias link targets `http://localhost:PORT` while the server
   binds `127.0.0.1`. `origin_tuple()` compared raw hostnames, so `localhost ≠ 127.0.0.1` → the link
   was treated as cross-origin and skipped.
3. **Descent already works.** `_enqueue` already turns buttons into frontier items, and after any click
   the result page's newly-revealed controls are enqueued. So once a control is *visible and enabled*,
   the agent clicks it and descends the injected chain. **Nothing to build there** — it was gated purely
   on #1 making controls visible. (Confirmed: with readiness on, the full
   `open_workflow→continue_setup→open_workspace→workspace_detail` and `load_late_reports→open_reports`
   chains fire.)

### What was changed
- **`robust_readiness`** — *no code change*; it is an existing, correct hydration-wait mechanism that the
  evaluated protocol left disabled. Re-enabling it is the fix for the SPA chain (+5 caps). The fixed
  readiness strategy suffices; `adaptive`/`extended` added nothing on this fixture.
- **`loopback_origin_equivalence`** (new, opt-in, default-off; `agent1/schema.py`). When on, it expands
  the start URL's loopback siblings (`127.0.0.1` / `localhost` / `::1` at the **same scheme+port**) into
  the existing *explicit* alias set. It reuses the declared-alias path, so **scope is never implicitly
  widened** — verified it rejects other ports, other schemes (`https`), and all external hosts
  (`tests/test_loopback_origin.py`, 7 tests).
- **`ignore_https_errors`** (new, opt-in, default-off). A general option for when Agent 1 is pointed
  directly at a self-signed-HTTPS app. **Correction after checking the harness:** the WebExploitBench
  `targetctl` exposes each target as **HTTP on a loopback port** (`http://127.0.0.1:PORT`), so HTTPS/certs
  is *not* the Track-B blocker — this flag is a general nicety, not a WebExploitBench fix. Playwright's own
  default is `False`, so default-off is byte-identical.

### Measurements
- **Recall `js_heavy_lab`: 3/13 → 13/13** (attribution in the table above). The authorized-write +3 only
  applies under an operator-attested **disposable** environment — see boundaries below.
- **No regression on server-rendered sites** (readiness off vs on, 120 s budget, same frozen config):

  | fixture | Δ states | Δ transitions | note |
  |---|---|---|---|
  | replay_lab | +0 | +0 | finished before budget; identical discovery |
  | coverage_lab | **+1** | **+4** | hit budget; readiness-on found *more* |
  | heldout_shop | +0 | +4 | — |

  On these *small* fixtures readiness adds 56–82 s of cumulative wait but coverage never drops. **This was
  misleadingly benign — see the refutation below.**

### ⚠️ Refutation on a real SPA: `robust_readiness` is NOT a safe blanket default
A real-SPA generalization run on WebExploitBench **`white-jotter`** (Vue, HTTP-loopback, frozen 180 s
config) **contradicts** the dev-fixture no-regression:

| arm | states | workflows | wall |
|---|---|---|---|
| A frozen | 16 | **72** | 157 s |
| B + `robust_readiness` (fixed) | 15 | **34** | 185 s (hit budget) |

`robust_readiness` **halved** reachable workflows (275 → 141 actions). Cause: the *fixed* readiness
strategy applies a ~1.6 s hydration wait to **every** page, and a large real SPA has hundreds of pages
whose dynamic chrome never fully settles, so the time budget drains into waiting instead of exploring.
The small dev fixtures (16–23 states, often finishing before budget) could not surface this.

**Conclusion (corrected):** readiness helps where functionality is *hydration-gated* (`js_heavy_lab`:
+5) and hurts where functionality is *already in the DOM* and the wait is pure tax (`white-jotter`: −38).
A general tool needs a readiness wait that is **cheap when not needed** — tightly bounded, evidence-gated,
exiting as soon as the actionable control shape is stable. Whether the `adaptive` strategy (shorter,
mutation-gated window) achieves this without losing the `js_heavy` gain is **under active measurement**;
until it does, `robust_readiness` stays opt-in and must not be defaulted on for breadth-heavy sites.

### ✅ Resolution: `readiness_any_enabled` makes readiness cheap-when-not-needed
Instrumenting white-jotter's readiness calls showed the tax precisely: of 53 calls, **every page had
enabled controls (53/53) and none was genuinely hydrating (0/53 aria-busy or disabled-only), yet 33/53
took the slow ~840 ms hydration path** — because their controls render *outside* a semantic `<main>` and
the "usable" test keyed off `main_enabled_control_count == 0`.

Fix (opt-in, default-off): **`readiness_any_enabled`** keys the usable-page test off *any* enabled
control, not just those inside `<main>`. Pages that are already rendered exit at the cheap stability
wait (~300 ms); pages with no enabled controls (or disabled-only / aria-busy) still wait for hydration.
Genuinely-pending pages are unaffected because the `initializing` guard already catches disabled/aria-busy.

Validation (one run each; js_heavy read-only recall, white-jotter workflow reachability):

| fixture | frozen | naive readiness | **readiness + `any_enabled`** | +adaptive |
|---|---|---|---|---|
| js_heavy_lab (recall) | 3/13 | 10/13 | **10/13** (kept) | — |
| white-jotter (workflows) | 51 | 23–34 (**−33%**) | **54** (+6%) | **56** (+10%) |

So the readiness lever **is** now general: it recovers hydration-gated SPA functionality *and* no longer
taxes breadth-heavy real SPAs. The regression was caught only because the fix was tested on a real app,
not just the small dev fixtures — the dev-fixture no-regression check was necessary but not sufficient.

### Recommended "general-web" configuration
For traversing arbitrary sites (SPA or server-rendered), enable together, all opt-in:
`robust_readiness=True, readiness_any_enabled=True, readiness_strategy="adaptive",
loopback_origin_equivalence=True` (+ `ignore_https_errors=True` only when pointed at a self-signed HTTPS
app; + `storage_state_path` for authenticated surface). All default-off; the frozen baseline is preserved
when they are not set.

### What IS safely general
`loopback_origin_equivalence` and `ignore_https_errors` are safe by construction (they only add
same-origin spellings / a cert tolerance; verified no scope widening, default-off). `readiness_any_enabled`
only *reduces* readiness wait and cannot lower coverage on the server-rendered dev fixtures (which already
showed no-regression with the more expensive readiness).

## Honest boundaries / what is *not* solved by this

- **Live-app login needs provisioning, not blind POST.** The +3 member-flow recovery used the
  disposable-write path (`write_policy=disposable` + attestation), legitimate only on throwaway test apps.
  For real third-party apps the agent **never types credentials**; the existing, correct mechanism is
  `storage_state_path` (operator provides a pre-authenticated Playwright session). The frozen protocol
  simply ran unauthenticated. This is roadblock #2 and is a *provisioning* task, not a capability gap.
- **Measurement is the genuinely hard gap (roadblock #3).** Track B apps have **no ground truth**, so even
  with these fixes we can report richer *inventories* but not a coverage %. The only way to *prove* SPA
  gains on realistic apps is measurable SPA fixtures; `js_heavy_lab` is the current one.
- **Canvas/WebSocket apps (comfyui) remain hard.** Hydration-waiting helps DOM-constructed controls; it
  does not enumerate a `<canvas>` driven over WebSocket. That is a separate mechanism.

## Safety / invariants preserved
All three flags default **off**; with them off the explorer reproduces the frozen baseline exactly
(`js_heavy_lab` 3/13, `breadth_starved_lab` 30/50). `loopback_origin_equivalence` only adds same-machine
loopback spellings (never a different host/port/scheme). No writes are enabled by #1's fixes; the write
path keeps its disposable-attestation gate. 44+ explorer/write-policy/readiness tests green plus the 7 new
loopback tests.

*Artifacts: `agent1/schema.py` (`readiness_any_enabled`, `loopback_origin_equivalence`,
`ignore_https_errors`), `agent1/explorer.py`, `tests/test_loopback_origin.py`,
`tests/test_agent1_browser.py` (behavioral readiness test). Committed as `584b61c` (not pushed).*

## Roadblock #3 (measurement) — made provable with a second measurable SPA

Track B has no ground truth, so SPA gains could only be *inferred*. Added `development_apps/spa_router_lab.py`
— a client-rendered SPA with **client-side `pushState` routing**, controls **outside `<main>`**, delayed
hydration, nested interaction-gated controls, and a member-cookie role dimension. Each client view fires a
tracking GET, so the server log is a clean capability oracle. Deliberately unlike `js_heavy_lab` so passing
it is real generalization.

Benchmark (`evaluation/spa_router_benchmark.py`), baseline vs general-web config:

| arm | anonymous recall | note |
|---|---|---|
| A frozen | **1–2/10** | nav disabled pre-hydration; only `/` reached |
| B general-web | **10/10** | every pushState view + nested control reached |

This both confirms the agent **handles pushState SPA routing** and gives a *provable* 1→10/10 coverage gain
independent of `js_heavy_lab`. Committed as `dfc0b95`.

## Roadblock #2 (auth) — the mechanism exists (`storage_state_path`); provisioning is the real work

Agent 1 never types credentials; authenticated surface is reached via an operator-provided Playwright
session (`storage_state_path`). Proven measurably on `spa_router_lab`:

| arm | anonymous | member | total |
|---|---|---|---|
| general-web (no session) | 10/10 | 0/2 | 10/12 |
| general-web + `storage_state` | 10/10 | **2/2** | **12/12** |

**Live-app finding (white-jotter):** an **API-only** login (`POST /api/login`, which succeeded with the
seed account `admin`/`123`) set the Shiro **session cookie** but did **not** unlock the admin surface —
because the Vue frontend gates login state on **client state** (`localStorage['username']`,
store/index.js), not the cookie. Injecting the cookie **and** `localStorage['username']` *still* did not
surface the admin menu (workflows 55 → 56) — the admin link is additionally gated on the user's **role**
(fetched into the Vuex store), which a reconstructed partial session does not carry. **General lesson for
SPA auth provisioning:** the operator session must capture the app's **complete client auth state
(cookie + localStorage + any role/token in the SPA store)**, which in practice means a genuine **UI
login** before saving `storage_state` — not an API call or a hand-built partial session. The agent
mechanism (`storage_state_path`) is proven on the fixture (0/2 → 2/2); live provisioning is
**app-specific**, and this characterizes what it requires — not an agent capability gap.

**Resolution — a UI-login helper (`agent1/auth_capture.py`).** `capture_login_session()` drives a real
login form in a browser (auto-detecting username/password/submit fields, or using given selectors) and
saves the **full client state — cookies *and* localStorage/sessionStorage** — to a `storage_state` file the
operator passes to `storage_state_path`. Running the app's own login code captures exactly the client state
a token/role-gated SPA needs. Unit-tested (`test_ui_login_helper_...`) and **validated live on
white-jotter**: UI login (`admin`/`123`) redirected to `/admin/dashboard` and captured
`localStorage['username']` + 2 cookies; the authenticated agent run then reached **39 states vs 18
anonymous** (2.2×) — traversing the authenticated/admin surface the anonymous run could not. (The agent
still never types credentials; this is the operator-side provisioning step.)

## Roadblock #4 (canvas/WebSocket, comfyui) — reframed: it is NOT a canvas wall

The frozen agent gets **1 state / 0 controls** on comfyui, and the general-web config + WS capture did not
change that. But a **plain browser left open ~15 s sees 47 enabled DOM controls** — a real toolbar
(`Manager`, `Run`, `Share`, `Unload Models`, workflow controls …) plus 2 canvas elements and a WebSocket.
So comfyui is **not** pure canvas; it has a mappable DOM surface that builds slowly from a heavy JS bundle.

Two precise findings:
1. **Readiness patience was the first blocker, and is fixed.** The agent observed comfyui's empty shell at
   ~2.5 s and gave up. New opt-in **`readiness_await_content`** keeps readiness waiting (bounded by
   `readiness_timeout_ms`) while a scripted page still exposes **no** actionable control. Verified it waits
   (instrumented comfyui run: 15 s, 144 samples) and unit-tested (`test_readiness_await_content_...`).
2. **The real blocker: Agent 1's own read-only write policy halted comfyui's init — now fixed.** Capturing
   the agent-context console revealed `net::ERR_ACCESS_DENIED` on `PUT /api/settings/Comfy.InstalledVersion`
   → `TypeError: Failed to fetch at ComfyApi.storeSetting`. comfyui performs a **benign write during
   startup** (stores a setting); the read-only write policy (`effective_write_policy="read_only"`, enforced
   by default) **aborts** that request, the rejected `fetch()` throws, and comfyui's whole init chain halts
   — so the DOM toolbar never builds. A plain browser lets the PUT through, so it builds. Diagnosis path
   ruled out viewport, launch args, readiness poll frequency, the readiness MutationObserver, and the
   `NetworkRecorder` — all reproduced fine in a plain context; only the write abort did not.

   Fix — opt-in **`neutralize_blocked_writes`**: a denied write is **fulfilled with a synthetic empty
   success instead of aborted**. The server still never receives the write (identical safety: the request is
   intercepted, never forwarded), but the page's `fetch()` resolves so init proceeds. Result: comfyui goes
   from **1 state → 14 states** (14 actions executed) — the agent now initializes and actively traverses it.
   Unit-tested (`test_neutralize_blocked_writes_...`); default off preserves the abort baseline.

   A second, independent drop: when the scope router *is* active (production config via `acg_evidence`), it
   aborted comfyui's same-origin **`blob:` module scripts** (a `blob:` URL's origin is the page itself, but
   `allowed_origin` judged it cross-origin). Fixed so the router passes `blob:`/`data:`/`about:` pseudo-URLs
   (they contact no server); unit-tested (`test_scope_router_allows_blob_url_scripts`).

**Remaining boundary:** comfyui now initializes and its DOM toolbar is traversable (14 states), but
`functional_workflows=0` — its controls are client-view-change buttons/dialogs over a canvas, not
server-round-trip workflows. The LiteGraph `<canvas>` node-graph itself is still not DOM-enumerable and
needs coordinate-based canvas interaction (a separate, larger capability); the WebSocket is capturable as
evidence, not as driven workflows. But the context-init blocker — the thing that made comfyui a flat zero —
is resolved.

## Roadblock #5 (canvas node-graph) — enumerated via framework introspection, not blind clicking

The canvas node-graph itself (LiteGraph in ComfyUI) is not in the DOM, so DOM crawling maps **0** of it.
Blind **coordinate-based clicking** on a canvas is both unreliable and **unsafe** (it can trigger arbitrary,
possibly destructive, actions), so it is deliberately not done. The tractable, safe path is to read the
app's **own graph model** through its JS globals.

New capability **`agent1/canvas_probe.py`**, covering both the enumeration and the driving frontier:

**(a) Extended introspection beyond LiteGraph.** `introspect_canvas_graph(page)` detects the graph
framework and extracts its model: **LiteGraph** (ComfyUI — `registered_node_types` catalog + `graph._nodes`),
**Cytoscape.js** (`window.cy`), **vis.js Network** (`window.network`), **React Flow** (its DOM nodes/edges),
plus a **generic `window` sweep** for any editor stored on a global that exposes a graph shape
(`._nodes` / `.nodes` / `.getNodes()` / `.model.nodeDataArray`). It reports which frameworks are present
even when a model is not reachable, and returns `None` honestly when there is no canvas/graph. Unit-tested
against React Flow, a generic-global editor, and Cytoscape mocks (`test_canvas_probe_extends_beyond_...`).

**(b) Driving the graph (safely).** `drive_node_schemas(page)` instantiates each registered node type
(`LiteGraph.createNode`) and reads its **full live I/O contract** — typed input/output ports and widgets
with defaults; `demonstrate_drive(page)` proves the graph is drivable by **adding then removing** a node.
This is client-side only: it **never executes the graph** (no `queuePrompt`), never reaches the server, and
restores the graph to its prior state. Unit-tested (`test_canvas_probe_drives_...`).

**Validated live on comfyui:** framework auto-detected (`litegraph`); **543 registered node types**
enumerated; **25/25 sampled node types instantiated with full I/O schemas** (e.g. `KSampler` → 10 typed
inputs MODEL/CONDITIONING/LATENT/INT/FLOAT/COMBO, output LATENT, 7 widgets with defaults); the add→remove
drive demo succeeded (node count 0→1→0, graph restored) — all where DOM crawling found zero, with no
execution and no risk.

**(c) Executing the workflow (authorized), with a RED roadblock when blocked.** `execute_canvas_workflow`
runs the app's workflow (ComfyUI `POST /prompt`) — a real server side-effect, so it is **double-gated**:
the opt-in `allow_canvas_execution` flag **and** a write policy that permits the POST (disposable env +
operator attestation), exactly like every other write. In an authorized (attested) engagement it fires and
captures the server's response; otherwise it records a **RED roadblock marker** (`as_red_node()`) for the
blocked capability — and can **inject a visible red annotation node into the canvas** — instead of silently
skipping it, so the operator sees exactly what functionality is gated. Default off.

**Validated live on comfyui:**
- *Unauthorized* (`read_only`): `roadblock=True`, `color=RED`, not executed; the RED marker names the
  capability (`canvas_workflow_execution`) and endpoint (`/prompt`), and a red node was injected into the
  graph (`injected: true`).
- *Authorized* (`disposable`): the real `POST /prompt` fired and the server responded (`400
  prompt_no_outputs` on the empty default graph — i.e. the execution endpoint was reached and processed the
  input; a loaded workflow would run). This is the full security-relevant capability, under the existing
  write-authorization contract.

**Honest scope:** enumeration and schema reading are read-only and always on; graph *driving* (add/remove)
is client-side and reversible; workflow *execution* is a real write, gated behind `allow_canvas_execution`
+ disposable attestation, with a RED roadblock recorded when not authorized. Generic-sweep extraction is
best-effort for frameworks that keep their instance off a global.


## Roadblock #6 (interactive exploration / write-chaining) — the biggest remaining layer

**Problem.** After the SPA/auth/canvas fixes, the residual misses on the measurable fixtures were all
*interactive*: controls that only appear or only fire after a prior action (multi-step), handlers wired in
script rather than in HTML attributes (listener `<div>`s, redefined handlers), and writes performed by a
JavaScript handler so the form's DOM method stays `GET`. ZAP's **Crawlground** testbed measures exactly
this axis.

**What actually moved the needle.** Most of this layer was unlocked by *composing capabilities the frozen
benchmark config left off* — one genuinely new, two existing:

1. **`runtime_listener_observation="revisit"`** (existing). The DOM snapshot recognizes controls by
   semantics (links, buttons, ARIA, inline handlers). It cannot see a plain `<div>` that got a listener via
   `addEventListener`, nor a control whose handler was *replaced* in place. The opt-in DevTools listener
   observer can, and `revisit` re-fires a control whose handler changed. This is what the residual
   `replay_lab` misses needed (listener-`<div>` chains; a button redefined after first click).
   → **replay_lab 17/22 → 21/22** (only the destructive `wipe_records` remains, skipped by design).

2. **`exploration_mode="persistent"`** (existing). `fresh` mode restores each action by *replaying a path
   from the start*. On a **stateful** app the list page mutates (a create/counter inserts a row), so the
   replayed source state no longer matches and the attempt is abandoned *before the control is even
   clicked* — which is why `view_record`/`create_record`/`update_record` never fired. Persistent mode
   explores from the live state (click → observe → go back), so a drifting page is no obstacle.
   → **stateful_lab 3/7 → 6/7** (only the destructive `delete_all` remains). Verified with the correct
   per-benchmark oracle that persistent mode does **not** regress the SPA fixtures (js_heavy 13/13,
   spa_router 12/12 in both fresh and persistent) — an earlier "regression" was an artifact of an ad-hoc
   scorer that stripped `?r=…` query routes; the dedicated `spa_router_benchmark.py` oracle is correct.

3. **`execute_js_driven_writes`** (NEW, opt-in, default off). The authorized write sweep used to promote a
   control only if its *DOM method* was non-GET (`<form method=post>`). A write done from a handler
   (`fetch(url,{method:'POST'})` wired in a `<script>`) leaves the form's method `GET`, so the sweep never
   promoted it — the write was deprioritized in discovery *and* invisible to the sweep. The new flag makes
   SAFE, same-origin `form_submit`/`button` controls promotable candidates, **only** on an attested
   disposable environment; the live write gate + `would_allow` still bound the real request (write cap,
   destructive-route block) and `control.safe` already excludes destructive labels. On the small fixtures
   the writes fire in persistent discovery (so the flag is redundant there), but on a larger app where such
   a write is deferred past the discovery budget to the sweep, this flag is the only thing that executes it
   — verified on a controlled fixture (sweep `promotable` 0→1 and the `POST` fires). With the flag off the
   sweep predicate is byte-identical to the frozen baseline
   (`tests/test_agent1_browser.py::test_execute_js_driven_writes_promotes_get_method_handler_writes`).

**Recommended config** (all opt-in; frozen baseline byte-identical when unset):
`exploration_mode="persistent", runtime_listener_observation="revisit", robust_readiness=True,
readiness_any_enabled=True, readiness_strategy="adaptive", loopback_origin_equivalence=True,
neutralize_blocked_writes=True, allow_post_forms=True, write_policy="disposable",
write_execution_policy="focused_adaptive", execute_js_driven_writes=True` (+ `storage_state_path` for an
authenticated surface). This one config maxes every measurable fixture.

### Measurable fixtures — frozen → corrected (persistent + listener + jswrite)

| fixture | kind | frozen | corrected | remaining miss |
|---|---|---|---|---|
| js_heavy_lab | SPA, 2 roles | 3/13 | **13/13** | — |
| spa_router_lab | SPA, pushState, 2 roles | 1/12 | **12/12** (10/10 anon + 2/2 member) | — |
| replay_lab | listener/multi-step | 17/22 | **21/22** | `wipe_records` (destructive, by design) |
| stateful_lab | CRUD + destructive | 2/7 | **6/7** | `delete_all` (destructive, by design) |

Every non-destructive capability is now covered; the only misses are the two intentionally-skipped
destructive ops (they would fire under `allow_destructive` in an authorized disposable run).

### External benchmark — ZAP Crawlground (interactive-control coverage, server-scored)

59 pages, one control each (button, link, form, JS event, frame, multi-step); reaching the hidden
`/score/<cat>/<id>` marker *through* the control scores it. The ZAP website publishes ~76% for its **three
spiders combined** (standard + AJAX + client).

**Agent 1, interactive config: 54/59 = 91.5%** — a single config, no per-run tuning, well above ZAP's
three spiders combined (45/59). Reached by two opt-in capabilities built for exactly the faults below:

- **`exhaustive_local_controls`** — on each reached state the persistent loop exercises that state's OWN
  novel controls first (not letting the standing form/write deprioritization strand a leaf's effect
  control) before paying restoration for global breadth. Fixes the "page mapped, its one control never
  driven" starvation.
- **`follow_client_navigation`** — after an action settles, a page whose only behaviour is to navigate
  (meta-refresh, a `setTimeout`→`location`, `window.replace`, hash/pushState routing — detected because it
  has no non-chrome actionable control, or a refresh meta) is followed via a bounded same-origin URL poll,
  recorded as a navigation transition.

Together they took the crawl 35 → 43 (`eager_child_expansion`) → **54/59**: buttons 2/2, frames 4/4,
js-events 14/14, forms 11/12, dynamic-content 9/10, links 5/7, **navigation 9/9**. The 5 residual are
genuinely out of scope for a functional crawler: WebSocket-injected URL, `<noscript>` (contradictory with
JS on), image-map `<area>`, an auto-`requestSubmit`, and the deliberate bot-detection trap. Earlier passes
scored lower only because the whole-site crawl left each leaf's control unexercised — a leaf-isolation probe
(starting Agent 1 directly on the "missed" pages) exercised the large majority correctly, which is what
motivated these two capabilities.

### External benchmark — Google Security Crawl Maze (resource discovery)

A deep directory tree of 84 (+7 framework-SPA, Docker-only) pages, each linking a `.found` marker via a
different mechanism (href, src, srcset, CSS, meta, headers, JS). Scores *resource extraction* — a different
axis from Agent 1's functional focus; the resource spider is the relevant subsystem.

**Agent 1 on the full Docker image: 62/91 = 68.1%** (css 1/1, headers 3/4, html 37/57, javascript 14/20,
misc 2/2, **framework-SPA 5/7**). The Docker build bundles the Angular/Polymer/React single-page apps, and
Agent 1's SPA config (persistent + listener + hydration wait) renders and exercises them — recovering 5 of
the 7 framework cases (Angular event-handler + router-outlet, Polymer event-handler + router, React
route-path; misses `angularjs/ng-href`, `react/.../search`). On the Flask-only subset (no framework build)
the same crawl scores **57–58/84 ≈ 69%**. Extraction itself is solid — a single-page probe confirms
`<a href>`, `<img src/srcset>`, `<link href>`, `<meta>` are all extracted when a page is reached. The
remaining misses are (a) deep pages not reached within budget, (b) rare/legacy attributes the spider does
not parse (`applet archive/codebase`, `object codebase`, `img dynsrc/lowsrc/longdesc`, `isindex`, `a ping`,
`background`), (c) resources referenced only inside JavaScript strings, and (d) interactive-write cases
(`js-post`, `js-delete`) that the *read-only* discovery config intentionally blocks. **62/91 matches the
prior 63/91 within one case — no regression.**
