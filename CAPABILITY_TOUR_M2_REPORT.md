# Capability Tour Scheduler (Phase 1b-R): offline results

Branch `agent1-browser-mapper-20261028`. The preregistration was committed before any scheduler code: `adb07f9`. Offline only: no live runs, no production explorer changes, no paid calls, no held-out data. The failed Phase 1b report ([OFFLINE_PLANNER_M1B_REPORT.md](OFFLINE_PLANNER_M1B_REPORT.md)) and its T2 artifacts are unchanged.

## 1. Outcome

**The Capability Tour Scheduler passes all seven preregistered T2R tests on fresh seeds. It fixes both regimes where Phase 1b failed (flat apps and prerequisite chains) and keeps the ACG's instance bounding and higher recall.**

Two qualifications follow from the ablations:
- **Local continuation is where the gain comes from.** Keeping a live context and continuing work in it has a large, consistent effect (50 of 50 seeds).
- **Cost-aware *global* selection does not help.** Choosing where to move uniformly at random scores the same on flat apps and slightly better on mixed apps. The coverage estimate behind global selection is fooled by superficially new pages.

| Test (frozen threshold) | Result | Observed (seeds 1000–1049) |
|---|---|---|
| R1 flat: AUC ≥ 0.95 × BFS | **PASS** | 0.489 vs 0.357 (ratio 1.37). Phase 1b planner: 0.209 |
| R2 prerequisites: ≥ legacy gated recall in ≥ 80% of seeds, each budget | **PASS** | 100% of seeds at 100, 200 and 400 actions. Gated recall 0.73 / 1.00 / 1.00 vs legacy 0.36 / 0.37 / 0.41 |
| R3 repeated instances: ≤ 3 sampled | **PASS** | max 3 in 50/50 seeds (legacy 14.7 mean, BFS 49) |
| R4 mixed: AUC > legacy (sign test p < 0.05); recall ≥ ACG uniform − 0.02 and > legacy | **PASS** | AUC 0.745 vs 0.621 (30 wins, 15 losses, p = 0.018); recall 0.876 vs 0.756 uniform, 0.709 legacy |
| R5 determinism | **PASS** | 50/50 identical decision logs |
| R6 safety: 0 gate refusals; 0 write re-executions below L3 | **PASS** | 0 and 0 over 1,680 tour runs |
| R7 diagnostics D1–D4 | **PASS** | D1 search verified 9/10; D2 snapshot write verified 10/10; D3 drifted snapshot: 0 verified, blocked 10/10; D4 no snapshot: 0 re-executions, blocked 10/10 |
| H_local: full > no local continuation | **supported** | gated recall averaged over budgets 0.909 vs 0.667; 50 wins, 0 losses |
| H_global: full > no global cost-aware selection | **falsified** | flat: identical (50 ties); mixed: −0.013 (15 wins, 14 losses, p = 0.5) |

Full data:
- [evaluation/results/t2r_tests.json](evaluation/results/t2r_tests.json);
- [evaluation/results/t2r_scorecard.json](evaluation/results/t2r_scorecard.json): every scenario, policy, recall curve, action breakdown and scheduler log summary.

## 2. How the scheduler works ([agent1/planner/tours.py](agent1/planner/tours.py))

1. **Same model, same questions.** After every executed plan the ACG is rebuilt from the evidence, and the Phase 1b generators produce the question pool, bounded per template and family. One fix there: a repeated family opens its next member only while each binding so far revealed a distinct capability. This replaces the Good–Turing rule.
2. **Discovery runs as tours.** A tour is a run of discovery experiments in the live browser context. Local candidates are questions answerable without leaving the context (stay, or one step back). They are ranked:
   1. a control seen disabled and then enabled in this context (witnessed prerequisite progress);
   2. a control newly revealed on the live view;
   3. any other local question;

   then by cost, with seeded tie-breaking.
