# Research next steps for Agent 1

Date: 2026-10-28

## Evidence boundary

This plan is based only on published research and the independent Coverage Lab/Northstar development evidence. It does not use WebExploitBench traces, protected metadata, locations, verifier results, or per-vulnerability misses. The benchmark evaluation is segregated in `WEBEXPLOITBENCH_EVALUATION.md` and supplies no optimization signal here.

The strongest development result is mixed:

- The frozen coverage policy discovered 8/8 independently labeled held-out areas, 11/11 controls, and 8/8 request surfaces.
- In the clean repeat it recorded reproducible paths for only 5/8 held-out areas before exhausting the browser-action budget, although all 19 attempted replays succeeded.
- A prior held-out run replayed 6/8 areas, showing scheduling variance rather than a deterministic completeness property.
- Short, redundant paths are replayed before some unique deep paths because validation is ordered by transition identity/path length and charged against the same global action budget.
- Exploration novelty is dominated by globally unseen control shape. It does not price restoration cost or directly reward novel state fragments, forms, request structures, or prerequisite-path prefixes.
- Interaction support covers ordinary clicks/forms and a bounded semantic subset, but not the full readiness space: hover disclosure, scroll-dependent controls, drag/drop, canvas/graph gestures, keyboard-only sequences, and overlay recovery remain limited.
- Grouping preserves raw observations and record/session facts, but whole-observation structure remains conservative. It can split cosmetic/transient variants or miss component-level equivalence; any more aggressive grouping risks merging distinct records or contexts.

Structural recall is therefore ahead of replay-complete coverage. The next experiment should optimize **accurate, independently replayable area/request coverage per action**, not raw state count.

## Competing method 1: restoration-cost-aware archive and replay scheduling

**Measured weakness addressed.** Northstar discovered all 8 areas but replayed only 5 in the clean repeat. Redundant shallow paths consumed validation budget while distinct deeper prerequisites remained untested.

**Mechanism and why it should work.** Maintain one archive entry per reversible state/path instance with its path prefix, covered areas/controls/forms/requests, observed restoration cost, last restoration result, and mutable-context requirements. Select exploration and validation targets by marginal independently labeled proxy novelty divided by predicted action cost. Reserve replay capacity across distinct path/instance classes rather than sorting all transitions shallow-first. Reuse only verified path prefixes; still execute complete paths in fresh contexts for validation.

This adapts Go-Explore's separation of remembering, returning, and branching. The published method identifies “detachment” and “derailment” as core exploration failures and first returns to an archived cell before exploring. Browsers cannot safely restore arbitrary server state, so Agent 1 must substitute evidence-checked path replay for simulator snapshots.

