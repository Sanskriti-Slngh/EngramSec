# Architectural migration plan

Status: plan. No production code was changed.
Inputs: [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md), [RELATED_WORK_AND_METHOD_COMPARISON.md](RELATED_WORK_AND_METHOD_COMPARISON.md), [PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md), [EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md), [GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md).

## 1. Recommendation

Rebuild Agent 1 as a **model-centred application-understanding engine**:

1. **Keep the evidence layer.** Retain browser execution, scope and budget routing, network capture with redaction, readiness, CDP listener observation, request-structure keys, action-behavior classification and provenance audits.
2. **Make the Application Capability Graph the working model.** It is an event-sourced view over an append-only evidence log, with separate templates, view states, component states, entities, operations, capabilities, conditions, effects and claims carrying status and confidence. A capability is identified by its observable behavior signature. It receives one of a small closed set of behavioral classes only when an evidence rule fires; otherwise it is reported as an **unidentified operation**. Display text is kept as labelled provenance and never defines meaning.
3. **Replace the frontier with a hypothesis-driven hierarchical planner.** An area allocator, a question selector valued by expected information gain plus unlock value per cost under a risk gate, and an experiment designer that plans restoration over reproducible model edges (including direct-URL teleports) and picks the strongest available oracle.
4. **Move everything environment-specific into adapters.** Adapters also provide isolation levels, so write-capable capabilities can be verified only where containment is attested and independently checked.
5. **Score capabilities, not URLs.** Use capability-level ground truth, a development/validation/held-out split, and Crawl Maze demoted to a regression check.

This is a redesign of the decision and model layers, not a rewrite of the evidence layer. Most existing code survives as providers, executors and exporters. The 4,042-line explorer, the 8 exploration policies, the static frontier and the post-hoc feature grouping do not.

## 2. Highest-impact changes (ranked)

| Rank | Change | Why highest impact | First measurable effect |
|---|---|---|---|
| 1 | **ACG with layered identity** (template / view / entity separation; content removed from state identity; reversible `same_as` claims) | Root cause of ComfyUI's 0 transitions and the whiteboard's wrong-record merges; prerequisite for every later change | False merges 0 on archived development-set runs (whiteboard, stateful lab), and one initial view on a new transient-initialization development fixture. ComfyUI itself is held-out and is not used for this |
| 2 | **Capabilities defined by behavior signatures (operations incl. dispatch values and WebSocket message classes + effect atoms), closed grounding rules, response-shape and ID-flow evidence** | Turns "transitions" into "what the app does" without inventing meaning; makes entities and dependencies inferable; language-independent | Offline tests T1 and T3 pass; M1a/M1b on fixtures with new ground truth |
| 3 | **Planner over questions with interleaved verification and model-based restoration** | Spends budget on unknowns instead of shape novelty; reaches prerequisite chains; replaces root-replay restoration with teleports | Capability-discovery AUC vs the frozen frontier at matched budgets |
| 4 | **Adapter boundary + isolation levels + attested snapshots** | The only way stateful capabilities (create, update, cart, queue) can ever be verified safely | Write-capable capabilities reach `VERIFIED` on the stateful lab at L3 with zero unexpected writes |
| 5 | **Oracle ladder** (differential, cross-view, round-trip, inverse, conformance) | Makes "verified" mean functional, not reproducible | Verified-claim correctness against adapter effect digests |
| 6 | **Affordance providers and interaction executors** (framework probes as providers; drag and canvas gestures) | Needed for React-delegated handlers, ComfyUI and whiteboard drawing | ComfyUI and whiteboard canvas capabilities move from `BLOCKED(unsupported)` to `OBSERVED` |
| 7 | **Evaluation framework** | Without it, every change optimizes Crawl Maze by default | Capability-level scorecards across ≥ 5 environments |

## 3. Target module layout

