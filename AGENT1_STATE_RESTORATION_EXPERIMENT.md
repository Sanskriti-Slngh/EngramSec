# Agent 1 state-tolerant restoration experiment

Preregistration: [AGENT1_STATE_RESTORATION_PREREGISTRATION.md](AGENT1_STATE_RESTORATION_PREREGISTRATION.md) (`82dcb18`). Implementation: `7c05be8` (`agent1/` tree `5b3fe75`; the harness refused any other tree). Results: [evaluation/results/restoration_ab_scored.json](evaluation/results/restoration_ab_scored.json) (30/30 trials ok, none host-sleep affected) and `restoration_ab_diagnostic.json` (10/10 ok, no instrumentation defects, no amendment).

## Answer

**Yes, conditionally.** A restored state can be recognized as *safe to act from* without being byte-identical to the saved one, provided the evidence establishes the pending action's starting contract rather than full state equivalence:
- the exact URL and session;
- the identical, unique target and its handler;
- the same affordance set;
- unchanged text in the target's container and in the page's identity and status regions;
- for anything other than a fully specified GET link, only passively volatile differences elsewhere.

On the development environments this:
- made **189 of 189** oracle-safe, strictly rejected restorations executable;
- cut Crawlground restoration failures from **59 to 1** per trial;
- raised volatile_lab functions from 6 to 14 of 14;
- caused **zero** wrong-record restorations, unsafe write replays or scope changes;
- caused no recall or precision regression.

It does **not** pass every preregistered criterion. The contract's evaluation overhead exceeded the 10% limit on stateful_lab (21.6% of a 9-second run). The production default therefore stays `strict`.

The decisive limit is now visible. On Crawlground, restoration was blocking navigation, not marker discovery: test pages reached rose from 5 to 37, but markers rose only from 4 to 5. Reaching a page is not executing its functionality.

## 1. Failure mechanism (Step 1)

The full audit is in the preregistration, §2. In short:
- The strict check compares a group signature that includes the main region's text, with digits not normalized, so any counter changes it.
- The existing tolerance, `_usable_return_screen`:
  - is gated on search actions or `robust_readiness`, so it is inactive by default;
  - ignores text and query values, so it **would accept** `/records?id=2` for `/records?id=1` (contract test);
  - still failed Crawlground when enabled, because the snapshot's occlusion test drops a wrapped link on every restored `/results` page.

