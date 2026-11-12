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

New read-only capability **`agent1/canvas_probe.py`** (`introspect_canvas_graph(page)` / `probe_url(url)`):
for a LiteGraph app it reads `window.LiteGraph.registered_node_types` (the full operation catalog) and
`app.graph._nodes` (placed nodes + widgets). **Validated live on comfyui: 543 registered node types**
(`KSampler`, `CheckpointLoaderSimple`, `CLIPTextEncode`, `VAEDecode`, `SaveImage`, `LoadImage`, …) — a rich
functionality inventory where DOM crawling found zero, obtained with **no interaction and no risk**.
Unit-tested (`test_canvas_probe_introspects_litegraph_model`); returns `None` (reported honestly) for a
canvas with no introspectable model.

**Honest scope:** this *enumerates* canvas functionality (the high-value, safe first step) and is
framework-specific (LiteGraph today; extensible to other graph frameworks by their globals). *Driving* the
graph — adding/wiring/executing nodes — remains a separate, larger capability and is not attempted here.
