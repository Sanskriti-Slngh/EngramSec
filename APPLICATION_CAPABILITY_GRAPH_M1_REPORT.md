# Application Capability Graph — Milestone 1 (Phases 0 and 1)

Branch `agent1-browser-mapper-20261028`. The commits are listed in §8.

- **Live browser runs:** 0. The regression suite's existing browser tests are reported separately in §7.
- **Production changes:** none. The crawler code in `agent1/*.py` is byte-identical to `f6744ba`.
- **Model or API calls:** 0.
- **Held-out data:** no held-out (ComfyUI, PrestaShop) or validation (SiyuCMS, held-out shop) archive was opened.

## 1. Answer

**Partly yes.** From evidence Agent 1 already collected, the offline ACG reconstructs behaviorally distinct capabilities, entity types and record instances, with no false capability merges and no false record merges on any development archive. On two of three annotated fixtures it reaches substantially more ground-truth capabilities than the existing transition graph, under the same action-based measure:
- replay lab: **24/25 vs 13/25**;
- JS-heavy lab: **14/14 vs 12/14**;
- stateful lab: **6/7 vs 6/7**, a tie.

It also unifies page URLs and API routes into entity types through shared identifiers. On the whiteboard, `/canvases/{id}` and three `/api/canvases/{id}…` routes become one entity type with 3 instances and 1 template.

Behavioral *meaning* is mostly not reconstructed, because the archives rarely contain the reproduction or oracle evidence the grounding rules require:
- only 18–27% of capabilities have a behavioral class (Crawl Maze 17/94, replay lab 8/30);
- the stateful lab and whiteboard have 0, and the JS-heavy lab 1;
- most capabilities remain correctly labelled as unidentified operations;
- the largest gap is that 22 of 25 JS-heavy replays recorded no requests, so they cannot establish reproduction.

## 2. What was built

**Phase 0** (commit 1, frozen before any resolver existed):
- **Evidence-log contract** `acg-evidence/1` (`agent1/model/evidence.py`). A capture manifest says what each run did and did not record.
- **Read-only, deterministic importer** for `run.json`, `checkpoint.json` and Graph A (`importer.py`).
- **ACG export contract** `acg/1` (`schema.py`).
- **Typed ground truth** (`evaluation/ground_truth.py`) with annotations for the stateful lab (7 capabilities), replay lab (25) and JS-heavy lab (14), plus a URL-identity-only file for the whiteboard.
- **Scorer** (`evaluation/score_acg.py`): M1a, M1b, merges/splits, entity and template identity, provenance, and a Graph A feature baseline.
- **Static purity check** (`evaluation/purity_check.py`):
  - new model package: 0 hits;
  - legacy crawler: 21 language-dependent literals, the known baseline.
- **Dataset registry** that refuses held-out paths, plus an archive inventory (`evaluation/development_inventory.json`).
- **T1:** 8 evidence logs with exact expected partitions. **T3:** a grounding log with expected classes, ablations, invariance and provenance rules (`evaluation/corpora/`).
- **Frozen tests** `tests/test_acg_frozen.py`, which skipped until the materializer existed.

**Phase 1** (commit 2):
- `agent1/model/routes.py`, `materialize.py`: the offline ACG.
- `evaluation/run_m1.py`: the development scorecard (`evaluation/results/acg_m1_scorecard.json`, aggregates only).
- `tests/test_acg_m1.py`: gate checks on real archives.
- An example export with full provenance (`evaluation/results/acg_stateful_lab_example.json`).

**Model** (the smallest version of PROPOSED_APPLICATION_MODEL.md §2–§5):

| Concept | Implementation |
|---|---|
| Evidence | Append-only records; every node and claim cites record ids |
| PageTemplate | Route with identifier positions as `{id}`, dispatch values as tokens, × role |
| ViewState | Template + affordance structure (no page text) + learned predicate values |
| ComponentState | Represented as effects on component regions (`component_state_changed`); no separate node yet |
| Affordance | Structural family (kind, role, interaction, component, locator, target route, form shape); labels are annotations |
| Operation | HTTP method + route + parameter names + encoding + dispatch tokens; or a WebSocket message class |
| EffectType | Closed set of observable atoms (navigated, instance_appeared/disappeared, collection size/membership, component, client state, visual region, message received) |
| Capability | Behavior signature = role + operations + effects (+ entry template when there is no operation) |
| EntityType / Instance | Identifier positions unified by shared values (ID flow); instances keyed by pseudonymous tokens |
| Claim | Identity, status, posterior `p`, support/against, evidence ids, sources, rule, and a reason when blocked or underdetermined |
| Grounding | 8 closed rules with minimum statuses; no class without its rule's evidence |

