# Agent 1 — Architecture, Experiments, and Benchmark Status

Written for: the EngramSec team and Agent 1 stakeholders reviewing where the system stands. Branch
`agent1-browser-mapper-20261028`. This is a status synthesis; per-benchmark detail (input, what Agent 1
produced, and whether it is accurate) is in [`agent1_benchmark_reports/`](agent1_benchmark_reports/).

> **One-paragraph summary.** Agent 1 is a deterministic, safety-bounded browser *functionality mapper*: it
> drives a real Chromium browser over an unfamiliar web app and emits two artifacts — **Graph A** (observed
> states, actions, and workflows with replay evidence) and the **ACG** (an Action-Capability Graph of
> distinct capabilities). It executes **no LLM** in the mapping loop; all decisions are heuristic and
> reproducible. Its strongest properties are **safety** (it never fired a destructive request in any
> benchmark) and **reproducibility** (replayed workflows validate). Its measured weaknesses are **recall on
> write-gated and client-rendered (SPA) functionality**, **budget lost to state restoration**, and the
> fact that **real-world coverage cannot be measured** without capability ground truth. The most recent
> work (Stage 2) cut restoration wall-time ~20% and raised capability coverage on three measurable
> fixtures with zero safety regression.

---

## 1. What Agent 1 is and what it produces

**Goal.** Given a start URL (and optional authorization), map *what the application can do* — not just its
pages. Output is consumed by downstream security/analysis tooling, so every claimed capability must carry
**evidence** and be **reproducible**, and the mapper must never itself perform a damaging action.

**Two output artifacts (per run, written by `agent1/exporter.py`):**

- **Graph A** — the evidence graph: `states` (grouped observations), `actions_evidence` (executed
  controls with network traces), `functional_workflows` (multi-step chains), `features`, `edges`
  (state→action→state transitions), `record_instances`, and `advertised_unexecuted` (controls seen but not
  run). Every executed action can be independently **replayed** to confirm it reproduces its requests.
- **ACG (Action-Capability Graph)** — distinct *capabilities* abstracted over route templates and session
  contexts (`acg_operations`, templates, entity types). This is the "what can this app do" inventory.

**Non-goals / guarantees.** No model inference in the loop (`model_provider: none`). Strictly scoped to
the start origin (`allowed_origin`). Writes are gated by a **write policy** (`read_only` or attested
`disposable`); destructive routes (`/delete`, `/destroy`, `/drop`, `/reset`, DELETE methods) are never
executed. Runs are deterministic: identical config + initial state ⇒ identical action sequences.

---

## 2. Architecture (the mapping pipeline)

```
RunConfig ─▶ Explorer.run()
   1. launch Chromium (Playwright), navigate start URL
   2. DISCOVERY  (_explore / _explore_persistent)
        pop frontier item ─▶ _attempt_frontier ─▶ record observation + transition ─▶ enqueue new controls
        restoration ladder picks the cheapest safe way to re-reach an item's parent state
   3. FOCUS SWEEP (_authorized_write_sweep)  [focused_adaptive]
        after discovery, descend functional subtrees + give queued safe writes a bounded, fair turn
   4. REPLAY / VERIFICATION  (ReplayScheduler)
        re-run a reserved budget of workflows to confirm they reproduce (replay_validated)
   5. write_outputs ─▶ Graph A + ACG
```

**Key components**

