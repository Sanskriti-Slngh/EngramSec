# T2 preregistration (Phase 1b)

Frozen in the evaluation-foundation commit, before any planner decision policy existed. The thresholds are the ones in [EXPLORATION_PLANNER_DESIGN.md](../EXPLORATION_PLANNER_DESIGN.md) §10.3. Machine-readable copies are in [sim_scenarios.py](sim_scenarios.py) (`SCENARIOS`, `T2`, `STRESS`). The harness and scoring are in [sim_eval.py](sim_eval.py), and the simulator is in [appsim.py](appsim.py).

## What is held identical across policies

All five policies (BFS, legacy frontier, ACG with uniform question choice, ACG with information gain but no Unlock, full ACG planner) use the same:
- application, seed and starting state;
- budget;
- adapter (executor and action costs);
- risk gate;
- evidence format;
- ACG materializer;
- scorer.

The scorer reads hidden truth through `Oracle` only. A policy's beliefs (EIG, P(NEW), saturation) are never a metric.

## Measurement choices the design left open

| Item | Fixed choice |
|---|---|
| Seeds | 0–49 for every T2 scenario; 0–19 for each stress diagnostic |
| Capability recall | An observable hidden capability counts as found when it is the majority hidden capability of at least one ACG capability. A merged ACG capability counts only for its majority. Unobservable capabilities (no observable effect) are excluded from the denominator and never counted |
| Discovery AUC | Mean recall at every 10 actions up to the budget |
| T2a outcome | `NEW` = the executed `bind_affordance` action belongs to a capability id absent from the ACG before it. A truth-based rate is reported as a diagnostic only |
| T2a bins | Width 0.10 on the predicted P(NEW); a bin is populated at ≥ 30 samples, pooled over the 50 mixed seeds |
| T2b metric | Distinct instances of the 200-instance detail template whose first visit came from a plan that is not a `split_test`. PASS: ≤ 3 in every seed |
| T2b application | One list template with 200 instances; 10 other capabilities (11 observable in total); budget 150 |
| T2c application | 3 chains of 3 prerequisite steps (2 on one page, 1 across pages), 3 distractor areas and a 40-instance collection. Gated capabilities are the observable capabilities whose control is initially disabled (9 per app). Each budget is a separate run |
| T2c pass | At each budget (100, 200, 400): full planner gated recall ≥ legacy frontier gated recall in ≥ 80% of seeds |
| T2d application | 12 pages × 5 distinct controls, with no repeated families or instances (84 capabilities); budget 100 |
| T2d pass | Mean AUC (full) ≥ 0.95 × mean AUC (BFS) |
| T2e | The 50 mixed seeds are rerun; every decision-log hash must be identical |
| T2f | Full vs `acg_uniform`. On the instance scenario the metric is discovery AUC; on the prerequisite scenario it is gated recall averaged over the three budgets. PASS on each scenario iff the mean paired difference is > 0 and a one-sided sign test (ties dropped) gives p < 0.05 |
| Unsafe experiments | Steps refused by the risk gate (attempts), and steps executed in violation of it (0 by construction; checked) |
| Legacy frontier | Offline approximation of `f6744ba`'s `multidimensional` policy in persistent mode with state-aware guards and the fixed 30% replay reserve. Approximations are listed in [agent1/planner/baselines.py](../agent1/planner/baselines.py) |

## Rules

- Stress diagnostics never change a T2 threshold.
- No simulator, scenario, seed or scorer change after the first planner result, except a bug fix that is disclosed with its before and after effect.