The statuses OBSERVED, REPRODUCED and VERIFIED are kept apart:
- **REPRODUCED** requires an independent replay whose own requests contain the capability's operations and whose effects match.
- **VERIFIED** requires a differential (paired search) or cross-view oracle.
- A Graph A "replay validated" flag alone never promotes anything.

## 3. Development scorecard

Last run of each dataset (whiteboard: run C1). Legacy = the `f6744ba` Graph A concepts. "n/a" = not measurable from this evidence, never zero.

| Metric | Stateful lab | Replay lab | JS-heavy lab (×4) | Whiteboard (×5) | Crawl Maze (×4) |
|---|---|---|---|---|---|
| 1 Page templates | 2 | 16 | 12 | 2 | 81 |
| 2 View states (legacy state groups) | 3 (13) | 21 (19) | 15 (15) | 3 (10) | 87 (86) |
| 3 Entity types | 1 | 5 | 0 | 1 | 0 |
| 4 Entity instances | 4 | 7 | 0 | 3 | 0 |
| 5 Capabilities (legacy features) | 6 (6) | 30 (18) | 18 (12) | 5 (13) | 94 (88) |
| 6 Unidentified operations | 6 | 22 | 17 | 5 | 77 |
| 7 Equivalent-interface groupings | 0 | 1 | 4 | 1 | 0 |
| 8 Capability merges correct / incorrect | 3 / 0 | 1 / 0 | 4 / 0 | n/a | n/a |
| 8b Capability splits vs ground truth | 0 | 2 (topics ×6, Begin ×2) | 4 (role duplicates) | n/a | n/a |
| 9 Entity merges correct / incorrect | 4 / 0 | 3 / 0 (1 split) | n/a | 3 / 0 | n/a |
| 10 M1a recall | 6/7 | 24/25 | 14/14 | n/a | n/a |
| 10 M1a precision (frozen) | 6/6 | 24/30 | 14/18 | n/a | n/a |
| 10 Role-aware precision (secondary) | 6/6 | 24/30 | 18/18 | n/a | n/a |
| 11 M1b precision | n/a (0 asserted) | 7/8 | 1/1 | n/a | n/a |
| 11 M1b recall (observable) | 0/6 | 7/14 | 1/9 | n/a | n/a |
| 12 Claims with complete provenance | 100% | 100% | 100% | 100% | 100% |
| Status OBSERVED / REPRODUCED / VERIFIED | 6/0/0 | 17/13/0 | 17/1/0 | 4/1/0 | 71/23/0 |
| Behavioral divergences inside a view state (legacy) | 0 (n/a) | 0 (1) | 0 (0) | 0 (0) | 0 (1) |
| Full rebuild deterministic; incremental = full | yes; yes | yes; yes | yes; yes | yes; yes | yes; yes |

**Fair comparison with the transition graph.** Same evidence, same action-to-ground-truth mapping, different grouping:

| Ground-truth capabilities reached | ACG | Graph A features |
|---|---|---|
| Stateful lab | 6/7 | 6/7 |
| Replay lab | **24/25** | 13/25 |
| JS-heavy lab | **14/14** | 12/14 |

The features miss capabilities whose transitions stay in one legacy state group without a non-GET request: listener-driven and XHR buttons such as "Load stock" or "Show history". Neither grouping has an incorrect merge. The ACG has more splits: role duplicates by design, plus the topic-page and wizard splits below.

**13. Evidence gaps that block further inference** (from the capture manifests):
- **No archive has:** response shapes, WebSocket frames, canvas digests or per-field digests. As a result:
  - entity identity is URL-only;
  - `instance_modification` can never be grounded;
  - canvas tools are invisible.
