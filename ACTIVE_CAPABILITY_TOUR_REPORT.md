# Active Capability Tours vs the legacy frontier (Phase 3)

Branch `agent1-browser-mapper-20261028`. The A/B was preregistered in `be32ccd` before the executor adapter existed ([evaluation/ACTIVE_AB_PREREGISTRATION.md](evaluation/ACTIVE_AB_PREREGISTRATION.md)).
- **Targets:** authorized local development applications only; no held-out applications, no paid calls.
- **Live time:** 9.3 minutes for the preregistered A/B and about 16 minutes in total, under the 25-minute cap.
- **Scheduler status:** `tour_v2` entered this comparison having **failed** its offline T2V check V3.

## 1. Outcome

**The tour scheduler lost to the legacy frontier in all three environments. The preregistered verdict is "redesign", and the legacy frontier stays the production policy.**

Safety held in every tour run:
- 0 destructive-endpoint hits;
- 0 repeated writes;
- 0 out-of-scope requests;
- 0 unsupported functional claims;
- no false capability or record merges.

| Environment (3 paired trials) | Legacy AUC (actions) | Tour AUC | Difference per trial | Legacy / tour AUC (wall time) | Final recall legacy / tour |
|---|---|---|---|---|---|
| Stateful CRUD lab | 0.821 | 0.562 | −0.257, −0.264, −0.257 | 0.849 / 0.571 | 6/7 / 4/7 |
| JavaScript-heavy lab | 0.799 | 0.737 | −0.082, −0.072, −0.031 | 0.755 / 0.678 | 12/14 / 11–12 of 14 |
| Replay / dynamic lab | 0.696 | 0.362 | −0.333 in each trial | 0.890 / 0.565 | 24/25 / 16/25 |

Decision rule: wins 0 of 3, big losses 3, safety OK, merges OK → **redesign** ([active_ab.json](evaluation/results/active_ab.json)).

The diagnosis (§4) points to the **executor–scheduler integration**, not the tour policy:
- three feedback defects in how executed outcomes reach the scheduler;
- unreliable restoration, because the scheduler's navigation knowledge is rebuilt from legacy workflow paths rather than from its own executed steps.

Fixing the defects in an exploratory, non-preregistered rerun closes the stateful gap entirely and most of the replay gap, but makes the JavaScript-heavy lab worse. That isolates restoration reliability as the remaining blocker.

## 2. What was built

**Thin executor adapter** ([agent1/live/executor.py](agent1/live/executor.py)). It runs `tour_v2` plans through the legacy browser session:

| Step kind | Executed by | Notes |
|---|---|---|
| Experiment click | Legacy `_attempt_frontier` from the live state | Control resolution, known-write suppression, form filling, scope checks, transition recording |
| Restoration click and verification replay | Legacy `_restore` | Refuses return paths through observed writes; not counted as a transition, as in legacy |
| Direct URL | A new in-scope `BrowserSession.goto` | Same readiness and evidence handling as the start navigation |
| History back | `go_back` | — |
| Fresh context | `reset_context` plus a start navigation | — |

Before each click the adapter checks:
- the control resolves in the current observation (structure plus pseudonymized target);
- the disabled-control evidence;
- the evidence-only risk gate;
- for the experiment, the intended record identity.

**Refused, never approximated:** snapshot restores, other roles and paired-search input variants. Verification replays count as independent only after a fresh context.

**Opt-in configuration:** `exploration_policy="tours"`, `tour_seed` and `action_ledger`, an instrumentation-only record of the browser-action count and time at which each evidence item was stored. All are absent from the stored configuration when off.

**Deterministic executor tests** ([tests/test_tour_executor.py](tests/test_tour_executor.py), real Chromium, server logs checked) all pass:

| Case | Verified behavior |
|---|---|
| Replaced handler | The new handler's request is attributed after the swap (`mode=a`, then `mode=b`) |
| Dynamically created control | Resolved live after creation; `control_not_found` (0 actions) after a reload |
| Multi-step session workflow | Accept → Continue → Review → Finish; 1 completed chain at the server |
| Disabled control that becomes enabled | Refused while disabled (0 actions, no request); executed once enabled |
| Session reset destroying a prerequisite | After a fresh context, Finish is disabled and refused; no finish request |
| Two records, one template; restoration to the wrong record | `record_identity_mismatch` before any click; only the intended record's endpoint is hit |
| Form intercepted by JavaScript and sent as POST | Executed once; the repeat is refused by the legacy write guard (1 POST total) |
| Unsafe control | `control_unsafe`; no request to the destructive endpoint |
| Unsupported operations | Snapshot, other role and input variants refused with 0 actions |
| Legacy-arm instrumentation | Legacy exploration and writes identical with and without evidence capture and the action ledger |

