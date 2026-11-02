# Offline planner (Phase 1b): results of the preregistered falsification tests

Branch `agent1-browser-mapper-20261028`. Evaluation foundation committed before any planner policy existed: `006b45d`. No live browser runs, no paid API calls, no held-out application data, no production crawler changes.

## 1. Outcome

**The specified planner does not deserve to replace the existing exploration algorithm.** Two of six preregistered tests pass and four fail.

What survives is the **question structure built on the ACG**. Questions are generated per template and capability hypothesis, never per record instance. On structured applications, this finds far more distinct functionality per action than either baseline, and with uniform random question choice it does just as well.

What does not survive:
- information-gain ranking (no better than uniform choice);
- the Unlock term (never changed a decision);
- the discounted-UCB area allocator (switches areas without counting restoration cost);
- the claim that interleaved verification is free.

| Test | Verdict | Observed | Frozen threshold | Hypothesis |
|---|---|---|---|---|
| T2a calibration | **FAIL** | P(NEW) underpredicted by 0.12–0.20 in 6 of 8 populated bins (pred 0.17 → emp 0.36; pred 0.25 → 0.42; … pred 0.66 → 0.78); within tolerance only for 0.7–0.9 | \|pred − emp\| ≤ 0.10 in every bin with ≥ 30 samples | Smoothed Good–Turing outcome model **falsified** (biased low) |
| T2b instance waste | **PASS** | 3 sampled instances in 50/50 seeds (legacy 14.7 mean, 0/50 within bound; BFS 49) | ≤ 3 + split tests, every seed | Instance-bounded question generation **supported** |
| T2c prerequisites | **FAIL** | full ≥ legacy gated recall in 56% / 56% / 52% of seeds at 100 / 200 / 400 actions (means 0.371 vs 0.353 / 0.353 / 0.380) | ≥ 80% of seeds at each budget | Unlock-driven prerequisite reasoning **falsified** |
| T2d flat app | **FAIL** | AUC 0.209 vs BFS 0.357, ratio 0.585 | ≥ 0.95 × BFS | "The machinery costs nothing when there is nothing to exploit" **falsified** |
| T2e determinism | **PASS** | 50/50 identical decision-log hashes (also after the post-run logging fix) | identical | Reproducibility **supported** |
| T2f value ablation | **FAIL** | instances: full − uniform AUC −0.002 (18 wins, 22 losses, p = 0.79); prerequisites: +0.005 gated recall (18–7, p = 0.02) | full > uniform with sign-test p < 0.05 on **both** scenarios | Gains come from question structure, **not** information gain |

The frozen decision rules therefore apply:
- **T2a failed:** the discovery-probability estimator is not calibrated, and this report does not claim it is.
- **T2c failed:** this report does not claim prerequisite reasoning improves exploration.
- **T2d failed:** restrict the planner to applications with detected structure, or keep a BFS/legacy fallback.
- **T2f failed:** remove information-gain weighting and keep only the question structure.
- **Safety and evidence integrity passed** (§5): nothing here blocks a future live trial on safety grounds. The failures above block deploying this planner as specified.

## 2. What was built

| Layer | File | Notes |
|---|---|---|
| Hidden truth, world, adapter, oracle | [evaluation/appsim.py](evaluation/appsim.py) | 10 architectures: CRUD, large list, multi-step workflow, client-only, duplicate pages, state variants, roles, hidden identifiers, flat, flaky. Agents receive `acg-evidence/1` records only. The adapter exposes `start`, `run`, `isolation`, `costs` and `oracle` (evaluation only) |
| Frozen scenarios, seeds, thresholds | [evaluation/sim_scenarios.py](evaluation/sim_scenarios.py), [evaluation/T2_PREREGISTRATION.md](evaluation/T2_PREREGISTRATION.md) | Committed in `006b45d` before the planner |
| Shared run loop and scoring | [evaluation/sim_eval.py](evaluation/sim_eval.py), [evaluation/sim_scorecard.py](evaluation/sim_scorecard.py) | Same adapter, gate, budget, materializer and scorer for every policy |
| Shared interfaces and risk gate | [agent1/planner/interfaces.py](agent1/planner/interfaces.py), [gate.py](agent1/planner/gate.py) | `Selector` / `Executor` contract; evidence-only gate |
| Baselines | [agent1/planner/baselines.py](agent1/planner/baselines.py) | BFS; legacy frontier approximation (§6) |
| Planner | [constants.py](agent1/planner/constants.py) (table I), [value.py](agent1/planner/value.py), [knowledge.py](agent1/planner/knowledge.py), [questions.py](agent1/planner/questions.py), [designer.py](agent1/planner/designer.py), [allocator.py](agent1/planner/allocator.py), [planner.py](agent1/planner/planner.py) | About 1,100 lines; modes `full`, `no_unlock`, `uniform` share everything else |
| Minimal model extension | [agent1/model/evidence.py](agent1/model/evidence.py), [materialize.py](agent1/model/materialize.py) | `disabled` flag on affordances (None = not captured); enable/disable changes as component-state effects; `observed_disabled` and `establishes`/`invalidates` claims. All 24 archive and corpus exports byte-identical apart from the resolver version |

