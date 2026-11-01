# Exploration planner design: hypothesis-driven hierarchical exploration

Status: design proposal. No production code was changed.
Model it plans over: [PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) (ACG).
Methods it draws on: [RELATED_WORK_AND_METHOD_COMPARISON.md](RELATED_WORK_AND_METHOD_COMPARISON.md).

## 1. The architectural change in one paragraph

Today the agent's decision unit is **(saved path, visible control)**, scored once by hand-tuned novelty weights and executed in a separate exploration phase. Verification happens later, in a replay phase.

The proposal changes the decision unit to **an open question about the application model**. Examples: "what does this affordance do?", "does `share Canvas` require an existing canvas?", "are these two buttons the same capability?", "do these two product pages behave the same?". Each question is generated from the ACG and valued by expected information gain per unit cost under a risk gate. Each is answered by a designed **experiment** that may explore, reproduce, verify or contrast.

Planning is hierarchical:
- an **area allocator** divides budget across functional areas;
- a **question selector** picks the next question in an area;
- an **experiment designer** turns it into a restoration plan, an action sequence, inputs and an oracle;
- the existing **executor** runs it.

Exploration and verification share one loop, and every result updates the model that generates the next questions. This is not a new priority term on the frontier: the frontier as a data structure goes away and is replaced by a question agenda derived from the model.

## 2. Why the current frontier cannot be fixed by re-weighting

| Property | Current frontier | Needed for functional understanding |
|---|---|---|
| Decision unit | (path, control) | (question about a capability, entity, dependency or abstraction) |
| Value | Static additive novelty weights at enqueue time | Recomputed from current uncertainty after every experiment |
| Knows what is unknown | No | Yes: unverified claims, untested dependencies, unbound affordances |
| Verification | Separate phase (30% reserve) | Interleaved; a verification result changes exploration immediately |
| Restoration | Path replay from root (+ one-step history) | Planned over the model: live reuse, history, direct-URL entry points, snapshot |
| Hierarchy | First URL segment (spatial) | Functional areas from entity/capability clustering |
| Stopping | Budget or empty frontier | Per-area saturation estimate (unseen-capability estimate + residual information gain) |
| Similar-looking states | Same group → suppressed | Explicit split tests; abstraction refined on contradiction |
| Equivalent interfaces | Both explored as novel | Equivalence test, then one is skipped |

The hierarchical experiment already showed that re-ordering the same decision units by a different key changes travel cost but not coverage ([HIERARCHICAL_EXPLORATION_REPORT.md](HIERARCHICAL_EXPLORATION_REPORT.md)). Changing the decision unit is the only change that alters what can be learned.

## 3. Architecture

```
           ┌──────────────────────────── ACG (materialized view over evidence log) ───────────────┐
           │ templates · views · affordances · operations · entities · capabilities · conditions  │
           └───────▲──────────────────────────────┬─────────────────────────────────────────────────┘
                   │ claim deltas                 │ queries
    ┌──────────────┴───────┐        ┌─────────────▼─────────────┐
    │ Resolvers (pure)      │        │ Question generators (pure)│  ← rules over the ACG (§4)
    └──────────────▲───────┘        └─────────────┬─────────────┘
                   │ evidence                     │ open questions (agenda)
    ┌──────────────┴──────────────────────────────▼──────────────────────────────────────┐
    │ L3 Area allocator     budget across FunctionalAreas & question classes (§5.1)        │
    │ L2 Question selector  value(q) = (EIG + unlock) / cost, subject to risk gate (§5.2)  │
    │ L1 Experiment designer restoration plan · action sequence · inputs · oracle (§5.3)   │
    │ L0 Executor           BrowserSession + observers + safety gate per step (existing)   │
    └─────────────────────────────────────────────────────────────────────────────────────┘
                   ▲ adapter: reset/snapshot level, auth, origin aliases, risk policy
```

