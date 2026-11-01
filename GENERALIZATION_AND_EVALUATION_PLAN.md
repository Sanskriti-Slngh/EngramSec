# Generalization and evaluation plan

Status: design proposal. No experiments were run for this document.
Related: [PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) (what is scored), [EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md) (what is compared), [ARCHITECTURAL_MIGRATION_PLAN.md](ARCHITECTURAL_MIGRATION_PLAN.md) (when each evaluation runs).

## 1. The engine/adapter boundary

### 1.1 Rule

The **universal engine** (`agent1/engine/…` after migration) may only consume:
- what a browser user of the application could observe: DOM, accessibility tree, network traffic of its own session, CDP listener metadata and framework-exposed handler metadata;
- generic, application-independent knowledge: HTML/HTTP/ARIA semantics, common identifier formats and interaction kinds.

The engine must not know any application's selectors, routes, labels, workflows, data, markers or expected results.

**Environment adapters** (`environments/<name>/adapter.py`) provide everything environment-specific. They do it through a fixed, typed interface. Each value an adapter gives the engine is recorded with provenance in the run artifact, so a reviewer can see exactly what non-generic information a run used.

### 1.2 Adapter interface

```python
class IsolationLevel(IntEnum):
    L0_NONE = 0; L1_BROWSER_CONTEXT = 1; L2_DISPOSABLE_INSTANCE = 2
    L3_DB_SNAPSHOT = 3; L4_FULL_STACK_SNAPSHOT = 4; L5_TRANSACTION_ROLLBACK = 5

class EnvironmentAdapter(Protocol):
    # --- lifecycle (operator side) ---
    def provision(self) -> EnvironmentHandle: ...            # start isolated stack, loopback only
    def teardown(self, handle) -> None: ...                  # remove only resources it created
    # --- given to the engine (recorded with provenance) ---
    def start_url(self, handle) -> str: ...
    def origin_aliases(self, handle) -> list[str]: ...       # e.g. PrestaShop internal host
    def roles(self) -> list[RoleSpec]: ...                   # label + how to obtain a session
    def session(self, handle, role: str) -> StorageStateRef: ...  # path outside repo; never logged
    def isolation(self) -> IsolationLevel: ...
    def risk_policy(self) -> RiskPolicy: ...                 # allowed effect classes, stubbed sinks,
                                                             # extra danger lexicon (e.g. zh-CN), compute caps
    def snapshot(self, handle, label: str) -> SnapshotId: ...           # L3+
    def restore(self, handle, snap: SnapshotId) -> None: ...            # L3+
    def start_state_fingerprint(self, handle) -> str: ...               # independent check (§PROPOSED §6.3)
    # --- evaluator side only (never visible to the engine unless explicitly enabled) ---
    def ground_truth(self) -> GroundTruthRef: ...            # capability/entity/dependency annotations
    def effect_digest(self, handle, since: SnapshotId) -> EffectDigest: ...  # row deltas, column names
```

**Allowed adapter content:**
- infrastructure (provisioning, ports, aliases);
- authentication (sessions per role);
- isolation (snapshot, restore, verify);
- risk policy (which effect classes may run; stubbed external sinks; a language lexicon as a generic *asset* keyed by locale, not by application);
- evaluation material.

**Forbidden adapter content:**
- selectors, routes or URL lists given to the engine as targets;
- workflows or action sequences;
- expected capabilities;
- benchmark markers;
- any hint whose value comes from reading the application's source or the ground truth.

An automated check enforces this (§5, item 4).

