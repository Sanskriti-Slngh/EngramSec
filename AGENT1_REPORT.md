# Agent 1 — System Report

*The single source of truth for what Agent 1 is, how it works, what it is safe to do, and how it performs.
Branch `agent1-browser-mapper-20261028`. Operational usage (install, commands, output files) is in
[README.md](README.md); this document is the architecture, safety model, capabilities, and measured results.*

---

## 1. What Agent 1 is

Agent 1 is a **deterministic, safety-bounded browser functionality mapper**. Given a start URL (and optional
operator-provided authentication), it drives a real Chromium browser over an unfamiliar web application and
emits a model of **what the application can do** — not just its pages. It runs **no LLM in the mapping loop**:
every decision is a reproducible heuristic. It never reads the target's source code; all evidence is
browser-observed.

It produces two artifacts per run (`agent1/exporter.py` + `agent1/model/`):

- **Graph A** — the evidence graph. `states` (grouped observations), `actions_evidence` (executed controls
  with network traces), `functional_workflows` (multi-step chains), `features`, `edges`
  (state→action→state), `record_instances`, and `advertised_unexecuted` (controls seen but not run). Every
  executed action can be independently **replayed** to confirm it reproduces its requests.
- **ACG (Action/Agent-Capability Graph)** — distinct *capabilities* abstracted over route templates and
  session contexts: `operations` (the API surface: method + route + params), `capabilities` (role +
  operation + effect), `affordances` (UI controls bound to capabilities), entity types/instances, claims,
  and evidence gaps. This is the "what can this app do, and for which role" inventory that downstream
  security tooling consumes.

**Guarantees.** No model inference in the loop (`model_provider: none`). Strictly scoped to the start origin.
Writes gated by a **write policy** (`read_only`, or attested `disposable`); destructive routes
(`/delete`, `/destroy`, `/drop`, `/reset`, DELETE methods, and localized Chinese/English destructive labels)
are never executed. Identical config + initial state ⇒ identical action sequences.

---

## 2. Running it on any website — profiles

Point Agent 1 at an arbitrary site with one preset instead of a dozen flags (`agent1/profiles.py`):

```bash
python -m agent1.cli map --url <any-site> --out <dir> --profile general
```

| profile | writes | use |
|---|---|---|
| **`general`** | none (read-only) | **Safe on any site, including production.** The validated general-web traversal set (below). This is the default choice for "map this site." |
| **`pentest`** | disposable, authorized | `general` + write-chaining (form POSTs, disposable write policy, focused-adaptive write execution, JS-driven writes). **Mutates the target** → requires `--attestation "disposable: <why>"`; disposable/authorized targets only. |
| **`default`** | none | Frozen baseline — every opt-in capability OFF. Hand-tune individual flags here. |

Authenticated surface is reached with `--storage-state <session.json>` (an operator-captured Playwright
session via `agent1/auth_capture.py`). **The agent never types live credentials** — the operator performs
the UI login once and hands Agent 1 the resulting session.

---

## 3. Architecture

```
RunConfig ─▶ Explorer.run()
  1. launch Chromium (Playwright), navigate start URL
  2. DISCOVERY (_explore / _explore_persistent)
       pop frontier item ─▶ _attempt_frontier ─▶ record observation + transition ─▶ enqueue new controls
       restoration ladder picks the cheapest safe way to re-reach an item's parent state
  3. FOCUS SWEEP (_authorized_write_sweep)        [focused_adaptive / pentest]
       after discovery, descend functional subtrees + give queued safe writes a bounded, fair turn
  4. REPLAY / VERIFICATION (ReplayScheduler)
       re-run a reserved budget of workflows to confirm they reproduce (replay_validated)
  5. write_outputs ─▶ Graph A ; import_run_artifact + materialize ─▶ ACG
```

**Key components**
- **`BrowserSession`** (`agent1/explorer.py`): `goto`/`goto_start`/`go_back` (all `domcontentloaded` +
  bounded readiness sampling), `observe` (DOM→controls snapshot), `execute` (resolves a control's locator on
  the live DOM and clicks/submits), `find_current` (matches a saved descriptor to a cached observation).
  Scope is enforced on every navigation.