The levels correspond to established ideas, without importing their learning machinery:
- **L3/L2/L1** have the structure of an options/HTN hierarchy. Each question class is an option with an initiation set (where it applies), a policy (experiment template) and a termination condition (oracle verdict).
- **L2's value function** is Bayesian experimental design in its cheapest form: the mutual information between binary claims and noisy experiment outcomes, plus the entropy of discovery outcomes (§5.2).
- **L1's restoration** is Go-Explore's "first return, then explore", with return planned over reproducible model edges.

No reinforcement-learning training is needed. The values are computed from the model, not learned across runs (the trade-off is discussed in §8).

## 4. Questions (hypotheses) and their generators

A question is a typed record:

```python
class Question(BaseModel):
    id: str
    kind: QuestionKind
    subject_ids: list[str]           # ACG nodes/claims it is about
    area_id: str
    target_claims: list[str]         # claims whose posterior the answer updates
    outcome_model: OutcomeModel      # categorical (discovery) or binary claim + channel (§5.2 B–D)
    risk_tier: int                   # 0 none/client-only, 1 never executed and may write, 2 write permitted by isolation
    risk: EffectRisk                 # worst plausible effect of the experiment (§PROPOSED §6.2)
    est_cost_actions: float          # incl. restoration (§5.3)
    blocked_reason: str | None = None
    generated_by: str                # generator id + resolver version (for reproducibility)
```

### 4.1 Question classes

| Kind | Generated when | Experiment | Oracle / answer | Typical value |
|---|---|---|---|---|
| `bind_affordance` | Affordance on a template with no binding claim | Execute it once from a representative view | Which capability/operations/effects it produced | High early; decays with area saturation |
| `sample_instance` | Template with ≥ 2 entity instances, < k sampled | Visit another instance | Same template behavior? (else split) | Moderate; k = 2–3, never 50 |
| `reproduce` | Capability `OBSERVED`, not `REPRODUCED` | Re-execute from an independent start (fresh context / snapshot / different instance) | Same operations + effects | High for capabilities, low for pure navigation |
| `verify_effect` | Capability `REPRODUCED`, an applicable oracle exists | Differential, cross-view, round-trip or inverse experiment | Oracle verdict (§PROPOSED §4.3) | High; gated by isolation for writes |
| `test_dependency` | Hypothesized `requires`/`enables` | Run the dependent capability with the condition absent vs present | Fails without and succeeds with | High when many capabilities depend on it |
| `test_equivalence` | Two bindings with matching operation keys, unconfirmed | Execute both from comparable states | Same capability identity? | Moderate; saves budget afterwards |
| `split_test` | A view state reached by ≥ 2 distinct paths or instances, with one shared affordance untested in one of them | Execute the affordance in the other context | Different outcome → refine abstraction | Moderate; prevents false merges |
| `find_entry_point` | Operation or URL known only from static/passive evidence (resource spider, script AST, ZAP) | Search the UI for an affordance producing it; else a direct GET if read-safe | Binding found, or `passive_only` | Moderate |
| `role_contrast` | Capability observed in role A; role B available via adapter | Check availability in role B | Availability claim per role | Moderate; authorization structure |
| `input_contrast` | Form-backed capability with validation outcome or unknown constraints | Contrast inputs (valid / empty / boundary) | Constraint claims; validation behavior | Low–moderate |
| `unsupported` | Affordance needing an interaction the executor lacks | None (recorded) | `BLOCKED(unsupported_interaction:…)` | 0, but reported as a coverage gap |

### 4.2 Generators are bounded by templates, not instances

Generators iterate over **templates, capabilities and claims**, never over raw controls on every observation. A product list with 500 items yields:
- one `bind_affordance` for the product-link family;
- two or three `sample_instance` questions.

It does not yield 500 frontier items. The ComfyUI node catalogue (hundreds of node types from `/object_info`, expected) yields one `bind_affordance` per *menu family* of the search dialog. Additional entries in that family are sampled only while new signatures keep appearing, which is the same Good–Turing rule as §5.4. Catalogue entries never become capabilities without an executed signature ([PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) §5.6).

## 5. Planning levels

### 5.1 L3: area allocator

