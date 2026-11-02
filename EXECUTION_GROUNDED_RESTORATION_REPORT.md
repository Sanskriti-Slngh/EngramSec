# Execution-grounded state and restoration

Branch `agent1-browser-mapper-20261028`. The implementation, contract tests and preregistration were frozen in `146928e` before any performance measurement ([evaluation/GROUNDED_AB_PREREGISTRATION.md](evaluation/GROUNDED_AB_PREREGISTRATION.md)).
- **Live browser time:** 15.0 minutes for the preregistered comparison, plus about 5 minutes of contract-test and smoke runs during development.
- **Targets:** development fixtures only; no held-out applications, no paid calls.
- **Scope:** no scheduler policy or constant was changed. Earlier preregistrations and reports are unchanged.

## 1. Outcome

**The planner now learns from what the browser actually did, and restoration became far more reliable:**
- restoration failures 8% vs 55% for the Phase 3 corrected tour;
- 44% fewer restoration actions per discovered capability;
- discovery up on both target environments (JavaScript-heavy 0.735 vs 0.572, replay 0.664 vs 0.653).

**The preregistered comparison still did not succeed.** Criterion C4 (precision) failed on the JavaScript-heavy lab.

**The legacy frontier remains better and stays the production policy.** Discovery AUC:

| Environment | Legacy | Grounded |
|---|---|---|
| Stateful CRUD lab | 0.821 | 0.829 |
| JavaScript-heavy lab | 0.799 | 0.735 |
| Replay lab | 0.696 | 0.664 |

Neither tour arm completed the prerequisite chain; legacy completed it in 3 of 3 trials.

## 2. Audit: the two defects, reproduced first

| Defect | Failing test | Evidence |
|---|---|---|
| **A.** `Knowledge.ingest` pairs observations with plan steps by position. A completed plan with missing intermediate observations credits the final state to the *first* step | `test_ingest_refuses_to_credit_a_final_observation_to_an_earlier_step` | A plan of fresh → click → click with one persisted observation gave that observation an empty trail and a new browser-context epoch |
| **B.** The live runner rebuilt trails from legacy return paths keyed by page *group*, so a record's state was reached through another record's actions | `test_trails_come_from_executed_steps_not_another_records_return_path` | In real Chromium, "Upgrade view" on *Linen apron* had the workflow path `[Copper kettle, Upgrade view]`, and its reconstructed trail began with Copper kettle |

**Fixes:**
- **A.** `ingest` now refuses a completed plan whose observation count differs from its step count. The simulator always records one per step, so offline behavior is unchanged.
- **B.** The legacy reconstruction is no longer used by the grounded arm.

## 3. What was built

**Step-execution ledger** ([agent1/live/ledger.py](agent1/live/ledger.py)). One `StepExecution` per planned step:

| Group | Fields |
|---|---|
| Identity | Plan id, step index, plan kind, purpose (restoration, discovery, verification) |
| Action | Intended action and target; actual resolved control |
| States | Source and result observations; expected and actual route and record (pseudonymized) |
| Session | Browser-context epoch, declared role, account reference, digest of cookie *names* only |
| Lifecycle | Stage (planned → attempted → executed → observed); outcome (succeeded, refused, failed, stale, unsupported, not attempted) with a reason |
| Evidence and cost | Request methods and pseudonymized routes; write or state-change flags; transition or replay id; browser actions, HTTP use and elapsed time; for verification, whether the replay reproduced or mismatched |

- Refused and unsupported steps are recorded with 0 actions.
- Steps after a stop are recorded as `not_attempted`.
- Integrity checks reject: duplicate results, success without an observation, actions charged to a step that never ran, evidence shared between steps, and execution after a stop.

**Reachability model** ([agent1/live/reachability.py](agent1/live/reachability.py)). Edges are (state, action) → state, derived only from executed steps. Each edge records:
- whether it is tied to a record or a session;
- whether it changed state;
- its evidence;
- successes in the same context and in independent replays;
- failures and their reasons.

It is never promoted by a plan. State-changing edges, edges whose latest outcome was a deterministic failure, and session-bound edges never reproduced independently are not reusable. Replaying a saved ledger rebuilds an identical model (checked in every contract test).

**Restoration controller and executor** ([agent1/live/grounded.py](agent1/live/grounded.py)). Steps execute through the same legacy session machinery as Phase 3.
- **Per step:** every step is observed and recorded, and checked against the state it was expected to reach (route, record).
- **Before the experiment,** the whole target state is checked:
  - route;
  - record;
  - role and session context;
  - the required control is present and enabled;
  - controls that depend on a prerequisite are still enabled.