- **Frontier + discovery loop.** `exploration_mode="fresh"` attempts each queued item in a fresh context;
  `persistent` explores from the live mutated state (needed for SPAs and stateful lists — it is in the
  `general`/`pentest` profiles).
- **Restoration ladder** (`_attempt_frontier`): to re-reach a parent state it tries, cheapest first — live
  reuse, prefix reuse / history return (`go_back`), a `direct_url` GET shortcut, else root reload + path
  replay. **The ladder never replays a write** (`_known_write` → `UnsafeRestoration`), so restoration cannot
  cause a state change.
- **Write policy** (`agent1/write_policy.py`): `read_only` blocks every non-GET; `disposable` allows
  bounded, logged, non-destructive writes only on an attested disposable environment, under a write cap,
  never on a destructive route.
- **Replay/verification** (`agent1/replay_scheduler.py`): a reserved fraction of budget re-executes workflows
  to prove they reproduce their application requests.
- **ACG + state identity** (`agent1/model/`, `state.py`, `action_behavior.py`): route templating, group
  signatures, record-instance identity, behavior classification (which action is a likely write / state
  change).

---

## 4. Safety model

Safety is the primary design property; it held across every benchmark and ablation.

- **Scope.** Every navigation is checked against the start origin (`allowed_origin`); off-scope navigations
  are blocked. `loopback_origin_equivalence` treats `localhost`==`127.0.0.1` without widening scope.
- **Destructive-never.** DELETE methods and destructive routes/labels are never executed; dangerous controls
  are skipped (crawl_maze skipped 24, crawlground skipped 197; `delete_all` refused on stateful_lab).
- **Writes are gated.** Read-only by default. The `pentest` profile's disposable writes require an
  `environment_attestation` beginning with `disposable:` (enforced by RunConfig validators) and are bounded,
  logged, non-destructive, and never replayed during restoration.
- **No credentials typed.** Authenticated runs start from an operator-provided session
  (`storage_state_path`); Agent 1 never enters a password.
- **Session-loss guard** (`session_loss_guard`, in the profiles): if an authenticated run bounces to a login
  route (e.g. an unlabeled logout icon fires `GET /api/logout`), the triggering control is blocklisted, the
  operator session is re-applied, and the login page is not crawled — so the privileged surface keeps being
  mapped instead of the budget being burned on `/login`.
- **No model inference, determinism.** Reproducible action sequences make the A/B experiments trustworthy.

---

## 5. Capabilities — the validated general-web set

Every capability below is opt-in and OFF in the frozen baseline (byte-identical when unset); the `general`
profile turns on the safe subset, `pentest` adds the writes. Rationale and tests per item:

| capability (flag) | what it fixes |
|---|---|
| `exploration_mode=persistent` | explore from the live, mutated state — SPAs and stateful lists a fresh-context replay cannot reproduce |
| `runtime_listener_observation=revisit` | DevTools listener observer makes `addEventListener` `<div>`/icon controls visible and re-fires redefined handlers |
| `robust_readiness` + `readiness_any_enabled` + `readiness_strategy=adaptive` | wait out hydration, but key "ready" off *any* enabled control (not just those in `<main>`) so a big SPA is not taxed ~1.6 s/page on already-ready pages |
| `loopback_origin_equivalence` | `localhost`==`127.0.0.1` for scope, so alias links are not skipped |
| `neutralize_blocked_writes` | a blocked write is fulfilled with a synthetic **local** 200 (server never receives it) so write-on-init SPAs still build their DOM |
| `eager_child_expansion` | batch distinct-template GET children from one parent visit → ~20% less restoration wall-time, +coverage, 0 incorrect restorations |
| `exhaustive_local_controls` | exercise each reached state's own novel controls first, so a leaf's effect control is not starved by breadth |
| `follow_client_navigation` | chase meta-refresh / `setTimeout`→`location` / `pushState` navigations via a bounded same-origin URL poll |
| `await_spa_route_change` | wait for a client-side route change before snapshotting, so a history-mode route is mapped instead of recorded as a self-loop |
| `session_loss_guard` | recover from a logout bounce on an authenticated SPA (§4) |
| `execute_js_driven_writes` *(pentest)* | promote a safe JS-handler write (`fetch(POST)` on a GET-method form) in the authorized write sweep |