- **Areas** are communities over capabilities ([PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) §5.4). Before any capability exists, the area is the template cluster, so it degrades gracefully to today's behavior.
- **Allocation is a non-stationary bandit over areas.** The reward is *realized information gain per action*: the sum of entropy reductions of claims caused by the last experiment, divided by its actions.
- **Mechanism: discounted UCB (deterministic).**
  - Per area *a*, keep a discounted count `n_a` and a discounted mean yield `ȳ_a`, with discount γ = 0.9 per decision. Yield is realized bits divided by actions, normalized by the run's running maximum yield.
  - Choose `argmax_a ȳ_a + c·sqrt(ln(Σ n) / n_a)` with c = 1, breaking ties by area id.
  - Areas never chosen have `n_a = 0` and are chosen first.
  - The earlier draft used Thompson sampling. That contradicted the deterministic, reproducible runs promised in §5.2, so UCB replaces it.
- **Floors and caps:**
  - every area with open `bind_affordance` questions keeps a minimum share (5% of decisions) until saturated;
  - no area may take more than 40% of decisions in a sliding window of 50.

  This implements the brief's "avoid starving ordinary navigation" and prevents camping in one area (the role `area_action_limit = 8` plays today).
- **Question-class budget split** within the run, adaptive with bounds:
  - discovery (`bind_affordance`, `find_entry_point`, `sample_instance`) ≥ 40% until global saturation;
  - verification (`reproduce`, `verify_effect`) ≥ 20% once ≥ 3 capabilities are `OBSERVED`;
  - structure (`test_dependency`, `test_equivalence`, `split_test`, `role_contrast`) gets the rest.

  The floors replace the fixed 30% replay reserve. Their purpose is that no class is starved by the value function's estimation errors.

### 5.2 L2: question selector (implementable specification)

The selector uses only quantities the executor can observe. Its few constants are fixed in table I and preregistered. It has no cross-environment priors, so nothing learned on one benchmark carries into another run.

**A. Observable quantities.** After each experiment the executor returns, deterministically from evidence:
- whether the plan executed (control found, no exception), and the failure reason if not;
- the set of operation keys and the set of effect atoms ([PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) §5.3);
- the result template and view ids, and any new identifier tokens;
- for reproduction-type experiments, whether the observed signature equals the target signature;
- the oracle verdict: `pass`, `fail` or `inconclusive`;
- browser actions consumed (restoration included), HTTP requests and wall time.

No planner belief is ever used as an outcome.

**B. Uncertainty representation.** There are two kinds of uncertainty.
1. **Discovery counts.**
   - A *family* is (role, template id, affordance locator family, interaction kind).
   - Per family, keep the number of binding experiments and the count of each signature they produced.
   - Per area, keep `N` (binding experiments) and `f1` (signatures observed exactly once).
   - Per interaction kind, keep attempts and failures.
2. **Binary claims.** Every non-discovery question targets one binary claim, for example "C is reproducible", "C passes the cross-view oracle", "C requires D's postcondition", "bindings X and Y are equivalent", "template T behaves uniformly across instances".
   - Each claim has a posterior probability `p`.
   - Its prior is the run-local base rate of that claim kind: `(confirmed_k + 1) / (tested_k + 2)`.

**C. Experiment channels.** A binary experiment returns `pos` or `neg` with sensitivity `s = P(pos | true)` and false-positive rate `f = P(pos | false)`:

| Experiment | s | f |
|---|---|---|
| reproduce (signature equality) | 1 − ε_env | 0.05 |
| differential-input oracle | 0.95 | 0.05 |
| cross-view or round-trip oracle | 0.90 | 0.05 |
| inverse-operation oracle | 0.90 | 0.10 |
| dependency, two arms (fails without ∧ succeeds with) | (1 − ε_env)² | 0.05 |
| equivalence or split test | 1 − ε_env | 0.05 |
| availability contrast (L0/L1 dependency proxy) | 0.70 | 0.20 |

