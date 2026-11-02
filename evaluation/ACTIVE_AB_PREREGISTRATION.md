# Phase 3 preregistration: active Capability Tours vs the legacy frontier

Frozen before the executor adapter exists. Machine-readable copy and harness: [active_ab.py](active_ab.py).

## Policies (frozen)

**Legacy.** The `f6744ba` frontier as it exists in `agent1/explorer.py` at `a43f69a`, configured per environment below. The only additions are behavior-preserving instrumentation:
- `acg_evidence` capture, shown not to change legacy exploration in Phase 2;
- an action ledger that records the browser-action count and elapsed time when each evidence item is stored.

**Tour.** `tour_v2` in `agent1/planner/tours.py` at `a43f69a`, executed through a thin adapter over the same browser session and safety path. `tour_v2` **failed** its preregistered T2V check V3 (verification waste); it passed V1, V2 and the guard checks ([t2v_tests.json](results/t2v_tests.json)). The tour arm does its own verification and so skips legacy's replay phase; both arms share the same `max_browser_actions`.

## Environments and budgets

Local, authorized, disposable development applications only. No held-out applications.

| Environment | Configuration |
|---|---|
| Stateful CRUD lab (`stateful_lab`) | `multidimensional`, persistent, 100 browser actions, 30 transitions, 35 s, writes allowed (the configuration of `tests/test_state_aware_lab.py`) |
| JavaScript-heavy lab (`js_heavy_lab`) | Its archived p2 baseline configuration in full (140 actions, 30 transitions, 60 s) |
| Replay / dynamic-interaction lab (`replay_lab`) | Its archived structure-replay configuration in full (90 actions, 80 transitions, 90 s, 1,000 HTTP requests, listener observation) |
| Diagnostic, not part of the decision: Phase 2 prerequisite fixture | Phase 2 budgeted fixture configuration (150 actions, 600 HTTP requests) |

Both arms use an identical fresh application state per run (each lab resets on start), the same role, budgets and time limits, and the same evidence capture.

## Trials

- **Count:** 3 paired trials per environment, run interleaved (legacy trial i, then tour trial i).
- **Tour seeds:** 101, 102, 103. The seed changes `tour_v2`'s tie-breaks and its uniform movement between areas.
- **Legacy:** has no seed parameter. Its trials differ only through run timing, including its timestamp-based replay tie-breaking. This is a limitation of the comparison and is reported.

## Metrics (one independent evaluator for both arms)

Ground truth is the frozen annotations in `evaluation/annotations/`. A capability counts as discovered only when an *executed* action supports it: the same `score_capabilities` M1a matching over the ACG built from each run's own evidence. Unexecuted proposals earn nothing.

**Primary.** Capability-discovery AUC versus browser actions: mean M1a recall at every 5 actions up to the budget, using only evidence stored by that action count (from the action ledger).

**Secondary:**
- AUC versus wall time (every 2 s up to the time limit), with browser setup time reported separately;
- final recall and precision;
- reproduced capabilities (navigation alone is never counted as verified);
- distinct record instances, and false record merges (`score_identity`);
- false capability merges;
- restoration share (browser actions not spent executing a recorded transition or replay);
- prerequisite chains completed (diagnostic fixture, counted at the server);
- runtime;
- safety (below).

## Safety gates (measured at the server and in evidence)

- Destructive-endpoint hits: ground-truth capabilities with `effect_risk: destructive`.
- Repeated hits on server-write endpoints (writes re-executed).
- Out-of-scope requests (HTTP router blocks and redirect scope violations).
- Unsupported functional claims: VERIFIED without a paired-search or cross-view replay.

## Decision rule

| Outcome | Condition |
|---|---|
| **Replace** (success) | Mean AUC(tour) > mean AUC(legacy) in ≥ 2 of 3 environments and not lower by > 0.02 in the third; **and** tour destructive hits and unsupported claims = 0, every safety measure ≤ legacy; **and** tour false capability merges and false record merges ≤ legacy (summed over trials) |
| **Experimental** (keep both policies) | Safety holds and the tour arm wins ≥ 1 environment, but success fails |
| **Redesign** | The tour arm loses all 3 environments, or any tour safety violation |

With 3 trials per environment no significance test is claimed; differences are reported per trial.

## Stop conditions

- A tour-arm destructive-endpoint hit, or an unsupported functional claim, stops that environment's tour trials.
- The cumulative live evaluation time is capped at 25 minutes. Executor tests and the WebSocket track count toward it.
- No A/B runs unless the deterministic executor tests pass.

## Not allowed during evaluation

Tuning either policy, changing the evaluator, or rerunning a trial for a better result. A crashed trial is reported as such.
