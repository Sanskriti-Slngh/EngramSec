# Agent 1 perception ablation: preregistration

Status: **frozen before any diagnostic or scored trial.** Contract tests ran before this was committed; no ablation trial had run. Diagnostic trials (one per arm and environment) may only reveal instrumentation defects. Any change they force is committed as a labelled amendment before the scored trials. Changes after the first scored trial are reported as deviations.

## 1. Question

The comprehensive evaluation (`4450b91`) attributed 16 of 21 technical misses on the annotated development labs to observation (9) or extraction (7). The question is whether the readiness and listener mechanisms already built into Agent 1 recover that functionality under a general-purpose configuration, or whether the limitation lies deeper than perception.

## 2. Frozen agent and arms

- **Agent:** `agent1/` at `a9802e3`, tree `320a1f8`, unchanged. The harness refuses to run otherwise.
- **Common configuration:** the comprehensive evaluation's primary configuration (`FROZEN` + `INSTRUMENTATION` in [evaluation/comprehensive_config.py](evaluation/comprehensive_config.py)):
  - policy, mode and safety: legacy `coverage` policy, fresh mode, state-aware, `allow_post_forms=False`, shallow replay, 30% replay reserve, `settle_ms=350`, `interaction_profile=basic`;
  - budgets: 180 s, 500 actions, 100 transitions;
  - no origin aliases, anonymous, no model calls;
  - `acg_evidence` and `action_ledger` on.
- **Production defaults:** not modified. The arms are passed as per-run overrides ([evaluation/perception_ablation.py](evaluation/perception_ablation.py), `ARMS`).

| Arm | Overrides | Everything else |
|---|---|---|
| A | none: production defaults, identical to the comprehensive primary track | — |
| B | `robust_readiness=True` | identical to A |
| C | `runtime_listener_observation="revisit"` | identical to A |
| D | both | identical to A |

A contract test asserts that each arm differs from A only in these fields, and that all arms have equal budgets, policy, mode, POST setting, interaction profile, settle and readiness timeout.

## 3. Phase 1 audit (from code and existing tests; no runs)

**Readiness (`robust_readiness`).** `_wait_for_readiness` in `agent1/explorer.py` polls a page script every 100 ms, bounded at 2.5 s.
- A page counts as initializing while the document is loading, any element is `aria-busy`, or every control is disabled.
- After that it requires 3 identical samples of the actionable-control fingerprint and a minimum wait: 300 ms with visible main controls; 1.6 s on script pages without main controls.
- A late-inserted control changes the fingerprint and resets the stability window.
- It runs after start navigation, direct navigation, history steps and every action. When on, it *replaces* the fixed 350 ms settle.
- **Can observe:** controls enabled or inserted while the page is busy or stabilizing, within 2.5 s (js_heavy_lab: enabled at 650 ms, inserted at 800 ms).
- **Cannot observe:** anything later than 2.5 s; controls that appear only after interaction; non-semantic elements, which readiness does not extract.
- **Cost:** 0.3–2.5 s per observation, instead of a fixed 0.35 s.

**Listener observation (`runtime_listener_observation`, `agent1/listeners.py`).** One Chrome DevTools listener enumeration per observation over the whole document, including same-process frames and open shadow roots. At most 300 nodes are described per observation; enumeration is skipped above 20,000 DOM elements.
- **Becomes a candidate:** an element with a *direct* click-family listener (click, mouse/pointer down/up; double-click and context menu are dropped under the basic interaction profile). Capped at 2 per handler location and 12 per observation.
- **Never a candidate:** listeners on document, window, html, body, main or a container holding other controls (counted as delegation hosts); elements in closed shadow roots; frames that cannot be observed.
- **`revisit`:** a handler change on the same element within one document lifetime yields a `behavior_revision`. That gives the control a new identity, so it is explored again.
- **Can observe:** listener `<div>`s at load or created by an action; replaced handlers; listeners in open shadow roots and same-process frames.
- **Cannot observe:** delegated handlers, so transfer_library F9's row family is expected *not* to be recovered; closed shadow roots; listeners added after the observation.
- **Cost:** DevTools calls and milliseconds are recorded per observation.

**Safety and scope for dynamically discovered controls.**
- Listener candidates become ordinary controls. They pass the same dangerous-label filter (contract-tested), the action budget and the frontier.
- Three static checks cannot apply because the target is unknown before the click: the cross-origin target check, the password/file-input check and the POST-form gate. The same is true of script-driven snapshot buttons.
- Scope is enforced at request level instead: enabling listener observation installs the HTTP scope router, and an action that leaves the origin raises.

**Defects and non-equivalences found (no agent code changed):**
1. **Router confound.** Arms C and D install the HTTP scope router, so every in-browser request is served through `route.fetch`, and out-of-scope sub-requests are aborted. Arms A and B have no router: out-of-scope sub-requests are not blocked, and only off-origin navigation is caught. C and D therefore differ from A and B in request delivery and scope strictness as well as in listener discovery. This is declared, not removed (removing it would require changing the agent).
2. **Observability gap.** The router's block counter is not exposed when there is no HTTP budget. The harness therefore measures scope symmetrically from the agent's own network records: out-of-scope requests recorded and completed.
3. **Readiness replaces settle.** B and D do not apply the fixed 350 ms settle. That is inherent to the mechanism and part of what B tests.

## 4. Environments, state and order