3. **Tours are bounded.** A tour ends after 20 experiments; witnessed chain steps may extend it, and each runs once. It also ends when no local question remains, when verification is due, or when a remote plan is at least 2× better per action. Every start, continuation and end is logged with its reason.
4. **Movement compares whole plans.** Restoration (stay, back, same-context direct URL, fresh-context replay, verified snapshot) is costed in actions before a plan competes. A 6-action return costs 6, not 1.
5. **The live session is protected.** While it holds unexecuted prerequisite progress, plans that would open a fresh context are excluded whenever a same-context plan exists.
6. **Revisits for cross-page prerequisites.** A page with a control seen disabled is revisited in the live context, at most twice per context, after a state change in the same area. The revisit loads pages only and never re-sends a request.
7. **Verification is a separate agenda.** It covers reproduction, paired search, cross-view under a verified snapshot, two-arm dependency tests and equivalence. It runs:
   - when discovery is exhausted;
   - from a reserve of up to 20% at the end of the budget;
   - at a tour boundary when verification is below 10% of actions and the live context holds no prerequisite progress.

   It never exceeds 30% while discovery has work. Each item gets at most 2 attempts, then is recorded as blocked with its evidence.
8. **Writes.** A write is replayed only after a verified L3 snapshot. A failed start-state check disables snapshots for the rest of the run.
9. **Fallback.** A breadth-first mode (legacy-style local burst plus earliest-observed order over the same question pool) is selected only from observable structure:
   - ≥ 15 bindings;
   - ≥ 80% of them each revealing a distinct capability;
   - < 10% of affordances in repeated or instance families;
   - no instance templates, disabled controls or chain events.

   Every mode switch is logged with its evidence.
10. **Nothing from the failed policy.** No EIG, Good–Turing, Unlock or UCB, enforced by a static test. No display text, and no app-specific strings (purity check).

**Chain records.** For each prerequisite event the scheduler records:
- the disabled observation and the enabled observation;
- the state-changing actions between them;
- the candidate dependency claim;
- whether the enabled control was then executed;
- what an independent test would need (a two-arm replay from a fresh context, plus a verified snapshot when a preceding step writes).

A chain record is never promoted to a verified dependency.

## 3. Why it differs from the failed allocator

| | Phase 1b planner | Tour scheduler |
|---|---|---|
| Unit of choice | one question, by EIG/cost inside a UCB-chosen area | a tour in the live context; remote plans compared by whole cost |
| Area switching | almost every decision (UCB rotation, 5% floors) | only when local work runs out, a tour hits its bound, or a remote plan is ≥ 2× better |
| Verification | ≥ 20% floor, interleaved, fresh context each time | separate agenda at boundaries or the end, never while the context holds prerequisite progress |
| Prerequisite chains | lost when a fresh context reset the session | newly enabled controls run first; cross-page revisits |
| Flat-app restoration share | 61% | 26% (BFS 43%) |

## 4. Where the improvements come from

| Source | Evidence |
|---|---|
| **Question structure** (from Phase 1b) | Instance bounding: 3 instances vs legacy 14.7 and BFS 49. Missing identifiers: AUC 0.942 vs legacy 0.647. Already shown by `acg_uniform` (0.700) |
| **Preserving live state** (local continuation) | H_local: gated recall 0.909 vs 0.667, 50/50 seeds. Chains completed at 200 actions: 150/150 vs 100/150 without it (legacy 56/150). Flat AUC 0.489 vs 0.450. Mixed AUC 0.745 vs 0.721 |
| **Separating verification from discovery** | Flat AUC 0.489 vs 0.196 for the same question pool under uniform choice with interleaved verification. Not isolated by its own ablation, so this attribution is inference |
| **Restoration-cost-aware global choice** | No measurable gain (H_global falsified). On duplicate pages it hurts: AUC 0.734 vs 0.905 with uniform global choice |

**Mixed applications** (AUC / recall at 150 actions):