**Question kinds implemented:**
- `bind_affordance`;
- `sample_instance`;
- `reproduce`;
- `verify_effect` (paired search; cross-view under L3 snapshots);
- `test_dependency` (two-arm, from an observed `establishes` claim);
- `test_equivalence`;
- `split_test`;
- `find_entry_point` (adapter-declared roles).

Every question records:
- its claim and motivating evidence;
- its experiment, including the restoration plan;
- estimated cost, risk tier, outcome classes, and the questions it may unlock.

**Every decision logs, before execution:**
- the live view, chosen area and selection rule;
- open, blocked and unreachable counts, and questions deferred by risk tier;
- the top three questions with EIG, Unlock, cost and value;
- the chosen question's predicted P(NEW) (for binds), risk and restoration plan.

**After execution it adds:** actual actions, abort reason, the outcome, the realized information (Bayesian surprise) and the new evidence ids.

## 3. Cross-scenario scorecard

Means over 50 seeds (T2 scenarios) or 20 seeds (stress diagnostics). AUC = mean capability recall sampled every 10 actions. Full data: [evaluation/results/t2_scorecard.json](evaluation/results/t2_scorecard.json) (includes recall-versus-budget curves, gated recall, splits and overhead per policy).

| Scenario (budget) | BFS | Legacy | ACG uniform | ACG no-Unlock | ACG full |
|---|---|---|---|---|---|
| T2b instances (150): AUC / recall | 0.273 / 0.27 | 0.780 / 0.79 | **0.869 / 1.00** | 0.867 / 1.00 | 0.867 / 1.00 |
| T2c prerequisites (100): AUC / recall | 0.274 / 0.33 | **0.405** / 0.52 | 0.276 / 0.47 | 0.305 / 0.53 | 0.305 / **0.53** |
| T2c prerequisites (200) | 0.324 / 0.53 | 0.470 / 0.53 | 0.450 / 0.75 | **0.512 / 0.85** | **0.512 / 0.85** |
| T2c prerequisites (400) | 0.523 / 0.74 | 0.515 / 0.57 | 0.658 / 0.89 | **0.700 / 0.89** | **0.700 / 0.89** |
| T2d flat (100) | 0.357 / **0.68** | **0.413** / 0.59 | 0.195 / 0.33 | 0.209 / 0.37 | 0.209 / 0.37 |
| Mixed, all 10 architectures (150) | 0.375 / 0.51 | **0.572** / 0.67 | 0.540 / 0.75 | 0.542 / **0.76** | 0.542 / **0.76** |
| — structured (large list, duplicates, variants, roles, hidden ids) | 0.307 / 0.43 | 0.546 / 0.64 | 0.671 / 0.92 | **0.677 / 0.94** | **0.677 / 0.94** |
| — stateful (CRUD, workflow) | 0.484 / 0.66 | **0.737 / 0.83** | 0.470 / 0.72 | 0.479 / 0.71 | 0.479 / 0.71 |
| — flat | 0.514 / 0.88 | **0.615 / 0.90** | 0.267 / 0.45 | 0.299 / 0.55 | 0.299 / 0.55 |
| — noisy (20% flaky actions) | 0.233 / 0.31 | **0.402** / 0.43 | 0.346 / **0.56** | 0.280 / 0.49 | 0.280 / 0.49 |
| — client-only | 0.500 / 0.50 | 0.500 / 0.50 | 0.490 / 0.50 | 0.495 / 0.50 | 0.495 / 0.50 |