```
agent1/
  evidence/            # retained: browser session, observers, network recorder, readiness,
    browser.py         #   scope router + HttpBudget, listeners.py, resource_spider.py (demoted),
    network.py         #   zap_adapter.py; + response_shape.py, idflow.py (HMAC tokens)
    affordances/       # dom.py (EXTRACT_SCRIPT without fixture selectors), cdp.py, react.py, canvas.py
    log.py             # append-only evidence log (JSONL), replaces in-memory artifact lists
  model/               # ACG
    nodes.py claims.py # PROPOSED_APPLICATION_MODEL §2–4
    resolvers/         # template.py, abstraction.py, entity.py, operation.py, capability.py,
                       #   condition.py, area.py — pure functions over evidence
    materialize.py     # rebuild/incremental update; same_as / split handling
  planner/
    questions.py       # generators per QuestionKind
    value.py           # EIG, unlock, cost model, Good–Turing saturation
    allocator.py       # discounted UCB over areas, class floors
    designer.py        # restoration graph, inputs, oracle selection
    oracles.py         # differential, cross_view, round_trip, inverse, conformance
  safety/              # gate: EffectRisk × IsolationLevel table, danger signals, existing filters
  execution/           # executor: runs experiment plans step by step through the safety gate
  export/              # graph_a.py (compat projection), acg_json.py, report.py
  engine.py            # main loop (EXPLORATION_PLANNER_DESIGN §6)
  legacy/              # frozen f6744ba explorer for baseline arms (read-only)
environments/
  <name>/adapter.py    # EnvironmentAdapter implementations: fixtures, whiteboard, siyucms,
  <name>/ground_truth/ #   prestashop, comfyui, crawlmaze; evaluator-side material
evaluation/
  score_capabilities.py, score_identity.py, score_dependencies.py, import_graph_a.py,
  engine_purity_check.py, appsim.py (offline simulator), corpora/signatures/ (T1/T3 logs)
```

## 4. Phases

Each phase ends with a commit that passes the full test suite and its own exit criteria. Live browser time is budgeted per phase, and the browser-free phases come first so that archived evidence is used before new runs are spent.

### Phase 0: Freeze the baseline and build the evaluator (no engine change, no live browser time)

- Tag `f6744ba` as `agent1-baseline-frontier`. Copy the explorer to `agent1/legacy/` for baseline arms.
- Write capability-level ground truth for the existing fixtures (`coverage_lab`, `js_heavy_lab`, `replay_lab`, `stateful_lab`, `heldout_shop`, `transfer_library`), extending today's schema (§[GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md) §3.1). An annotator other than the engine developer should write held-out annotations.
- Add `evaluation/import_graph_a.py`, so archived Graph A runs can be scored at capability level where possible.
- Add `evaluation/engine_purity_check.py` (the static deny-list check) and run it against the current code. It should flag the fixture selectors in audit §2.9: a known-failing baseline.
- Write the T1/T3 evidence-log corpora ([GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md) §4.1) and their expected partitions *before* any resolver exists, so the tests cannot be fitted to an implementation.
- **Exit:**
  - archived development-set runs scored with M1a (M1b where effects are recorded; M3 is not measurable until Phase 5);
  - a baseline scorecard committed;
  - corpora committed.
- **Risk:** Graph A lacks the fields to recognize capabilities. The scorecard then reports "not determinable", which is itself a finding.

### Phase 1: Offline ACG over archived evidence (shadow, no live browser time)

- Implement `model/` resolvers that consume existing `run.json` / Graph A artifacts. Archived observations, transitions and network events are enough for template, view abstraction, URL-entity, operation and capability resolution.
- Run them over archived **development-set** runs: whiteboard (`state_aware_whiteboard_*`), Crawl Maze (`replay_crawlmaze_3x3`) and the fixtures. Archived SiyuCMS runs are validation material: they are scored once at the end of the phase, aggregate only. Archived ComfyUI and PrestaShop runs are held-out and are not used.
- **Exit criteria:**
  - stateful lab: 2 record instances and 1 template, with no false merge;
  - whiteboard: seeded + created canvases as separate instances;
  - Crawl Maze view-state count ≤ the current group count, without increasing the merge audit;
  - capability recall measurable on fixtures;
  - **T1 and the model-level T3 checks pass** on the Phase 0 corpora: T3a export invariance, T3b, T3c and T3d. The planner-level T3 checks (T3a decision-log invariance, T3e planner isolation) cannot run before a planner exists. They are unchanged and are exit criteria of Phase 1b.