| App kind | BFS | Legacy | ACG uniform | Tour full | No local | No global |
|---|---|---|---|---|---|---|
| All mixed | 0.377 / 0.51 | 0.621 / 0.71 | 0.539 / 0.76 | **0.745 / 0.88** | 0.721 / 0.85 | 0.758 / 0.87 |
| Structured | 0.305 / 0.40 | 0.638 / 0.70 | 0.668 / 0.92 | 0.840 / 0.96 | 0.828 / 0.94 | 0.873 / 0.96 |
| Stateful (CRUD, workflow) | 0.484 / 0.65 | 0.719 / 0.82 | 0.468 / 0.73 | 0.729 / 0.85 | 0.688 / 0.79 | 0.720 / 0.85 |
| Flat | 0.514 / 0.88 | 0.603 / 0.88 | 0.280 / 0.47 | 0.676 / 1.00 | 0.607 / 0.90 | 0.676 / 1.00 |
| Noisy | 0.259 / 0.38 | 0.484 / 0.55 | 0.348 / 0.54 | 0.622 / 0.77 | 0.587 / 0.75 | 0.603 / 0.75 |
| Client-only | 0.500 / 0.50 | 0.500 / 0.50 | 0.483 / 0.50 | 0.500 / 0.50 | 0.500 / 0.50 | 0.500 / 0.50 |

## 5. Regimes in detail

**Flat apps (fixed).**
- AUC 0.489 vs BFS 0.357 and legacy 0.414.
- Restoration 26.0 actions per 100 (BFS 43.0, uniform ACG 60.1).
- Area switches 18.8 per run, costing 22.7 restoration actions (BFS 21.0 / 29.0; uniform ACG 26.4 / 51.4).
- **The fix comes from tours, not from the fallback.** The breadth fallback never triggered in any of 3,970 runs. Its repeated-family measure groups sibling controls by container and tag, so 59% of the flat app's affordances count as repeated (threshold 10%) even though each is a distinct capability; every binding was distinct (unique share 1.0). The criterion is miscalibrated, and the fallback is implemented and logged but **untested in practice**.

**Prerequisite chains (improved).**

| Budget | Chains completed / abandoned (tour) | Legacy | No local continuation |
|---|---|---|---|
| 100 | 105 / 33 | 53 / 17 | 100 / 24 |
| 200 | 150 / 0 | 56 / 14 | 100 / 33 |
| 400 | 150 / 0 | 61 / 14 | 100 / 33 |

- Of 595 chain events at 200 actions, 450 enabled controls were executed in the same context. The rest were controls already bound earlier.
- 59 events were cross-page, each completed through a live-context revisit (59 revisits).
- **No dependency is verified causally.** Two-arm tests need the preceding steps replayed. Where a step writes, they were blocked (290 `write_not_replayable` at 200 actions), as designed.

**Repeated instances (preserved).** 3 sampled instances in every seed; AUC 0.959 vs 0.860 for `acg_uniform`.

**Verification.**

| Per run, mean | Mixed (tour) | Mixed (legacy) | Prerequisites @200 (tour) |
|---|---|---|---|
| Reproduced capabilities | 13.0 | 7.6 | 24.1 |
| Verified capabilities (T2 apps) | 0 | 0 | 0 |
| Discovery / verification / restoration actions | 63.1 / 60.6 / 61.7 | 85.0 / 58.2 / 71.9 | 91.3 / 108.7 / 100.1 |
| Blocked verification items | 2.7 | — | 16.5 |
| Write re-executions without isolation | 0 | — | 0 |

- **VERIFIED.** It stays 0 on the T2 apps: their search filters an already visible list, and their writes have no snapshot. The diagnostics show the machinery works when evidence allows it:
  - D1 search verified in 9/10 seeds;
  - D2 cross-view write verified from a verified snapshot in 10/10;
  - D3 drifted snapshot: blocked with `unverified_start_state`;
  - D4 no snapshot: the write is never replayed and verification is recorded as blocked (`write_not_replayable`).
- **Correctly refused writes** appear as blocked verification items: 290 `write_not_replayable` items on the prerequisite app at 200 actions.
- **Verification waste.** At 400 actions the prerequisite app finishes discovery after about 91 actions. The scheduler then spends 268 actions on verification, much of it reproductions of session-dependent capabilities that cannot succeed independently. Each item is capped at two attempts, so 600 items end `inconclusive`. This costs nothing in discovery but is wasted effort, and it is a real limitation (§7).

## 6. Safety and graph accuracy (Phase 8)

