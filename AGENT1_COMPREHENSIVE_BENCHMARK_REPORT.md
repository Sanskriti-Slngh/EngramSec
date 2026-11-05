# Agent 1 comprehensive benchmark evaluation: report

Evaluation of the frozen Agent 1 (`agent1/` tree `320a1f8`, revision `a9802e3`) under preregistration revision 1 ([`74426ce`](AGENT1_COMPREHENSIVE_EVALUATION_PREREGISTRATION.md)). Scored runs: 2026-11-04 22:45 to 2026-11-05 13:36. Aggregates: [evaluation/results/agent1_comprehensive_summary.json](evaluation/results/agent1_comprehensive_summary.json) (primary), [evaluation/results/agent1_post_diagnostic_summary.json](evaluation/results/agent1_post_diagnostic_summary.json) (Track S), [evaluation/results/comprehensive_deviations.json](evaluation/results/comprehensive_deviations.json) (deviations D1–D9).

## 1. Executive summary

**Out of the box, Agent 1 maps a small and predictable slice of an unfamiliar application: its static, semantic, server-navigable surface. It does not map the majority of an application's functionality.**

**Primary track.** All 51 trials completed with status ok: 12 development environments and 5 public WebExploitBench targets, 3 trials each. They used the production configuration: legacy coverage policy, 180 s / 500 actions / 100 transitions, no model calls, no credentials, POST forms disabled. Model calls were 0, destructive-endpoint hits 0, state-changing requests in replay 0, and there were no reset failures.

**Reference-based results.** On the three annotated development labs, annotation-based recall was:
- 0.29 (2 of 7) on stateful_lab;
- 0.21 (3 of 14) on js_heavy_lab;
- 0.68 (17 of 25) on replay_lab.

The same code scored 0.86, 0.86 and 0.96 there earlier, under per-lab development configurations (a historical comparison, not controlled). Recall reaches its final value within 10–20% of the action budget, so more budget would not have helped. On the testbeds with their own third-party scoring, Agent 1 reached 4 of 91 Crawl Maze expected paths and 4 of 59 Crawlground markers.

**WebExploitBench.** Without independent ground truth, the percentage of functionality captured cannot be established.
- SiyuCMS and White-Jotter produced inventories of 26–27 capabilities each. None was verified; 5 of 26 and 18 of 26 had no identified behavioural class.
- PrestaShop, ComfyUI and JetLinks produced **zero** capabilities in every trial, each for a different mechanism-level reason:
  - PrestaShop: all navigation pointed to a non-loopback host and was refused by scope.
  - ComfyUI: no page state was ever reproducible, so every action failed restoration.
  - JetLinks: the application root answered 404.

**Verification.** No capability reached VERIFIED status in any of the 51 trials. Discovered capabilities are at best *reproduced* (re-executed with the same observed outcome), never functionally verified.

**Three general bottlenecks**, each verified in the agent's own outputs on more than one application:
1. **Perception is limited to semantic static elements.** 100% of extracted controls in every development run came from the static DOM snapshot, and all were links, buttons or form submits. Non-semantic interactive elements (`<div>` listeners, shadow-root and frame listeners, delegated handlers, replaced handlers) are invisible. Pages are also read before client hydration completes.
2. **Restoration depends on exact state reproduction.** In fresh mode, every action requires reloading the root and returning to an exactly matching state group. Any state that changes on its own or as a side effect breaks restoration: live counters, a state-changing GET, an unstable single-page app. Results:
   - Crawlground: 59 failed actions from one page.
   - ComfyUI: zero executable actions.
   - stateful_lab: the record pages were never reached.
3. **The frontier spends its budget on breadth and defers writes.** Non-search form submissions are deferred by a fixed −45 priority whenever other controls exist. Exploration stops at the 70% time reserve (126 s) in 9 of 17 environments. The supplementary write diagnostic (Track S) shows how much allowing POST forms recovers:
   - nothing on the two fixtures whose exploration hit the deadline, because the deferred submissions were never reached;
   - one member capability on the fixture whose frontier emptied first.

Safety refusals were legitimate and did not damage anything: dangerous labels such as "Delete all" and "Reset all scores", password and file inputs, POST forms, cross-origin links. They are responsible for some misses, but Track S shows they are rarely the only barrier.

**Maturity.** Agent 1 is a safe, deterministic, well-instrumented *surface* mapper whose graph is useful for downstream agents as a structured starting inventory. It is not a reliable functional map of unfamiliar applications.

## 2. Evaluation protocol and frozen configuration

Full detail is in the preregistration; summary:

| Item | Value |
|---|---|
| Agent | `agent1/` tree `320a1f888cc2…` at `a9802e3`. Verified unchanged before every launch by the harness freeze guard (`tree_clean`). |
| Entry point | `Explorer(RunConfig(...)).run()` + `write_outputs`, the `agent1.cli map` path |
| Configuration | `--policy coverage --seconds 180 --max-transitions 100 --max-browser-actions 500`; all other fields at production defaults. Implied: fresh mode, state-aware, `allow_post_forms=False`, shallow replay, 30% replay reserve, `settle_ms=350`, `robust_readiness=False`, `interaction_profile=basic`, `runtime_listener_observation=off`, no origin aliases, anonymous. |
| Instrumentation | `acg_evidence`, `action_ledger` (evidence-only). Preflight: identical action selection on 5 fixtures; exact equivalence on 3. |
| Trials | 3 per environment; no seeds (deterministic frontier) |
| Model calls | 0 (provider `none`) |
| Harness revisions | Primary: `74426ce`. Track S: `4a4f819` (Track S configuration-merge fix only, D5). |

