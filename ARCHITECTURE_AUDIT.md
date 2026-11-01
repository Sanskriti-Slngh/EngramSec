# Agent 1 architecture audit

Code examined: branch `agent1-browser-mapper-20261028` at `f6744ba` (no production code was changed for this audit).
Companion documents: [RELATED_WORK_AND_METHOD_COMPARISON.md](RELATED_WORK_AND_METHOD_COMPARISON.md), [PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md), [EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md), [GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md), [ARCHITECTURAL_MIGRATION_PLAN.md](ARCHITECTURAL_MIGRATION_PLAN.md).

## 0. Summary

Agent 1 is a careful, evidence-disciplined **UI-transition recorder**. It is not yet an application-understanding system. Its central object is a pair *(hashed DOM-state group, control signature)*. Every higher concept is derived after the run by grouping transitions or hashing pages again: "feature", "functional workflow", "record instance", "page template", "request surface". These concepts never feed back into what the agent does next.

Five architectural decisions limit it:

1. **One identity hash carries too many meanings.** A *state group* digest mixes route template, control shapes, form shapes, session markers and a page-content fingerprint. Template, runtime state and entity instance are therefore conflated. Instance and template identities were bolted on later (`record_instance`, `template_identity`), but each is computed differently and none is used by the planner.
2. **There is no capability-level representation.** Graph A's `features` are `digest(action shape, outcome shape)`, and its `functional_workflows` are one per transition. The model cannot express that "create canvas" exists, needs authentication, produces a canvas entity, and enables "share canvas". So it cannot know what is still unknown.
3. **Exploration chooses among (path, control) pairs using hand-weighted novelty scores, computed once at enqueue time.** Nothing represents uncertainty or hypotheses, and there is no stopping rule other than budget. Eight `policy` values, plus the area planner, are variations on that one mechanism.
4. **Restoration and verification both assume the action path is the state.** Restoring a state means replaying the path in a fresh browser context. This is correct only for applications without server-side state. The whiteboard runs showed that it silently creates records, and the stateful guard (`f6744ba`) now refuses those paths. So the agent cannot reach, or verify, anything behind a state-changing prerequisite.
5. **Its oracle is reproducibility, not functionality.** "Replay validated" means the same state group, enough shared content tokens and the same request structures. "Functionally verified" means a CSS/ARIA outcome signal appeared. Only the paired-search check is a real differential oracle.

Most of the existing *evidence infrastructure* is sound and should be kept:
- the scope and HTTP budget router;
- network capture with value redaction;
- readiness detection;
- CDP listener observation;
- request-structure keys;
- the action-behavior classifier;
- provenance-complete Graph A connection audits;
- checkpoints;
- fixtures with held-back ground truth.

What must change is the layer above the evidence: the model of the application, and the planner that decides what to learn next.

## 1. Current architecture

```
                         RunConfig (75 fields, 8 exploration policies, 3 replay policies)
                                      │
 ┌────────────────────────────────────▼─────────────────────────────────────────────────────┐
 │ Explorer (explorer.py, 4,042 lines)                                                       │
 │                                                                                          │
 │  BrowserSession ── EXTRACT_SCRIPT (DOM snapshot: controls, forms, outcome signals)        │
 │      │            ├─ ListenerObserver (CDP getEventListeners; behavior revisions)         │
 │      │            ├─ NetworkRecorder (method, path, param names, encoding; no values)     │
 │      │            ├─ readiness sampler      └─ scope/HTTP-budget router                   │
 │      ▼                                                                                   │
 │  Observation ─► signatures() ─► state_signature / group_signature / behavior_signature    │
 │      │                                                                                   │
 │  _enqueue: for each safe control → FrontierItem(path, action, priority=Σ hand weights)    │
 │      │                                                                                   │
 │  _explore (fresh | persistent [+ AreaTourPlanner]) → _attempt_frontier                   │
 │      │      └ _restore: replay path from root, verify group & instance; refuse known writes│
 │      ▼                                                                                   │
 │  Transition (source obs, action, result obs, network, behavior classification)           │
 │      │                                                                                   │
 │  _replay (shallow | diverse | structure) → fresh-context path replay → ReplayResult       │
 │      ▼                                                                                   │
 │  _finalize: _build_features, _build_functional_workflows, audits, 122 metrics            │
 └──────────────────────────────────────┬───────────────────────────────────────────────────┘
          TypedResourceSpider (1,772 lines) ── passive GETs of referenced URLs (shared HTTP budget)
                                         ▼
          exporter.py → Graph A (states, templates, instances, actions_evidence, features,
                        functional_workflows, resources, request_surfaces, behavior_evidence,
                        replay_evidence, connection_evidence)
```

