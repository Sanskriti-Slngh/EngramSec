# Live ACG and shadow Capability Tour Scheduler (Phase 2)

Branch `agent1-browser-mapper-20261028`. The legacy explorer remains the production control and the only component that executes actions. Everything new is opt-in (`acg_evidence`, `shadow_tours`) and absent from default runs. There were no paid calls, no held-out applications and no changes to frozen benchmarks. Live browser use was limited to local development fixtures (about 10 minutes in total, including reruns).

## 1. Outcome

**The ACG now updates live from real browser evidence, and the tour scheduler proposes grounded, mostly executable capability investigations in shadow mode without changing what the legacy explorer does.**

- **Shadow runs:** 95 shadow decisions on three local labs at their established budgets, plus 39 on the new Phase 2 fixture.
- **Feasibility:** 0 scheduler errors. In the three labs, 72% of decisions produced a proposal executable from the live state immediately (68 of 95) and 25% one executable after a short restoration (24). The other 3% (3) were decisions where legacy's live page had not been recorded. On the fixture: 38 of 39 immediately and 1 after restoration.
- **Legacy unchanged:** legacy exploration was identical with shadow on and off in every lab, as were legacy recall, wall time (within 0.7 s) and server writes.

**It is ready for a controlled active-policy comparison on development fixtures, with two blockers to fix first (§9).** A shadow run cannot show that the tour scheduler would outperform the legacy explorer: an unexecuted proposal has no observed outcome, and agreement with legacy is not success.

## 2. Step 1: scheduler cleanup (preregistered T2V, offline)

`tour_v2` makes three changes; the frozen `tour_full` and all T2/T2R results are unchanged:
- **Seeded-uniform movement between areas**, the policy the T2R ablation supported.
- **Structural deduplication of global navigation.** One binding question per targeted control family seen on two or more templates; untargeted controls are never treated as global.
- **Explicit verification feasibility:**
  - `blocked_unrestorable_context`: independent replay would need a write without a verified snapshot, or restoration already failed;
  - `oracle_not_applicable`: a paired search showed no differential;
  - `not_reproduced_independently`: a conclusive mismatch, never retried.

Preregistered in `d2973a6` before `tour_v2` existed. Fresh seeds 3000–3029, results in [evaluation/results/t2v_tests.json](evaluation/results/t2v_tests.json):

| Check | Result |
|---|---|
| V1 CRUD AUC | **PASS**: 0.704 vs `tour_full` 0.617 (30 wins, 0 losses). Also beats legacy 0.667 (25 wins, 3 losses) |
| V2 duplicate pages AUC | **PASS**: 0.927 vs 0.704 (30–0). vs legacy: higher mean (0.638), but only 13 of 30 seeds |
| V3 verification waste | **FAIL**: 7.2 vs 4.5 wasted actions per run. The unrestorable rule never applied on CRUD, and v2 finds more capabilities, so it queues more verification attempts |
| Guards | **PASS**: flat 1.37 × BFS; prerequisites 100% of seeds ≥ legacy; ≤ 3 instances; 0 refusals; deterministic |

The preregistered T2V success rule is **not met** because of V3. `tour_v2` is used for shadow mode because it is better on discovery with identical safety.

## 3. Real evidence pipeline (Step 2)

[agent1/live/capture.py](agent1/live/capture.py) attaches to the explorer through side channels. With the option off, `run.json`, Graph A and the stored config are byte-identical: the new config keys are dropped when false, and tests check this.

| Evidence | How it is captured | Privacy |
|---|---|---|
| Disabled and `aria-disabled` controls | The same extraction script with an inverted filter; the same control builder (pure refactor) | Structural fields only |
| Replay request attribution | Replays' own network events | URLs pseudonymized |
| Request and response shape | JSON key-path skeleton digest; JSON bodies only, size-bounded, never copied twice | No values; raw bodies never stored |
| Identifier flow | Per-run HMAC tokens for identifiers in URL segments, query values and JSON request/response bodies, with structural key paths | The key lives only in memory |
| Query dispatch values | Format-preserving keyed pseudonyms, so dispatch and identifier classes keep their meaning for the resolvers | No raw values |
| WebSocket frames | Skeleton digest plus a keyed digest of short top-level discriminator values, attributed to the action whose window contains them | No payload values |
| Client-side state | Storage key names (existing); component and enablement changes as effects | Names only |

- **WebSocket scope is now enforced** when the option is on. Out-of-scope sockets are refused through `route_web_socket` and counted; on the Phase 2 fixture, 2–3 refusals per run. Two implementation findings:
  - `route.close()` deadlocks the sync API, so refusal leaves the socket unconnected inside the browser;
  - **pre-existing:** under legacy's HTTP budget router (`route.fulfill`), Chromium's local-network-access checks block every WebSocket to `127.0.0.1` on fulfilled pages. Local WebSocket evidence is therefore captured only in router-free configurations, which a test covers.