- **Structured failure:** any mismatch is recorded as a restoration failure and stops the plan. There is never a silent fall-back to another record or a weaker check.
- **Learning from failure:** a failed route (`back`, `goto` or `fresh` to that target), or a failed click edge, is excluded from later restoration plans. A state with no executed trail is never offered as a target.
- **Write guard:** legacy's write guard is applied to *every* click, including restoration, and covers observed state-changing GETs.

**Feedback to the scheduler** (scheduler policy unchanged):

| Gap | How it now closes |
|---|---|
| Refusals | Permanent safety refusals (known writes, unsafe controls, unsupported operations) block the question. Other refusals and failed restorations block it under the same conditions (browser-context epoch and page structure) and are retried only when those conditions change |
| Verification accounting | The scheduler's verification share is charged the actual browser actions of verification plans, including their restoration. A completed replay that mismatches is final; a transient failure may retry once |
| Role identity | Entered roles come from the structured session identity, not from a display string with cookie names. Accounts are distinguished by an account reference |

**Knowledge from execution.** Each observation's trail is the steps actually executed to reach it in that browser context. "Back" resolves to the page it returned to only if every step it undid was a read-only page load or in-page step and the arrival verifiably matches.

## 4. Contract tests (real Chromium, server state checked)

[tests/test_grounded_restoration.py](tests/test_grounded_restoration.py) has 15 tests: the 2 audit regressions, the 12 required cases, and 1 post-evaluation fix (§6). All pass, and every test also checks ledger integrity, a unique result per step, no evidence shared between steps, and an identical rebuild from the saved ledger.

| # | Case | Verified |
|---|---|---|
| 1 | Multistep restoration with intermediate observations | 4 steps, 4 distinct observations, record verified; only record 7302's endpoint hit |
| 2 | Failed intermediate step | Failed (control not found, 0 actions), then not attempted; no transition fabricated; the edge is excluded from later plans |
| 3 | Redirect to the wrong state | `arrived_at_wrong_state:route`; the target action never ran |
| 4 | Changed handler | Each request is attributed to its own step (`mode=view`, then `mode=edit`) |
| 5 | Disabled → enabled | Refused while disabled with 0 actions; executed once enabled |
| 6 | Session reset destroys a prerequisite | The stale state is rejected; restoration replays the prerequisite in the new context, then succeeds |
| 7 | Direct URL, right page, wrong record | `arrived_at_wrong_state:record`; neither record's endpoint hit |
| 8 | Repeated refusal of a write | One POST; refused questions never re-proposed over 30 real scheduler decisions |
| 9 | State-changing GET | Executed once, then refused (`known_state_change`); the edge is marked state-changing and not reusable |
| 10 | JavaScript-only state | History back loses the client tab and is detected and recorded; the next plan replays the tab click and succeeds |
| 11 | Deterministic replay mismatch | Recorded as `mismatch` and never retried |
| 12 | Role and session with a cookie | Role `anonymous`; cookie-name digest only; no cookie value persisted; no role entry-point loop |

## 5. Preregistered comparison

Three pairs, seeds 301–303; pair 0 passed the gate. Same environments, budgets and evaluator as Phase 3.

**Discovery AUC** (mean of 3 trials):

| Environment | Legacy | Tour (control) | Grounded |
|---|---|---|---|
| Stateful CRUD | 0.821 | 0.829 | 0.829 |
| JavaScript-heavy | **0.799** | 0.572 | 0.735 |
| Replay | **0.696** | 0.653 | 0.664 |

| | Legacy | Tour (control) | Grounded |
|---|---|---|---|
| Final recall (stateful / JS / replay) | 0.86 / 0.86 / 0.96 | 0.86 / 0.60 / 0.92 | 0.86 / 0.79 / 0.92 |
| Precision (stateful / JS / replay) | 1.00 / 0.75 / 0.80 | 1.00 / 0.87 / 0.82 | 1.00 / 0.64 / 0.82 |
| Restoration failures / attempts (3 scored envs, pooled) | — | 95 / 172 (55%) | **10 / 121 (8%)** |
| Restoration actions per unit of recall (pooled) | — | 54.5 | **30.3** |
| Verified restorations (grounded: replay lab) | — | — | 29 of 29 per trial |
| Wasted verification actions per run (replay) | — | 24–26 | **3** |
| Repeated blocked proposals (same condition / any) | — | — / 0 | 0 / 0 |
| Prerequisite chain completed (fixture) | 3 / 3 | 0 / 3 | 0 / 3 |
| Destructive hits / repeated writes / unsupported claims | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| False capability / record merges | 0 / 0 | 0 / 0 | 0 / 0 |
| Ledger integrity problems | — | — | 0 |