- **Why first:** it tests the model on real evidence at zero browser cost and de-risks the expensive phases.
- **Risk:** archived evidence lacks response shapes and ID flow. Entity recall is then lower bound only, which Phase 2 addresses.

### Phase 1b: Offline planner on the simulator (no live browser time)

- Implement `evaluation/appsim.py` and the planner's value, selection and allocation code against the simulator ([EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md) §10).
- Implement the legacy-selector wrapper over the same simulator interface.
- **Exit:** T2a–T2f pass, and the planner-level T3 checks pass (T3a decision-log hash unchanged under label rewriting; T3e planner never reads label fields).
  - If T2f fails, the EIG machinery is dropped in favour of the cheaper question structure before any live experiment.
  - If T2d fails, the planner is restricted to applications with detected structure.
- **Depends on:** Phase 1 resolvers (question generators read the ACG).

### Phase 2: Behaviour-preserving decomposition + new evidence kinds (≤ 10 min live)

- Split `explorer.py` into `evidence/`, `execution/`, `safety/` and `export/` behind interfaces, including the `Selector` interface. The old frontier still drives, through the legacy selector.
- Add new evidence capture, all value-free:
  - response shapes;
  - HMAC identifier-flow tokens;
  - dispatch-parameter tokens;
  - WebSocket message classes (not captured today);
  - storage-key, fragment and title changes;
  - canvas/svg region digests.

  The run key lives in memory only, and a leak regression proves no values are persisted.
- **After** the equivalence check below, remove fixture- and benchmark-specific selectors from the DOM extractor (audit §2.9) in a separate, measured commit. Where a selector was compensating for a missing generic mechanism, record the gap rather than restoring the selector.
- Introduce the append-only evidence log. Graph A becomes a projection.
- **Exit:**
  - full suite passing;
  - before selector removal: fixture runs produce equivalent Graph A (same transitions and replays on deterministic fixtures);
  - after selector removal: changes reported per fixture;
  - one Crawl Maze regression run within ±2 markers;
  - the purity check passes.
- **Risk:** decomposition changes timing-sensitive behavior. Mitigation: deterministic fixtures with exact artifact comparison; the decomposition lands in small commits.

### Phase 3: Online ACG + planner in shadow mode (≤ 10 min live; depends on Phases 1b and 2)

- Maintain the ACG online. Generate questions and compute the planner's choice at each step, but let the legacy frontier act.
- Log the planner's would-be choice, its predicted value and the realized outcome of the legacy action.
- **Exit:**
  - planner overhead < 5% of wall time;
  - predicted `P(new capability)` calibration reported (reliability diagram);
  - question counts bounded by template/capability, not by instance.
- **Why:** calibration and cost are measured before the planner can waste any browser budget.

### Phase 4: Planner drives (≤ 20 min live, development fixtures + whiteboard)

1. L2 selector + L1 designer, with restoration over reproduced edges and direct-URL teleports; interleaved verification. The replay phase and its reserve are removed. Request-structure keys and failure reasons carry over into `reproduce` experiments. Until Phase 5, dependency questions use only the availability-contrast channel, and write-capable verification stays blocked (L0/L1/L2 rules).
2. Then the L3 allocator and saturation stopping.
- **Arms:** frozen frontier, ACG + frontier, ACG + BFS, ACG + planner; ablations of `Unlock`, teleports, `sample_instance` cap and `split_test`.
- **Exit:**
  - higher capability-discovery AUC than ACG + frontier on most development fixtures;
  - no M4/M9 regression;
  - whiteboard reports capabilities with statuses.
- **Risk:** the value function underperforms simple BFS on small fixtures. Then the class floors and BFS fallback stay, and the claim is restricted to larger apps after validation.

### Phase 5: Adapters and isolation (≤ 15 min live; depends on Phase 4's `verify_effect` / `test_dependency` questions)

- Define the `EnvironmentAdapter` protocol.
- Port the existing whiteboard runner (`experiments/run_stateful_whiteboard.py`) and the stateful lab into adapters.
- Implement L3 restore for SQLite (file copy) and Postgres (`CREATE DATABASE … TEMPLATE …`), plus the independent start-state fingerprint and evaluator-side effect digests.
- Enable `verify_effect` and `test_dependency` for write-capable capabilities only under L3+ with a verified start state. The existing L0/L1 guards (`f6744ba`) remain the default everywhere else.
- **Exit:**
  - create/update capabilities `VERIFIED` on the stateful lab and whiteboard;
  - zero unexpected writes by effect digest;
  - false-verified rate ≤ 5%;
  - no write experiment executed without attestation (asserted in tests).