| Mixed apps, per run means | BFS | Legacy | ACG full |
|---|---|---|---|
| Reproduced capabilities | 0.3 | 7.5 | 14.2 |
| Verified capabilities | 0 | 0 | 0 |
| False merges / same-role false splits | 0.20 / 0.16 | 0.20 / 0.16 | 0.20 / 0.10 |
| Restoration share of actions | 0.62 | 0.50 | 0.61 |
| Risk-gate refusals (unsafe attempts), total over 50 runs | 61 | 9 | **0** |
| Planner time per decision | <0.1 ms | 0.3 ms | 0.9 ms + 15.7 ms ACG rebuild (up to 175 ms on the 200-instance list) |

**How to read it:**
- **Discovery per action:** the planner finds more behaviorally distinct functionality per action than both baselines where there is repeated structure:
  - large lists (3 instances visited instead of 15–49);
  - duplicate pages (stress AUC 0.797 vs 0.514 legacy);
  - hidden identifiers (0.719 vs 0.516);
  - state variants (recall 0.96 vs 0.94).
- **By the end of the budget:** it also finds more capabilities in mixed apps (recall 0.76 vs 0.67).
- **Early discovery:** it is slower early wherever the legacy frontier's persistent, local exploration suits the app (flat, CRUD, workflow, noisy).
- **Uniform choice:** in every row, uniform question choice is within noise of the full planner. The full planner is ahead on prerequisites, behind on noisy apps.

## 4. Why the four tests failed (mechanisms found in the decision logs)

**T2f and Unlock: the value function is not what helps.**
- Uniform choice inside the same question pool matches full EIG ranking.
- The pool already excludes the waste (per-template generation, family bounding, ≤ 3 instance samples, risk tiers), so ranking within it changes little.
- Unlock was non-zero in 96 of 1,438 decisions on the prerequisite app (and 2 of 977 on mixed apps). It **never** changed which question was chosen: the chosen question already had the highest EIG/cost.
- Unlock fires only on executable controls in the same page region as a disabled control. On the live page these are already the cheapest choice ("stay").
- The `no_unlock` arm is identical to `full` on every aggregate metric.

**T2d: restoration overhead from area switching.**
- The design separates area choice (discounted UCB) from question value. Cost only matters inside the chosen area.
- With γ = 0.9 and c = 1, plus the 5% area floor, the allocator rotates areas almost every decision. On the flat app each page is its own area.
- Each switch costs a context reset plus a click. Restoration was 61% of the planner's actions vs 43% for BFS.
- The 20% verification floor adds about one reproduction per five decisions, each starting from a fresh context.
- Result: AUC ratio 0.585.

**T2c: interleaved verification destroys session-scoped prerequisites.** On seed 0:
- The legacy frontier completed two 3-step chains in one persistent context. Its local burst executes each newly enabled step immediately.
- The planner executed the first steps (Unlock fired), then moved to another area.
- A later independent reproduction opened a fresh context, which reset the session flags.
- At L2 the write-capable chain steps cannot be replayed, so the gated control became unreachable.
- The planner then stops early (it used 301 of 400 actions on average, with no feasible question left). Its gated recall is therefore the same at 100, 200 and 400 actions.
- No policy ever completed the cross-page chain in these seeds. Nothing tells any of them that a page must be revisited after a control may have become enabled elsewhere.
- Overall the planner still found more capabilities at 200 and 400 actions (recall 0.85 / 0.89 vs 0.53 / 0.57). It loses only on the gated ones.

**T2a: Good–Turing pooled per area underestimates novelty.**
- P(NEW) uses the area's singleton count over all binding experiments. The outcome is whether a new capability id appears.
- Distinct families within an area are mostly new, so the pooled estimate is biased low (empirical rate 0.12–0.20 above prediction).
- The truth-based diagnostic rate shows the same bias up to 0.6.
- Calibration is acceptable only above 0.7.

## 5. Planner-level semantic and safety integrity (Phase 6)

All in [tests/test_planner_t3.py](tests/test_planner_t3.py) and [tests/test_appsim.py](tests/test_appsim.py):