| Criterion | Result |
|---|---|
| C1 ledger integrity | **pass** |
| C2 safety | **pass** |
| C3 no repeated identical blocked proposals | **pass** |
| C4 accuracy | **fail**: JavaScript-heavy precision 0.637 vs control 0.870. In 2 of 3 trials the control collapsed to 8 discovery transitions (89–96% of its actions on restoration), leaving a small map with few unmatched capabilities. When both arms explored comparably (trial 2), precision was identical (0.611) |
| C5 restoration (≥ 25% better) | **pass**: −85% failure rate, −44% actions per unit of recall |
| C6 discovery on JS-heavy and replay | **pass** |
| **Success** | **not met** (C4) |

## 6. Failures found during the comparison

**The prerequisite fixture exposed a remaining defect.** 41 `test_dependency` proposals targeted a page for which no executed trail existed, so the restoration plan was a bare fresh context. That lands on the start page, which verification correctly rejected (`restoration_mismatch:route`) every time.

So the controller never believed a false state, but it repeated the same invalid route. That violates the requirement that failed restorations prevent repeats. It also cost the fixture runs: grounded runs used their full 150 actions, with 42–59 failed restorations each.

**Fixed after the evaluation, not re-measured** (test 13): a failed fresh-context route is remembered per target; a state without an executed trail is never a restoration target; and failed restorations block the question under unchanged conditions. Offline simulator decisions are unchanged (40 rechecked).

## 7. Decision

| Question | Answer |
|---|---|
| Did we eliminate execution-state ambiguity? | **Yes, for the grounded executor.** Every planned step has exactly one typed result with its own observation and evidence, and ledger integrity checks pass in every run. Both demonstrated misassociation paths are closed and covered by tests. Remaining ambiguity: observations recorded by legacy code paths outside the ledger are treated as untraceable, not as reachable |
| Did the scheduler stop repeating refused actions? | **Yes for refusals:** 0 same-condition and 0 any-condition repeats in all runs, and 0 in the 30-decision real-scheduler test. **No for failed restorations** in the comparison (§6); fixed afterwards, not re-measured |
| Can it reconstruct JavaScript-driven states? | **Yes, in the tested case.** A client-only tab state was restored by replaying the tab click, after the history route was detected as losing it. In the JavaScript-heavy lab, restoration failures fell from 21–26 per run to 1–3 |
| Does restoration succeed more reliably? | **Yes:** failures per attempt 8% vs 55%, and 29 of 29 restorations verified per replay-lab trial |
| Does capability discovery improve? | **Against the Phase 3 corrected tour, yes:** JS-heavy +0.163 AUC, replay +0.011. **Against legacy, no:** −0.064 (JS-heavy) and −0.032 (replay), +0.008 on the stateful lab |
| Which failures remain architectural? | See below |

**Remaining architectural limitations:**
1. Prerequisite chains are still not completed by tours. The cross-page revisit logic exists, but tours spend the budget on dependency tests and verification instead. Legacy's persistent local bursts finish the chain.
2. Independent reproduction of session-dependent capabilities needs prerequisites replayed. Without snapshots, writes cannot be replayed, so many verifications stay blocked by design.
3. Observations recorded by legacy machinery outside the ledger have no executed trail. The model treats them as untraceable, which is safe but loses them as restoration targets.
4. With n = 3, the AUC differences are descriptive; there are no significance claims.

**Recommendation.**
- Keep the legacy frontier as production.
- Keep the grounded execution model as the default execution layer for any future tour experiment: it is strictly more trustworthy than the Phase 3 adapter.
- Before another comparison, address prerequisite-chain completion in the tour scheduler; that is a scheduling problem, not an execution one.
- Restoration tests passing does not make the scheduler production-ready.

## 8. Reproduce

```
.venv/bin/python -m pytest tests/test_grounded_restoration.py tests/test_tour_executor.py
.venv/bin/python -m evaluation.grounded_ab     # preregistered comparison (~15 min live)
```

Results: [evaluation/results/grounded_ab.json](evaluation/results/grounded_ab.json).