[tests/test_tours.py](tests/test_tours.py), [tests/test_t2r_foundation.py](tests/test_t2r_foundation.py) and the existing T1/T3/T2 tests all pass:
- decision logs are identical under random and Chinese relabeling, and on rerun (13 cases, plus R5 over 50 seeds);
- no label reads, none of the failed machinery, and a clean purity check (static);
- renaming every hidden simulator identifier leaves decisions unchanged;
- every chosen question cites existing evidence; role entry points cite the adapter's role declaration;
- no unsafe or disabled control is ever clicked;
- every reproduction is an independent replay, and VERIFIED requires a paired-search or cross-view replay;
- no write is re-executed below L3;
- chain records are complete, and tours are bounded;
- open question counts do not grow with the number of record instances (200 vs 50).

Graph accuracy is unchanged:
- false merges 0.20 per mixed run, the same for every policy (the client-only storage and region atoms);
- same-role false splits 0.10 (legacy 0.14).

**Performance.**
- Agenda and choice: 1.7–3.7 ms per decision.
- ACG rebuild: 8–21 ms (126 ms on the 200-instance list).
- After the official run, a memoized identifier lookup inside one rebuild roughly halved rebuild time: 22.0 → 10.7 ms per export single-threaded; 32.8 → 13.8 ms per decision under the evaluation's parallel load.
- The change is proven semantics-preserving: all 24 archive and corpus exports are identical, 54 simulated exports are identical, and 160 official T2R runs reproduce bit-identical decisions and metrics.

## 7. Negative results and limitations

- **Cost-aware global selection is unjustified.** Uniform global choice matches or beats it. On 30 duplicate pages the coverage estimate (each unvisited link counted as a likely new template) chases superficially novel pages: AUC 0.734 vs 0.905 uniform. It should be removed or replaced.
- **Still below legacy in some places:**
  - CRUD apps: AUC 0.599 vs 0.651. Global navigation on every template creates per-template binding questions that legacy suppresses as global chrome.
  - Writes without snapshots: 0.618 vs 0.667.
  - Duplicate pages: 0.734 vs 0.777.
- **The fallback never ran.** Its repeated-family measure counts sibling controls of the same tag as repeated (59% on the flat app), so the "few repeated families" condition can never hold on realistic pages. It should measure repeated *outcomes* (bindings that produced an already-known capability), not repeated markup. Whether the fallback helps on a truly structureless app is unknown.
- **Independent verification of session-dependent capabilities** is mostly impossible without snapshots, so late-budget verification is largely wasted.
- **Evidence the simulator cannot provide:**
  - real timing and readiness;
  - controls revealed only by hover or gesture;
  - session expiry;
  - whether the "request effects persist in the context" assumption holds;
  - how often real apps show prerequisites as disabled controls rather than validation errors;
  - real snapshot cost and drift.
- **Same author.** The simulator, scenarios and scheduler were written by one author. The scheduler was built after the T2R freeze and evaluated on fresh seeds, but its design was informed by the Phase 1b failures on these same architectures.

**Development disclosure.**
- Development runs used only the old T2 seeds 0–9 and diagnostic seeds 0–2, never the T2R evaluation seeds.
- Constants were set once and not tuned.
- Changes during development, before the official run:
  - a two-attempt cap per verification item, after an unreproducible item looped;
  - revisits to pages seen disabled in an earlier context, which fixed the cross-page chain;
  - chain logging across contexts;
  - the discovery-first, verification-override restructuring of the choice step.
- After the official run, only the proven-equivalent materializer memoization changed.

## 8. Recommendation

1. **Yes to a browser shadow-mode experiment** for the tour scheduler (migration Phase 3: decisions logged beside the existing frontier, not driving the browser). It is warranted with two changes, preregistered as their own small offline checks first:
   - drop or replace the cost-aware global coverage estimate (H_global);
   - suppress per-template rebinding of global navigation.
2. **Keep the legacy frontier as the production policy** until shadow mode has compared real decisions. The simulator does not establish real-world safety or performance.
3. Before shadow mode needs it, Phase 2 must capture `disabled` and `aria-disabled` state in live evidence (the simulator assumes it).

## 9. Reproduce

```
.venv/bin/python -m evaluation.t2r_eval --all --workers 9   # ~3,970 runs, ~10.5 min on 10 cores
.venv/bin/python -m evaluation.t2r_scorecard
.venv/bin/python -m pytest tests/test_t2r_foundation.py tests/test_tours.py
```

`evaluation/results/t2r_runs.json` (per-run records) is regenerable and ignored by git.