| Check | Result |
|---|---|
| 1. Labels replaced with random strings or Chinese ⇒ identical decision-log hash (T3a) | Pass: 12 cases × 2 rewrites, and every T2e seed |
| 2. Planner never reads label fields (T3e, static) | Pass: no `label`, `labels`, `title` or `label_candidates` access in the planner modules. The legacy baseline reads labels, as the legacy code does, and is exempt |
| 3. No hidden truth reaches the planner | Pass: renaming every hidden capability, class and area leaves decisions unchanged. Evidence records contain no hidden ids, the adapter exposes no world state, and the planner package imports nothing from `evaluation` |
| 4. No claim verified or reproduced without an experiment | Pass: every reproduction id is an independent replay; VERIFIED requires a paired-search or cross-view replay (none occurred, §7) |
| 5. Every prerequisite is evidence-backed | Pass: every Unlock names blocked questions on controls observed disabled or refused (401/403); every `test_dependency` comes from an observed `establishes` claim |
| 6. Write-capable actions stay blocked without isolation | Pass: 0 gate refusals for every planner arm in 2,650 runs; no known write re-executed below L3 |
| 7. Similar-template instances not merged | Pass: one identifier value per ACG instance; 0 false merges on instance apps |
| 8. Every discovery cites evidence | Pass: every capability and every chosen question cites existing evidence ids |

The full regression suite and its result are reported in §9.

## 6. Fairness, approximations and what changed after the freeze

**Held identical:** application, seed, starting state, budget, adapter costs, available observations, risk gate, isolation, materializer and scorer.

The ACG is materialized from each policy's own evidence, for scoring as well as for the planner.

**Legacy frontier approximation** (documented in [baselines.py](agent1/planner/baselines.py)).

The legacy baseline is `f6744ba` with `multidimensional` scoring, persistent session, state-aware guards and the fixed 30% replay reserve. Differences from the real code:
- browser actions replace wall time;
- prefix and history-return reuse are omitted;
- restoration replays the saved path from the start URL in the same context;
- replays prefer unseen request structures.

It reads display labels as the original does; the simulator gives list rows distinct labels, as real lists have, so that is not an advantage. BFS is the second, exact baseline.

**Frozen evaluation unchanged.**
- The simulator, scenarios, seeds, thresholds and scorer are byte-identical to `006b45d`; source hashes were recorded before the official run.
- The T2 thresholds were not edited.
- Stress diagnostics did not change anything.

**Planner implementation changes after the first smoke runs and before the official run.** These came from inspecting decision logs, not from tuning a constant; table I is unchanged.
1. Bug: the reproduction verdict compared replay ids with evidence record ids, so every reproduction looked failed.
2. Restoration kept every state-changing click since the context began. Fix: shortened trails (page loads plus the final in-page steps) for controls never observed disabled, with a fallback to the full trail if a shortened replay fails.
3. Within one browser context, steps that sent requests are not replayed during restoration: their effect persists, and the executor still checks the control on arrival. Without this the planner could never return to a page after a write-capable step.
4. Bug: a trail containing a history "back" step was replayed into a different history. Fix: a back step's result takes the trail of the page it returned to.
5. The planner now predicts the shared gate from evidence before proposing a plan. Before this it proposed steps the gate refused.

**After the official run:** one logging fix. `sample_instance` cited an observation id instead of its record id. It changes only the explanation log: 600 rechecked runs show identical metrics, and T2e still passes 50/50.