- **Risk:** snapshot incompleteness (files, caches). Mitigation: the drift probe; L4 required for ComfyUI-like stacks.

### Phase 6: Affordance providers and interaction executors (≤ 15 min live)

- Promote the React props probe to an affordance provider (handler names → affordances with `framework` provenance, still observational). It must pass the framework-provider admissibility rule ([GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md) §1.2) on two React applications.
- Add a drag/gesture executor:
  - pointer sequences on canvas elements, bounded and recorded as gestures;
  - risk-gated like other actions;
  - effect evidence from DOM, ComponentState and network.
- Language-independent danger signals (dialogs, ARIA, icon semantics) plus locale lexicon assets in adapters.
- **Exit:**
  - whiteboard drawing and a new development canvas/node-editor fixture produce gesture signatures: unidentified operations unless a grounding rule fires. ComfyUI is held-out and is first run in Phase 7;
  - no new destructive executions.

### Phase 7: Validation and held-out evaluation (≤ 60 min + ≤ 60 min live, preregistered)

- Freeze constants and commit the preregistration.
- Run the validation set (held-out shop, Crawlground, SiyuCMS), then the held-out set (PrestaShop, ComfyUI, two independently chosen apps) with aggregate-only reporting.
- **Exit:** a cross-environment scorecard with the distributions, failures included, against the baselines.

### Phase 8: Deprecation

- Remove ablation-only flags (§5).
- Move the legacy explorer to an archived tag once two milestones have passed without needing it as a baseline.
- Keep the Graph A export for downstream consumers.

## 5. Deprecation schedule

| Item | Phase removed | Replacement |
|---|---|---|
| `policy` values `exact`, `grouped`, `breadth`, `multidimensional`, `hierarchical` | 4 (kept in `legacy/`) | Planner; `coverage` kept frozen as the baseline arm |
| `selective_model`, `model_all`, `model_form_assistance`, `providers.py` in the engine | 2 | None in the engine; any model-based hypothesis source must be an optional offline component with explicit approval |
| `AreaTourPlanner` | 4 | L3 allocator over functional areas |
| `replay_policy` (`shallow`, `diverse`, `structure`), `replay_reserve_fraction` | 4 | Interleaved `reproduce`/`verify_effect` questions; structure keys reused |
| `LOW_VALUE_REPORT`, `.control-area`, `[id^="toggle-"]`, view-count selectors | 2 (the frozen baseline copy in `legacy/` keeps them) | Generic mechanisms or recorded gaps |
| Resource-spider tuning flags (`resource_frontier_policy`, `budget_allocation_strategy`, `passive_document_max_depth`, `budget_aware_deepening`, `html_extraction`, `response_body_reader`, …) | 8 | Fixed defaults; passive inventory with its own small budget |
| `Feature`, `FunctionalWorkflow` as computed concepts | 2 (projection only) | Capability, Binding, witnessing transitions |
| 122 run metrics | 8 | Capability scorecard + safety gates + a small set of engine health metrics |

Archived experiment directories and reports are kept unchanged. Old results stay reproducible from the `agent1-baseline-frontier` tag.

## 6. Risks to the migration as a whole

| Risk | Signal | Response |
|---|---|---|
| The ACG adds complexity without capability gains | Phase 1 shows no better identity, and Phase 4 shows no AUC gain over ACG + frontier | Keep the ACG as a reporting layer and stop before Phase 4; the evidence and identity gains still stand |
| Capability inference is too noisy on real apps | Low precision on SiyuCMS/whiteboard validation | Raise the minimum status for reporting; invest in oracles before the planner |
| Isolation is too costly or unavailable for many targets | Adapters cannot provide L3 | Stateful capabilities stay `BLOCKED` with reasons; the report says so instead of guessing |
| Time pressure pulls the work back to benchmark tuning | Changes justified by Crawl Maze deltas | The §5 rules in the evaluation plan apply; Crawl Maze is a regression check only |
| Refactor breaks the evidence guarantees | Leak / scope / provenance tests fail | Phase gates: the M9 metrics must stay at zero in every phase |