- **The stateful lab has only a Graph A export:** no per-observation affordances and 17 representative-only URLs, so no collection or component effects.
- **JS-heavy and whiteboard replays recorded no requests** (22 JS-heavy and 5 whiteboard replays unusable for reproduction).
- **No archive contains a cross-view or round-trip oracle**, so nothing reaches VERIFIED except through a paired search, and no development archive with a paired search is in this dataset set.

## 4. Phase gate

| Criterion | Result |
|---|---|
| Frozen T1 partitions match exactly | **Pass**, 8/8, plus bindings, unbound/no-effect affordances, learned predicate, entity and template expectations |
| Applicable T3 tests pass | **Pass**: classes; 7 ablations; text invariance (random and zh-CN rewriting of every label and title, 18 cases); 1,000 random subsets; label provenance. Planner-level T3 checks move to Phase 1b, unchanged (migration plan updated) |
| Stateful lab's two seeded records distinct | **Pass** (`/records/1`, `/records/2` → two instances; 4/4 instances, 0 merges) |
| Whiteboard record identities separate | **Pass** in all 5 runs (7 or 3 instances = 7 or 3 true canvases; 0 merges, 0 splits) |
| Shared templates without false record merges | **Pass**: whiteboard canvases 1 template / 3 instances; stateful records 1 template / 4 instances |
| Crawl Maze view states add no demonstrated false merges | **Pass**: 0 behavioral divergences inside a view state, vs 1 in legacy groups on 3 of 4 runs. The *numeric* plan criterion (view states ≤ legacy group count) holds against legacy's behavior-refined groups (87–88 = 87–88) but is exceeded by 1 against plain group signatures on 3 of 4 runs. That extra view state is the evidence-backed handler-revision split |
| Recall/precision measured on ≥ 1 fixture | **Pass** (3 fixtures) |
| Every reported capability has grounded evidence | **Pass** (100% of capabilities and claims cite existing records) |
| Full rebuild = incremental rebuild | **Pass** (every cut point on corpora; mid-point on all 15 archives) |
| Existing production behavior unchanged | **Pass**: no `agent1/*.py` change; regression result in §7 |

**Verdict:** Phase 1 passes its exit criteria with one disclosed deviation: the literal numeric Crawl Maze view-state criterion is exceeded by one state.

## 5. Adversarial counterexample search (development evidence)

| Case | Where found | ACG outcome |
|---|---|---|
| Same endpoint, different payload-dependent effects | No genuine development instance. Synthetic T1.8 (two settings via one `PUT`, same parameters) | **Cannot distinguish**: merged, by design and documented |
| Same requests, different effects by context | Whiteboard: opening a seeded canvas for the first time yields `instance_appeared`, a revisit does not, because canvas cards are buttons and the canvas id is first seen on its own page | **Incorrect split** (2 capabilities for 1 function). Not fixable without response shapes from the list API |
| Different endpoints, equivalent effects | Stateful lab: create, view and update all end on a record page; `/counter` and "All records" both end on `/` | **Separated correctly** by their operations (ground truth confirms they differ) |
| No backend request | Replay lab: "Show details", "Begin", "Continue" | **Separated correctly** as client-view changes. One extra "Begin" capability (re-click replaces instead of adds) is an evidence-backed split the ground truth does not distinguish |
| No backend request and no DOM change | Whiteboard drawing tools (Select, Line, Rectangle, …); "Refresh status" | **Cannot distinguish**: no capability (`executed_no_effect`). Correct for "Refresh status"; a blind spot for drawing tools (no visual or attribute evidence) |
| Same element, behavior revised | Replay lab "Check loans"; Crawl Maze "Submit" (did nothing, then sent a request) | **Separated correctly** with a learned `behavior_revision` predicate |
| Multiple prerequisite steps | 8–85 deep actions per archive; 0–7 reproduced | Represented as capabilities. **Dependencies are not inferred** in M1 (no Condition resolver) |
| Different records | Replay lab `/records/3` vs `/api/records/3/history` | **Incorrect entity split**: one shared integer is below the union threshold (≥ 2 shared integers or 1 UUID) |
| Structurally identical static pages | Replay lab topics (6 pages) vs JS-heavy `/shallow/a`, `/shallow/b` | Six templates and six capabilities. **The annotations are inconsistent**: one calls the topic pages one template, the other calls the shallow pages two. Behavior cannot decide this, and I did not change either frozen annotation |
| Different sessions, identical interfaces | JS-heavy anonymous vs member on `/`, `/shallow/a`, `/shallow/b` | **Kept separate per role**, as designed. This costs frozen precision (14/18), and no false merge results |