- **The HTTP budget is unchanged:** the capture makes no requests and reads only bodies the browser already received.
- **Body-read failures** after a page closes are counted as missing evidence (`body_unavailable`: 5 in the stateful lab) and never raised.

## 4. Live ACG (Step 3)

[agent1/live/acg.py](agent1/live/acg.py) projects the explorer's evidence after every completed legacy action. It uses the offline importer's own per-item builders, split into `observation_item`, `action_item`, `replay_item` and `assemble`. All 24 archive and corpus exports are byte-identical after that refactor.

**Privacy.** Every identifier and query value is replaced by a format-preserving per-run pseudonym before it reaches the model, so neither the live graph nor its persisted log holds a raw identifier.

**Tested on real runs** ([tests/test_live_shadow.py](tests/test_live_shadow.py)):
- the persisted evidence log rebuilds exactly the live export;
- without capture, the live records equal the offline import of the same run;
- on the same run, pseudonymized and raw records give the same templates, view states, instances, capabilities and statuses (identical summaries);
- no fixture identifier, query value or WebSocket payload value appears in any persisted file.

**Update latency per decision** (mean / max ms):

| Lab | ACG update | Shadow decision |
|---|---|---|
| Stateful lab | 2.9 / 4.9 | 4.1 / 7.0 |
| JS-heavy lab | 2.8 / 13.5 | 3.6 / 10.2 |
| Replay lab | 4.7 / 17.1 | 6.5 / 20.0 |
| Phase 2 fixture | 3.8 / 9.6 | 5.2 / 12.3 |

## 5. Deterministic fixture validation (Step 5)

[development_apps/phase2_lab.py](development_apps/phase2_lab.py) covers:
- dynamic controls and a replaced handler;
- a two-page prerequisite chain (a client-enabled control, then a server-session flag enabling a control on a later page);
- existing records;
- a method-less form whose script POSTs;
- global navigation on every page;
- client-only interactions;
- a search whose results add links;
- a write with no reset;
- in-scope and out-of-scope WebSockets.

Results, legacy budgeted configuration, shadow off vs on:

| Check | Result |
|---|---|
| Legacy exploration unchanged | Identical actions, targets and network in all 39 transitions; identical POSTs (`/api/notes`, `/api/reindex`, once each); same replay count |
| Shadow proposals grounded | Every proposal cites evidence records present in the log; no snapshot steps; all risk tier 0 or 1 |
| Missing evidence explicit | Capture gaps listed per decision (`instance_fields`, `visual_regions`); the replaced handler appears as `behavior_depends_on: unknown` (2 claims) because listener observation is off in this configuration. With it on (replay lab), a learned predicate is produced |
| No unexpected writes | Same writes with and without shadow; the gate blocks re-execution of known writes |
| No false verification | VERIFIED only with paired-search or cross-view replay evidence |
| ACG reconstructible | Exact rebuild from the persisted evidence |
| Concepts captured | Disabled controls (12); `observed_disabled` (2) and `establishes` (1: Accept → Continue); 3 distinct item instances; the method-less form's POST as an operation; response shapes and identifier tokens; WebSocket sends and receives attributed to actions (router-free run) |

**Findings about the legacy explorer:**
- **Generated controls trap it.** The first fixture version appended a new button on every click; legacy spent 47 of 60 actions on that one control because each click made a "new" state. The fixture was corrected to insert once.
- **Its replay order is not reproducible.** Ties are broken by transition ids that embed timestamps, so two legacy-only runs replay in different orders. Exploration itself was identical across runs.

## 6. Limited real-browser shadow experiment (Step 6)

Each lab used its archived baseline configuration in full (the stateful lab uses its test configuration). Summaries: [summary.json](agent1/experiments/live_shadow_20261102/summary.json) and [analysis.json](agent1/experiments/live_shadow_20261102/analysis.json).

| | Stateful lab (CRUD records) | JS-heavy lab | Replay lab |
|---|---|---|---|
| Legacy browser actions / transitions | 45 / 30 | 62 / 30 | 89 / 34 |
| Legacy recall (M1a, ground truth) | 6/7, same with shadow | 12/14, same | 24/25, same |
| Legacy exploration identical with shadow | yes | yes | yes |
| Wall time off / on (s) | 7.4 / 7.6 | 40.1 / 40.2 | 24.2 / 24.9 |
| Shadow decisions | 31 | 30 | 34 |
| Executable now / after restoration | 10 / 18 | 25 / 5 | 33 / 1 |
| Live state not recorded by legacy | 3 | 0 | 0 |
| Proposal kinds | 12 binds, 15 reproductions, 1 split test | 28 binds, 1 reproduction, 1 equivalence | 33 binds, 1 reproduction |
| Same control as legacy's next action | 3 of 27 | 12 of 30 | 9 of 34 |
| Mean proposed plan / restoration actions | 2.18 / 1.18 | 1.23 / 0.23 | 1.06 / 0.06 |
| Context-preservation opportunities (legacy restored elsewhere instead) | 1 | 1 | 13 |
| Global-navigation binding questions suppressed | 0 | 9 | 0 |
| Open discovery questions per decision | 2.1 | 3.3 | 11.1 |
| Discovery questions unreachable | 0% | 10.9% | 0% |
| Live ACG: templates / capabilities (reproduced) / instances | 2 / 6 (0) / 4 | 11 / 16 (9) / 0 | 16 / 30 (13) / 7 |
| Entity identity vs ground truth | 4/4, no merges or splits | no record entities | 7/7, no merges; 1 split (record 3 vs its history API, as in M1) |
| Legacy-missed capabilities | `delete_all` (correctly refused) | 2 alias capabilities | `wipe_records` (correctly refused) |

