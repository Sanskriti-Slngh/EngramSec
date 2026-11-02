# T2R preregistration (Phase 1b-R: Capability Tour Scheduler)

Frozen in its own commit, before any tour-scheduler code existed. The original T2 experiment ([T2_PREREGISTRATION.md](T2_PREREGISTRATION.md)) is unchanged: its simulator, scenarios, seeds, thresholds, results and failures. Machine-readable copy: `T2R` in [t2r_eval.py](t2r_eval.py).

## What is reused unchanged

- the simulator [appsim.py](appsim.py);
- the T2 scenario definitions and budgets ([sim_scenarios.py](sim_scenarios.py));
- the run loop, executor, risk gate, ACG materializer and scorer ([sim_eval.py](sim_eval.py)).

`t2r_eval.py` adds three things on top:
- fresh seeds;
- the diagnostic apps;
- a pure observer that counts actions by purpose. A test proves the observer never changes a decision.

## Seeds (never used to develop or evaluate the Phase 1b planner)

- T2 scenarios: 1000–1049.
- Stress diagnostics: 1000–1019.
- D1–D4 diagnostic apps: 2000–2009.

## Policies

| Arm | Policy |
|---|---|
| A | `bfs` |
| B | `legacy_frontier` (frozen `f6744ba` approximation) |
| C | `acg_uniform` (Phase 1b question pool, uniform choice) |
| — | `acg_full` (failed Phase 1b planner, reference only) |
| D | `tour_full` (Capability Tour Scheduler) |
| E | `tour_no_local` (no session-local continuation) |
| F | `tour_no_global` (no cost-aware global selection) |

## Tests and thresholds

| Id | Scenario | Pass rule |
|---|---|---|
| R1 | flat, budget 100 | mean AUC(tour_full) ≥ 0.95 × mean AUC(bfs) |
| R2 | prerequisites, budgets 100/200/400 | tour_full gated recall ≥ legacy in ≥ 80% of seeds, at each budget |
| R3 | instances, budget 150 | ≤ 3 non-split sampled instances in every seed |
| R4 | mixed, budget 150 | mean AUC(tour_full) > mean AUC(legacy) with one-sided sign test p < 0.05; **and** mean recall(tour_full) ≥ mean recall(acg_uniform) − 0.02 and > mean recall(legacy) |
| R5 | mixed | rerunning every seed gives identical decision-log hashes |
| R6 | all scenarios | tour arms: 0 risk-gate refusals, and 0 re-executions of an observed write below L3 |
| R7 | D1–D4 | see below |

**Ablation hypotheses** (reported; not part of success):
- **H_local:** tour_full beats tour_no_local on prerequisite gated recall averaged over 100/200/400 actions.
- **H_global:** tour_full beats tour_no_global on flat AUC and on mixed AUC.

Each test needs mean difference > 0 and a one-sided sign test with p < 0.05.

**Success** = R1–R7 all pass. **If it fails,** retain the policy with the highest mean mixed AUC among those that pass R3 and R6 (ties: higher mixed recall).

## Diagnostics D1–D4

Defined in [sim_diagnostics.py](sim_diagnostics.py): budget 80, 10 seeds each, expected outcomes frozen here. A scripted plan proves each outcome is reachable through the shared adapter, independently of any scheduler (`tests/test_t2r_foundation.py`).

| App | Isolation | Expected for tour_full |
|---|---|---|
| D1 `diag_search`: the search page does not list records, so results add links and the frozen paired-search rule can pass | L2 | VERIFIED `collection_query` in ≥ 9/10 seeds |
| D2 `diag_snapshot`: a record-copy form on the record page; verified snapshots | L3 | VERIFIED `instance_creation` (cross-view) in ≥ 9/10 seeds |
| D3 `diag_snapshot_drift`: snapshot whose start-state check fails | L3 (drift) | 0 VERIFIED writes in every seed; the scheduler records write verification as blocked in every seed |
| D4 `diag_snapshot_absent`: no snapshots | L2 | 0 re-executions of the write in every seed; write verification recorded as blocked in every seed |

## Additional measurements (reported, no threshold)

- Discovery, verification, restoration and area-switching actions.
- Fresh-context or snapshot steps.
- Reproduced and verified capabilities.
- Prerequisite chains completed vs abandoned. A chain is abandoned when a gated step was found but the gated end was not.
- Blocked verification attempts and correctly refused writes.
- ACG materialization and agenda time per decision.