**Framework-provider admissibility.** An affordance or effect provider that reads library-level state (React props, a canvas library's node count) may live in the engine only if all of these hold:
1. it targets a documented, public library structure, not an application's globals;
2. it is read-only and returns counts or handler names, never data values;
3. it is evaluated on at least two applications that use the library.

Otherwise it is an adapter-supplied hint. Its outputs are tagged with provenance, and runs that use it are excluded from universal-engine claims. A LiteGraph node-count probe used only by ComfyUI is therefore an adapter hint until a second LiteGraph application is in the suite.

### 1.3 Common vs environment-specific components

| Component | Universal engine | Adapter |
|---|---|---|
| Browser control, readiness, network capture, scope router, HTTP budget | ✓ | origin aliases only |
| Affordance providers: DOM, ARIA, CDP listeners, framework probes (React, Vue, Angular, canvas libraries) | ✓ (framework-generic, not app-generic) | — |
| Interaction executors: click, form, keyboard, scroll, hover, drag, canvas gestures | ✓ | — |
| ACG resolvers: template, view abstraction, entity, operation, capability, condition | ✓ | — |
| Planner L0–L3, oracles | ✓ | — |
| Danger signals: ARIA, dialogs, icons, request/effect evidence | ✓ | locale lexicon asset, extra risk policy |
| Authentication | session use and role labels | how to obtain sessions; credentials never reach the engine |
| Isolation and reset | consumes the level and the restore API | implements the level |
| Ground truth, effect digests, scoring | — | ✓ (evaluator side) |
| Setup quirks (macOS `targetctl` patches, loopback binding) | — | ✓ |

## 2. How the same engine investigates five kinds of application

The engine code path is identical in each case. What differs is what the model fills in, and therefore which questions the planner generates.

| Kind (our instance) | What dominates the ACG | Dominant question classes | Key engine requirement | Adapter contributions |
|---|---|---|---|---|
| **Conventional CRUD** (stateful lab; whiteboard's canvas management) | Entity types with create/read/update/delete; list + detail templates; ID flow from responses to URLs | `bind_affordance` → `sample_instance` → `verify_effect` (cross-view, round-trip) → `test_dependency` | Entity resolver with response ID flow; isolation for write verification | L3 snapshot (SQLite copy / Postgres template DB); authenticated role |
| **CMS** (SiyuCMS) | Public read capabilities (list, search, view by category/tag) plus admin authoring; slugs; rich text; non-English UI | Differential `verify_effect` for search/filter; `role_contrast` anonymous vs admin; `sample_instance` over articles | Slug/query identity; language-independent behavioral classes; rich-text input executor | Admin session; zh-CN danger lexicon asset; L2/L3 for authoring |
| **E-commerce** (PrestaShop; held-out shop fixture) | Catalogue entities; cart as session-scoped entity; chained dependencies (view → add to cart → checkout); external effects | `test_dependency` along the purchase chain; `verify_effect` for cart via cross-view; checkout `BLOCKED` without a stub | Query-parameter identity; session-scoped entities; external-effect risk class | Origin alias; mail/payment stub declaration; snapshot of catalogue DB |
| **Node-based visual editor** (ComfyUI) | One route; many ComponentStates; client-side graph entities (nodes, links); a server job queue; WebSocket progress | `bind_affordance` over menus/dialogs; `find_entry_point` from API catalogue traffic; `sample_instance` over node types; canvas gestures | Content-free view abstraction; readiness gating; canvas gesture executor; WebSocket evidence | Compute cap for queue experiments; L4 snapshot (outputs on disk); tiny default workflow allowed by risk policy |
| **Dynamic benchmark with hidden interactions** (Crawl Maze, Crawlground) | Affordances that appear only via listeners, timers or handler revisions; operations; few entities | `bind_affordance`, `find_entry_point`, `split_test` (handler revisions) | CDP listener provider; readiness; passive resource inventory | None beyond the start URL |

## 3. Evaluation framework

### 3.1 Ground truth schema (extends the current fixture schema)

The current fixture ground truth (`heldout_shop_ground_truth.json`: `areas`, `controls`, `requests`, `instances`, `contexts`) scores surfaces. It gains capability-level records:

```json
{
  "application": "whiteboard",
  "annotation": {"annotator": "independent", "source": ["public docs", "API route list", "DB schema"],
                 "frozen_at": "2026-11-…", "engine_revision_unseen": true},
  "roles": [{"id": "anon"}, {"id": "member"}],
  "entity_types": [{"id": "canvas", "identity": "path:/canvas/{uuid}", "table": "canvases"}],
  "capabilities": [
    {"id": "create_canvas", "behavioral_class": "instance_creation", "entity": "canvas", "roles": ["member"],
     "operations": ["POST /api/canvases"], "observable_effects": ["instance_appeared(canvas)"],
     "class_observable_to_role": true, "entry_points": ["dashboard:create_form"],
     "effect_risk": "server_write", "in_scope": true},
    {"id": "share_canvas", "behavioral_class": null, "entity": "canvas", "roles": ["member"],
     "operations": ["POST /api/canvases/{id}/invites"], "observable_effects": ["component_state_changed(share_dialog)"],
     "class_observable_to_role": false, "requires": ["exists(canvas owned_by self)"], "in_scope": true},
    {"id": "draw_shape", "behavioral_class": null, "entity": "canvas", "interaction": "canvas_gesture",
     "observable_effects": ["visual_region_changed(canvas)"], "class_observable_to_role": false,
     "in_scope": true, "note": "unsupported until gesture executor"}
  ],
  "dependencies": [{"from": "create_canvas", "to": "share_canvas", "type": "enables"}],
  "equivalent_interfaces": [{"capability": "create_canvas", "entry_points": ["dashboard:create_form", "empty_state:button"]}],
  "instances": [{"entity": "canvas", "seeded": 2}]
}
```

These whiteboard capability entries illustrate the schema only; they are not an annotation.

Annotators use the model's closed class vocabulary and effect atoms ([PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) §5.3, §5.6):
- `behavioral_class` is `null` when no observable rule could identify the capability. Sharing an invitation is an example: its observable effect for the inviting role is at most a dialog change.
- `class_observable_to_role: false` removes the capability from the M1b denominator but keeps it in M1a.

Business names (share, publish, checkout) appear only in `id` and notes. They are never scored. Real annotations are produced by someone who does not develop the engine, using public documentation, the server route table and the DB schema. They are stored outside `agent1/` and loaded only by the evaluator after the run, as today's fixtures are.

### 3.2 Metrics (in priority order)

| # | Metric | Definition | Notes |
|---|---|---|---|
| M1a | **Capability discovery recall / precision (behavior)** | A ground-truth capability matches an ACG capability when they share ≥ 1 operation key (method + route pattern + dispatch) or, for capabilities without operations, the same entry template plus ≥ 1 effect atom. Recall is over in-scope capabilities reachable in the given roles; precision is over ACG capabilities at status ≥ `OBSERVED`. Unidentified operations count | One-to-one Hungarian matching on match score; ambiguous matches reported separately; identical-signature ground-truth pairs are reported as "indistinguishable by design" |
| M1b | **Behavioral identification** | Precision: the fraction of asserted behavioral classes equal to the annotated class. Recall: the fraction of matched capabilities with `class_observable_to_role: true` that received the correct class. Unidentified operations are neither false positives nor recall hits | Labels are never scored; a wrong class is worse than none |
| M2 | **Functional workflow coverage** | Fraction of in-scope capabilities with status ≥ `REPRODUCED`, and separately `VERIFIED` | Splits "found" from "confirmed" |
| M3 | **Verification correctness** | Of `VERIFIED` claims, the fraction confirmed by the adapter effect digest or ground truth; false-verified rate | Requires an adapter at L2+; the most important precision metric |
| M4 | **Entity and state identity accuracy** | B-cubed precision/recall of EntityInstance clustering vs true instances; **false merge count** (distinct true instances in one node); false split count; view-state purity (fraction of view-state members with the same available capability set) | Replaces the structural `incorrect_state_merges` audit with ground-truth scoring |
| M5 | **Dependency accuracy** | Precision/recall of `requires`/`enables` edges (status ≥ `OBSERVED`) against annotated dependencies | Reported by edge status |
| M6 | **Interface-equivalence accuracy** | Precision/recall of `equivalent_interface` pairs | |
| M7 | **Exploration efficiency** | Area under the capability-discovery curve over 0–N browser actions (normalized); actions to 50% / 80% of final recall; restoration actions per experiment; wall time | Matched budgets |
| M8 | **Robustness** | Per-environment scores; worst-environment M1a/M1b; variance across ≥ 3 repeats; cross-environment rank stability | The headline is a *distribution*, not a mean on one benchmark |
| M9 | **Safety and integrity** (gates, not objectives) | Unexpected writes (adapter digest deltas not attributed to a permitted experiment); out-of-scope requests; destructive actions executed; sensitive-value leaks; graph claims missing evidence | Any non-zero leak, scope or destructive count fails the run |
| M10 | **Stopping calibration** | Claimed saturation vs actual M1a at stop; reliability of predicted new-capability probabilities | Validates the planner's self-assessment |

Legacy metrics remain as regression checks:
- Crawl Maze marker recall (strict 2xx, offline scorer);
- fixture area/control/request recall;
- replay success.

None of them is a headline.

### 3.3 Environment suite and roles in the protocol

| Set | Environments | Use |
|---|---|---|
| **Development** (engine may be tuned against aggregate results) | `coverage_lab`, `js_heavy_lab`, `replay_lab`, `stateful_lab`, `transfer_library`, Crawl Maze (regression only), whiteboard (disposable runner) | Building and debugging; fixtures get capability ground truth |
| **Validation** (used to choose between frozen candidate designs, at most once per milestone) | `heldout_shop`, ZAP Crawlground, SiyuCMS (public + admin when an authorized session exists), and a subset of E2EBench (AutoE2E, ICSE 2025: 8 apps with 13–130 instrumented ground-truth features each; see [RELATED_WORK_AND_METHOD_COMPARISON.md](RELATED_WORK_AND_METHOD_COMPARISON.md) §2.5) | Model selection without per-case inspection: only aggregate metrics are read. E2EBench's feature grammar must be mapped to our capability schema, and that mapping must be reported |
| **Held-out test** (never used for design; frozen config; aggregate reporting only) | PrestaShop, ComfyUI (WebExploitBench public targets), plus ≥ 2 applications chosen by someone other than the engine developer from different categories (for example an issue tracker and a wiki/forum) | Generalization claims |

**WebExploitBench terms.** Its gated dataset terms state that outputs and derived artifacts are evaluation-only and must not be used for agent optimization ([WEBEXPLOITBENCH_EVALUATION.md](WEBEXPLOITBENCH_EVALUATION.md)). This matches the held-out role exactly:
- WebExploitBench targets are never development or validation environments;
- only aggregate per-environment metrics are reported;
- vulnerability metadata is never read.

### 3.4 Baselines (all budget-matched)

1. **Frozen `f6744ba` Agent 1** (`coverage` policy, current replay), scored through the new evaluator via a Graph A → ACG import.
2. **Same ACG resolvers + current frontier.** Isolates the planner's contribution from the model's.
3. **BFS over the ACG affordances.** A naive planner on the same model.
4. **ZAP traditional spider** (existing adapter) for operation/URL inventory only. It cannot score on capabilities beyond operation matches; that limit is the point of including it.
5. **Optional:** an LLM-guided exploration baseline run *offline by the evaluator* for comparison only, never inside Agent 1, and only if budget is explicitly approved.

### 3.5 Statistical protocol

- **Repeats:** ≥ 3 per arm per environment. Seeds must vary something that matters (frontier tie-break, sampling order). The replay milestone's seeds did not vary FIFO runs, so its repeats were effectively identical ([REPLAY_VALIDATION_REPORT.md](REPLAY_VALIDATION_REPORT.md)).
- **Pairing:** paired comparisons on the same environment snapshot.
- **Uncertainty:** report per-environment means with min–max, and a bootstrap 95% CI over environments for cross-environment claims.
- **What counts as a win:** a design is better only if it improves M1a/M1b/M2 on a majority of validation environments, does not worsen M3/M4 beyond their CIs, and passes all M9 gates.
- **Live-time budget** per milestone is preregistered: development ≤ 35 min, validation ≤ 60 min, held-out ≤ 60 min.

## 4. Experimental validation of each major proposal

| Proposal | Hypothesis | Experiment | Success criterion |
|---|---|---|---|
| Layered identity (template / view / entity) | Fixes false merges without raising false splits | Stateful lab + whiteboard + a new "transient init" fixture (ComfyUI-like) | M4 false merges 0; views per template ≤ the current group count; ComfyUI-like fixture yields 1 initial view |
| Response shapes + ID flow | Entities and producer–consumer dependencies become inferable | Fixture with JSON API IDs vs HTML-only IDs | Entity recall improves in the JSON case; no regression in the HTML case |
| Capability identity from operations/effects | Interface equivalence and same-label disambiguation | Fixture: 3 entry points → 1 capability; 2 same-label buttons → 2 capabilities | M6 P/R ≥ 0.9 on the fixture |
| Hypothesis-driven planner | Better capability recall per action than the frontier | Baselines 2 and 3 vs planner on the development + validation sets | Higher M7 AUC and M1a at a fixed budget, without lower M1b precision on most environments |
| `Unlock` + dependency experiments | Reaches gated capabilities | Fixture with 3-step prerequisite chains (auth → create → share) | Gated capability recall; M5 recall |
| Oracle ladder | `VERIFIED` means something | Adapter effect digests on the stateful lab and whiteboard | M3 false-verified rate ≤ 5% |
| Isolation levels | Write verification without leaks | Stateful lab at L3 (SQLite copy), whiteboard at L3 (Postgres template DB) | M9 unexpected writes 0; create/update capabilities reach `VERIFIED` |
| Saturation stopping | The agent knows when it is done | Compare claimed saturation vs ground truth | Areas claimed saturated have M1a ≥ 0.9 |

### 4.1 Deterministic offline falsification tests

These run without a browser, on committed inputs, and must pass before the corresponding live phase. A failure falsifies the mechanism named in the test, not just a score.

**T1: capability identification** (corpus `evaluation/corpora/signatures/*.jsonl`). Hand-written evidence logs in the engine's evidence format, each with an expected capability partition:

| Case | Evidence | Expected partition |
|---|---|---|
| T1.1 dispatch values | two affordances, `GET /index.php?controller=…`, different constant values (PrestaShop style) | 2 capabilities |
| T1.2 same request, different labels | two affordances, identical request structure and effects, labels "Save" / "保存" | 1 capability, 2 bindings (labels must not split it) |
| T1.3 client-only | two toggles with no request, different region targets | 2 capabilities |
| T1.4 WebSocket only | sends of two message classes; then two sends of one class | 2, then 1 |
| T1.5 canvas | two drag gestures on one canvas, only `visual_region_changed` | 1 unidentified operation family, no class |
| T1.6 delegated handler revision | same visible button, different operation before and after a context change | 2 capabilities + 1 learned context predicate |
| T1.7 equivalent interfaces | whiteboard-style create form and empty-state button, same signature | 1 capability, `equivalent_interface` |
| T1.8 indistinguishable | two settings saved via the same endpoint, same parameters, no dispatch | 1 capability (documented limit) |

Pass condition: exact partition equality (adjusted Rand index 1.0) on every case.

**T2: planner.** Run on the offline simulator; defined in [EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md) §10.3.

**T3: semantic grounding.**
- **T3a text invariance.** Rewrite every display string in the T1 corpus and in recorded fixture logs: affordance names, headings, titles, outcome text. Use random strings, then a zh-CN rendering. Route paths are kept, because they are structural. Capability partitions, behavioral classes, claim statuses and the planner decision-log hash must be identical; only display labels may differ.
- **T3b evidence ablation.** Removing the cross-view evidence from a create log must remove `instance_creation` and leave an unidentified operation. Removing one side of a differential pair must remove `collection_query`. No other class may appear in its place.
- **T3c no class without a rule.** Over 1,000 seeded random logs, every asserted class must cite a rule id and evidence ids satisfying that rule's minimum status.
- **T3d label provenance.** Every display label must occur verbatim in a cited evidence record.
- **T3e planner isolation.** A static check that the planner package never reads layer-3 label fields. This is the static counterpart to T3a's decision-log invariance.

## 5. Avoiding overfitting to Crawl Maze or any one benchmark

1. **Demote Crawl Maze to a regression check.** Its denominator is URL markers, so it rewards fetching, not understanding. Rule: a change may reduce Crawl Maze markers by ≤ 2 only if it improves M1a/M1b/M2 on ≥ 3 other environments; it may never be adopted *because* it raised Crawl Maze alone.
2. **Freeze constants before validation.** The few constants (`λ_unlock`, class floors, saturation thresholds, evidence weights) are set on development fixtures, written in a preregistration file with a git hash, then frozen for validation and held-out runs.
3. **Leave-one-environment-out development.** When tuning on development fixtures, report the held-out fixture's metric before and after each change. A change that only helps the environment it was designed for is flagged.
4. **Static checks on the engine package** (CI test):
   - no string literal in `agent1/engine/` matches any route, label, selector or class name appearing in `development_apps/`, `environments/` or ground-truth files (generated deny-list);
   - no import of adapter or ground-truth modules from the engine;
   - engine config has no per-environment keys.
5. **Independent annotation.** Capability ground truth is written by someone not modifying the engine, from documentation and schemas, and frozen before the first run on that environment.
6. **Report everything, every time.** Every milestone report contains the full environment table (including failures such as ComfyUI 0 transitions), not a selected subset.
7. **Rotate held-out applications.** After a held-out application has been used for two milestones it moves to validation, and a fresh one is added. This limits slow leakage through repeated reading of aggregate results.
8. **No fixture-shaped features.** New fixtures are written *after* the corresponding engine mechanism exists, by testing against a specification of an application class. That is the reverse of how `.control-area` and `[id^="toggle-"]` entered the engine.

## 6. What could go wrong with the evaluation itself

| Risk | Mitigation |
|---|---|
| Capability annotation is subjective (granularity) | Annotate at behavioral class × entity × role granularity, with `null` class where no rule can apply; adjudicate disagreements with a second annotator on a sample; report inter-annotator agreement |
| Matching rules favour operation-heavy apps | Separate UI-only capability rule; report M1a split by "has operation" vs "UI-only" |
| Effect digests unavailable for some stacks | Report M3 as "not measured" rather than substituting UI signals |
| Held-out apps too expensive to set up (ComfyUI 4-minute build, 10 GB images) | Cache images; count setup outside mapping time (as already done); keep a small held-out set run rarely |
| Evaluation budget exceeds live-time limits | Preregistered per-milestone live-time caps; prioritize paired designs over many arms |