Primary source: [Ecoffet et al., “First return, then explore,” Nature 2021](https://www.nature.com/articles/s41586-020-03157-9) and [preprint](https://arxiv.org/abs/2004.12919).

**Implementation complexity.** Medium. The archive and return paths already exist. New work is a deterministic scheduler, prefix-equivalence key, measured-cost estimate, per-class replay reservation, and checkpoint-compatible bookkeeping. It does not require RL.

**Expected benefits.** More distinct areas and request-bearing paths independently replayed under the same action cap; lower run-to-run variance; deeper verified chains; fewer repeated root reloads.

**Tradeoffs/failure modes.** Cost estimates can favor cheap but unimportant paths; stale mutable state can invalidate an archive entry; prefix sharing can be unsafe across sessions or records; reserving budget may reduce raw exploration. Fresh-context outcome checks remain mandatory.

**Independent evaluation.** Compare the current scheduler with cost-aware archive selection on the unchanged Coverage Lab and Northstar ground truth plus a new deep-path development fixture. Use equal total browser actions, including restoration and replay. Score distinct applicable area paths replayed, deepest verified chain, request-surface recall with reproducible prerequisites, actions per newly replayed area, and variance across reset seeds.

**Falsifier.** Reject the hypothesis if it does not improve the median number of distinct replayed areas under the fixed action cap, if gains disappear when restoration actions are counted, or if replay reliability drops below the current attempted-path result.

## Competing method 2: multi-dimensional curiosity without RL

**Measured weakness addressed.** Current prioritization treats globally unseen control shape as the main novelty signal. Common-looking controls can lead to new forms or requests, while visually novel but behaviorally redundant controls can consume actions.

**Mechanism and why it should work.** Score each frontier edge using a deterministic novelty vector: unseen control-in-component, form field structure, changed state fragment, request method/path/parameter shape, session/context change, and prerequisite prefix. Discount dimensions that have repeatedly produced no new evidence, and divide by estimated restoration/action cost. Keep each dimension inspectable and ablatable rather than collapsing it into an opaque learned policy.

WebExplor couples curiosity reward with an incrementally built automaton and, when local exploration stalls, returns along a selected path before branching. Its reported objective is diverse action sequences with temporal prerequisites. Agent 1 can test the underlying novelty/archive hypothesis before accepting the training cost and instability of online Q-learning.

Primary source: [Zheng et al., “Automatic Web Testing using Curiosity-Driven Reinforcement Learning,” ICSE 2021](https://arxiv.org/abs/2103.06018).

**Implementation complexity.** Medium. Most raw signals already exist, but request novelty must be attributed only after an action and cannot guide the first execution. The policy needs deterministic weights, visit counters, stable tie-breaking, and checkpoint serialization.

**Expected benefits.** Higher area/control/request recall per browser action; less proxy gaming by repeated control shapes; better selection of branches that expose new request parameters even when UI structure is similar.

**Tradeoffs/failure modes.** Cosmetic fragments can dominate novelty; background telemetry can inflate request reward; delayed request feedback can bias selection; manually chosen weights may overfit the development fixtures. Sanitization must continue to store parameter names/shapes, never secrets.

**Independent evaluation.** Run one-factor variants for control-only (current), component/form novelty, request novelty, and the combined vector. Ground truth remains outside the mapper. Measure marginal recall per action over time, redundant transition rate, request precision where labeled, and false state splits.

**Falsifier.** Reject a dimension if its ablation has indistinguishable or better coverage/efficiency across applications, or if it increases graph size without increasing independently labeled applicable surfaces or replayed paths.

## Competing method 3: fragment-aware state/action equivalence

**Measured weakness addressed.** Whole-observation identity is conservative, while control-shape novelty ignores where a control appears. This permits unnecessary splits from dynamic chrome and redundant exploration of equivalent shallow navigation; an aggressive whole-page merge would instead risk losing distinct records or session contexts.

**Mechanism and why it should work.** Build a reversible DOM component tree from browser-observed landmarks, forms, lists/tables, accessible subtrees, and stable ancestor relationships. Compare corresponding fragments and classify changes as stable content, data-fluid/cosmetic, or unknown. Define actionable equivalence using both the control and its containing fragment. Never erase raw observations, instance facts, or session markers; unknown comparisons remain separate.

FragGen was designed specifically because thresholded whole-page comparison produces near-duplicate states and repeated actions. It uses page fragments both for state equivalence and to de-prioritize equivalent actionables. Its published evaluation reports improved model precision/recall and much more reliable same-version action replay, but those results concern its own datasets and regression-testing task, not Agent 1 coverage.

Primary source: [Yandrapally and Mesbah, “Fragment-Based Test Generation For Web Apps,” IEEE TSE 2022](https://arxiv.org/abs/2110.14043).

**Implementation complexity.** Medium-high for DOM/accessibility fragments; high for full screenshot/VIPS/OpenCV parity. Start with browser-native semantic/DOM fragments and exact reversible provenance. Do not adopt visual native dependencies until the simpler ablation fails.

**Expected benefits.** Fewer redundant shallow states/actions, better local novelty, more stable return checks, and fewer false splits from cosmetic regions while preserving record-level differences.

**Tradeoffs/failure modes.** Component boundaries can move; virtualized lists and shadow DOM complicate correspondence; fluid classification learned from repeated observation can suppress meaningful changes; fragment equivalence can cause critical record/session merges. Computation may reduce browser throughput.

**Independent evaluation.** Use separately labeled pairs containing cosmetic clocks, changing counters, different records, session-dependent controls, reordered lists, transient overlays, and component-local JS changes. Measure false merges and unnecessary splits first, then area/replay efficiency under the same action budget.

**Falsifier.** Reject or constrain the method on any critical record/session false merge, or if reduced graph redundancy does not translate to higher independently labeled coverage or replay efficiency.

## Competing method 4: event/state-flow crawling with semantic readiness

**Measured weakness addressed.** The mapper's finite interaction alphabet cannot expose every browser-observable control. Independent fixtures cover some JS-only disclosure, but hover, scroll, overlay, drag/drop, canvas, and keyboard sequences remain outside or weakly represented.

**Mechanism and why it should work.** Extend candidate extraction from static clickability to browser-observed readiness: accessible roles/states, focus order, scroll containers, pointer/keyboard affordances, hover-disclosed descendants, dialogs/overlays, and safe drag handles. Execute each new action class behind an explicit safety policy and retain its pre/post observation in the same state-flow graph.

Crawljax dynamically scans the DOM for candidate elements, fires events, observes DOM state changes, and incrementally constructs a state-flow graph. The useful adaptation is the event/state model and bounded candidate plugins, not a wholesale replacement of Agent 1.

Primary sources: [Mesbah, van Deursen, and Lenselink, “Crawling Ajax-Based Web Applications through Dynamic Analysis of User Interface State Changes,” ACM TWEB 2012](https://repository.tudelft.nl/record/uuid%3Af7a5f58d-5d36-4105-8ac2-385c0f18cf1a) and the [Crawljax implementation](https://github.com/crawljax/crawljax).

**Implementation complexity.** Medium per action class, high in aggregate. Hover/scroll/focus are tractable; arbitrary canvas and drag gestures require coordinate/action semantics and robust replay locators.

**Expected benefits.** Higher control/action recall on applications where important state is not reachable by ordinary DOM click/form interaction; explicit evidence for previously blocked controls.

**Tradeoffs/failure modes.** Candidate explosion, unsafe gestures, ephemeral overlays, coordinate fragility, and many ineffective actions. More actions can reduce coverage efficiency unless readiness and novelty are jointly enforced.

**Independent evaluation.** Add an interaction-readiness fixture with evaluator-only labels for hover menus, below-fold controls, keyboard tabs, modal dismissal, safe drag/drop, and a canvas-like control. Compare one action class at a time against current extraction under equal budgets.

**Falsifier.** Reject an action class if it adds no independently labeled reachable surface across at least two fixtures, materially lowers existing replay reliability, or mostly produces ineffective transitions.

## Longer-horizon alternative: active automata learning

Active automata learning could systematically distinguish action sequences that current grouping treats alike. ALEX models Selenium/HTTP inputs and infers a Mealy machine through repeated queries. This is appealing for conformance and counterexample discovery, but it assumes a finite useful action alphabet, stable output abstraction, and reliable resets—the three pieces still under active measurement. It is therefore a later alternative, not the next implementation.

Primary sources: [ALEX implementation](https://github.com/LearnLib/alex) and [Steffen, Howar, and Isberner, “Active Automata Learning: From DFAs to Interface Programs and Beyond,” PMLR 2012](https://proceedings.mlr.press/v21/steffen12a.html).

Falsification gate before adoption: if the proposed archive and fragment experiments cannot achieve stable reset/output classes on the development corpus, exact learning queries would be unreliable and should remain deferred.

## Ranked recommendation

1. **Restoration-cost-aware archive and replay scheduling.** Highest expected impact because it directly targets the measured 8/8-discovered versus 5/8-replayed gap and can reuse existing infrastructure with the smallest conceptual change.
2. **Multi-dimensional deterministic curiosity.** Likely to improve surface/action efficiency beyond control-shape novelty, especially for forms and requests, while remaining inspectable and cheap.
3. **Fragment-aware state/action equivalence.** Potentially high impact on redundancy and state quality, but it carries the greatest critical false-merge risk and needs a correctness-first evaluator.
4. **Semantic readiness/event classes.** Important for interaction recall, but should be added incrementally only after the scheduler stops wasting actions; otherwise it enlarges an already expensive frontier.
5. **Active automata learning.** Strong systematic model, but premature until resets, action abstraction, and output identity are demonstrably stable.

This ranking is a hypothesis. It must be changed if the matched experiments falsify it.

## Concrete matched development experiment

Do not use any WebExploitBench target or output. Keep evaluator ground truth in a separate process and repository path unavailable to the mapper.

**Applications.** Use unchanged Coverage Lab and Northstar, plus a new disposable DeepBranch fixture authored before policy implementation. DeepBranch should contain independently labeled deep prerequisites, repeated shallow chrome, equivalent controls in distinct components, hover/scroll/overlay actions, background Fetch/XHR, two record instances, transient cosmetic content, and one session-dependent branch. Freeze its ground truth before running policies. Tune only on Coverage Lab and DeepBranch; use Northstar once after freezing choices.

**Policies.** Compare:

- P0: current coverage/control-shape policy and shallow-first replay scheduler.
- P1: P0 plus restoration-cost-aware archive and per-path replay reservation.
- P2: P0 plus multi-dimensional novelty, with fragment, form, and request dimensions separately ablated.
- P3: P0 plus semantic-readiness actions, enabled one class at a time.
- P4 only after individual results: the best two components combined, followed by leave-one-out ablation.

**Matched budget.** One worker; fresh/reset fixture per run; 60 seconds, 140 total browser actions, 30 transitions, and the existing 30% replay reserve. Count start/reset, restoration, exploration, and verification actions uniformly. Run five deterministic seed/tie-order repetitions per policy/application. Record one-time fixture startup separately. Use no model calls.

**Primary endpoint.** Applicable independently labeled areas with at least one fresh-context replayed prerequisite path divided by 140 actions. This prevents raw discovery from hiding replay debt.

**Secondary endpoints.** Area/control/request recall; structural-only versus replayed areas; deepest verified chain; request surfaces with reproducible prerequisites; replay success numerator/denominator; restoration failures; redundant shallow paths; false merges/splits; record/session preservation; time-to-coverage curves; median and range across repetitions.

**Decision rule.** Keep a component only if it improves the median primary endpoint on both development applications without a critical false merge or sensitive-value leak, does not reduce attempted replay reliability below 95%, and transfers directionally to the single frozen Northstar evaluation. Report negative and mixed results. Do not combine components until their independent ablations are complete.

## Agent 1 boundary

Agent 1 should own website-only observation, safe interaction readiness, state/component/instance identity, sanitized request-surface capture, prerequisite-path archiving, cost-aware exploration, fresh-context replay, and evidence/provenance. It should report blocked and unresolved surfaces without inventing reachability.

Future planning/testing agents should own vulnerability hypotheses, choosing security tests, acquiring or requesting authorized credentials, role-specific plans, state-changing/destructive test approval, exploit construction, impact confirmation, and benchmark submissions. Agent 1 may expose a request surface and its path; it must not infer that the surface is vulnerable or execute an exploit to improve its map.

## Next decision

Implement only P1 first: restoration-cost-aware archive/replay scheduling with explicit unique-path reservations. Its success criterion is not more discovered states; it is materially more independently labeled held-out areas with fresh-context replayed paths at the same total action budget. If P1 fails, inspect the charged restoration trace before moving to novelty or interaction expansion.