Track A = development (white-box failure analysis). Track B = WebExploitBench public targets (evaluation-only). Track S = supplementary safe-isolated write diagnostic (`allow_post_forms=True`, in-process fixtures only), never pooled.

**Protocol deviations** (all in [comprehensive_deviations.json](evaluation/results/comprehensive_deviations.json)):

| ID | Kind | Data affected |
|---|---|---|
| D1 | The freeze guard refused the first launch (operator's log file inside `agent1/`); no trial ran | no |
| D2 | Host on battery entered clamshell sleep; **SiyuCMS trials 0–1 mapped across sleep** (wall minus agent clock 1,527 s and 3,602 s). Driver paused at a clean boundary and resumed on AC power. | yes, flagged |
| D3 | The 30-min SiyuCMS reset-verification cycles disclosed in the preregistration were host sleep | no |
| D4 | The preregistration wrongly said phase2_lab never exercises WebSocket scope enforcement; it deliberately does (15 correct refusals per trial) | no |
| D5 | Track S harness bug (duplicate keyword); 9 trials failed before the agent started; fixed and run once | no (Track S only) |
| D6 | The readiness rule (status < 500) accepted JetLinks' 404 root | yes |
| D7 | Log line prints `reference=None` for non-annotation reference kinds | no |
| D8 | `terminated_by` cannot see the exploration time reserve; additive field `exploration_ended_s` added | no (descriptive) |
| D9 | Track S ran partly across host sleep; affected trials flagged | Track S only |

No agent code, configuration, threshold or scoring rule was changed after a result was observed. No mapping trial was rerun.

## 3. Complete benchmark inventory

| Env | Track | Category | Prior exposure | Reference | Trials ok | Notes |
|---|---|---|---|---|---|---|
| stateful_lab | A | server-rendered CRUD + destructive control | developed against | annotation (7) | 3/3 | |
| js_heavy_lab | A | client-rendered SPA, 2 session contexts | developed against | annotation (14) | 3/3 | |
| replay_lab | A | catalog/records, listener widgets | developed against | annotation (25) | 3/3 | |
| phase2_lab | A | prerequisite chain + WebSocket | development | server-state diagnostic | 3/3 | |
| coverage_lab | A | multi-area site | development | surface truth (author) | 3/3 | Track S |
| heldout_shop | A | small e-commerce | development (not held out) | surface truth (author) | 3/3 | Track S |
| transfer_library | A | resource discovery, listener functions | development | author evaluator | 3/3 | |
| restoration_lab | A | restoration contract | development | none | 3/3 | |
| hybrid_lab | A | catalog + setup chain | development | none | 3/3 | Track S |
| Crawl Maze | A | crawler testbed | repeatedly used | testbed expected paths (91) | 3/3 | |
| Crawlground | A | crawler testbed | transfer-checked | testbed server markers (59) | 3/3 | |
| whiteboard | A | collaborative whiteboard (logged-out) | user's own app | identity only | 3/3 | |
| SiyuCMS | B | PHP CMS | development/validation, **not held out** | none | 3/3 | t0–t1 sleep-affected (D2) |
| PrestaShop | B | PHP e-commerce | mapped once (2026-10-28) | none | 3/3 | 0 capabilities |
| ComfyUI | B | canvas/graph ML UI, WebSocket | mapped once (2026-10-28) | none | 3/3 | 0 capabilities |
| JetLinks | B | Java IoT SPA | never run | none | 3/3 | 404 root (D6) |
| White-Jotter | B | Java/Vue library manager | never run | none | 3/3 | |
| 10 gated WebExploitBench targets | B | — | — | — | — | **NOT EVALUATED — ACCESS RESTRICTED** |

**Reset integrity.**
- **Docker-backed trials (24):** 0 reset failures. All pre-start and post-trial teardowns exited 0; no residual containers or named volumes; every mount profile matched the frozen profile; container IDs and volume names were disjoint across trials.
- **In-process trials (27 primary):** the initial server log was empty and the initial-state digest identical across trials; the fixture port was closed after every trial.

## 4. Per-application scorecards

Medians of 3 trials. "Caps" = distinct ACG capabilities with at least OBSERVED status. "Repro" = REPRODUCED. "Exploration end" = when exploration stopped: either at the 126–131 s time reserve ("reserve"), or earlier because the frontier was empty.

**Track A (development)**

| Env | Actions | Caps | Repro | Verified | Reference result | Exploration end |
|---|---:|---:|---:|---:|---|---|
| stateful_lab | 16 | 2 | 0 | 0 | annotation recall 0.29 (2/7), precision 1.00 | 7 s (frontier) |
| js_heavy_lab | 31 | 3 | 3 | 0 | annotation recall 0.21 (3/14), precision 1.00 | 12 s (frontier) |
| replay_lab | 172 | 22 | 20 | 0 | annotation recall 0.68 (17/25), precision 0.77 (5 unmatched) | 57 s (frontier) |
| phase2_lab | 379 | 16 | 13 | 0 | server-state diagnostic only | reserve |
| coverage_lab | 373 | 16 | 15 | 0 | areas 0.80, controls 0.94, requests 0.80, contexts 0.50 | reserve |
| heldout_shop | 313 | 17 | 10 | 0 | areas 0.875, controls 0.91, requests 0.75, contexts 0.50 | reserve |
| transfer_library | 341 | 27 | 16 | 0 | documents 54/107, static 37/64, functions executed 3/9 (1/9 replay-validated) | reserve |
| restoration_lab | 335 | 19 | 14 | 0 | none | reserve |
| hybrid_lab | 203 | 16 | 16 | 0 | none | 78 s (frontier) |
| Crawl Maze | 368 | 65 | 34 | 0 | **4/91** expected paths fetched (0.044); 0 references extracted | reserve |
| Crawlground | 332 | 22 | 21 | 0 | **4/59** markers (0.068); js-events 0/14, frames 0/4 | reserve |
| whiteboard | 15 | 2 | 1 | 0 | 0 entity instances (logged-out surface only) | 7 s (frontier) |

**Track B (WebExploitBench).** There are no coverage percentages: without independent capability ground truth, the share of each application's functionality captured cannot be established. The six report sections are kept separate.

| Section | SiyuCMS | White-Jotter | PrestaShop | ComfyUI | JetLinks |
|---|---|---|---|---|---|
| **Functional inventory**: caps (client-only) / ACG operations / templates / grouped states | 26 (3) / 24 / 21 / 30 | 26 (13) / 8 / 6 / 16 | 0 / 0 / 1 / 1 | 0 / 0 / 1 / 11 | 0 / 0 / 1 / 1 |
| Controls observed / executed; request structures | 131 / 46; 133 | 76 / 54; 30 | 66 / 15; 1 | 36 / 10; 518 | 0 / 0; 1 |
| Behavioural classes | 18 navigation, 1 instance view, 2 client view change, 5 unidentified | 6 navigation, 2 client view change, 18 unidentified | — | — | — |
| **Evidence quality**: observed / reproduced; replays validated; failed actions | 5 / 21; 25/25; 13 (click timeouts 6–7, restoration mismatch 5–8) | 12 / 14; 18/18; 3 (1 click timeout, 2 unsafe restorations refused) | 0 / 0; 1/1; 1 ("action left the configured origin"; 14 executed with no effect) | 0 / 0; 0; 10 (all restoration mismatch) | 0 / 0; 0; 0 |
| **Unidentified operations**: unidentified capabilities; operations without capability | 5; 0 | 18; 0 | 0; 0 | 0; 0 | 0; 0 |
| **Blocked functionality**: safety (POST / protected input / dangerous); scope; not selected | 7 (4 / 3 / 0); 156; 5,372 | 0; 204; 2,987 | 60 (60 / 0 / 0); **1,650**; 945 | 0; 0; 157 | 0; 0; 0 |
| **Entity identity**: types / instances (correctness NOT MEASURABLE) | 43 / 51 | 6 / 25 | 2 / 3 | 0 / 0 | 0 / 0 |
| **Verification**: VERIFIED | 0 | 0 | 0 | 0 | 0 |
| Exploration end | reserve (t2); t0–t1 sleep-affected | reserve | 18 s (frontier) | 6–12 s (frontier) | 1 s (single 404 page) |

Mechanism notes. These are limited to the agent's own outputs; no application internals were inspected.
- **PrestaShop:** all 1,650 refused controls target a non-loopback host (1,530 http, 120 https). None targets another loopback port. As deployed, the shop builds its navigation on a host other than the loopback address it is published on. Strict-origin scope (no aliases, by protocol) correctly refuses all of it. This also refutes the preregistration's hypothesis that the 2026-10-28 cross-origin result came from the failed post-up hook: the hook ran this time and the pattern persists.
- **ComfyUI:** every one of 11 observations of the root produced a distinct state signature. Every action failed with "saved return path restored X, expected Y". The in-scope WebSocket worked (21 frames received, 0 refused).
- **JetLinks:** the root answered HTTP 404 after 44–47 s of startup in all three trials (D6). The agent saw one page, with 0 controls.

## 5. Cross-application comparisons

- **Repeatability is near-perfect, and that makes the failures systematic rather than noise.**
  - 16 of 17 environments have pairwise capability-set Jaccard 1.0 and identical executed-action sequences.
  - The only exception is SiyuCMS (0.963), where the two sleep-affected trials found 26 capabilities and the unaffected one 27.
  - ComfyUI's third trial ran fewer actions (6 vs 11), again with 0 capabilities.
- **What separates productive from unproductive targets** is not size or framework but three properties of the starting state:
  - Is the start state reproducible? ComfyUI no; Crawlground's results page no.
  - Do in-scope links exist under the configured origin? PrestaShop no.
  - Does the root serve a page? JetLinks no.

  Where all three hold (SiyuCMS, White-Jotter, the server-rendered labs), the agent produces a consistent navigation-heavy inventory.
- **The inventory is navigation-dominated.** SiyuCMS: 18 of 26 capabilities are navigation. White-Jotter: 18 of 26 are unidentified and 6 are navigation. No instance-creation, removal, modification or collection-query capability was found on any WebExploitBench target. That is expected with POST disabled, listener-only controls invisible, and writes deferred.

## 6. Capability discovery and verification results

**Advertised, executed, reproduced and verified (Q2).** Totals summed over the 17 environments (one trial each, medians):

| Stage | Count |
|---|---:|
| Advertised-but-unexecuted control occurrences (counted per observation, all skip reasons) | 27,492 |
| …of which "not selected" (no refusal) | 24,621 (90%) |
| Capabilities with at least OBSERVED status | 279 |
| …of which REPRODUCED or better | 198 (71%) |
| …of which VERIFIED | **0** |

Most advertised controls were never attempted, and 90% of those were not refused: the frontier simply never selected them. The agent sees far more than it acts on: in all 17 environments the frontier either empties early (8) or stops at the time reserve (9) with most advertised controls unattempted.

**Annotation-based curves.** Normalized AUC, versus actions / versus seconds:
- stateful_lab: 0.271 / 0.271;
- js_heavy_lab: 0.204 / 0.204;
- replay_lab: 0.634 / 0.618.

Every curve reaches its final value by the first or second checkpoint (10–20% of budget) and stays flat. Budget is not what limits these labs.

**Legitimate vs technical misses on annotated labs.** Of the 24 missed annotated capabilities:
- **3 are explained by legitimate refusals**:
  - stateful_lab `delete_all`: a destructive control refused by the dangerous-label filter;
  - js_heavy_lab `alias_area`: a link to `localhost` while the configured origin is `127.0.0.1`;
  - `alias_data`: on the page behind that link.
- **21 are technical failures**, by earliest cause:
  - 9 observation;
  - 7 extraction;
  - 3 restoration;
  - 2 candidate generation.

Annotation-based recall excluding legitimate safety refusals is 0.33 / 0.21 / 0.68, so excluding refusals barely moves recall.

## 7. Deep development-set failure case studies

Each missed annotated capability gets one earliest causal failure (author-defined categories, preregistration §8). "Verified" means established from the agent's outputs plus the fixture source or agent code; "hypothesis" means inferred but not confirmed. All traces were identical across the 3 trials. Tracer: [evaluation/comprehensive_failures.py](evaluation/comprehensive_failures.py).

### 7.1 stateful_lab (recall 0.29)

| Missed | Earliest failure | Evidence | Status |
|---|---|---|---|
| view_record, create_record, update_record | **9 Restoration/replay** | The "Counter" link is a GET that inserts a record (annotated `counter_get_insert`). Afterwards the root shows a new record, so its state group changes (`9b04…` → `c937…`). The next fresh-mode restoration fails ("saved return path restored c937…, expected 9b04…"). Every later attempt is refused as UnsafeRestoration, because the return path contains an observed write. Record pages are never reached, so `update_record`'s form is never seen. | verified |
| home | **3 Candidate generation** | The self-link to `/` was advertised 16 times with no skip reason and never executed, although the frontier emptied. The GET `/` request seen in the run belongs to the Counter redirect and was folded into the Counter capability. | first failure verified; mechanism (same-URL deduplication) is a hypothesis |
| delete_all | 4 Safety: legitimate | Dangerous-label filter; annotated destructive | verified |

Root cause: fresh-mode restoration cannot recover from a server-state change caused by a GET. Refusing the unsafe restoration is the correct safety behaviour; the cost is losing everything downstream. Subsystem: restoration. Generality: also Crawlground and ComfyUI (below).

### 7.2 js_heavy_lab (recall 0.21)

| Missed | Earliest failure | Evidence | Status |
|---|---|---|---|
| open_workflow, continue_setup, open_workspace, workspace_detail, load_late_reports, open_reports, enter_member_mode, member_preferences, load_preferences (9) | **1 Observation** | All 7 root observations were taken while the page read "Initialising application". Two buttons are disabled until a script enables them at 650 ms; a third is inserted at 800 ms. With `settle_ms=350` and `robust_readiness=False`, only the 5 static links were extracted. Everything downstream hangs off these three controls. | verified (observation text and control lists; fixture timers) |
| alias_area | 4 Scope: legitimate | Link uses `localhost`, configured origin is `127.0.0.1`, no aliases | verified |
| alias_data | downstream of alias_area | Page never reached | verified |

Root cause: the production readiness default does not wait for client hydration. Subsystem: observation/readiness. Session-conditioned recall is 0.12, because the member session context is never entered.

### 7.3 replay_lab (recall 0.68)

| Missed | Earliest failure | Evidence | Status |
|---|---|---|---|
| load_details, save_item, wipe_records, wizard_continue → wizard_finish | **2 Extraction** | The pages were reached (3–9 observations each), and the labels "Open details", "Save first item", "Delete all records" and "Continue" appear in the observed text. 0 controls were extracted, because these are `<div>` elements with click listeners and listener extraction is off by default. `wipe_records` would have been a legitimate dangerous-label refusal next. | verified |
| reveal_details, wizard_begin | **2 Extraction** (downstream symptom: no capability) | The button was executed and the page changed: a new listener `<div>` appeared. The ACG derives component-state effects only from changes in extracted controls; text-only changes are not effects, and visual regions are not captured. The new element was never extracted, so no effect was registered and no capability created. | verified (code: `materialize.py` effect derivation) |
| check_loans_second | **3 Candidate generation** | The handler is replaced after the first click, so the second capability needs a second click. Exactly 1 click was recorded. Handler-revision tracking (`behavior_revision`) exists only with runtime listener observation (default `off`), so the same control signature counts as already tried. | verified (trace + code) |

Five unmatched ACG capabilities lower precision to 0.77. One capability split was reported; no incorrect merges.

### 7.4 Other development environments

| Env | Finding | First failure | Status |
|---|---|---|---|
| Crawlground | 59 of 59 failed actions start from `/results`. That page shows a live score ("0 / 59 controls reached" → "1 / 59"), which is part of the state signature, so `/results` is never restorable after the first test visit. Only 5 of 59 test pages were reached. The 197 dangerous-label refusals are all "Reset" and "Reset all scores" (legitimate: they would erase the scoring state). | 9 Restoration (volatile content in the state signature) | verified |
| Crawl Maze | 63 distinct pages reached (mostly category indexes and test pages), but only 4 of 91 expected marker paths fetched. 0 references extracted, because the passive resource spider is off by default. Exploration stopped at the time reserve. | 3 Candidate generation / budget allocation (breadth over index pages) | verified (counts); the mechanism (BFS depth vs marker depth) is a hypothesis |
| transfer_library | F4–F9 are, per the evaluator's own definitions, a replaced handler, a `<div>` listener created by an action, a `<div>` listener at load, a shadow-root listener, a frame listener and a delegated row-family listener. None was executed. | 2 Extraction (F5–F9), 3 Candidate generation (F4) | mechanism class verified (0 listener-derived controls in all runs); per-function trace not done |
| coverage_lab, heldout_shop | Missed: the member area, behind a POST form (coverage_lab), and checkout, behind an "Add to cart" POST form (heldout_shop). Admin areas behind passwords were correctly blocked. | 4 Safety: legitimate (POST disabled); Track S shows a second, technical barrier (§7.5) | verified |
| whiteboard | Logged-out surface only; login and registration forms refused for password input | 4 Safety: legitimate (no credentials by protocol) | verified |
| phase2_lab | Out-of-scope WebSocket refused 15 times per trial (D4) | correct scope enforcement | verified |

**Cross-cutting verified fact.** In every development run, 100% of extracted controls have provenance `snapshot`, and every control kind is link, button or form submit. Not one listener-derived control was extracted anywhere in this evaluation.

### 7.5 Track S: supplementary safe-isolated write diagnostic (reported separately)

Configuration: frozen + `allow_post_forms=True`. Fixtures were selected by the preregistered rule: in-process fixtures whose primary trials recorded a `post_forms_disabled` skip. The rule selected coverage_lab, heldout_shop and hybrid_lab. Isolation checks passed in every trial: empty initial log, identical initial-state digest, fixture port closed after the trial.

| Fixture | Actions (primary → S) | Caps | POST refusals | State-changing requests | Session contexts | ACG operations | Reference metrics | Exploration end | Sleep-affected S trials (D9) |
|---|---|---|---|---|---|---|---|---|---|
| coverage_lab | 373 → 368 | 16 → 16 | 122 → 0 | 0 → 0 | 1 → 1 | 11 → 11 | unchanged (contexts 0.50; member area missed) | time reserve | 0 of 3 |
| heldout_shop | 313 → 311 | 17 → 17 | 26 → 0 | 0 → 0 | 1 → 1 | 7 → 7 | unchanged (checkout missed) | time reserve | 2 of 3 |
| hybrid_lab | 203 → 214 | 16 → **17** | 4 → 0 | 0 → **1** (`POST /session`) | 1 → **2** | 14 → **16** | no reference; gained member capability (`POST /session` → `GET /member`) | frontier (78 s) | 3 of 3 |

All Track S trials were deterministic (Jaccard 1.0); the sleep-affected trials reproduced the unaffected ones.

**Finding (verified).** Allowing POST forms removed every `post_forms_disabled` refusal, but recovered functionality only where exploration ran out of frontier before the time reserve:
- **coverage_lab and heldout_shop:** no reference metric changed and **0 state-changing requests** were issued; the newly allowed forms were never executed.
  - State-aware exploration defers any non-search form submission by −45 priority whenever the page has other controls (`explorer.py`, frontier enqueue).
  - Exploration then stops at the 70% time reserve (127 s) before reaching the deferred submissions. On coverage_lab the member form was visible from the very first observation and advertised 122 times.
- **hybrid_lab:** the frontier empties at 78 s, so the deferred "Enter member mode" form was eventually executed. It issued 1 state-changing request (`POST /session`), entered a second session context and added a member capability.

For coverage_lab and heldout_shop, then, the POST gate is the *recorded* cause of the miss but not the binding one. Their member area and checkout have two independent barriers: the production safety refusal and the frontier's deferral of writes under the time limit. No destructive request was issued in any Track S trial.

## 8. ACG effectiveness

| Env | Graph A action-based recall | Offline ACG recall | Live ACG recall | Offline vs live content |
|---|---:|---:|---:|---|
| stateful_lab | 0.29 | 0.29 | 0.29 | identical |
| js_heavy_lab | 0.21 | 0.21 | 0.21 | identical |
| replay_lab | 0.52 | 0.68 | 0.68 | identical |
| other envs (counts only) | — | — | — | identical, except live has +1 operation / +2 capabilities on phase2_lab and +1 capability (−1 reproduced) on the whiteboard |

- **ACG adds understanding Graph A lacks**: behavioural classes, equivalent interfaces (7 on SiyuCMS, 8 on White-Jotter), entity types and instances, session contexts, explicit gaps. On replay_lab its capability matching beats Graph A's feature grouping (0.68 vs 0.52). It never did worse on the annotated labs.
- **It cannot recover what was never observed.** Every miss above happens before the ACG gets involved; only `reveal_details` and `wizard_begin` fail inside effect derivation, and even those are downstream of extraction.
- **The live ACG adds no recall over the offline reconstruction.** Its value is online availability, not more content.
- **On WebExploitBench the ACG says little about function:** 5 of 26 (SiyuCMS) and 18 of 26 (White-Jotter) capabilities have no behavioural class, and none is verified.
- **Entity identity:** no incorrect record merges on the annotated labs, but correctness is NOT MEASURABLE on Track B (43 entity types for 51 instances on SiyuCMS suggests heavy over-typing; that is a hypothesis).

## 9. Runtime and resource analysis

| Item | Value |
|---|---|
| Agent mapping time (sum of child processes, agent clock) | 5,412 s (≈ 90 min) for 51 primary trials |
| Wall time | Track A: 22:45–23:58 (73 min). Track B: 23:58–01:32 (sleep-affected), then 12:38–12:56 (18 min). |
| Track B setup per trial (median) | SiyuCMS 17.7 s, PrestaShop 14.6 s, ComfyUI 6.9 s, JetLinks 44.9 s, White-Jotter 10.7 s; teardown 3–4 s |
| One-time builds | JetLinks 136 s, White-Jotter 206 s (preregistration §5) |
| Peak target memory during mapping | JetLinks ~2.5 GB after setup; White-Jotter 1.40 GB; PrestaShop 1.06 GB; SiyuCMS 0.93 GB; ComfyUI 0.76 GB; all within the unchanged 7.65 GiB limit, one target at a time |
| Waiting vs executing (estimate: readiness waits + 350 ms × actions) | roughly 70% waiting on in-process labs (e.g. coverage_lab 131 s waiting vs 52 s executing) |
| Restoration cost | 60–132 restoration actions and 66–126 root reloads per time-limited run; e.g. coverage_lab 113 restoration actions + 109 reloads out of 373 actions |
| Unique-discovery vs redundant actions | e.g. heldout_shop 16 unique vs 59 redundant; restoration_lab 17 vs 46; White-Jotter 19 vs 52 |
| Capabilities per 100 actions | 0 (3 WebExploitBench targets) to 17.7 (Crawl Maze); SiyuCMS 17.0, White-Jotter 9.5 |

Fewer actions are not reported as improvements. The dominant costs are fixed settle waits and restoration (root reload plus replaying the path), not decision-making.

## 10. Reproducibility

- **Determinism:**
  - 16 of 17 environments: identical executed-action sequences and capability sets across 3 trials.
  - SiyuCMS: Jaccard 1.0 / 0.963 / 0.963. The odd trial is the sleep-unaffected one.
  - Time-limited labs vary in how many actions fit (phase2_lab 378–384), not in capabilities.
- **Initial state and configuration:** identical configuration digest in every environment. The first state group was identical across trials everywhere except ComfyUI (no reproducible state at all) and JetLinks (its 404 page differed between trials). SiyuCMS's first state was identical in all three trials, including the sleep-affected ones.
- **Reset integrity:** verified per trial (§3).
- **Three deterministic repetitions support no statistical-significance claim**, and none is made. Determinism makes the numbers precise, not general.

## 11. Historical comparisons

| Comparison | Then | Now | Interpretation |
|---|---|---|---|
| Annotated labs, legacy agent with per-lab development configs (active/hybrid A/B, 2026-11-02/03) | stateful 0.86, js_heavy 0.86, replay 0.96 | 0.29, 0.21, 0.68 | Each verified failure in §7 lines up with a setting the development configuration had changed: persistent mode and POST forms (stateful_lab); `robust_readiness`, a `localhost` origin alias and POST forms (js_heavy_lab); `runtime_listener_observation=revisit` and the extended interaction profile (replay_lab). **Historical, not controlled:** no tuned-configuration runs were done in this evaluation. |
| PrestaShop, 2026-10-28 frozen protocol | 54 actions, 1 area, 50 controls blocked cross-origin | 32 actions, 1 state, 1,650 cross-origin refusals, 0 capabilities | Same mechanism; the bash-5.3 post-up hook fix did not change it (preregistration hypothesis refuted). |
| ComfyUI, 2026-10-28 | 6 actions, every action failed restoration | 6–11 actions, every action failed restoration, 0 capabilities | Same mechanism, reproduced. |
| SiyuCMS | development/validation target | 26–27 capabilities, 0 verified | Not a held-out result. |

## 12. Generalization limitations

| Architecture category | Environments | Result | Failure categories observed | Evidence from more than one app? |
|---|---|---|---|---|
| Server-rendered, link-navigable | coverage_lab, heldout_shop, SiyuCMS, Crawl Maze | Good navigation and area recall; writes missed | 4 (POST), 3 (deferral / budget) | yes |
| Client-rendered SPA with late hydration | js_heavy_lab, (JetLinks: unknown) | Most functionality never observed | 1 | one verified app |
| Listener-driven widgets (`<div>`, shadow, frame, delegated) | replay_lab, transfer_library, Crawlground (js-events 0/14, frames 0/4) | Systematically invisible | 2, 3 | yes |
| Apps with volatile or self-mutating start states | stateful_lab, Crawlground, ComfyUI | Restoration collapse; up to 0 capabilities | 9 | yes |
| Origin-mismatched deployments | PrestaShop, js_heavy_lab alias | Correct scope refusal; 0 or partial coverage | 4 (scope) | yes |
| Authenticated surfaces | whiteboard (logged-out), js_heavy_lab member | Not mapped by protocol | 4, 6 | yes |
| Canvas/graph UIs | ComfyUI | Not reached (restoration fails first) | 9 | no |

No single successful fixture is generalized to its category. Positive results (navigation inventories) generalize across server-rendered apps. Negative results generalize across categories, because they come from global defaults (no listener extraction, no hydration wait, fresh-mode exact restoration), not from application specifics.

## 13. Threats to validity

1. **Reference data is author-curated.** The three annotations are `independent: false`: written by the agent's developer from the fixture source, frozen 2026-11-01, not adjudicated. Surface truth and the transfer evaluator are author-written too. Only Crawl Maze and Crawlground use third-party references.
2. **Development exposure.** All Track A labs were designed and tuned against; SiyuCMS is development-exposed; PrestaShop and ComfyUI were mapped once before. Only JetLinks and White-Jotter were never run, and JetLinks produced a 404 page.
3. **Host sleep (D2, D9).** Two SiyuCMS trials and some Track S trials ran across sleep. They are flagged; SiyuCMS's unaffected trial differs by one capability.
4. **Readiness criterion (D6).** JetLinks' zero result may reflect an application still initializing rather than a mapper limit.
5. **Deployment origin.** PrestaShop's zero result is a scope consequence of how the target is published, not evidence about the shop's surface.
6. **Small n.** Three deterministic trials; no significance claims; 5 public targets out of 15.
7. **Fixed configuration.** Results describe production defaults. They are not the agent's best achievable configuration (§11).
8. **Tracer matching is approximate.** Missed-capability tracing matches entry points by kind, label and route. Each conclusion in §7 was checked by hand against the trace.

## 14. Final maturity assessment

| Dimension | Assessment |
|---|---|
| Safety and isolation | **Strong.** 0 destructive hits, 0 replay writes, correct dangerous-label, protected-input, POST and scope refusals, WebSocket scope enforced, loopback-only verified per trial. |
| Determinism and instrumentation | **Strong.** Byte-stable action sequences; evidence ledger, offline and live ACG agree. |
| Surface (navigation) mapping of server-rendered apps | **Moderate.** Areas 0.80–0.875 and controls 0.91–0.94 on development fixtures. |
| Functional coverage of unfamiliar apps | **Weak.** Recall ≤ 0.29 on 2 of 3 annotated labs; 4/91 and 4/59 on third-party testbeds; 0 capabilities on 3 of 5 public targets. |
| Interaction perception (non-semantic, late, listener-driven) | **Missing under defaults** |
| Restoration robustness | **Fragile.** Exact-group matching collapses on volatile or self-mutating states. |
| Functional verification | **Absent in practice:** 0 VERIFIED across 51 trials. |

Agent 1 is a dependable, safe *surface-inventory* component. It is not yet a functional mapper, and its development-lab scores do not carry over to production defaults.

## 15. Recommended next research direction

**State-tolerant interaction perception.** Make the agent see and reliably return to what is interactive, before investing further in policy or modeling. Every one of the three general bottlenecks sits upstream of the ACG and the frontier policy; better policies cannot act on controls they never see or states they cannot return to. The research opportunities below are ordered accordingly.

## Answers to Q1–Q10

**Q1. Can Agent 1 discover the majority of an unfamiliar application's actual functionality?** No.
- Where a reference exists, it reaches the majority only on replay_lab (0.68, a lab it was developed against). It reaches 0.21–0.29 on the other annotated labs, 4% of Crawl Maze paths and 7% of Crawlground markers.
- On WebExploitBench the share is NOT MEASURABLE. Three of five targets yielded zero capabilities, and the other two yielded navigation-dominated, unverified inventories.

**Q2. What proportion of discovered functionality is merely advertised, actually executed, independently reproduced and functionally verified?**
- 27,492 advertised-but-unexecuted control occurrences were recorded; 90% were simply not selected, not refused.
- Of 279 capabilities with at least OBSERVED status, 198 (71%) were REPRODUCED and 0 VERIFIED.
- Reproduction means re-execution with the same observed outcome, not functional verification.

**Q3. Which application architectures cause the most severe coverage failures?**
1. Apps whose start state is not reproducible: ComfyUI, and Crawlground's results page. The result is total collapse (0 capabilities).
2. Origin-mismatched deployments: PrestaShop (0 capabilities, by correct scope refusal).
3. Listener-driven widgets: invisible everywhere.
4. Late-hydrating SPAs: js_heavy_lab, 9 of 14 never observed.

**Q4. What is the dominant bottleneck?** Observation/extraction, then state restoration.
- On the annotated labs, 16 of 21 technical misses originate in perception (9 observation, 7 extraction), 3 in restoration and 2 in candidate generation.
- On the third-party testbeds and WebExploitBench, restoration (Crawlground, ComfyUI) and scope/deployment (PrestaShop) dominate.
- Exploration budget is not dominant on the annotated labs: recall is flat after 10–20% of budget. It does bind on larger fixtures, where write deferral and the time reserve leave advertised controls unattempted.

**Q5. Does ACG materially improve application understanding compared with the historical Graph A?** Yes in structure, modestly in recall.
- The ACG adds behavioural classes, equivalent interfaces, entities, session contexts and explicit gaps.
- It matches or beats Graph A recall (replay_lab 0.68 vs 0.52).
- It cannot compensate for missing observations, and the live ACG adds no recall over the offline reconstruction.

**Q6. Can Agent 1 reliably distinguish different records, capabilities, sessions and roles?**
- **Records:** yes where tested; 0 incorrect record merges on the annotated labs.
- **Capabilities:** mostly; 0 incorrect capability merges and 1 split. Precision is 1.00 / 1.00 / 0.77, with 5 unmatched capabilities on replay_lab.
- **Sessions:** only cookie-name session contexts, and every run stayed in one context (anonymous). The member context was never entered: js_heavy_lab session-conditioned recall is 0.12.
- **Roles:** semantic authorization roles cannot be assessed (no credentials; no independent role annotation). The ACG's "roles" are cookie-name session contexts.
- **Track B entity identity:** NOT MEASURABLE.

**Q7. How much functionality is missed because of legitimate safety restrictions rather than technical inability?** A small share.
- On the annotated labs, 3 of 24 misses: 1 safety refusal, 1 scope refusal and 1 capability behind that scope-refused link.
- On coverage_lab and heldout_shop, the POST refusal is the recorded cause of the member-area and checkout misses. Track S shows that removing it recovers nothing within the budget, because of the frontier's write deferral. On hybrid_lab, removing it recovers one member capability.
- On WebExploitBench, scope refusal dominates PrestaShop (a deployment-origin issue). Safety refusals are small: SiyuCMS 7, White-Jotter 0.

**Q8. Are the failures consistent across different applications, or are they application-specific?** Consistent.
- The three bottlenecks recur across independent applications: perception (replay_lab, transfer_library, Crawlground, js_heavy_lab) and restoration (stateful_lab, Crawlground, ComfyUI).
- They trace to global defaults, not app-specific quirks.
- The app-specific part is which bottleneck bites first.

**Q9. What does the evidence actually establish about Agent 1's ability to generalize?**
- Established: under production defaults the agent generalizes as a safe, deterministic navigation mapper for server-rendered applications.
- Established: it does not generalize as a functional mapper.
- High development-lab scores depended on per-lab configuration (historical comparison), so they are not evidence of generalization.
- Positive evidence on genuinely unseen applications is limited to White-Jotter (26 capabilities, 18 unidentified, 0 verified). JetLinks yielded nothing interpretable.

**Q10. Is Agent 1 sufficiently reliable to serve as the foundation for downstream cybersecurity agents?**
- **Architecturally, yes as a foundation:** safe, deterministic, evidence-backed, with a structured ACG downstream agents can consume and explicit gaps and refusals they can reason about.
- **In demonstrated coverage and reliability, no:** a useful graph is not a complete graph. A downstream agent relying on it today would never see listener-driven functionality, writes, authenticated areas or anything behind a non-reproducible state, and would have no verified capability to anchor on.
- It should be consumed as a *partial, refusal-annotated surface inventory*, never as the application's attack surface.

## Prioritized research opportunities (not implemented)

**1. Listener-aware, hydration-aware perception as a default.**
- *Problem:* 0 listener-derived controls in any run; 16 of 21 technical annotated misses are observation or extraction; js-events 0/14 and frames 0/4 on Crawlground; transfer_library F5–F9.
- *Evidence:* §7.2, §7.3, §7.4. The listener machinery exists but is off by default (`runtime_listener_observation`).
- *Why previous approaches failed:* it was enabled per lab in development, never evaluated as a default, so its cost and false-positive behaviour on real apps is unknown.
- *Mechanism:* a bounded readiness model (wait for quiescence of DOM mutations and network) plus listener-derived controls with handler-revision identity, under a fixed cost cap per observation.
- *Benefits:* recovers listener-only and late controls across categories.
- *Risks:* more candidates and slower observations; listener noise from analytics and global handlers.
- *Falsifiable experiment:* rerun this exact protocol with only those defaults changed.
- *Success criterion:* annotated recall on js_heavy_lab and replay_lab of at least 0.6 and 0.9 respectively, with precision ≥ 0.75; Crawlground js-events markers ≥ 7/14; no safety regression.

**2. State-tolerant restoration.**
- *Problem:* exact state-group matching collapses on volatile or self-mutating states: Crawlground 59 failures, ComfyUI 0 executable actions, stateful_lab downstream loss.
- *Evidence:* §7.1, §7.4, §4.
- *Why previous approaches failed:* persistent mode avoids reloads but was only tuned per lab; volatile text sits inside the state signature.
- *Mechanism:* restoration targets a control-presence contract ("the control I need is present and enabled") instead of full-group equality; volatile regions (counters, clocks) are detected and excluded from restoration identity; writes are isolated by reset hooks where available.
- *Benefits:* executable actions on ComfyUI-like and dashboard apps.
- *Risks:* false restorations, i.e. acting in the wrong record or state; this needs a mismatch audit.
- *Falsifiable experiment:* same protocol, restoration contract changed only.
- *Success criterion:* ComfyUI with at least 5 capabilities and at least 50% of attempted actions executed; Crawlground restoration failures under 10; 0 incorrect record merges on annotated labs.

**3. Write-aware frontier scheduling instead of a fixed deferral.**
- *Problem:* Track S shows allowed POST forms are never reached; exploration hits the 126 s reserve in 9 of 17 environments with most advertised controls unattempted.
- *Evidence:* §7.5, §6.
- *Why previous approaches failed:* the −45 deferral protects state but starves writes regardless of budget.
- *Mechanism:* a per-run quota for distinct untested submission shapes, executed late but before the reserve, in isolated or resettable contexts only.
- *Benefits:* reaches member areas and checkouts on fixtures where POST is permitted.
- *Risks:* more state change; requires reset guarantees.
- *Falsifiable experiment:* Track S again, scheduling changed only.
- *Success criterion:* coverage_lab context recall 1.0 and heldout_shop checkout covered in Track S, with 0 destructive hits.

**4. A real functional oracle for VERIFIED.**
- *Problem:* 0 VERIFIED in 51 trials; reproduction is the ceiling.
- *Evidence:* §6.
- *Why previous approaches failed:* VERIFIED needs paired-search or cross-view evidence, which shallow replay under defaults never produces.
- *Mechanism:* schedule cross-view checks (create, then observe in list view; query, then compare a paired query) as explicit verification actions with budget.
- *Benefits:* trustworthy capability claims for downstream agents.
- *Risks:* budget cost; write side effects.
- *Falsifiable experiment:* same protocol plus a verification scheduler.
- *Success criterion:* at least 30% of reproduced capabilities verified on annotated labs, with 0 unsupported claims.

**5. Deployment-origin and readiness diagnostics before mapping.**
- *Problem:* PrestaShop (all navigation to a non-loopback host) and JetLinks (404 root) produced zero results for reasons outside mapping.
- *Evidence:* §4, D6.
- *Why previous approaches failed:* the harness readiness is status < 500, and origin mismatch is only discovered as scope refusals.
- *Mechanism:* a pre-mapping probe that reports the share of in-scope links and an application-level readiness signal, with an operator-approved alias proposal (never auto-applied).
- *Benefits:* separates infrastructure failures from mapping failures.
- *Risks:* a temptation to auto-widen scope, which must stay operator-gated.
- *Falsifiable experiment:* run the probe on the 5 public targets.
- *Success criterion:* PrestaShop and JetLinks flagged before mapping; 0 scope widenings without approval.

## Regression results

Full regression suite after the evaluation (`pytest`, repository root): **384 passed, 0 failed** (8 min 38 s). That is the pre-evaluation 383 plus the Track S configuration test added with the D5 fix.

During revision 1, one timing-sensitive agent test (`test_observed_form_success_is_not_replayed_without_reset`) failed once in a full run right after heavy Docker activity. It passed 3 of 3 times in isolation and in the next full run; it does not touch the harness.

`git diff a9802e3 -- agent1` is empty: the evaluated agent tree is `320a1f8`, unchanged.