- `ε_env` is the only measured channel parameter. It is the fraction of reproductions of already-`REPRODUCED` read-only capabilities that mismatch, starting at 0.10.
- An `inconclusive` verdict does not update the posterior but its cost is charged. After 2 inconclusive verdicts the question is `BLOCKED(inconclusive)`.
- After a `pos` outcome, the posterior is `p' = p·s / (p·s + (1−p)·f)`, with the symmetric rule for `neg`. This is the confidence update referenced in the model's §4.1.

**D. Expected information gain** (bits; every claim weighted equally):
- **Binary question:** `EIG = H_b(p·s + (1−p)·f) − [p·H_b(s) + (1−p)·H_b(f)]`, the mutual information between the claim and the outcome.
- **`bind_affordance` (categorical):** the outcome is fully revealed, so `EIG = H(P)`. `P` covers:
  - `FAIL`, with probability `(fails_kind + 1) / (attempts_kind + 2)`;
  - `NEW`, with probability `(1 − P(FAIL)) · (f1 + 1) / (N + 2)` (smoothed Good–Turing for the area);
  - each signature already seen in the family, plus `NO_EFFECT`, sharing the remaining mass in proportion to `count + 0.5`.
- **`find_entry_point`:** binary, with prior equal to the run-local rate of found entry points.
- **`sample_instance`:** the split-test channel on "T behaves uniformly".

**E. Unlock value** (bits, one level, never recursive):

```
Unlock(q) = P(q succeeds) · Σ_{b ∈ B(q)} EIG(b)
```

- `B(q)` holds the blocked questions whose recorded `blocked_reason` names the condition, capability or role that `q` targets. Reasons that can name a target:
  - an affordance observed `disabled` / `aria-disabled`;
  - an affordance available only in another role;
  - an experiment that failed with a validation outcome, a 401/403, or a redirect to an authentication template.
- If no blocked question names `q`'s target, `Unlock(q) = 0`. The planner never invents a prerequisite.

**F. Cost** (browser actions):

```
Cost(q) = (R(q) + A(q) + O(q)) / (1 − P_fail(q))
```

- `R(q)`: the shortest restoration path in the return graph (§5.3). Each edge kind costs the run's running mean of measured actions, starting at 1 per step.
- `A(q)`: the experiment's own actions (`_descriptor_action_cost`).
- `O(q)`: extra oracle actions, for example the second execution of a differential pair or navigation to a collection view.
- Wall time is reported but not optimized.

**G. Risk.** Risk is a gate plus tiers, not a penalty term:
1. The `may_execute` table ([PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) §6.2) removes impermissible questions. They become `BLOCKED` with a reason.
2. Permitted questions are tiered:
   - tier 0: none observed or client-only;
   - tier 1: never executed and possibly writing (non-search forms, actions with unknown effect);
   - tier 2: write-capable, permitted by isolation.
3. In the chosen area, only the lowest non-empty tier is eligible.

Tier 1 is reached only when tier 0 in that area is empty or saturated. This is `f6744ba`'s "defer untested non-search forms", stated as a rule instead of a −45 weight.

**H. Selection.**

```python
def select(agenda, areas, recent):                          # deterministic
    area = allocator.choose(areas)                          # §5.1 discounted UCB
    cands = [q for q in agenda.open(area) if gate.permits(q)]
    starved = [k for k in CLASS_FLOORS if share(recent, k) < CLASS_FLOORS[k] and agenda.has_open(k)]
    if starved:                                             # floors override area choice
        cands = [q for q in agenda.open_any_area(starved[0]) if gate.permits(q)]
    tier = min(q.risk_tier for q in cands)
    pool = [q for q in cands if q.risk_tier == tier]
    return max(pool, key=lambda q: ((eig(q) + LAMBDA_UNLOCK * unlock(q)) / cost(q),
                                    -cost(q), perm[q.id]))  # perm: seeded id permutation, per run
```

The seeded permutation is the only randomness: it breaks exact ties. A given seed and given application responses yield the same decision log.

**I. All tunable constants** (preregistered; no others exist):