| Env | Reference | Notes |
|---|---|---|
| stateful_lab | annotation (7) | restoration-limited in the comprehensive evaluation; perception predicted not to help |
| js_heavy_lab | annotation (14) | **ceiling under fixed constraints: 9/14 = 0.643** (alias_area and alias_data refused by scope with no aliases; enter_member_mode, member_preferences and load_preferences behind a POST form) |
| replay_lab | annotation (25) | **ceiling 24/25 = 0.96** (wipe_records would be refused by the dangerous-label filter even if extracted) |
| transfer_library | author evaluator | F4–F8 listener-based (F4 a handler revision); F9 delegated, predicted not recovered |
| Crawlground | testbed server markers (59) | Docker container, reset checks as in the comprehensive evaluation |

- **Initial state:** in-process fixtures start in a fresh process with fixture state created from code. Crawlground starts as a fresh container from the official image, with the same reset-integrity checks as the comprehensive evaluation.
- **Order:** one environment at a time. Within each trial index the four arms run in a rotating order: trial 0 runs A B C D, trial 1 B C D A, trial 2 C D A B.
- **Runtime** is measured independently by the driver with both a monotonic and a wall clock. A difference above 5 s flags the trial as host-sleep-affected. The host is kept awake with `caffeinate` on AC power.

## 5. Phases

1. **Contract tests** ([tests/test_perception_ablation.py](tests/test_perception_ablation.py)): arm isolation, equal budgets, order rotation, development-only environments, metric extraction on synthetic artifacts, dangerous-label filtering of listener-derived controls. Passed before this commit.
2. **Diagnostic:** 1 trial per arm per environment (20 runs), stored separately (`phase diagnostic`). Used only to detect instrumentation defects: a missing field, a crash, or a config not applied as intended (checked against `applied_config` in each trial). Not used to choose settings, and not reported as results except to describe any defect found.
3. **Scored:** 3 trials per arm per environment (60 runs). Every trial is preserved, including failures and zero results; no mapping trial is rerun.

## 6. Measures (per trial; medians, min, max over 3)

**References**
- Annotation-based recall and precision, false positives, matched set.
- Transfer: documents, static resources, functions executed and replay-validated.
- Crawlground markers, overall and by category.

**Capabilities and evidence**
- Capabilities, reproduced, verified, unidentified.
- Capabilities by the provenance of their bound affordances: listener-only, mixed, snapshot.

**Perception**
- Controls observed by provenance (snapshot vs listener-derived); listener candidates and their skip reasons.
- Listener controls executed vs advertised-but-never-executed: the accumulation measure.
- Listener transitions: total, successful, failed, executed with no observable effect.
- Handler-revision transitions.
- Controls that became enabled or visible during readiness waits (first vs last readiness sample).

**Annotated attribution**
- Matched capabilities reached *only* via listener-derived actions.
- Matched capabilities that needed a revision action.

**Cost**
- Browser actions; observations; agent elapsed time; driver wall time.
- Readiness wait and timeouts; listener observer time and DevTools calls.

**Failures**
- Action failures by error class.
- Restoration failures: group mismatch, missing return-path control, unsafe restoration refused.

**Safety and scope**
- State-changing requests; destructive-endpoint hits; dangerous controls skipped.
- Out-of-scope requests recorded and completed; WebSocket refusals; unsupported claims.

## 7. Attribution rules

- **Effects:** B − A (readiness), C − A (listeners), and D against B and C (interaction). Each is computed on matched annotated sets and on the reference counts.
- **Listener credit requires listener evidence.** A capability recovered in C or D counts toward listeners only if it is matched through listener-derived actions or a revision action. A capability that B alone also recovers is credited to readiness. Improvement is never attributed to listener detection when readiness alone explains it.
- **Exploration vs accumulation.** Newly visible functionality counts as *explored* only when executed. Listener controls advertised but never executed are reported as accumulated in the frontier.
- **When perception improves but coverage does not,** the execution traces must show where the newly visible control stopped (not selected, failed, restoration, or no capability).

## 8. Decision gates (development-stage only, not generalization evidence)

Perception "recovers the majority of missing annotated functionality" if, in some arm, all of the following hold:
- js_heavy_lab annotation recall ≥ 0.60;
- replay_lab annotation recall ≥ 0.85;
- precision ≥ 0.75 on both;
- no new safety or scope violations relative to A. That means 0 destructive hits, no increase in state-changing requests, and no completed out-of-scope requests beyond A's;
- a cost per correctly matched capability no more than 2× arm A's, in browser actions and in driver wall time, on the annotated labs where both are defined.

The arm that meets the gates at the lowest cost is the recommended configuration. If no arm meets them, the report classifies the residual misses by earliest cause: candidate generation, execution, restoration or capability modeling.

**Predictions** (from the audit, recorded before running):
- B recovers js_heavy_lab's hydration-blocked controls.
- C recovers replay_lab's listener `<div>` capabilities and `check_loans_second`, and transfer_library F4–F8 but not F9.
- Neither changes stateful_lab.

## 9. Integrity

- No change to `agent1/`, the default policy, thresholds or budgets.
- No WebExploitBench run, metadata or trace access. No benchmark-specific fixes. No paid models.
- Negative results are preserved. Three deterministic repeats support no significance claim.
- Results: `evaluation/results/perception_ablation_scored.json`. Raw runs are git-ignored.