- **`BrowserSession`** (`agent1/explorer.py`): `goto` / `goto_start` / `go_back` (all `domcontentloaded`
  + bounded readiness sampling), `observe` (DOM→controls snapshot), `execute` (resolves a control's
  locator on the live DOM and clicks/submits), `find_current` (matches a saved descriptor against a cached
  observation's controls). Scope is enforced on every navigation.
- **Frontier + discovery loop.** Default `exploration_mode="fresh"`: each queued item is attempted in a
  **fresh browser context**, with a "local burst" that chains depth-first while the next control is on the
  live page. A `persistent` mode exists but is not the frozen default.
- **Restoration ladder** (`_attempt_frontier`): to re-reach an item's parent state it tries, cheapest
  first — (1) **live reuse** (the live page already *is* the source), (2) **prefix reuse** / (3)
  **history return** (`go_back`) [both gated on `state_reuse="prefix"`], (4) **`direct_url` shortcut** (one
  navigation straight to a plain-GET parent URL), else (5) **root reload + path replay**. The ladder never
  replays a write (`_known_write` → `UnsafeRestoration`), so restoration cannot cause a state change.
- **Write policy** (`agent1/write_policy.py`): `read_only` blocks every non-GET; `disposable` allows
  bounded, logged, non-destructive writes only on an attested disposable environment, under a write cap,
  and never on a destructive route.
- **Replay/verification** (`agent1/replay_scheduler.py`): a reserved fraction of the budget re-executes
  workflows to prove they reproduce their application requests (`replay_validated`).
- **ACG + state identity** (`agent1/state.py`, `action_behavior.py`): route templating, group signatures,
  record-instance identity, behavior classification (which action is a likely write / state change).

**Scheduling policies** (`write_execution_policy`, all reuse the one sweep loop, no second engine):
`deferred` → `authorized_fair` → `focused_subtree` → **`focused_adaptive`** (frozen baseline). Opt-in
Stage-1/2 flags layer on top (§4): `focus_to_budget`, `fair_subtree_rotation`, `focus_stagnation_limit`,
`eager_child_expansion`. **All default off; the frozen baseline is unchanged.**

---

## 3. How we measure — and the measurability problem

Two evaluation **tracks**, and this distinction governs every number below:

- **Track A — development fixtures (measurable).** Server apps we wrote, with author-curated capability
  annotations. We can compute **annotation recall** (fraction of annotated capabilities Agent 1 executed)
  and **precision**. *Caveat stated in the data itself:* these are "annotation-based recall/precision, not
  independently established application ground truth," and ACG "roles" are cookie-session contexts, not
  semantic authorization roles.
- **Track B — real third-party apps (NOT MEASURABLE).** prestashop, comfyui, siyucms, jetlinks,
  white-jotter. Without independent capability ground truth, **the percentage of functionality captured
  cannot be established** — discovery counts are *inventories*, not coverage percentages. We report them as
  inventories and nothing more.

**Two config regimes** also matter when reading numbers:

- **Comprehensive regime** (`agent1_comprehensive_summary.json`, revision `4a4f819`): `policy=coverage`,
  180 s, `allow_post_forms=false` (**read-only**), `exploration_mode=fresh`, `shallow` replay. This is the
  broad 17-environment sweep. Because it is read-only, *write* capabilities are structurally unreachable
  there — a large part of the "missed" set on CRUD fixtures.
- **Research regime** (Stage 0/1/2, `MATCHED` + `adaptive_protected`): 140 s, `allow_post_forms=true`,
  `write_policy=disposable`, `interaction_profile=extended`, `focused_adaptive`, `structure` replay,
  replay floor 0.25. Used for the restoration/scheduling experiments on purpose-built GET fixtures.

---

## 4. What we have tried — what worked, what didn't

### 4.1 Write-execution scheduling (`deferred` → `focused_adaptive`) — **worked**
Problem: safe, state-changing workflows (and the functionality they unlock) were deferred by a write
penalty and often never run. We added a post-discovery **authorized write sweep** that gives queued *safe*
writes a bounded, fair turn (never destructive, under the write cap, with a replay-budget floor), then a
**focused** descent that follows a newly-unlocked subtree instead of wandering back to the global queue,
and finally **`focused_adaptive`**, which also descends functional subtrees unlocked during ordinary
discovery. On the dev fixtures this took competing-subtree coverage from partial to full (e.g. branch_lab
2/6→6/6, gated_get 5/10→10/10) deterministically, with safety intact. This is the **frozen baseline**.

### 4.2 LLM / model-ranker augmentation — **investigated, rejected (for now)**
We asked whether an LLM could beat the deterministic scheduler. A per-action ranker (`gpt-5.4-mini`) was
only 2–6/85 better than the novelty heuristic at 2.1 s/call vs ~0.9 s/action — **budget-negative** under
equal wall-clock. Conclusion: no LLM in the loop until a deterministic baseline leaves a residual that is
*specifically semantic*. (Details: `AGENT1_LLM_AUGMENTATION_DECISION.md`,
`AGENT1_MODEL_AND_SCALING_REPORT.md`.)

### 4.3 Stage 0 — a valid breadth-starved benchmark — **worked (and reframed the problem)**
Existing fixtures either saturate or confound breadth with auth/JS/writes, and Track B is unmeasurable. We
built `breadth_starved_lab` (GET-only; 50 caps = 18 shallow + 32 deep; no auth/write/JS/destructive) so
*any* miss is attributable to exploration prioritization. **Key finding:** breadth is *not* the bottleneck
(the explorer already dedups breadth to ~1 visit); the baseline reached 30/50, and the misses were caused
by **descent ordering** and **per-capability restoration cost**, not redundant enumeration.
(`AGENT1_STAGE0_BENCHMARK_REPORT.md`.)

### 4.4 Stage 1 — cheap deterministic scheduler (fair rotation + stagnation) — **marginal; no**
We added opt-in `fair_subtree_rotation` + `focus_stagnation_limit` (+ lifting the 12-step focus cap). On
two held-out variants (atlas, orchard) the full policy bought only **+1 deep capability** each and
*redistributed* coverage across hubs rather than increasing it; fair rotation alone even regressed one
variant. The ablation **refuted the Stage-0 hypothesis** that the step cap was binding (the sweep already
stops at 5–7 steps) and localized the real bottleneck to **restoration cost**, not ordering.
(`AGENT1_STAGE1_SCHEDULING_REPORT.md`.)

### 4.5 Stage 2 — eager child expansion (restoration saver) — **worked**
Diagnosis: on GET apps ~**85% of restorations re-fetch the same parent** once per child (a parent was
reached up to 12×), and restoration is ~**98% of transition wall-time**; the cheap return paths were
disabled under the frozen `state_reuse="root"`. We added opt-in **`eager_child_expansion`**: when a
verified, plain-GET, non-destructive parent has several *distinct-template* children queued, execute a
**bounded batch** of them in **one** browser session — reaching the parent once and returning with a
verified `go_back` between children (reusing the cached parent observation) — instead of a fresh context +
parent restore per child. Every child still runs through the normal `_attempt_frontier` (live-state reuse)
so recording, write-caps, scope, record-identity, and replay are unchanged; it falls back on any
uncertainty and **never batches writes**. Result across all three measurable fixtures (median of 3, 140 s):

| fixture | exec A→B | deep A→B | restoration wall-time | caps/min | eager (batches/children/returns/**rejected**) |
|---|---|---|---|---|---|
| breadth_starved_lab | 29 → **34** / 50 | 11 → **16** / 32 | 85.4 → **67.2 s** (−21%) | 12.4 → **14.5** | 5 / 21 / 16 / **0** |
| atlas (held-out) | 31 → **33** / 44 | 13 → **15** / 26 | 87.1 → **67.3 s** (−23%) | 13.1 → **14.0** | 5 / 19 / 14 / **0** |
| orchard (held-out) | 28 → **31** / 48 | 10 → **13** / 30 | 86.3 → **71.1 s** (−18%) | 12.0 → **13.2** | 4 / 17 / 13 / **0** |

Safety/replay held on every arm (transitions_failed 0, replays preserved, state-changing requests
unchanged, **0 incorrect restorations**). Transfer/safety check on independent apps (workflow_lab,
stateful_lab, heldout_shop): eager batched only GET children (e.g. workflow_lab batched 8) while
**state-changing writes and destructive requests were unchanged (destructive = none)**. *Restoration
`actions` rose slightly* (each `go_back` counts as one) **while wall-time fell** — so the win is time +
coverage, not an action-count artifact. (`AGENT1_STAGE2_RESTORATION_REPORT.md`.)

---

## 5. Current performance across all benchmarks

**Track A — development fixtures.** Columns: Agent 1's Graph A size (states / actions / workflows), caps
observed, and accuracy. Recall/precision exist only where capabilities were annotated; the rest have
surface/server-state references (inventory only). Comprehensive-regime numbers are **read-only**.

| fixture | input (shape) | Graph A (st/act/wf) | caps obs. | recall / prec. | headline |
|---|---|---|---|---|---|
| stateful_lab | server CRUD + destructive | 3 / 12 / 2 | 2 | **0.29 / 1.00** | read-only ⇒ create/update unreached; `delete_all` correctly refused |
| js_heavy_lab | client SPA, 2 roles | 3 / 9 / 9 | 3 | **0.21 / 1.00** | SPA controls not discovered (no JS-driven exploration) |
| replay_lab | catalog/search/records | 19 / 43 / 42 | 22 | **0.68 / 0.77** | good recall; misses = write wizard steps + a few no-control |
| phase2_lab | prereq workflow + WebSocket | 23 / 66 / 66 | 16 | server-state only | reaches prerequisite chains; WS diagnostic |
| coverage_lab | multi-area SSR site | 23 / 74 / 74 | 16 | surface only | broad area coverage; restoration-heavy (113 restor.) |
| heldout_shop | small e-commerce | 16 / 75 / 75 | 17 | surface only | solid inventory; 59 redundant actions |
| transfer_library | resource/link + boundary traps | 57 / 70 / 69 | 27 | transfer eval | strong link/resource discovery (134 controls seen) |
| restoration_lab | restoration-contract fixture | 12 / 78 / 63 | 19 | none | stresses restoration; 15 failed actions |
| hybrid_lab | catalog + setup chain | 11 / 49 / 49 | 16 | none | deep fn gated behind POST/JS (not breadth) |
| crawl_maze | crawler testbed (link/JS/HTML) | 64 / 65 / 65 | **65** | testbed paths | highest throughput (21 caps/min, 0 redundant) |
| crawlground | crawler testbed (interaction-gated) | 29 / 98 / 39 | 22 | **crawl recall 0.068** | interaction markers mostly unmet (59 failed) |
| whiteboard | auth collaborative whiteboard | 2 / 4 / 4 | 2 | templates only | anonymous-only; little reachable without auth |
| **breadth_starved_lab** | GET-only breadth+hubs (built) | — | 34/50 (B) | **exact ground truth** | Stage-2 arm B; semantic slice (releases) still 0 |
| **atlas / orchard** | held-out GET variants (built) | — | 33/44, 31/48 (B) | **exact ground truth** | Stage-2 held-out confirmation |

**Track B — real apps (NOT MEASURABLE; inventories only).** prestashop (blind, 1 state / 14 wf, hit a
login/redirect wall), comfyui (11 states, 0 workflows — canvas/WebSocket UI), siyucms (30 states / 33 wf),
jetlinks (**1 action total** — SPA/login wall, effectively blocked on first run), white-jotter (16 states
/ 71 wf). These show Agent 1 *runs* against real stacks within scope and safety, but **no coverage % can
be claimed**. 10 WebExploitBench targets were **not evaluated** (access restricted).

---

## 6. What we are doing well

1. **Safety is airtight in evidence.** Across all 17 environments and all Stage 0/1/2 arms, **zero
   destructive requests fired** and dangerous controls were skipped (e.g. crawl_maze 24, crawlground 197
   dangerous controls skipped; `delete_all` refused on stateful_lab). The write policy and restoration
   "never replay a write" invariant hold.
2. **Reproducibility.** Replays validate (coverage_lab 34/34, phase2 31/31, crawl_maze 34/34; failures are
   rare and logged). A claimed capability is one that re-runs.
3. **Determinism.** Identical config + initial state ⇒ identical action sequences, across trials — which is
   what makes the A/B experiments trustworthy.
4. **Breadth is handled.** Novelty dedup keeps uniform catalogs to ~1 visit (crawl_maze 0 redundant
   actions); we do not drown in list items.
5. **Restoration efficiency is now materially better** (Stage 2): ~20% less restoration wall-time and
   higher capability throughput, with no safety or replay cost.
6. **High discovery throughput where structure is plain GET** (crawl_maze 21 caps/min; strong link and
   resource discovery on transfer_library).

## 7. What we are missing / open problems

1. **Write-gated functionality under read-only.** The comprehensive sweep is read-only, so create/update
   capabilities are structurally unreachable there (stateful_lab recall 0.29 is mostly this). The
   disposable-write path exists but was not used in the broad sweep.
2. **Client-rendered (SPA / JS) capability.** js_heavy_lab recall 0.21 and comfyui's 0 workflows show we
   do not drive JS-constructed controls well; `no_matching_advertised_control` dominates those misses.
3. **Restoration cost is structural, not eliminated.** Even post-Stage-2, restoration is the largest
   single budget consumer; the saver helps on GET parents with distinct children but not on write/JS
   parents, and the focus sweep is still budget-starved (≈15 actions after discovery).
4. **Semantic / content distinctions.** On the breadth benchmark the release-vs-note "changelog" slice is
   reached by *no* arm (0/5–0/6) — it needs page-content understanding the structural explorer lacks. This
   is the one place reserved (but **not yet built**) for a content-token rule or, last, an LLM.
5. **Interaction-gated markers.** crawlground recall 0.068 — many capabilities require specific input
   sequences the heuristic explorer does not synthesize.
6. **Real-world coverage is unmeasurable.** Track B gives inventories, not coverage; we cannot yet claim
   "Agent 1 maps X% of PrestaShop." Auth walls (jetlinks, prestashop) further limit blind runs.
7. **Deep workflows vs budget.** Under the 140 s research budget the sweep reaches only part of the deep
   hubs; coverage is budget-bound, and restoration is why.

## 8. Roadmap (next, in priority order — none started here)

1. **Promote `eager_child_expansion` toward default-on** after wider transfer validation (it is opt-in and
   safety-neutral today), and extend the batch idea to the persistent mode and the focus sweep.
2. **Content-token list rule** (deterministic, no model): prioritize list items whose link text differs
   from the list's dominant token ("Release" ≠ "Note") to reach the semantic slice. *Kept as a separate
   hypothesis from restoration so gains attribute cleanly.*
3. **A disposable-write comprehensive re-sweep** so write capabilities (stateful_lab, replay_lab wizards)
   are counted, closing the biggest recall gap.
4. **JS/SPA control discovery** — the largest unaddressed recall gap (js_heavy_lab, comfyui).
5. **LLM stays gated** until a deterministic baseline leaves a residual concentrated in the semantic slice.

---

*Sources: `evaluation/results/agent1_comprehensive_summary.json` (17-env read-only sweep, rev `4a4f819`),
`stage0_breadth_benchmark.json`, `stage1_scheduling_benchmark.json`, `stage2_restoration_benchmark.json`,
and the `AGENT1_STAGE{0,1,2}_*` / `AGENT1_LLM_AUGMENTATION_DECISION` / `AGENT1_MODEL_AND_SCALING` reports.
Accuracy caveats (annotation-based, not independent ground truth; Track B not measurable) are carried from
the summary's own terminology and preserved here.*