| Constant | Value |
|---|---|
| D-UCB discount γ / exploration c | 0.9 / 1 |
| Class floors | discovery 40%, verification 20% (once ≥ 3 capabilities are observed), each area with open discovery questions 5% |
| Area cap | 40% |
| Floor/cap window | 50 decisions |
| `λ_unlock` | 1 |
| Channel table C (except ε_env) | as listed |
| Initial ε_env | 0.10 |
| Max inconclusive verdicts per question | 2 |
| `sample_instance` k (unless a split is found) | ≤ 3 |
| Saturation (§5.4) | P(NEW) < 0.05 with N ≥ 10; max value < 10% of the run's median realized yield |
| Agenda cap per area | 200 |

`λ_unlock` and the channel values are set once from the development fixtures and the offline simulator (§10), then frozen.

**Risk gate (unchanged).** Questions whose risk is not permitted under the adapter's isolation level never receive a value. They are reported as untested capabilities with their reason.

### 5.3 L1: experiment designer

An experiment is `(start_requirement, restoration_plan, action_sequence, inputs, oracle, risk)`.

**Restoration planning.** Restoration is a shortest-path problem over a *return graph*:

| Return edge | Cost (initial, then measured) | Preconditions |
|---|---|---|
| stay (live state already satisfies the start requirement) | 0 | same view and same entity instance |
| history back | 1 | the last step was input-free and read-only (existing rule) |
| direct URL entry point | 1 navigation + readiness | template has an instance-addressable URL `REPRODUCED` in this role |
| reproduced read-only transition | its action count | claim `REPRODUCED`, risk `none_observed`/`client_only` |
| fresh context + root | 1 + readiness | always |
| adapter snapshot restore (L3–L5) | measured restore seconds → action-equivalents | adapter attests the level and the start-state verification passes |

Edges are only those whose claims are at least `REPRODUCED`. An observed-once transition is never used as a restoration step, because it may depend on hidden state. Known-write steps are never used without a snapshot edge. This generalizes `_known_write` and the `UnsafeRestoration` rule.

Direct-URL teleports are a large, safe win. A canvas, product or article view with a reproduced instance URL becomes one navigation instead of a replayed click path. Today a 5-step Crawl Maze path costs 6+ actions each time it is restored.

**Inputs.**
- Typed generation (existing `_generated_value`), plus:
  - *contrast pairs* for differential oracles;
  - *validation-derived constraints* (pattern, min/max) learned from `input_contrast`;
  - *in-run identifier reuse*: an identifier-shaped value visible in the current page or URL may be used in memory for a field whose name matches an entity type's ID key path.
- Values are never written to the evidence log; only their HMAC token and input-reference ids are.

**Oracle selection.** The strongest applicable oracle from the ladder ([PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) §4.3) that fits the remaining budget and the isolation level. Fallback is `operation conformance`, which gives at most `REPRODUCED`.

**Dependency experiment design (example).** To test `requires(share Canvas, exists(Canvas owned_by self))`:
1. Restore snapshot S0 (no canvases owned by this user).
2. Look for the share affordance on the dashboard. Its absence or disabled state is evidence for the requirement.
3. Restore snapshot S1 (one canvas), or, under L2, run `create Canvas` once.
4. Look for the affordance again.
5. Under L0/L1 (no snapshots), use a weaker *availability contrast*: compare views where the condition is observed true vs false without creating anything.

The claim's status ceiling is `OBSERVED` and the reason is recorded.

### 5.4 Stopping and saturation

An area is **saturated** when all three hold:
1. the Good–Turing probability that the next `bind_affordance` reveals a new capability is < 0.05, with at least 10 binding experiments in the area;
2. the maximum `value(q)` in the area is below 10% of the run's median realized yield;
3. no `Unlock` question in the area exceeds that threshold.

The run stops when all areas are saturated or the budget is exhausted. The report states which.

This gives a defensible statement: "this area is mapped to an estimated ≥ 95% capability-discovery completeness under the current abstraction". Today the agent can only say "the frontier was empty or the budget ran out".