## 6. Changes after Phase 0, disclosed

Phase 0 was committed first. After it, no frozen T1/T3 expectation or test assertion was edited. The following were changed:

1. **Whiteboard annotation route** corrected from `/canvas/{id}` to `/canvases/{id}`; I had misremembered it, and the archived URLs show the real route. The annotation records this. A Phase 0 scorer unit test used that string as sample input and was updated to match.
2. **A secondary role-aware precision diagnostic** was added to the scorer. The frozen M1a is unchanged and remains the headline.
3. **Resolver refinements** made after seeing development results; the frozen tests passed before and after each:
   - A document load of the result page counts as navigation, so a reload is navigation too. This removed 3 spurious JS-heavy splits.
   - A component effect inside a region present in both views names which affordances changed. This removed the replay lab's one incorrect merge (Begin + Continue).
   - A replay is compared using the action's own reload evidence, because a replay's requests span its whole path. This restored 6 Crawl Maze reproductions that the previous change had wrongly dropped.
   - "No observable effect" counts as an outcome when learning context predicates. This removed the Crawl Maze divergence.
   - Behavior already explained by distinct source view states is not reported as underdetermined.
4. **Two design clarifications made during implementation:**
   - the navigation and instance-view rules exclude actions whose requests carry engine-filled input, since navigation is input-independent;
   - per-record presence of replay requests is authoritative. The frozen T3 corpus manifest says `replay_requests: false` while its replay records contain requests; that is a corpus inconsistency, left unedited.

## 7. Regression suite

Full suite on the final Phase 1 code: **254 passed in 249 s**.
- 170 pre-existing tests, including their usual headless browser tests against local fixtures.
- 84 ACG tests: 15 Phase 0, 62 frozen T1/T3, 7 Phase 1 gate.

An earlier run, started before the whiteboard route correction reached the Phase 0 scorer test, failed only that test (253/254). It passed after the disclosed input-path update in §6.

## 8. Limits and what this does not show

- **The annotations are not independent.** I wrote them as the engine developer, from fixture source, before the resolvers existed. The topic/shallow inconsistency shows the subjectivity.
- **Small datasets:** the replay lab is one probe run, and the stateful lab is one Graph A export with reduced evidence.
- **Effect atoms have known blind spots:**
  - `instance_appeared` cannot tell "created" from "first observed" when identifiers are hidden;
  - slugs are not recognized;
  - entity-type union is threshold-based.
- **Not implemented in M1:** dependencies (Conditions), functional areas, ComponentState as its own node, response-shape and WebSocket capture.
- **Tokens are pseudonymous, not secret.** Offline exports from local services stay git-ignored.

## 9. Is there enough evidence to proceed to Phase 1b?

Yes, for the reason Phase 1b exists: the planner can now be developed offline against the simulator, using a model whose identity behavior is tested.

Two findings should shape Phase 1b and the evidence work that follows:
1. **Most uncertainty in real archives comes from missing evidence, not from resolver ambiguity:** replay requests, response shapes, oracles. The planner's value of reproduction and verification questions will matter, but no archive can calibrate ε_env or the oracle error rates yet. The simulator must supply them, and Phase 2 capture must add replay requests, response shapes and WebSocket frames.
2. **The known resolver limits should be built into the simulator** so T2 does not test an idealized model: hidden identifiers, structurally identical static pages, role duplication and blind client-only tools.

## Reproduction

```sh
.venv/bin/python -m evaluation.inventory            # archive inventory (aggregates)
.venv/bin/python -m evaluation.run_m1               # local exports + committed scorecard
.venv/bin/python -m evaluation.purity_check agent1/model
.venv/bin/python -m pytest -q tests/test_acg_phase0.py tests/test_acg_frozen.py tests/test_acg_m1.py
```
