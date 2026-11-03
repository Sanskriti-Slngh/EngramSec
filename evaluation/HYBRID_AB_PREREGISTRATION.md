# Preregistration: capability-aware legacy hybrid vs frozen legacy frontier

Frozen together with the hybrid policy ([agent1/live/hybrid.py](../agent1/live/hybrid.py)), its offline tests ([tests/test_hybrid_policy.py](../tests/test_hybrid_policy.py)) and its browser contract tests ([tests/test_hybrid_browser.py](../tests/test_hybrid_browser.py)), before any run of the hybrid on an evaluation environment. Harness: [hybrid_ab.py](hybrid_ab.py).

- **Development so far:** contract-test fixture only ([development_apps/hybrid_lab.py](../development_apps/hybrid_lab.py)).
- **Unchanged:** earlier preregistrations, reports and results.

## Arms

| Arm | Policy |
|---|---|
| A. `legacy` | Frozen legacy frontier, the per-environment configuration of the Phase 3 and grounded comparisons (`exploration_policy` absent) |
| B. `hybrid` | The same loop, configuration, budgets, safety, scope and HTTP controls with `exploration_policy="hybrid_capabilities"` |

Both arms capture the same evidence (`acg_evidence`, `action_ledger`).

## Frozen hybrid rules

| Mechanism | Rule |
|---|---|
| Families | A control with a target: kind, interaction, method, target route pattern, field shape, handler revision. A handler-driven control (no target): the page's route pattern, kind, interaction, component, role, label, field shape, handler revision |
| Behavior | The ACG capability's operation ids and effect kinds for that executed transition (`no_effect` when none) |
| Deferral (A) | `same_target_repeat`: the same exact target was executed in this role with one consistent behavior. `family_settled`: 2 distinct instances, one behavior. `cross_role_repeat`: the family is settled in another role and this role's first 2 cross-role samples matched with 0 mismatches |
| Never deferred | A family with diverging behaviors (`family_split`), one sample or one instance (`uncertain`), no evidence (`novel`) |
| Fallback | A deferred item stays queued. When every candidate is deferred, the legacy choice runs |
| Continuation (B) | A control revealed on the same page by the executed action, or enabled now after being disabled on the last visit to this page (same role), is taken first while it is actionable on the live page, past the legacy 8-step local-burst limit |
| Verification (C) | Legacy's replay phase skips, at zero cost, a replay whose action or prerequisite issued a write or possible state change, whose prefix already failed with a missing control, or whose source role differs from the fresh-context role with no role-changing step in its path |
| Logging | Every exploration attempt and replay decision goes in `execution_ledger.jsonl`; every selection in `hybrid_decisions.jsonl` (legacy choice, chosen item, reason, deferred items with evidence transition ids) |

## Environments, trials, budgets

- **Environments:** stateful CRUD lab, JavaScript-heavy lab and replay lab (scored against frozen ground truth), plus the Phase 2 prerequisite fixture (workflow diagnostic only). Each run starts with fresh application state, using the same per-environment budgets as before.
- **Smoke:** one paired smoke trial over all 4 environments first. The 3 trials run only if, in every smoke environment, the hybrid has:
  - 0 ledger integrity problems;
  - 0 destructive hits and 0 unsupported claims;
  - repeated write hits ≤ legacy;
  - false record merges ≤ legacy.
- **Trials:** then 3 paired trials. The smoke trial is not scored.
- **Seeds:** none; neither arm has a random component, so trials differ only by timing.
- **Live time:** cap 14.5 minutes for smoke plus trials. The contract tests used about 1.5 minutes of the ~15-minute budget. If the cap is reached, the run stops and the partial result is reported.

## Metrics

**Primary:** ground-truth capability discovery AUC versus browser actions (the Phase 3 evaluator, unchanged).

**Secondary, identical for both arms:**
- final recall and precision, with absolute true positives, false positives and the matched count;
- false and correct capability merges, capability splits;
- functional areas mapped (ground-truth templates observed);
- record-instance counts and false record merges;
- prerequisite-chain completion (server side);
- ground-truth-redundant transitions: an observed exploration transition whose ground-truth capability, under the frozen action mapping, was already exercised earlier in the run;
- the hybrid's deferred and prevented counts;
- restoration share; replay (verification) actions; blocked verifications;
- safety (destructive hits, repeated write hits, unsupported claims) and redirect scope violations;
- wall-time AUC;
- the precision-audit categories of every unmatched capability ([precision_audit.py](precision_audit.py), the frozen M1a scorer unchanged).

## Hypotheses (each evaluated independently)

| Id | Criterion |
|---|---|
| H1 no loss | Per scored environment: mean final recall (hybrid) ≥ legacy **and** mean AUC (hybrid) ≥ legacy − 0.02 |
| H2 efficiency | Pooled over the scored environments: ground-truth-redundant transitions per observed exploration transition ≥ 20% lower (relative) than legacy, **and** false capability and record merges (summed over trials) ≤ legacy in every environment |
| H3 prerequisites | The prerequisite chain completes in all 3 hybrid trials |
| H4 better | Mean AUC (hybrid) ≥ legacy + 0.03 in ≥ 2 scored environments, **and** mean precision (hybrid) ≥ legacy in every scored environment, **and** safety holds in every environment: 0 destructive hits, 0 unsupported claims, repeated write hits ≤ legacy, scope violations ≤ legacy |

- **Viability:** H1–H3 establish whether the architecture is viable.
- **Replacement:** H4 establishes whether the hybrid is worth replacing legacy.
- **Default:** legacy remains the default unless H1–H4 all pass, and even then replacement needs a larger comparison.

## Not allowed

- tuning on evaluation runs;
- rerunning a trial for a better result;
- changing the evaluator, metrics or thresholds after the smoke run.