## 6. Main loop (pseudocode)

```python
def explore(env: EnvironmentAdapter, budget: Budget) -> ACG:
    log, acg = EvidenceLog(), ACG()
    live = executor.start(env.start_url, env.session(role=env.default_role))
    acg.apply(resolvers.update(log.append(live.evidence)))
    agenda = QuestionAgenda()
    while budget.remaining():
        agenda.refresh(generators.run(acg, changed=acg.dirty_nodes()))      # incremental
        area = allocator.choose(acg.areas(), agenda)                        # L3
        q = selector.best(agenda.open(area), acg, env.isolation, live)      # L2 (risk-gated)
        if q is None:
            allocator.mark_saturated(area)
            if allocator.all_saturated(): break
            continue
        plan = designer.design(q, acg, live, env)                           # L1
        if plan.blocked:
            agenda.block(q, plan.reason)
            continue
        if plan.needs_snapshot:
            env.restore(plan.snapshot)
            if not verify_start_state(env, acg, plan.snapshot):             # §PROPOSED §6.3
                agenda.block(q, "unverified_start_state")
                continue
        result = executor.run(plan, safety_gate=SafetyGate(env.policy, acg))  # L0, per-step gate
        deltas = resolvers.update(log.append_all(result.evidence))
        realized = acg.apply(deltas)                                        # entropy reduction
        allocator.reward(area, realized / max(1, result.actions))
        agenda.resolve(q, result.verdict)
        live = result.final_state
        budget.charge(result)
    return acg
```

Every decision is logged with: question id, alternative top-3 values, chosen experiment, restoration plan and realized gain. Each action is therefore explainable ("why did it click this?"), which the current frontier cannot offer.

## 7. Examples on our environments

**Whiteboard (authenticated).** L2 exists today: the existing disposable runner gives a fresh database per run. L3 per-experiment snapshots do not exist yet; they arrive in migration Phase 5. Steps 4 (L3 branch) and 6 apply only after that.
1. Initial dashboard → `bind_affordance` questions for "+ Create canvas", the canvas cards and "Log out" (refused by the existing danger filter → `BLOCKED(destructive_possible)`).
2. The canvas cards bind to one capability, grounded as `instance_view(E1)` once reproduced.
3. `sample_instance` on the second seeded canvas confirms one template and two instances (fixes the 5-canvas merge by construction).
4. The create form's risk is `server_write_possible`:
   - under L0 it runs once and is never repeated (as now);
   - under L3 it is a `verify_effect` with a cross-view oracle: a new instance token in the dashboard list, plus round-trip by its direct URL.
5. Editor affordances: share dialog (ComponentState), rename, and canvas gestures (`unsupported` until a gesture executor exists, reported as a gap).
6. `test_dependency` for share-requires-canvas runs from snapshots S0/S1.

The run reports about 6–10 capabilities with statuses, not "43 transitions, 36 untested".

**PrestaShop (anonymous; adapter supplies the origin alias).**
1. Home → category, product and search affordances.
2. `sample_instance` stops at 2–3 products.
3. Search gets `verify_effect` via contrast queries (generalized paired search).
4. "Add to cart" is `server_write_possible`. With L2/L3 it is explored, then cart-view cross-view verification follows.
5. `test_dependency` shows checkout requires a non-empty cart.
6. Checkout's potential external effects (order email) keep it `BLOCKED` unless the adapter stubs mail.

**ComfyUI (anonymous, single route).**
1. Readiness gating plus content-free abstraction gives one stable initial view.
2. Menu, sidebar and dialog affordances bind to `view History`, `load Workflow`, `open Settings` and similar.
3. `find_entry_point` for `GET /object_info` (seen in network) links the node-type catalogue to the add-node search dialog.
4. `queue Workflow` (`POST /prompt`) is `server_write_possible` with adapter-declared compute cost, so `BLOCKED` unless the adapter allows it with a tiny default workflow.
5. Canvas drag and connect are `unsupported` until the gesture executor exists (migration phase 5).