## 3. Results in detail

**Mean recall versus browser actions** (from the action ledger; every 15 actions):

| Actions | 15 | 30 | 45 | 60 | 75 | 90 | budget |
|---|---|---|---|---|---|---|---|
| Stateful, legacy | 0.71 | 0.86 | 0.86 | 0.86 | 0.86 | 0.86 | 0.86 (100) |
| Stateful, tour | 0.57 | 0.57 | 0.57 | 0.57 | 0.57 | 0.57 | 0.57 |
| JS-heavy, legacy | 0.64 | 0.86 | 0.86 | 0.86 | 0.86 | 0.86 | 0.86 (140) |
| JS-heavy, tour | 0.50 | 0.64 | 0.81 | 0.81 | 0.81 | 0.81 | 0.81 |
| Replay, legacy | 0.24 | 0.52 | 0.80 | 0.96 | 0.96 | 0.96 | 0.96 (90) |
| Replay, tour | 0.16 | 0.28 | 0.28 | 0.36 | 0.52 | 0.64 | 0.64 |

**Secondary measures** (trial means unless stated):

| | Stateful legacy / tour | JS-heavy legacy / tour | Replay legacy / tour |
|---|---|---|---|
| Browser actions used | 45 / 7–10 | 62 / 45–55 | 89 / 90 |
| Transitions (discovery actions) | 30 / 4 | 30 / 17–20 | 34 / 21 |
| Reproduced capabilities | 0 / 0 | 9 / 2–3 | 13–14 / 9 |
| Restoration share of actions | 0.27 / 0.43–0.60 | 0.35 / 0.49–0.65 | 0.44 / 0.67 |
| Precision | 1.00 / 1.00 | 0.75 / 0.61–0.69 | 0.80 / 0.76 |
| Record instances (true observed) | 4 (4) / 4 (1) | — | 7 (7) / 3 (7) |
| False capability / record merges | 0 / 0 | 0 / 0 | 0 / 0 |
| Setup / exploration seconds | 0.3 / 7 vs 0.3 / 1.5 | 1.3 / 39 vs 1.3–1.7 / 28–34 | 0.45 / 24 vs 0.47 / 24 |

**Safety.**
- Destructive hits, unsupported claims and out-of-scope requests: 0 in both arms.
- Repeated write-endpoint hits: legacy 3 per stateful run (its `GET /counter` mutation is re-fetched across views); tour 0.

**Prerequisite fixture** (diagnostic, not part of the decision):
- legacy completed the chain in 3 of 3 trials (server count 1 each);
- the tour arm in 0 of 3: its tours averaged 1.26 decisions, and 80 of 120 decisions were repeated role entry-point probes (§4).

**Overhead.**
- Tour decisions: about 1 ms each.
- ACG updates: about 7 ms each.
- Computation is not a cause of the losses: wall-time AUC differences follow the action-based ones.

**Action traces** (first trial):
- **Stateful.** Legacy: `Counter, GET mutation, All records, Submit, … Create record, New record, … Alpha, Beta` (30 transitions). Tour: `Alpha, All records, Counter, Submit`, then 42 consecutive proposals of the same link, refused each time by legacy's write guard.
- **Replay.** Legacy reached Twins, Save first/second item, Claim voucher and Cart, which the tour arm never reached. The tour arm spent 59 of 88 actions on 21 reproduction plans, each starting a fresh context.

## 4. Why the tours lost (from the traces)

| Cause | Evidence | Where |
|---|---|---|
| **Unsafe or blocked workflow, not fed back** | 42 of 48 decisions re-proposed one link. Legacy's state-aware guard classifies it as a known state-changing GET and suppresses it; the scheduler's method-based gate does not know. The refusal never became a blocked reason, so the run hit the zero-action stop after 7–10 of 100 actions | Stateful lab (whole loss) |
| **Verification accounting not fed back** | The active runner never added verification actions to the scheduler's verification share, so every tour boundary looked under-verified: 18 boundary verifications and 59 of 88 actions on reproductions | Replay lab (most of the loss) |
| **Role identity mismatch** | The evidence role is `anonymous+sid` (session cookie names appended); the scheduler's declared role is `anonymous`. The role "entry point" never closed (80 of 120 decisions) | Prerequisite fixture |
| **Unreliable restoration (missing evidence about how pages were reached)** | 5–11 failed restorations per trial (`control_not_found`) and restoration shares of 0.49–0.67. The scheduler's trails are rebuilt from legacy workflow paths, which do not reproduce JavaScript-driven states | JS-heavy and replay labs |
| Wrong question selection, incorrect ACG grouping, computational cost | No evidence. Questions were grounded; 0 false merges; about 8 ms per decision in total | — |