Module sizes: `explorer.py` 4,042 lines; `resource_spider.py` 1,772; `exporter.py` 751; `schema.py` 727; `listeners.py` 412; `providers.py` 419. `RunConfig` has 75 fields and `RunMetrics` has 122. There are 38 milestone reports in the repository root.

## 2. Component-by-component diagnosis

### 2.1 Exploration and frontier scheduling

**Mechanism (`Explorer._enqueue`, `_sort_frontier`, `_explore*`).**
- Each observed safe control becomes a `FrontierItem(path, action, priority)`.
- The priority is a sum of constants:
  - kind (form 3, button 2, link 1);
  - novelty bonuses: +12 globally novel shape, +15 novel target, +8 novel component, +12 novel form shape, +10 non-click interaction;
  - penalties: −0.2 or −0.6 per path step, −18 global chrome, −28 for labels matching `LOW_VALUE_REPORT`, −45 for an untested non-search form, −8 per earlier ineffective execution.
- `tried_key = group (+instance) + control signature (+behavior revision)` suppresses repeats.
- The persistent mode prefers controls on the live page. `AreaTourPlanner` reorders by URL first-segment "areas".

**Why it blocks functional understanding.**
- **Priority is static.** It is computed when the control is first seen and never revised as evidence accrues. For example, after five product pages behave identically, the sixth product link keeps its original novelty-based score. The frontier has no notion of a question being answered.
- **The unit of choice is syntactic novelty.** Novel CSS component, novel target, novel form shape. None of these is about functionality. Two controls that invoke the same capability (a nav-bar "New post" and a dashboard "+") are both novel. Two controls with the same shape that do different things (same label, different handler) are suppressed unless CDP revision evidence intervenes.
- **The weights are hand-tuned on the benchmarks.** `LOW_VALUE_REPORT` (`results|score|reports|status|exports`), the −45 form deferral and the +20 search bonus were each added to fix a specific observed failure. The 8 policies (`exact`, `grouped`, `coverage`, `breadth`, `multidimensional`, `hierarchical`, `selective_model`, `model_all`) are alternate weightings, not alternate models.
- **Hierarchy is spatial, not functional.** `area_key` is `(session digest, first URL path segment)`. The hierarchical experiment ([HIERARCHICAL_EXPLORATION_REPORT.md](HIERARCHICAL_EXPLORATION_REPORT.md)) found 61% fewer area switches and no coverage change: *"Area locality and cost locality are different things."* SPAs (whiteboard, ComfyUI) and single-route apps (PrestaShop front office as observed) collapse to one area.
- **The stopping criterion is budget or frontier exhaustion.** PrestaShop and ComfyUI both ended with an empty executable frontier (29 s, 8 s), not with knowledge that the application was mapped.

### 2.2 State representation and grouping

**Mechanism (`state.signatures`).**
- `state_signature` = digest(full URL, title, safe control signatures, form shapes, session, markers, content fingerprint).
- `group_signature` = digest(route pattern, grouped control shapes, form shapes, session, markers, content fingerprint).
- `behavior_signature` refines the group with CDP handler revisions.
- `record_instance` = digest(path) when the path contains a UUID or integer token.
- `template_identity` = digest(route pattern, control shapes, form shapes).

**Diagnosis.**
- **Three concepts in one hash.** The group signature includes the *content fingerprint*, so a page template and its data are mixed. Two consequences, both observed:
  - *Over-splitting:* ComfyUI produced six groups for one route because transient initialization content differed ([WEBEXPLOITBENCH_EVALUATION.md](WEBEXPLOITBENCH_EVALUATION.md)). Each fresh load then failed to restore the "expected" state, so 5/5 actions failed.
  - *Under-splitting:* the whiteboard grouped 5 and 2 concrete canvases into single groups, because content was similar and the route pattern abstracted the UUID. The group's shared return path could then restore the wrong canvas ([RECORD_IDENTITY_REPORT.md](RECORD_IDENTITY_REPORT.md)).