**SiyuCMS.**
1. Search binding plus differential `verify_effect` (already demonstrated).
2. `sample_instance` over articles.
3. `role_contrast` anonymous vs admin when the adapter provides an admin session.
4. Danger classification by dialog, ARIA and icon cues plus the adapter lexicon, not English regexes.

**Crawl Maze.**
1. Almost every question is `bind_affordance` plus `find_entry_point`.
2. Hidden interactions arrive as affordances from the CDP and framework providers.
3. Handler revisions arise naturally as `split_test` outcomes.
4. Verification uses operation conformance.

The planner should be *no worse* than the current coverage policy here (§9 guard rail), but it is not expected to be much better: Crawl Maze has little functional structure to exploit.

## 8. Algorithm comparison

| Approach | Decision unit | Model updated online | Handles server state | Needs reliable reset | Stopping rule | Per-decision cost | Fit |
|---|---|---|---|---|---|---|---|
| BFS/DFS crawl (Crawljax-style) | (state, event) | state graph only | no | implicit (reload) | exhaustion | O(1) | baseline only |
| Current Agent 1 frontier | (path, control) | no (static priority) | refuses writes | fresh context | budget/exhaustion | O(log n) | being replaced |
| Curiosity RL (WebExplor/QExplore) | (state, action) | Q-values / counts | no | episodic reset | budget | low, but needs many episodes | novelty signal only |
| Go-Explore | archive cell → return → explore | archive | via simulator restore | yes (deterministic restore) | budget | low | return/teleport idea adopted |
| Active automata learning (L*/TTT) | membership/equivalence queries | hypothesis automaton | needs reset per query | yes, strict | equivalence-oracle approximation | polynomial in states, alphabet and counterexample length, but far beyond a 100–500-action budget | too query-hungry; adopt counterexample-driven refinement only |
| Model-based testing (EFSM walk) | test sequences over a given model | model is input | via model guards | test setup | coverage criterion | low | adopt coverage criteria over the learned ACG for verification |
| **Proposed hypothesis-driven HTN** | question on the ACG | yes, after each experiment | yes, via adapter isolation levels | only for write verification | saturation estimate | O(questions in area), incremental | recommended |

Why not learn a policy with RL? Our targets are single applications, mapped once per run with budgets of 100–500 actions. Learned policies need many episodes per application, or transfer across applications we cannot train on without overfitting. The value function here is computed from the model, so it transfers by construction. A learned *prior* (for example `P(new capability | affordance features)`) could later replace the Good–Turing default if a held-out comparison shows it helps.

## 9. Why it should work, what could go wrong, how to validate

**Why it should work:**
- **The decision unit matches the objective.** Capability discovery, verification and dependencies are explicit model claims, so the value function rewards reducing uncertainty about them directly.
- **Budget is no longer spent on repeated instances or equivalent interfaces.** `sample_instance` with k ≤ 3 plus `test_equivalence` bounds the waste that the audit identified (PrestaShop: 2,492 advertisements for 64 controls).
- **Prerequisite chains become reachable.** `Unlock` values and dependency experiments drive the agent through prerequisites, and teleports cut restoration cost.
- **Verification can change exploration.** Interleaving lets a failed reproduction (a hidden precondition) generate a `test_dependency` question in the same run.

**What could go wrong:**

| Risk | Mitigation |
|---|---|
| Wrong capability inference cascades into wrong questions | Claims below `REPRODUCED` never gate other claims; a `REFUTED` claim re-materializes dependants |
| EIG estimates are poorly calibrated early | Class floors (§5.1); Good–Turing needs ≥ 10 samples before saturation can trigger |
| Question explosion on large apps | Generators keyed by template and capability; per-area agenda cap (e.g. 200), with lowest-value eviction recorded |
| Planner overhead | Incremental generation from dirty nodes; target < 5% of wall time (the CDP observer is 0.6% today) |
| Too clever to debug | Per-decision rationale log; deterministic tie-breaks; ablation switches for each level |
| Single-route SPAs give no areas | Areas fall back to ComponentState clusters, then to one area (degrades to L2 only) |
| Regresses Crawl Maze markers | Guard rail: Crawl Maze is a regression check, not a target. Accept a regression of ≤ 2 markers only if the functional metrics improve on ≥ 3 other environments |