---

## 6. Measured performance

### 6.1 The measurability distinction (governs every number)
- **Track A — development fixtures (measurable).** Apps we wrote with author-curated capability
  annotations → annotation recall/precision. Caveat (from the data itself): annotation-based, not
  independent ground truth; ACG "roles" are cookie-session contexts, not semantic authorization roles.
- **Track B — real third-party apps (NOT measurable).** Without capability ground truth, the percentage of
  functionality captured **cannot** be established. Reported as inventories only.

### 6.2 Track A — frozen baseline vs general-web profile
The frozen read-only comprehensive sweep (rev `4a4f819`, 180 s) understated client-rendered and write-gated
recall because those capabilities are structurally unreachable read-only. The general-web profile recovers
them on the four measurable interactive fixtures (medians; see §5 flags):

| fixture | frozen | general-web profile | remaining misses |
|---|---|---|---|
| `js_heavy_lab` (client SPA) | 3/13 | **13/13** | — |
| `spa_router_lab` (pushState routing) | 1/10 | **12/12** (10 anon + 2 member) | — |
| `replay_lab` (catalog/search/records) | 17/22 | **21/22** | 1 no-control |
| `stateful_lab` (CRUD + destructive) | 2/7 | **6/7** | the 2 intentionally-skipped destructive ops (`wipe_records`, `delete_all`) |

The broad frozen Track-A inventory (read-only) remains the reference for apps not re-run under the profile:
e.g. `crawl_maze` 64 states / 65 caps at 21 caps/min with 0 redundant actions (highest throughput);
`transfer_library` 57/70/69 with strong link/resource discovery; `coverage_lab`/`heldout_shop`/`phase2_lab`
broad SSR coverage. `eager_child_expansion` cut restoration wall-time ~20% (e.g. breadth_starved_lab
85.4→67.2 s) with +coverage and 0 incorrect restorations.

### 6.3 External crawler benchmarks (third-party, ground-truthed)
- **Google Security Crawl Maze** (resource discovery; 84 `/test/` + 7 Docker-only framework SPAs):
  **80/91 = 87.9%** on the full Docker image with thorough resource discovery (`typed_resource_spider` +
  `max_resource_depth=8` + `html_extraction="standards"`). The extractor already handled the legacy
  attributes, the DOCTYPE `SYSTEM` URL, conditional comments, HTML imports, CSP report-uris and free-text
  URL strings; the earlier 62/91 was the benchmark harness running the spider shallow (`depth=3`) and in
  `baseline` extraction. The residual 11 are not simple capability gaps: 3 are maze **scoring artifacts**
  (it expects non-RFC relative resolution), 1 is a data-URI SVG with percent-encoded `xlink:href`, 1 is the
  read-only-blocked `js-delete` (Agent 1 never fires DELETE — principled), 2 are execution-gated multi-step
  JS, and 4 are framework-SPA rendering. A genuine scanner bug surfaced and was fixed: the free-text URL
  scanner matched only a single `../` segment, so `../../x` strings were invisible.
- **ZAP Crawlground** (59 interaction-gated controls): markers register only when a control is driven with a
  request that passes the test's `scoreWhen` guard (correct form values, method and sequence), so the score
  is **high-variance** across runs — the agent fully explores it (200+ states) but which value/sequence-
  gated markers register varies. A real efficiency regression was found and fixed here: `await_spa_route_
  change` paid the full 1500ms route-settle on every non-navigating click, and Crawlground's controls fetch
  and stay put — this burned ~70% of the exploration budget (132 vs 224 transitions in the same wall-clock).
  The poll now breaks shortly after the click's network response (keeping the SPA-capture and fetch-then-
  navigate patterns). Best observed single-config score is 54/59 (`navigation` 9/9, `js-events` 14/14,
  `forms` 11/12); the 5 structural residual are out of scope for a functional crawler (WebSocket-injected
  URL, `<noscript>` with JS on, image-map `<area>`, auto-`requestSubmit`, a bot-detection trap — the last
  deliberately not defeated). Crawlground's destructive `/reset` is blocked, so Agent 1 never wipes scores.