| Env | Strict failures / trial | What differed | Classification |
|---|---|---|---|
| Crawlground | 59 | scoreboard counters, row marks and timestamps (server state changed by the agent's own visits) + one link dropped by the occlusion artefact | safe for a link whose own row is unchanged |
| stateful_lab | 3 + 7 write-guard refusals | a new record link created by `GET /counter` | irreproducible server-state change; needs an isolated reset |
| replay_lab | 1 | the "Claim voucher" button removed (voucher consumed) | not equivalent |
| volatile_lab (new) | 19 | clock, scoreboard, carousel (16); desk showing another record (3) | 16 safe; 3 unsafe (wrong record) |

## 2. Implementation contract

[agent1/restoration.py](agent1/restoration.py), `RunConfig.restoration_policy="contract"` (opt-in). It is reached only after the strict check has failed. The explorer, frontier, ACG, replay verifier and write guard are unchanged.

The contract has two tiers:
- **Declarative:** a same-origin GET link with no inline or observed handler. Stable differences outside the target's container and the identity and status regions are tolerated.
- **Contextual:** everything else. Only passively volatile differences are tolerated: text that changes on its own across up to three samples, 300 ms apart.

Both tiers require:
- the exact URL, session, forms and frame structure;
- an identical, unique, enabled target with the same handler;
- an equal affordance set.

Two affordance exceptions:
- A snapshot-dropped control counts as present only if a DOM probe finds it at its recorded position, with the same label and target, and not covered by an unrelated element.
- Controls that change on their own count as volatile.

## 3. Adversarial tests

21 contract tests, all passing (preregistration §4):

| Case | Outcome |
|---|---|
| live clock | accepted after passive samples; refused if the clock stops changing |
| score counter | link accepted; contextual button and changed target row refused |
| carousel | outside action accepted; slide link refused (`target_changed`: the explorer's matcher would have chosen "slide 2" for "slide 1") |
| two records, same controls | refused (query id, heading, hidden id, card) |
| two sessions | refused |
| changed handler or target | refused |
| disabled after a prerequisite | refused |
| GET mutation (unflagged / flagged) | refused (`affordance_added` / write guard before the contract) |
| return path with an observed write | refused |
| same-label controls | refused |
| occlusion artefact vs overlay | present vs refused |
| frames, shadow DOM, missing evidence | refused |

## 4. Paired comparison (3 trials per arm; medians; all trials identical unless a range is shown)

Both arms: perception arm C (listener revisit, readiness off); 180 s / 500 actions / 100 transitions; legacy coverage policy; fresh mode; no POST; no model calls.

| Env | Measure | A strict | B contract |
|---|---|---:|---:|
| volatile_lab | functions executed (/14) | 6 | **14** |
| | restoration failures | 19 | **0** |
| | safe restorations accepted (oracle) | 0/16 | **25–26/25–26** |
| | replay-validated transitions | 22–23 | 26–27 |
| | capabilities (reproduced) | 17–18 (16) | 20 (15–16) |
| Crawlground | restoration failures | 59 | **1** (`target_absent`: oracle-unsafe) |
| | safe restorations accepted | 0/58–59 | **37–38/37–38** |
| | test pages reached (/59) | 5 | **36–37** |
| | markers (/59) | 4 | 5 |
| | capabilities (reproduced) | 22 (20–21) | **61–62 (33–35)** |
| | replay-validated transitions | 25–26 | 34–35 |
| stateful_lab | recall / precision | 0.286 / 1.0 | 0.286 / 1.0 |
| | restoration failures | 3 mismatch + 7 write guard | 3 refused (`affordance_added`) + 7 write guard |
| replay_lab | recall / precision | 0.96 / 0.80 | 0.96 / 0.80 |
| | restoration failures | 1 | 1 refused (`affordance_removed`) |
| js_heavy_lab | recall / precision | 0.214 / 1.0 | 0.214 / 1.0 (no restoration failures in either arm) |

Crawlground markers by category moved from links, navigation, forms and dynamic content (1 each) to buttons, JavaScript events, forms, links and navigation (1 each). The +1 is small and category-shifted, not a broad gain.

## 5. Criteria

| Criterion | Result |
|---|---|
| H1 wrong record / unsafe accepted / audit | **pass:** 0 / 0 / 0 in all 15 B trials |
| H2 writes replayed during restoration; state-changing replay ≤ A | **pass:** 0; 0 |
| H3 out-of-scope completed ≤ A; destructive hits | **pass:** 0; 0 |
| S1 ≥ 80% of oracle-safe rejections accepted | **pass:** 189/189 (100%) |
| S2 Crawlground failures ≤ 50% of A | **pass:** 59 → 1 |
| S3 more functional areas | **pass:** test pages 5 → 37, markers 4 → 5; volatile functions 6 → 14 |
| S4 no recall/precision regression | **pass** on all three annotated labs |
| S5a overhead ≤ 10% of elapsed | **fail on stateful_lab (21.6%)**; volatile_lab 7.6%, Crawlground 2.1%, replay_lab 1.2%, js_heavy_lab 0.7% |
| S5b actions and time per unit coverage ≤ 1.5× A | **pass:** volatile_lab 54.5 → 23.9 actions per function; Crawlground 81.8 → 64.8 actions per marker; annotated labs equal (stateful_lab time 1.28×) |

The S5a failure comes from passive sampling (about 0.6 s) spent *before refusing* the three stateful_lab root restorations, whose difference is an added affordance that sampling cannot explain. Wherever the contract accepted, the cost was repaid by the coverage gained.

## 6. Safety tradeoffs and generality limits

- **What is guaranteed is action-level, not state-level.** In 452–469 tolerated Crawlground differences per trial, the server state *had* changed (scoreboard). The contract accepts that because the link's request is fully specified by its `href`. A contextual action from the same page would have been refused.
- **Evidence gap: the wrong-record case never arose in arm B's runs.** Arm A met the volatile_lab desk wrong-record restoration 3 times per trial (and refused it). In arm B, exploration order differed and the desk was never restored after the record changed. The contract's refusal of that case is shown by unit tests only.
- **Session equivalence is by key names**, as under the strict policy. Two principals with the same cookie and storage names and identical pages are indistinguishable to both policies.
- **Region evidence covers the main document only.** Frames and unlocalized (shadow DOM) changes are refused. Volatility slower than about 600 ms is refused, not tolerated.
- **The oracle is author-declared** and covers volatile_lab and Crawlground `/results` precisely. Elsewhere it falls back to an affordance-change rule. It is independent of the contract code, but it is not independent ground truth.
- **Irreproducible server state is still a wall.** stateful_lab is unchanged: 7 write-guard refusals and 3 affordance-change refusals per trial. Progress there needs an **isolated-reset architecture** (snapshot/restore of server state, verified per trial), not a more tolerant comparison. The write guard was not bypassed.

## 7. Next decision

1. **Keep `strict` as the default.** Make `contract` the recommended opt-in for exploration where restoration volatility is evident.
2. Before reconsidering the default, cut refusal-path overhead: skip passive sampling when the unexplained differences include an added or removed non-volatile affordance. That addresses S5a without weakening any check.
3. The next coverage bottleneck on Crawlground is **interaction depth on reached pages**, not restoration: 37 test pages reached, 5 markers. This is policy and budget; the historical 39/59 used the multidimensional policy, extended interactions, persistent mode and 600 s. It belongs in the next, separate milestone.

Tests: 416 passed before the scored runs (21 contract + 5 harness tests new).