**Experimental validation.** Matched budgets, three repeats, frozen constants; details in [GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md).
1. **Planner vs frozen `coverage` policy**, both on the ACG resolvers (so only planning differs): capability recall at 50/100/200 actions (area under the discovery curve), dependency recall, verified-capability count, false merges.
2. **Ablations:**
   - no L3 (uniform areas);
   - EIG replaced by uniform choice over questions;
   - no `Unlock`;
   - no teleports (path replay only);
   - no `split_test`;
   - no `sample_instance` cap.
3. **Calibration:** predicted `P(new capability)` vs realized, per environment (reliability diagram); saturation claims vs ground-truth capability recall at stop time.
4. **Cost accounting:** planner wall time and restoration actions per experiment vs today's root reloads (53 → 31 per run in the hierarchy milestone, as a reference point).

## 10. Fair comparison with the existing frontier, and offline falsification

### 10.1 One execution stack, two selectors

Both the legacy frontier and the planner implement one interface:

```python
class Selector(Protocol):
    def next(self, acg: ACG, live: ViewState, budget: Budget) -> ExperimentPlan | None: ...
```

- **Legacy selector.** It wraps the `f6744ba` `_enqueue` scoring: each frontier item becomes a `bind_affordance` plan. Its replay reserve becomes `reproduce` plans in the legacy replay order.
- **Everything else is shared:** executor, observers, resolvers, safety gate, adapter, browser-action budget, HTTP budget and time limits.
- **Scoring is independent of the selector.** The evaluator scores the resulting ACG against ground truth; the planner's own beliefs (EIG, saturation) are never a metric.
- **No benchmark knowledge enters either arm.**
  - The planner's only inputs are the ACG and the constants in table I.
  - The constants are frozen before any validation or held-out run.
  - The engine purity check ([GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md) §5) covers the planner package.

### 10.2 Deterministic offline simulator

`evaluation/appsim.py` (new, evaluation-side) generates abstract applications from a seed. Each application has:
- templates and affordance families;
- entity types with N instances;
- capabilities with signatures, including deliberate *identical-signature confounders*;
- `requires` dependencies expressed as disabled affordances;
- equivalent interfaces;
- write-risk classes;
- an injected nondeterminism rate ε.

The simulator exposes the same interface the resolvers consume (affordance lists per view, signatures per execution), so both selectors run against it unchanged, with no browser.

Its limit is the abstraction gap: passing the simulator is necessary, not sufficient.

### 10.3 Falsification test T2 (planner)

Each criterion below is a prediction. Failing it falsifies the stated mechanism; it does not just lower a score. The thresholds are fixed now.

| Test | Setup (50 seeds each) | Planner prediction; failure falsifies… |
|---|---|---|
| T2a calibration | mixed apps | Predicted P(NEW) within ±0.10 of the empirical frequency in every bin with ≥ 30 samples; else the Good–Turing outcome model |
| T2b instance waste | 1 template × 200 instances + 10 other capabilities | Actions on that template ≤ 3 + split tests, independent of the instance count; else instance-bounded generation |
| T2c prerequisites | capabilities behind 3-step `requires` chains | ≥ the frontier's gated-capability recall at 100/200/400 actions in ≥ 80% of seeds; else `Unlock` |
| T2d flat app | every affordance a distinct capability; no structure | Discovery AUC ≥ 0.95 × BFS AUC; else the claim that the machinery costs nothing when there is nothing to exploit |
| T2e determinism | any | Same seed ⇒ identical decision-log hash; else the reproducibility claim |
| T2f value ablation | T2b + T2c apps | The full planner beats "EIG replaced by uniform choice". If it does not, the gains come from the question structure, not information gain, and the EIG machinery should be dropped |

T2 needs no browser time and runs before any live planner experiment (migration Phase 1b).