### 6.4 Track B — real apps (inventories only)
prestashop, comfyui, siyucms, jetlinks, white-jotter: Agent 1 *runs* against real stacks within scope and
safety, but **no coverage % can be claimed**. comfyui's context-init write-abort and canvas model are
handled by `neutralize_blocked_writes` + `agent1/canvas_probe.py` (client-side node introspection; execution
double-gated). SPA/login walls limit blind runs.

### 6.5 Case study — white-jotter authenticated mapping → downstream relevance
Anonymous: 23 states / 6 routes; ACG 43 capabilities / 9 operations. With an operator admin session
(`--profile pentest --storage-state`, `session_loss_guard` on), the logout trap was caught and the session
restored (**root reloads 426→80, readiness wait 153 s→68 s, `/login` observations 26→12**), letting the same
budget exercise every backoffice section. The **combined (anonymous + admin) ACG = 71 capabilities / 16
operations / 2 roles**, newly surfacing the privileged `/api/admin/role{,/menu,/perm}`, `/api/admin/user`,
and `/api/authentication` reads.

Mapped against white-jotter's 7 benchmark vulnerabilities (from `agent_pentest_bench`):

| vuln | location | surface | mapped? |
|---|---|---|---|
| 001 Weak creds | `/api/login` | anon | yes (anon ACG) |
| 002 Access-control bypass | `/api/admin/*` | admin | **yes — the authenticated run's new win** |
| 003 Stored XSS | `/api/admin/content/article` | admin write | partial (area mapped; write not exercised) |
| 004 RCE | `/api/admin/user` | admin write | partial (read mapped; mutation not exercised) |
| 005 SQLi | `/api/search` | anon | yes (`?keywords=`) |
| 006 Arbitrary file read | `/api/file/` | — | not yet reached |
| 007 IDOR | `/api/register` | anon | yes (params mapped) |

The authenticated ACG's genuine marginal value is **002** (and setup for 003/004); 001/005/007 were already
addressable from the anonymous map; 006 is still a gap. Because 4 of 7 vulns are write/mutation, **exercising
admin writes (the `pentest` profile against a disposable instance) is the higher-leverage next step** than
authenticated reads alone. Whether this improves the downstream scored run is an empirical A/B (baseline map
vs this ACG), not an assumption.

---

## 7. What is solid, what is missing, roadmap

**Solid.** Safety is airtight in evidence (zero destructive requests across all 17 environments and every
ablation). Reproducibility (replays validate; a claimed capability is one that re-runs). Determinism.
Breadth dedup (uniform catalogs → ~1 visit). Restoration efficiency (Stage 2, −~20% wall-time). SPA/interactive
recall now strong under the general-web profile (§6.2–6.3).

**Missing / open.**
1. **Admin/write capability surface** — reads are mapped; the high-value mutation operations (create/edit/
   delete) are deferred by default and only exercised under `pentest` on a disposable target.
2. **Semantic/content distinctions** — the release-vs-note "changelog" slice is reached by no structural
   arm; reserved (not built) for a deterministic content-token rule before any LLM.
3. **File/upload-served endpoints** (e.g. white-jotter `/api/file/`) are not reached without exercising
   upload flows.
4. **Real-world coverage is unmeasurable** (Track B gives inventories, not percentages).
5. **Deep workflows vs budget** — coverage is budget-bound; restoration is the main consumer.

**Roadmap (priority order).** (1) Exercise the admin-write surface on disposable targets and A/B the
downstream score. (2) Promote `eager_child_expansion` toward default-on after wider transfer validation.
(3) Deterministic content-token list rule for the semantic slice. (4) Reach upload/file-served endpoints.
(5) LLM stays gated until a deterministic baseline leaves a residual that is specifically semantic
(a per-action ranker was budget-negative: +2–6/85 at ~2× the cost).

---

*Determinism, safety, and the Track-A/Track-B measurability caveats are carried verbatim from the evaluation
data's own terminology. The ACG is built from the run's evidence log (`agent1/model/importer.py` →
`materialize.py`); it is grounded in the same observations as Graph A, never a re-crawl.*