**Interpretations of the design.** These were fixed before the official run and are stated here because they matter:
- **Restoration edges.** The design allows only REPRODUCED edges. Here an observed-only read-only step may be replayed from a fresh context, where it is itself recorded and checked as a reproduction, or within the same context. Recorded writes replay only after a verified L3 snapshot. Without this relaxation, deep pages are unreachable until every edge on the way has been reproduced.
- **Areas** are the first route segment (the design's "template cluster" fallback). Capability communities are not implemented.
- **Risk tier 1** is unexecuted non-GET forms (the `f6744ba` deferral). Unexecuted buttons stay in tier 0.
- **Unlock target.** A disabled control names its page region as the blocked reason; Unlock credits executable controls in that region. An observed `establishes` claim enables `test_dependency`; role refusals (401/403) unlock adapter-declared role entry points.
- **ε_env** = (mismatches + 1) / (trials + 10), starting at 0.10.
- **Floors** apply when a class's or area's count in the window is below floor × window length. The area cap is 20 of the last 50 decisions.
- **Realized information** is Bayesian surprise; its expectation equals the EIG.
- **Not implemented** (not required): `role_contrast`, `input_contrast`, split tests across view states, passive-evidence entry points.

## 7. Diagnostics outside the T2 assumptions (20 seeds each)

| Diagnostic | Finding |
|---|---|
| Rare capability among repetitive controls (state variants) | Planner and legacy both find it (recall 0.96 / 0.94). BFS made 121 gate refusals |
| Misleading novelty (30 identical pages) | Planner AUC 0.797 vs legacy 0.514; every policy splits the identical pages into separate templates (1 false split per run), as the M1 report predicted |
| Incorrect initial equivalence (variants) | Recall 0.96 with `split_test` runs on sampled instances; which split recovered which variant was not separately audited |
| Role-specific functionality | Planner recall 0.73 vs legacy 0.41 (it opens the member role via the adapter), but AUC 0.38 vs 0.40. Each role duplicate is a separate ACG capability, as designed |
| Missing identifiers | Family bounding replaces instance bounding: AUC 0.719 vs 0.516 legacy, recall 1.00 |
| Unobservable client-only effects | Every policy finds 4 of 8: the ACG's storage and region effect atoms do not name the key or region, so distinct client controls merge (2 false merges per run). A model limitation, not a planner one |
| Noisy outcomes (25% flaky) | The planner keeps exploring (recall 0.48 vs 0.46), but its AUC (0.30) is below legacy (0.42) |
| False prerequisite signals (permanently disabled decoys) | No crash and no unsafe attempts. Unlock credit on decoy regions is bounded by the run-local enablement rate. AUC 0.611 vs legacy 0.791 |
| Long restoration chains (depth 6) | AUC 0.411 vs legacy 0.628; restoration 66% of actions |
| Writes with / without snapshots / unverifiable snapshot | All three are identical. Write-capable reproductions are risk tier 2 and were never eligible while tier 0 had questions, so snapshots were never used and the unverifiable snapshot was never exercised. **Write verification under L3 remains untested** |
| Verification | 0 VERIFIED anywhere. The frozen Phase 1 search rule needs results to add links compared with the page before the search; the simulated search filters a list that is already fully shown |

## 8. Recommendation and next step

1. **Do not replace the frontier with this planner.** Do not start Phase 3 shadow runs of it as specified.
2. **Keep the ACG question structure.** It is the evidence-supported part:
   - template- and family-bounded binding;
   - ≤ 3 instance samples plus split tests;
   - risk tiers and evidence-backed blocked reasons;
   - the per-decision explanation log.
3. **Drop EIG ranking and Unlock** (T2f rule). Choose within the pool with a simpler, cheaper rule.
4. **Replace the area allocator with cost-aware locality.**
   - Prefer questions answerable in the live state.
   - Treat session state as a resource: before a fresh context, count the open questions that would become unreachable.
   - Defer independent reproductions until the live context's dependent questions are exhausted, as the legacy reserve effectively does.
5. **Keep a BFS or legacy fallback** for applications without detected structure (T2d rule).
6. **Separate model gaps to fix:**
   - name the storage key and region in client effect atoms;
   - verify searches by the links that disappear as well as those that appear;
   - add a revisit trigger for pages whose controls were disabled.

Any revised selector must be preregistered and tested against the same frozen scenarios, without changing them, before any live work. This milestone does not start Phase 2.

**Limits of this evidence.**
- Passing the simulator is necessary, not sufficient.
- The simulator, scenarios and planner were written by the same author. The simulator was frozen first, but its architectures reflect that author's view of web applications.
- The legacy baseline is an approximation.

## 9. Reproduce

```
.venv/bin/python -m evaluation.sim_eval --all --workers 9   # 2,650 runs, ~7 min on 10 cores
.venv/bin/python -m evaluation.sim_scorecard
.venv/bin/python -m pytest tests/test_appsim.py tests/test_planner_t3.py
```

**Outputs:**
- [evaluation/results/t2_tests.json](evaluation/results/t2_tests.json): T2 verdicts, reliability bins and per-budget rows;
- [evaluation/results/t2_scorecard.json](evaluation/results/t2_scorecard.json): the aggregated scorecard;
- `evaluation/results/t2_runs.json`: per-run records, kept local and ignored by git.

**Full regression suite:** see the commit message.