## 7. Validation summary per phase

| Phase | Live browser minutes | Primary evidence of success |
|---|---:|---|
| 0 | 0 | Baseline capability scorecard from archived runs |
| 1 | 0 | Identity accuracy on archived development-set evidence; T1 and T3 pass |
| 1b | 0 | T2a–T2f pass on the offline simulator |
| 2 | ≤ 10 | Equivalent artifacts on fixtures before selector removal; purity check passes; no leaks |
| 3 | ≤ 10 | Planner calibration and overhead in shadow mode |
| 4 | ≤ 20 | Capability-discovery AUC vs frontier and BFS on the same ACG |
| 5 | ≤ 15 | Write capabilities `VERIFIED` with zero unexpected writes |
| 6 | ≤ 15 | Canvas and framework capabilities observed |
| 7 | ≤ 120 (preregistered) | Cross-environment scorecard, held-out included |

Phases 0, 1 and 1b cost no browser time and test the most important claim: that a layered model over the evidence we already have identifies entities and capabilities better than the current hashes. If that claim fails, the plan stops early and cheaply.

## 8. Phase dependencies

```
Phase 0 (ground truth, corpora, evaluator, purity check)
   └─► Phase 1 (offline resolvers; T1, T3) ──► Phase 1b (simulator; T2)
                                    └──────────────┐            │
Phase 2 (decomposition, Selector interface, new evidence kinds) │
   └───────────────────────────────► Phase 3 (shadow planner) ◄─┘
                                        └─► Phase 4 (planner drives; L0–L2 only)
                                               └─► Phase 5 (adapters, L3 snapshots, write verification)
                                                      └─► Phase 6 (providers, gesture executor)
                                                             └─► Phase 7 (validation, held-out) ─► Phase 8
```

Constraints that the dependency order enforces:
- **No live planner run happens before T2 has passed offline.**
- **No write-capable verification happens before Phase 5's attested snapshots.**
- **No held-out environment (PrestaShop, ComfyUI) is touched before Phase 7**, including its archived artifacts.

## 9. Adversarial review record (2026-11-01)

A scoped review of the seven documents before commit. It found these issues and corrected them in the documents. No code was changed.

| Issue | Finding | Correction |
|---|---|---|
| Capability identification | WebSocket, client-only and canvas effects had no evidence representation. Query-dispatched routes (`controller=`, `s=`) collapsed into one operation because query values are dropped | Behavior signature with dispatch tokens, WebSocket message classes, storage/fragment changes and region digests (model §4.2, §5.3); stated limits (model §5.7); test T1 |
| Information-gain planning | The EIG specification depended on an unspecified outcome model and hand-set layer weights. Thompson sampling contradicted the claimed determinism | Observable quantities, categorical and binary-channel uncertainty, closed-form EIG, one-level Unlock, measured cost, risk tiers, all constants listed (planner §5.2); deterministic D-UCB (planner §5.1); shared Selector interface and simulator test T2 (planner §10) |
| Semantic grounding | Examples asserted business verbs (`create`, `share`, `add Node of type T`) and entity names that the engine cannot observe | Three-layer separation, closed rule-based behavioral classes, entity types stored as `E1…`, unidentified operations (model §5.6); M1 split into M1a/M1b (evaluation §3.2); test T3 |
| Contradictions | L0 described as "no write-capable experiments" while the risk table allowed a first observation; L\* called exponential in one document and polynomial in another; the whiteboard example assumed L3, which does not exist yet; ComfyUI was used as a development target in Phases 1 and 6 despite being held-out; Phase 2 required equivalent Graph A while removing selectors that change extraction | Each corrected in place |
| Unsupported claims | Isolation-level costs were stated as facts; the evidence weights were arbitrary | Costs marked as unmeasured estimates; evidence weights replaced by channel-based Bayes updates |
| Missing dependencies | The planner had no offline gate; the Selector interface was not scheduled; Phase 5 depended on Phase 4 implicitly | Phase 1b added; Selector scheduled in Phase 2; dependency graph above |
