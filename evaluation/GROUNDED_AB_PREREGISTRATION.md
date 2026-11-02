# Preregistration: execution-grounded tours (small real-browser comparison)

Frozen together with the execution-grounded interface and its contract tests (`tests/test_grounded_restoration.py`), before any performance measurement. Harness: [grounded_ab.py](grounded_ab.py). The Phase 3 preregistration and report are unchanged.

## Arms (matched budgets, sessions, safety policy and evaluator)

| Arm | Policy |
|---|---|
| `legacy` | Unchanged frontier (production policy) |
| `tour` (control) | `tour_v2` through the Phase 3 adapter with the post-hoc feedback fixes (`exploration_policy="tours"`) |
| `grounded` (treatment) | The same `tour_v2` scheduler, with knowledge built from the step-execution ledger, verified restoration, a reachability model and complete executor feedback (`exploration_policy="tours_grounded"`) |

The scheduler's selection policy and constants are identical in both tour arms; only the execution model differs.

## Environments

The same environments and configurations as the Phase 3 A/B, each freshly reset per run:
- stateful CRUD lab, JavaScript-heavy lab and replay lab, scored against their ground truth;
- the Phase 2 prerequisite fixture, for chain completion only.

## Trials and seeds

- **Seeds:** 301, 302, 303 (never used before), shared by both tour arms within a pair.
- **Pair 0 is the diagnostic trial.** Pairs 1 and 2 run only if pair 0 shows:
  - no ledger integrity problem;
  - no safety violation;
  - no executed record or session identity error.
- **Live-time cap:** 15 minutes for this comparison. The contract tests and smoke runs used the rest of the 20-minute milestone limit. If the cap is reached, the run stops and the partial result is reported.

## Metrics

Computed by the Phase 3 evaluator for all arms:
- discovery AUC versus browser actions and versus wall time;
- final recall and precision;
- false capability and record merges;
- prerequisite-chain completion, counted at the server;
- safety (destructive hits, repeated write hits, unsupported claims);
- verification actions and wasted attempts.

From each tour arm's decision log, with the same definitions for both tour arms:

| Metric | Definition |
|---|---|
| Restoration attempts | Proposals whose restoration kind is neither `stay` nor `none` |
| Restoration failures | Those aborting with `control_not_found`, `record_identity_mismatch`, `arrived_at_wrong_state*`, `restoration_mismatch*`, `live_state_stale`, `history_unavailable` or `goto_unresolved*` |
| Restoration actions per discovered capability | Browser actions not spent on a recorded transition or replay, divided by final recall, pooled |
| Re-proposals after refusal | Same-condition repeats (grounded, exact) and any-condition repeats (both tour arms) |

The grounded arm detects failures the control cannot see (`arrived_at_wrong_state`, `restoration_mismatch`). Those count *against* it under this definition.

## Success criteria

| Id | Criterion |
|---|---|
| C1 | 0 ledger integrity problems in every grounded run |
| C2 | Grounded: 0 destructive hits, 0 unsupported claims, repeated write hits ≤ control in every environment |
| C3 | Grounded: 0 re-proposals of a refused question under unchanged conditions |
| C4 | Per environment: grounded mean precision ≥ control − 0.02, and false capability and record merges ≤ control |
| C5 | Pooled over the scored environments: restoration failure rate **and** restoration actions per discovered capability each ≥ 25% lower than control |
| C6 | Mean discovery AUC (grounded) > control on the JavaScript-heavy and replay labs |

**Success** = C1–C6 all hold. The legacy frontier remains the production policy regardless; replacing it would require a separate, larger comparison.

## Not allowed

Tuning on evaluation trials, rerunning a trial for a better result, or changing the evaluator after the first run.