- **Identity is only from the URL.** `INSTANCE_TOKEN` recognizes UUID and integer path segments, and only after a UUID-fragmentation bug was fixed (`6c76b56`). It misses:
  - slugs (`/blog/hello-world`, common in CMSs);
  - query-identified records (PrestaShop's `index.php?id_product=3&controller=product`; the SiyuCMS search results);
  - SPA records with no URL change (ComfyUI workflows, whiteboard objects on a canvas);
  - entities only visible in API responses.
- **No distinction between the page-level state and component-level state.** A modal, a drawer, a tab panel and an expanded menu all produce a new page-level group. FragGen-style component awareness was explicitly deferred ([RESEARCH_DECISIONS.md](RESEARCH_DECISIONS.md)).
- **Abstraction is fixed, not learned.** One wrong grouping cannot be refined by evidence; the reverse error (two groups that behave identically) is never merged. APE-style dynamic abstraction refinement was never attempted ([RELATED_WORK_AND_METHOD_COMPARISON.md](RELATED_WORK_AND_METHOD_COMPARISON.md) §2.3).

### 2.3 Graph A and record identity

**Mechanism (`exporter.build_graph_a`).** Graph A is an evidence graph with:
- node families: `states`, `page_templates`, `record_instances`, `actions_evidence`, `features`, `functional_workflows`, `advertised_actions`, resource nodes, external discoveries;
- edges: `offers_untested`, `offers_or_executes`, `results_in`, `starts_at`, `ends_at`, `validated_from_path_instance`, `instance_has_observed_state`, `observed_with_template`;
- `connection_evidence`: 219 entries in the fixture graph, auditing that each claimed edge has referenced evidence.

**Strengths to keep.** Every claim cites concrete observations or network events, and failed and untested claims are explicit. No sensitive values are stored. The audit (`graph_connections_missing_evidence`) has been 0 in every milestone.

**Diagnosis.**
- **It is an export format, not the agent's working model.** It is built in `_finalize`; the explorer never queries it. So "which capability lacks verification" cannot drive action selection.
- **`Feature` is a syntactic grouping.** `feature_key = digest(feature_action_signature, outcome_signature)`. The same capability reached from two interfaces becomes two features. Different capabilities behind the same control shape and route become one feature.
- **`FunctionalWorkflow` is one per transition.** It is a path instance, not a workflow type, and has no inputs, preconditions or effects.
- **Template and instance nodes are annotations.** The whiteboard example shows 3 instance references, but nothing says the canvas is an *entity type* with create/read/rename/share operations.

### 2.4 Runtime listener discovery

**Mechanism.**
- CDP `DOMDebugger.getEventListeners` is run over a bounded set of nodes.
- Created vs attached-later is distinguished with a `WeakSet`.
- Handler revisions (changed listener identity on a node) become `behavior_revision` keys.
- An evidence-only React-props probe and a DOM-size guard (20k elements) are included.

**Assessment.** Valuable, observational and cheap (about 0.6% of runtime on Crawl Maze). It added +3 markers on Crawl Maze, but found 0 candidates on React 19, because React delegates to the root ([RUNTIME_GENERALIZATION_REPORT.md](RUNTIME_GENERALIZATION_REPORT.md)). Its outputs feed the frontier (new candidate controls) and state identity (behavior signature).

**Keep it, but reposition it.** It is one *evidence source for interaction affordances*, not a discovery strategy in its own right. Framework adapters (React fiber props, Vue, Angular, LiteGraph canvases) should feed the same affordance interface (§2.10).

### 2.5 Network and resource evidence

**Mechanism.**
- `NetworkRecorder` attributes requests to the action window. Each request is recorded as method, sanitized URL, parameter names, body encoding and status.
- `TypedResourceSpider` performs passive GETs of references found in HTML, JS (AST), CSS, headers, manifests and sitemaps, under a shared HTTP budget.

**Diagnosis.**
- **The request evidence is never lifted into an API model.** `request_structure_key` exists only to schedule replay. `build_request_surfaces` runs after the run. Nobody asks:
  - which request creates the entity that a later request consumes (RESTler-style producer–consumer dependency);
  - which UI actions hit the same endpoint (interface equivalence);
  - whether a response carries IDs that later appear in URLs (instance identity).
- **No response-shape evidence.** Response bodies are not summarized, even as privacy-preserving shapes (top-level key names, ID-like field names, array cardinalities). So entity types are invisible. The whiteboard's `POST /api/canvases` returns a canvas with an `id`; the next URL contains that id. Agent 1 never links the two.
- **Blind spots in what is captured.**
  - WebSocket frames are not captured at all: there is no Playwright WebSocket listener.
  - Storage is read only as `localStorage`/`sessionStorage` key names, used as session markers, never as action effects.
  - Canvas and SVG changes leave no evidence.
  - `request_structure_key` drops query values, so applications that route by a parameter value (`index.php?controller=…`) collapse into one operation.
- **Causal attribution is time-window based.** Late, background, polling and WebSocket traffic is ambiguous ([STATE_AWARE_EXPLORATION_REPORT.md](STATE_AWARE_EXPLORATION_REPORT.md) lists this as a known limit). Window attribution is a reasonable default if confidence is recorded alongside it.
- **The resource spider dominated the Crawl Maze score, not functionality.** About 1,772 lines and most of the depth/quota/ablation flags exist to fetch more marker URLs. Fetching a URL proves the server answers, not that the application has a capability there. It is a useful *passive surface inventory* and should be demoted to an evidence source with its own budget, not a lever for the headline metric.

### 2.6 Functional workflow representation

- There is no input model. `_generated_value` fills fields per HTML type. Values are not tied to entity types, constraints learned from validation errors, or values produced by earlier actions.
- There are no preconditions, postconditions or effects. A transition records *what was seen*, not *what changed in the application*.
- Outcome classification (`_classify_result`) maps outcome signals to statuses:
  - signals come from `[data-outcome]`, `role=alert|status`, `aria-live`, `.success`, `.error`, `.alert`, `.notice`, `.message`;
  - `success` or `result` → `VERIFIED`; `validation_error` → `VALIDATION_FAILURE`; link without a signal → `NAVIGATION_ONLY`.
  - This is a UI-text oracle. `data-outcome` exists in our own fixtures, not in real applications.

### 2.7 Replay and verification

**Mechanism.**
- Fresh-context replay of the full workflow path.
- Checks: each control present, final group signature matches, content-token overlap, record identity, and, under the structure policy, reproduction of each request structure.
- 10 failure reasons are recorded.
- Paired search replay (primary vs contrast query) is the one differential oracle.

**Diagnosis.**
- **It verifies reproducibility, not the capability's claimed effect.** A replay of "Create canvas" that reaches the same page shape proves the path is repeatable. It does not prove that a canvas was created, that the creation is visible elsewhere, or that it persists.
- **Replay is the only verification instrument, and it is unavailable for any workflow with an observed write** (`f6744ba`). On the whiteboard, 36 of 43 observed transitions remained untested ([STATE_AWARE_EXPLORATION_REPORT.md](STATE_AWARE_EXPLORATION_REPORT.md)).
- **Replay is a separate phase after exploration** (30% reserve). Verification cannot inform exploration: a failed replay that reveals a hidden precondition is never acted on during the run.
- **Path replay assumes a deterministic environment reset (a fresh browser context).** That holds for client state only. Server state, time and other users are uncontrolled. This is exactly the assumption active-automata learning makes explicit (a reliable reset), and our applications violate it.

### 2.8 Safety mechanisms

**Mechanism.**
- `DANGEROUS_ACTION` label regex.
- POST forms disabled unless `allow_post_forms`.
- Strict origin scope.
- HTTP budget and redirect scope checks.
- Recorded-write suppression and unsafe-restoration refusal (`_known_write`).
- Dialog handling.
- Value redaction.

**Diagnosis.**
- **English-only lexical risk.** `delete|remove|destroy|…|log\s*out|sign\s*out` does not match `删除` (SiyuCMS is a Chinese CMS), icon-only buttons (trash can), or a destructive item inside a context menu. The `AMBIGUOUS_LABEL` and `SEARCH_SEMANTICS` regexes are also English.
- **Method-based write detection is both over- and under-inclusive.**
  - Read-only POST searches and GraphQL queries are blocked.
  - Mutating GETs (the stateful fixture, legacy PHP admin links) and WebSocket mutations pass.
  - The `f6744ba` report states this limit honestly.
- **There is a policy of refusal but no mechanism for containment.** Nothing restores state, so the only safe choice is to not do it. Stateful capabilities therefore stay permanently untested (§6 of [PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) and [ARCHITECTURAL_MIGRATION_PLAN.md](ARCHITECTURAL_MIGRATION_PLAN.md) address this).
- **Strict origin is correct but needs an adapter.** PrestaShop rendered links to its internal `prestashop` host; 50 of 64 controls were blocked. That is an environment publication fact, so it belongs in the environment adapter (canonical-origin aliases), not in an engine heuristic.

### 2.9 Benchmark- and fixture-specific assumptions in the engine

| Location | Assumption | Origin |
|---|---|---|
| `EXTRACT_SCRIPT` `componentFor`: `.control-area,section,article,[data-component]` | `.control-area` is a class name from a lab fixture | `decc0a2` (Crawlground breakthrough) |
| Interactive selector `[id^="toggle-"]` | Fixture ID convention (`coverage_lab.py` `#toggle-tools`) | coverage lab |
| Cosmetic selectors `i[class*="eye"]`, `[aria-label*="view count"]` | View-counter cosmetics on SiyuCMS-like pages | SiyuCMS iteration |
| Outcome selector `[data-outcome]` | Our fixtures' explicit outcome attribute | fixtures |
| `LOW_VALUE_REPORT` link penalty | Benchmark "results / scoreboard" pages | `decc0a2` |
| `SEARCH_SEMANTICS`, `AMBIGUOUS_LABEL`, `DANGEROUS_ACTION` | English vocabulary | general, but not language-independent |
| Resource spider depth/quota flags (`E_DEPTH_FLAGS`, document reserve, budget-aware deepening) | Tuned on Crawl Maze's 91-marker denominator | root-cause milestones |
| `INSTANCE_TOKEN` | Records are identified by numeric/UUID path segments | heldout shop, whiteboard |

None of these reads benchmark answers; the integrity boundary held. Each one, though, is a decision made to move a benchmark number, and collectively they encode a picture of "what a web app looks like" that ComfyUI and PrestaShop did not match.

### 2.10 Interaction vocabulary

The supported interactions are click, navigate, hover, focus, key_enter, press_hold, toggle, select_option, scroll_viewport, scroll_container, double_click and context_menu, plus form submit with generated values.

Missing for the target set:
- drag and drop, and coordinate gestures on a canvas (ComfyUI node graph; whiteboard drawing);
- connect-port gestures;
- keyboard shortcuts;
- rich-text editing (CMS editors);
- file upload (deliberately excluded);
- multi-select;
- wizard flows needing valid data;
- pagination and infinite scroll as *collections* rather than as "scroll the container".

A node-based editor's capabilities live almost entirely behind these.

### 2.11 Sessions and roles

- `context_label` plus hashed cookie-marker names; one role per run; operator storage state.
- No model of *role* as a dimension of capability (an anonymous user can browse products, a customer can check out, an admin can edit them).
- No cross-role comparison, so authorization structure is invisible.

### 2.12 Engineering structure

- `explorer.py` is a monolith. Browser control, extraction, frontier, restoration, replay, model calls, feature building, auditing, metrics and checkpointing share one class with heavy mutable state.
- 75 config flags. Many are ablation toggles that should not be in a production engine (`resource_frontier_policy`, `budget_allocation_strategy`, `html_extraction`, `response_body_reader`, `passive_document_max_depth`, …).
- 122 metrics, most counting mechanism events rather than answering a question about the application.
- `providers.py` holds optional LLM decision providers (`selective_model`, `model_all`). They were measured once and are not used; they are inconsistent with the "no paid calls" engine boundary.

## 3. Which decisions block understanding (ranked)

| Rank | Decision | Symptom in our evidence | Consequence |
|---|---|---|---|
| 1 | Transition-centric model; no capability/entity/precondition layer | Graph A "features" are action+outcome hashes; the whiteboard canvas is never an entity type | The agent cannot state what the app does, what it hasn't verified, or what depends on what |
| 2 | Fixed, monolithic state hash (template + data + session) | ComfyUI 6 groups / 0 transitions; whiteboard 5-canvas merge | Restoration fails or restores the wrong record; repeated views over-count |
| 3 | Static-priority syntactic-novelty frontier | Hierarchy changed travel, not coverage; PrestaShop exhausted on 1 area | Budget spent on shape novelty; no information-driven stopping |
| 4 | Path replay as both restoration and verification, with no isolation | Whiteboard: 9 stray canvases, then 36/43 transitions untestable | Stateful functionality is invisible by construction |
| 5 | Request evidence not modelled (no producer→consumer, no response shapes) | Request surfaces exist only as an export | Entity identity, dependencies and interface equivalence cannot be inferred |
| 6 | Lexical and method-based safety/oracles | English regexes; POST-search blocked; `data-outcome` oracle | Behavior is wrong on non-English and non-conventional apps |
| 7 | Monolithic explorer and config accretion | 4,042-line class; 75 flags; 8 policies | Each new idea becomes another flag and weight; hard to test alternatives |

## 4. Retain / redesign / replace / deprecate

| Component | Verdict | Rationale |
|---|---|---|
| Scope router, `HttpBudget`, redirect accounting | **Retain** | Correct, audited, environment-independent |
| `NetworkRecorder` with value redaction | **Retain**, extend | Add privacy-preserving response *shapes* and ID-flow hashes (§[PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) §4) |
| Readiness detection | **Retain** | Generic; needed by every environment. Separate "settled" from "identity" so transient content does not define state |
| DOM extraction (`EXTRACT_SCRIPT`) | **Redesign** | Strip fixture selectors; emit an *affordance list* plus *component regions* rather than a single control list |
| `ListenerObserver` (CDP) | **Retain** as an affordance source | One of several affordance providers behind one interface |
| Framework probe (React props) | **Promote** to an affordance provider | Evidence-only today; React apps need it to see handlers |
| State signatures | **Replace** with layered identity | Separate template, runtime state, component state and entity instances (§[PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md)) |
| `record_instance` / `template_identity` | **Redesign** into the entity-instance resolver | Multi-source identity: URL, query, response IDs, visible keys |
| Frontier + 8 policies + `AreaTourPlanner` | **Replace** with the hypothesis-driven hierarchical planner | §[EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md). Keep `coverage` frozen as a baseline arm |
| `_restore` path replay | **Redesign** as one restoration strategy among several | Ranked: live reuse → history → path replay (read-only only) → environment snapshot via adapter |
| Replay phase and scheduler | **Replace** with interleaved verification experiments | Request-structure keys and failure reasons carry over unchanged |
| Paired-search oracle | **Generalize** | It is the template for differential oracles (contrast inputs, cross-view checks) |
| `action_behavior` classification | **Retain**, extend | It becomes the effect-evidence record; adding adapter-provided ground-truth effects (DB diff) where authorized |
| `DANGEROUS_ACTION` regex | **Demote** to one of several risk signals | Add icon/ARIA semantics, request evidence, adapter risk policy; language-independent tokens where possible |
| Graph A exporter | **Retain** as a projection | ACG is the working model; Graph A becomes an export view for backward compatibility |
| `TypedResourceSpider` | **Retain, demote** | Passive surface inventory with its own small budget; not a driver of the headline metric |
| ZAP adapter | **Retain** | External evidence source, already provenance-tagged |
| Model providers (`selective_model`, `model_all`, form assistance) | **Deprecate** from engine | May return later as an optional offline hypothesis source; not part of the universal engine |
| Ablation-only flags | **Deprecate** | Freeze defaults; keep archived configs for reproducing old results |
| Fixture/benchmark selectors (§2.9) | **Remove** from engine | If needed, re-express as an adapter-supplied hint with provenance, never default behavior |
| Fixtures + held-back ground truth | **Retain**, extend | Ground truth must gain capabilities, entities and dependencies (§[GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md)) |

## 5. Evidence base for this audit

All quantitative claims above come from committed reports and artifacts:
- [REPLAY_VALIDATION_REPORT.md](REPLAY_VALIDATION_REPORT.md) (3-arm × 3-seed Crawl Maze);
- [RUNTIME_GENERALIZATION_REPORT.md](RUNTIME_GENERALIZATION_REPORT.md) (React whiteboard);
- [STATE_AWARE_EXPLORATION_REPORT.md](STATE_AWARE_EXPLORATION_REPORT.md) and [RECORD_IDENTITY_REPORT.md](RECORD_IDENTITY_REPORT.md) (`f6744ba`);
- [WEBEXPLOITBENCH_EVALUATION.md](WEBEXPLOITBENCH_EVALUATION.md) (PrestaShop, ComfyUI);
- [HIERARCHICAL_EXPLORATION_REPORT.md](HIERARCHICAL_EXPLORATION_REPORT.md);
- [GENERALIZATION_BASELINE.md](GENERALIZATION_BASELINE.md) (JS-heavy lab, ZAP Crawlground);
- the SiyuCMS reports under `agent1/experiments/siyucms_*`.

No benchmark was re-run for this audit.

Some limits of this audit:
- **SiyuCMS search runs:** only reports were inspected; the authenticated admin area was never mapped, so CMS-specific claims (slugs, rich-text editors, Chinese labels) are partly about the *class* of application. For SiyuCMS, the only measured fact is that public search was the main verified workflow.
- **ComfyUI:** the evidence is a single 8-second run that never executed a transition. What ComfyUI needs is inferred from its known architecture (LiteGraph canvas, REST + WebSocket API), not from Agent 1 observations.
