# Capability-aware legacy hybrid

Branch `agent1-browser-mapper-20261028`, continuing from `2a5a927`. The hybrid, its tests, the precision audit and the preregistration were frozen in `c8608f3` before any evaluation-environment run ([evaluation/HYBRID_AB_PREREGISTRATION.md](evaluation/HYBRID_AB_PREREGISTRATION.md)).
- **Live browser time:** 14.3 minutes for the comparison, plus about 1.5 minutes of development and contract-test runs on the dedicated fixture.
- **Scope:** no held-out applications and no paid calls. Earlier preregistrations, reports and results are unchanged.

## 1. Outcome

**The hybrid is not viable as built. Legacy stays the default.**

| Hypothesis | Result |
|---|---|
| H1 no loss | **Fail** (stateful lab) |
| H2 efficiency | Pass on the preregistered pooled measure, but only because of the stateful collapse; on the other two labs redundancy is unchanged |
| H3 prerequisite chain | **Pass**, 3 of 3 |
| H4 better than legacy | **Fail** |

The hybrid was safe and kept the prerequisite chain:
- 0 ledger integrity problems;
- 0 destructive hits and 0 unsupported claims;
- 0 repeated writes, against legacy's 3 per stateful run.

On the JavaScript-heavy and replay labs it matched legacy's recall and stayed within 0.005 AUC. On the stateful lab it lost:
- AUC 0.700 vs 0.821;
- recall 5 of 7 vs 6 of 7.

The cause is architectural (§6): in a persistent-session explorer, a link that is redundant in capability terms is also the cheap, safe way to reach the rest of the frontier. Deferring it forced restoration through return paths that legacy's write guard correctly refused.

## 2. Precision audit of the grounded comparison

[evaluation/precision_audit.py](evaluation/precision_audit.py) re-scores the saved runs with the frozen M1a scorer, which is unchanged, and classifies every unmatched capability. Results are in [evaluation/results/precision_audit.json](evaluation/results/precision_audit.json).

| Environment / arm (3 trials) | True positives | False positives | Mean precision | Mean recall | False-positive categories |
|---|---|---|---|---|---|
| JS-heavy / legacy | 36 | 12 | 0.750 | 0.857 | 12 role duplicates |
| JS-heavy / tour | 25 | 7 | 0.870 | 0.595 | 7 role duplicates |
| JS-heavy / grounded | 33 | 19 | 0.637 | 0.786 | 19 role duplicates |
| Replay / legacy | 72 | 18 | 0.800 | 0.960 | 18 behavioral splits |
| Replay / tour, grounded | 69 | 15 | 0.821 | 0.920 | 15 behavioral splits |
| Stateful / all arms | 18 | 0 | 1.000 | 0.857 | none |

- **The JavaScript-heavy regression is entirely role duplication.** After "Enter member mode" adds a session cookie, the ACG asserts each capability again under the new role. Every unmatched capability in every arm has the same operations as an already-matched one, under a different role. There was no incorrect splitting, repeated-navigation split, behavior absent from the ground truth, or unsupported effect.
  - The grounded arm entered member mode in every trial and re-explored, so it produced the most duplicates.
  - Precision without role duplicates is 1.000 in every arm.
- **The annotation is ambiguous here, and I did not change it.** It lists one capability with `roles: [anonymous, member]`, while the ACG scopes capabilities per role by design. The frozen metric counts the second role as a false positive.
- **Replay-lab false positives are behavioral splits** of `view_topic`. Topic links (`/topics/science`, `/topics/history`) are one ground-truth capability, but slugs are not recognized as identifiers, so each topic becomes its own capability.

## 3. What was built

**Opt-in policy.** `exploration_policy="hybrid_capabilities"` is implemented in [agent1/live/hybrid.py](agent1/live/hybrid.py), with about 30 lines of hooks in [agent1/explorer.py](agent1/explorer.py).
- The legacy persistent loop, local bursts, safety, scope and HTTP budgets are unchanged.
- With the option off, runs are identical to before; a test checks this.