**Exploratory post-hoc diagnostics** (not preregistered; they do not change the verdict). Three fixes, none touching scheduler constants:
- executor refusals become blocked questions;
- roles are compared by session context;
- the active runner counts verification actions.

The simulator never populates these paths, and 40 rechecked offline decision logs are unchanged. One tour trial (seed 101):

| | Preregistered tour mean | + refusal and role fixes | + verification accounting | Legacy mean |
|---|---|---|---|---|
| Stateful AUC | 0.562 | **0.829** | 0.829 | 0.821 |
| Replay AUC | 0.362 | 0.362 | **0.653** (recall 0.92) | 0.696 (recall 0.96) |
| JS-heavy AUC | 0.737 | 0.717 | **0.490** (26 failed restorations, 89% restoration) | 0.799 |

So the stateful loss is explained by the refusal-feedback defect, and most of the replay loss by the verification-accounting defect. In the JS-heavy lab, correct accounting makes the scheduler move between pages more, and nearly every move then fails to restore: **restoration reliability is the remaining architectural blocker.** These single exploratory trials support the diagnosis; they are not evidence that a corrected scheduler beats legacy.

## 5. WebSocket compatibility (separate track)

- **Mechanism.** Under the HTTP budget router, documents are delivered with `route.fulfill`. Chromium then applies its local-network-access check to the page's WebSocket and blocks every connection to `127.0.0.1` with `ERR_BLOCKED_BY_LOCAL_NETWORK_ACCESS_CHECKS`. HTTP subresources are unaffected because they are also fulfilled through the router.
- **Correction.** With the separate opt-in `websocket_local_access` (which requires evidence capture), the context grants the `local-network-access` permission to the configured origins only. Out-of-scope sockets are still refused through `route_web_socket` (unconnected, which avoids the `route.close()` deadlock), and HTTP scope and budgets are unchanged. A global Chromium feature flag also works but was not used because it is broader.
- **Tests.** A deterministic test under the router shows in-scope frames sent and received, at least one out-of-scope socket refused, and 0 scope violations.
- **Scope of the change.** The grant is behavior-changing for applications with local WebSockets: with it on, the fixture's live feed works and legacy explores differently, which the Phase 2 shadow-equivalence test caught. It is therefore its own opt-in, off by default and separate from evidence capture, which stays behavior-preserving. The preregistered A/B ran before the correction existed. The exploratory reruns had it on, but the three labs have no WebSockets.

## 6. Decision

1. **Preregistered verdict: redesign.** The tour scheduler does not replace the legacy frontier. Legacy stays the production policy.
2. **Keep the tour policy and adapter experimental.** The redesign the evidence points to is the **executor–scheduler integration**, not the tour policy:
   - The scheduler should learn navigation from its **own executed steps** (`Knowledge.ingest` of real plans and results), not from a reconstruction of legacy workflow paths.
   - It should treat a failed restoration as evidence about that state's reachability.
   - It needs a one-to-one feedback channel for every executor outcome: refusals, verification cost, and role identity.
   - Any change must be preregistered against these same environments, with fresh trials.
3. **Where each policy did better in this evidence:**
   - **Legacy:** JavaScript-driven state restoration (its persistent local bursts never leave the context) and deep linear workflows (it completed the fixture chain in 3 of 3 trials).
   - **Tour arm:** made 0 repeated writes where legacy made 3 per stateful run, and with feedback fixed it matched legacy on the CRUD lab using fewer than half the actions (17–19 vs 45).
4. **Limitations:**
   - 3 trials per environment; legacy has no seed (its trials varied only in timing) and tour trials varied only slightly by seed.
   - The three development labs were used during earlier development.
   - Prerequisite chains were measured only on the diagnostic fixture.

## 7. Reproduce

```
.venv/bin/python -m pytest tests/test_tour_executor.py tests/test_live_shadow.py
.venv/bin/python -m evaluation.active_ab                 # preregistered A/B (~9 min live)
.venv/bin/python experiments/run_active_posthoc.py       # exploratory diagnostic (+ env names for the second pass)
```