## 7. Answers

1. **Does real browser evidence support the ACG's concepts?** Mostly yes:
   - **supported:** templates, record identities, operations (including a method-less form's POST), effects, disabled-control conditions, same-page `establishes` claims, WebSocket message classes, response shapes and identifier tokens;
   - **still missing:** per-field instance digests and canvas region digests;
   - **captured but not yet consumed by any resolver:** response shapes and identifier-flow tokens (entity union still uses URL identifiers only);
   - **needs listener observation:** handler revisions are learned only when it is enabled.
2. **Can the scheduler generate useful, executable questions?**
   - **Executable:** yes. In the labs, 68 of 95 decisions gave a proposal executable without restoration and 24 one executable after a short restoration (mean 0.06–1.18 restoration actions per lab).
   - **Grounded:** every proposal cites evidence.
   - **Useful:** unknown. Usefulness needs executed outcomes, which shadow mode cannot provide.
3. **What fraction is blocked by missing evidence?**
   - Discovery questions: 0–11% unreachable per lab (JS-heavy 10.9%).
   - Verification: no blocked items in the labs. On the fixture, write verification is blocked by design (no snapshot).
   - Decisions where legacy's live state was unrecorded: 3 of 95.
4. **Does it recognize genuine prerequisite progress?**
   - **Yes on the fixture:** 2 prerequisite-progress proposals, both the control legacy then executed, plus the `establishes` claim.
   - **None in the three labs,** which have no disabled controls (0 captured).
   - **Cross-page enablement** is recorded only as a chain event, not as a causal claim.
5. **Does it distinguish entity instances?** Yes. 4/4 and 7/7 with no false merges. The known history-API split remains (a single shared small identifier).
6. **Runtime overhead.**
   - 3–7 ms per decision on average, 20 ms at most.
   - Wall-time increase ≤ 0.7 s per run (≤ 3%).
   - The fixture used 25 s with and without shadow.
7. **Which capabilities remain unobservable?**
   - Destructive capabilities (`delete_all`, `wipe_records`): correctly refused, so unobserved.
   - Client-only effects that change no affordance, storage key or region.
   - Canvas and gesture interactions.
   - Local WebSockets under the HTTP budget router.
   - Effects visible only in fields not captured (`instance_fields`).
8. **Ready for a controlled active-policy comparison?** **On development fixtures, yes, after two fixes** (§9). Not on public or held-out targets until those fixes and an executor adapter for the tour plans exist.

## 8. Limitations

- **Agreement is not success.** Shadow agreement (3–12 per lab) measures overlap, not quality. An unexecuted proposal's outcome is unknown and is not inferred.
- **Small sample:** three small development labs and one fixture, one run each. No statistical claim is made.
- **V3 failed:** explicit verification feasibility did not reduce waste on CRUD.
- **Untried executor paths:** no snapshot adapter exists in the real executor; shadow write-verification proposals are blocked, which is correct but untested live.
- **Approximate trails:** the shadow reconstructs trails from legacy workflow paths. When legacy resets to an unrecorded page, the live state is unknown (3 decisions).

## 9. Blockers before an active comparison

1. **Executor adapter for tour plans.** Tour proposals are ACG steps (click by structural locator, `goto`, `back`, `fresh`). Legacy executes `ActionDescriptor`s through `_attempt_frontier`. A thin adapter is needed that resolves an `AffordanceEvidence` to the live control, re-checks it with the legacy safety filter, and returns the same evidence records. This is the single architectural blocker; no rewrite is needed.
2. **The HTTP router and local WebSockets.** Local WebSocket applications cannot be compared under the budget router until this is resolved, for example by serving fulfilled responses with a declared local address space or by exempting in-scope WebSocket targets. Both arms are affected equally, so this matters only for WebSocket-heavy targets.

**Also recommended:**
- make legacy replay tie-breaking deterministic, so paired comparisons are exact;
- feed response shapes and identifier-flow tokens into the entity resolver, preregistered against the frozen T1 corpus.

## 10. Reproduce

```
.venv/bin/python -m evaluation.t2v_eval                      # offline T2V (~1.5 min)
.venv/bin/python -m pytest tests/test_live_shadow.py         # fixture validation (real browser, ~2 min)
.venv/bin/python experiments/run_live_shadow.py             # labs, shadow off/on (~2.5 min)
.venv/bin/python experiments/analyze_live_shadow.py agent1/experiments/live_shadow_<date>
```