| Mechanism | What it does |
|---|---|
| A. Redundancy control | **Families:** for targeted controls, the target route pattern, method and fields. For handler-driven controls, the page, component and label. Labels, DOM shape or template alone never defer anything. **Behavior:** the live ACG capability (operations and effect kinds) of each executed transition. **Deferred:** an exact target already executed with one behavior in this role; a family with 2 distinct instances and one behavior; a repeat from another role once 2 cross-role samples matched with no mismatch. **Never deferred:** diverging, single-sample and unseen families. Deferred items stay queued; when everything left is deferred, legacy's choice runs |
| B. Prerequisite continuation | A control revealed on the same page by the executed action, or enabled now after being disabled on the last visit, is taken first while actionable on the live page, past legacy's 8-step burst limit. This is recorded as a dependency hypothesis, not as a cause |
| C. Verification gate | Legacy's separate replay phase skips, at zero cost, replays that would repeat an observed write or state-changing step, need session state a fresh context cannot rebuild, or start with a prefix that already failed with a missing control |
| Grounding | Every exploration attempt and replay decision is a `StepExecution` in the existing ledger. Every selection is in `hybrid_decisions.jsonl`: legacy's choice, the chosen item, the reason, and each deferred item with its reason and evidence transition ids. Evidence is recomputed from the ACG and the artifact on each decision, with no parallel state model |

## 4. Tests

[tests/test_hybrid_policy.py](tests/test_hybrid_policy.py): 13 offline deterministic tests.

| # | Case | Result |
|---|---|---|
| 1 | 200 records, one capability | All 6 distinct behaviors covered in 7 executions vs legacy's 205. Under a 10-action budget: 6 of 6 behaviors vs 1. Nothing dropped |
| 2 | Identical controls, different operations | Both run; the family is marked split and a third member is not deferred |
| 3 | Dynamic handler | A handler revision is a new family; a later diverging sample lifts a deferral |
| 4 | Global navigation across templates | Executed once; a shared label alone never forms a family |
| 5 | Stateful chain | An enabled control is taken first, past the burst limit |
| 6 | Disabled → enabled | Detected against the last visit; plain navigation reveals nothing |
| 7 | JavaScript-only state | A same-page reveal is detected; another record's page is not |
| 8 | Safe read-only replay | Feasible |
| 9 | Replay needing state-changing prerequisites | Blocked (write prerequisite, write action, missing session, failed prefix) |
| 10 | Ambiguous equivalence | One sample, one instance or no evidence: not deferred |
| — | Cross-role repeats | Need 2 matching transfer samples; one mismatch re-opens the role |
| — | Everything deferred | Falls back to legacy's choice |
| — | Post-evaluation fix (§6) | A re-render does not reopen an already-executed control |

[tests/test_hybrid_browser.py](tests/test_hybrid_browser.py): 7 real-Chromium contract tests on [development_apps/hybrid_lab.py](development_apps/hybrid_lab.py). The fixture has a 200-record catalog, twin buttons, global navigation, a setup chain with disabled controls, a JavaScript-only panel, and a member area behind a POST. With legacy's budget, the hybrid:
- reached every endpoint pattern legacy reached, plus the member area legacy never reached;
- repeated fewer navigation targets;
- kept the twins as separate capabilities;
- completed the chain through continuation;
- never repeated the POST;
- had one ledger entry per step.

## 5. Preregistered comparison

One paired smoke trial (gates held), then 3 paired trials; 858 s of live time.
- **Determinism:** both arms are deterministic, so the trials agree to within timing noise.
- **Reporting:** all numbers are per trial; where trials differed, the range is given.

| | Stateful (legacy / hybrid) | JS-heavy (legacy / hybrid) | Replay (legacy / hybrid) |
|---|---|---|---|
| **AUC vs actions** | **0.821 / 0.700** | 0.799 / 0.793 | 0.696 / 0.700 |
| AUC vs wall time | 0.849 / 0.706–0.714 | 0.745–0.752 / 0.745–0.755 | 0.888 / 0.888–0.889 |
| Recall (matched / total) | 6 / 7 vs **5 / 7** | 12 / 14 vs 12 / 14 | 24 / 25 vs 24 / 25 |
| Precision (true / false positives) | 1.00 (6 / 0) vs 1.00 (5 / 0) | 0.75 (12 / 4) vs 0.80 (12 / 3) | 0.80 (24 / 6) vs 0.80 (24 / 6) |
| Functional areas mapped | 2 / 2 vs 2 / 2 | 8 / 9 vs 8 / 9 | 11 / 11 vs 11 / 11 |
| False capability / record merges | 0 / 0 vs 0 / 0 | 0 / 0 vs 0 / 0 | 0 / 0 vs 0 / 0 |
| True record instances observed | 4 vs 2 | — | 7 vs 7 |
| Redundant transitions (ground truth) / observed | 20 / 26 vs 1 / 6 | 15 / 30 vs 15 / 30 | 10 / 34 vs 10 / 34 |
| Browser actions; restoration share | 45; 27% vs 34; 47% | 62; 35% vs **84; 51%** | 89; 44% vs 89–90; 45–46% |
| Failed exploration attempts | 0 vs **12 of 18** | 0 vs 0 | 0 vs 1–2 |
| Verification replays (actions); blocked | 3 (3) vs 0; 0 | 10 (27) vs 11 (37); 0 | 16 (38) vs 15 (35–36); 0 |
| Items deferred / never executed / executed later | — / 9 / 0 / 9 | — / 51 / 46 / 5 | — / 1 / 0 / 1 |
| Repeated write hits | 3 vs **0** | 0 vs 0 | 0 vs 0 |

**Prerequisite fixture.** The chain was completed in 3 of 3 trials by each arm. The hybrid took 147 actions vs legacy's 128, with 39 transitions each.

**Never triggered in any arm:** destructive hits, unsupported claims, scope violations.

**Precision audit of this comparison:**
- **JS-heavy:** hybrid 6 role duplicates plus 3 behavioral splits, against legacy's 12 role duplicates.
- **Replay:** 18 behavioral splits in each arm.

| Hypothesis | Measured | Result |
|---|---|---|
| H1 | Stateful recall 0.714 < 0.857 and AUC −0.121; JS-heavy −0.005; replay +0.004 | **Fail** |
| H2 | Pooled redundant rate 0.371 vs 0.500 (−26%); no false merges. Driven entirely by the stateful runs, which executed 6 transitions instead of 26. JS-heavy and replay: 25 / 64 in both arms | **Pass as preregistered; not a real efficiency gain** |
| H3 | 3 of 3 | **Pass** |
| H4 | 0 environments with +0.03; precision not lower; safety holds | **Fail** |

## 6. Why it failed

1. **Deferring navigation breaks persistent-session reachability (architectural).** On the stateful lab, "All records" was a same-target repeat, so the hybrid deferred it. It then chose items on other pages that needed restoration.
   - After the first POST, every saved return path contained an observed write, and legacy's guard refused them (`UnsafeRestoration`). Some other paths restored the wrong state.
   - 12 of 18 attempts failed, and *Create record* was never reached.
   - Legacy succeeds because its repeated local navigation *is* its restoration mechanism.

   A redundancy signal at capability level ignores what an action is worth as navigation.
2. **Deferral moved cost into restoration (architectural, same cause).** On the JS-heavy lab the hybrid deferred 51 items (46 never executed), mostly repeated global navigation. Reaching non-local items instead raised browser actions from 62 to 84 and restoration share from 35% to 51%. The 30-transition cap was still reached, with the same ground-truth redundancy (15 of 30).
3. **Continuation re-prioritized already-executed controls (implementation).** When the JS-heavy home page re-rendered, controls that had already run counted as "revealed" again, and continuation outranks redundancy, so they ran again. That contradicts the design's "previously unavailable control".
   - **Fixed after the evaluation, not re-measured:** a control already executed on that page in that role never opens a hypothesis (test above).
4. **Handler-driven controls are scoped per page state.** Their exact key includes the DOM group, so each re-rendered state is a new instance. This is deliberately conservative, since behavior can depend on state, but it limits savings on JavaScript-heavy pages.
5. **The replay lab had almost nothing to save.** Its repeats are wizard steps in new states and topic links with distinct routes; 1 item was deferred.

## 7. Conclusion

- **Combining the architectures this way is not better than legacy.** It preserves breadth on two of three labs, matches the prerequisite workflow and avoids repeated writes, but it does not discover faster anywhere and loses badly where navigation doubles as restoration.
- **Before any further hybrid attempt,** redundancy must be weighed against restoration cost and feasibility: never defer a safe local action when the alternative needs a return path through an observed write. That is a different design from capability-level deferral and needs its own preregistered test.
- **Precision:** the earlier regression is a role-scoping question (ACG per role vs annotation per capability), not a behavioral error. Resolving it needs an explicit decision on role-scoped capabilities and the annotation, not a scorer change.
- **Legacy remains the default.**

## 8. Reproduce

```
.venv/bin/python -m pytest tests/test_hybrid_policy.py tests/test_hybrid_browser.py
.venv/bin/python -m evaluation.precision_audit      # needs the saved grounded runs
.venv/bin/python -m evaluation.hybrid_ab            # preregistered comparison (~14 min live)
```

Results: [evaluation/results/hybrid_ab.json](evaluation/results/hybrid_ab.json).
