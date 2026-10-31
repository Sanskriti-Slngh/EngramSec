# Replay validation: request-structure scheduling

This continues from fd7f3e8. That run's runtime listener discovery added three Crawl Maze markers but replay-validated none of them. This milestone:
- finds out why;
- adds an evidence-driven replay scheduler that is off by default (`--replay-policy structure`);
- tests the scheduler on a new replay fixture;
- repeats the Crawl Maze comparison as three arms × three seeds.

The frontier, resource spider and graph architecture are unchanged.

## 1. Why the runtime behaviors were never replayed

The answer comes from the fd7f3e8 treatment run (`agent1/experiments/runtime_crawlmaze_180/adaptive_readiness_C/run.json`).

| Fact | Value |
|---|---|
| Exploration ended (time reserve 30%) | 126 s, after 222 browser actions |
| Replay ran | 126 s → 163 s, then stopped at **299/300 browser actions** (not time, not HTTP) |
| Replays executed | 25, all validated; path lengths 1–3; 77 actions |
| Observed, not yet replayed | 78 transitions; path lengths 3 (31), 4 (26), 5 (20), 6 (1) |
| The 3 runtime behaviors | path length 5; status `observed`; **never attempted** |

The legacy order:
1. sorts observed transitions by workflow length;
2. keeps one per replay destination;
3. replays shallowest first until a budget ends.

A behavior that only exists after earlier actions has to wait behind every shallower workflow:
- a `<div>` created by a click;
- the second handler of a button.

Here the action budget ran out about 50 workflows before it. The verification logic was not the problem: these replays were never attempted. Reaching the final URL also proved nothing about requests. A replay counted as validated when its final screen matched. Request structures were checked only when the action changed nothing visible.

## 2. Design

`agent1/replay_scheduler.py`, enabled by `RunConfig.replay_policy = "structure"`. Shallow and diverse are unchanged.

**Request structure.** A request structure is a privacy-preserving key built from:
- the initiator class: `script` (fetch/XHR) or the resource type;
- the HTTP method;
- the route pattern, with instance-like path segments and all query values removed;
- the parameter names;
- the body encoding class.

Only behavioral requests count: script requests, any non-GET request, and document GETs with parameters (form submissions). Plain navigations and static subresources are excluded, as are failed or blocked requests. Values, bodies and cookies are never stored.

**Scheduler.** Replay keeps the existing reserve, time limit and HTTP verification reserve. Each replay comes from the lane that has spent fewer browser actions; the structure lane wins ties.
- **Structure lane:** a greedy cover of request structures not yet verified. It picks the workflow with the most unverified structures per action, where cost is the replay's full action count including all prerequisites. A structure is closed once a validated replay reproduces it, and no equivalent workflow is replayed for it again. A structure whose replays fail twice (`replay_structure_attempts`, attempts across both lanes) is given up.
- **Shallow lane:** the legacy order, so ordinary navigation and prerequisite workflows keep their share. It skips request-only workflows whose structures are all verified or given up.
- **Eligibility:** the structure lane never promotes a workflow with a non-GET structure unless the run opted into non-GET forms (`allow_post_forms`). It also never promotes a workflow with a dangerous-labelled step. Such workflows keep their legacy position in the shallow lane.

**State-changing workflows.** These are not replayed by either lane without `allow_post_forms`. A workflow counts as state-changing when an exact recorded prefix of it (the action itself or a prerequisite) issued a non-GET request during exploration. The check is keyed by the workflow path, not the action label: on Crawl Maze a read-only "Submit" button shares its label with POST-issuing ones. Excluded workflows stay untested (`state_changing_workflows_not_replayed`), and their structures are reported as `not_attempted` / `state_changing_workflow`.

This rule was added after the Crawl Maze runs, prompted by the whiteboard evaluation in `RUNTIME_GENERALIZATION_REPORT.md` §3. Applied offline to the three R2 runs, it excludes none of their replays, so §4 is unchanged.

**Replay.** A replay runs the transition's recorded workflow in a fresh browser context from the start URL:
- each step resolves its control with the existing `find_current`, which requires the recorded handler revision;
- the existing safety and scope routing apply;
- the listener observer runs in replay contexts too, so runtime-created controls and handler revisions are rediscovered rather than assumed.

**Validation under the structure policy.** A replay is validated only if all of these hold:
1. The existing state checks pass: navigation or same-screen checks, unchanged.
2. **Every** request structure the original final action issued is issued again by the replay's final step.
3. **Record identity holds:** for each reproduced structure, the replay requested the same concrete request path, ignoring query values. A session-scoped record (for example a per-session cart id) is therefore not "reproduced" by requesting a different record.

So a replay that only reaches the right URL is not validated when the original action issued requests.

**Failure reasons.** Recorded under every policy, as `ReplayResult.failure_reason`, with `failed_step` set on step failures:

| Reason | Meaning |
|---|---|
| `control_missing` | the recorded control is not in the replay observation at that step |
| `handler_revision_not_reproduced` | the control exists, but not with the recorded handler revision |
| `control_now_unsafe` | the control is now refused by the safety filter |
| `control_ambiguous` | more than one control matches the recorded step |
| `state_mismatch` | the final state checks failed (failed checks are listed) |
| `request_structure_not_reproduced` | the expected request structures were not issued |
| `record_identity_changed` | the structure was reproduced, but for a different record |
| `navigation_error` | the replay's navigation failed |
| `exception` | any other error |
| `http_budget_exhausted` | the replay could not be sent; recorded as untested, not failed |

When a step's control is missing, the replay keeps the observation in which it was absent. Its Graph A claim therefore has complete evidence: `step_k_control_present: false`.

**Graph A.** The new `replay_evidence` section has one record per observed request structure. Each record lists:
- the actions that produced it, with provenance, handler revision, workflow length and prerequisite labels;
- every replay that expected or targeted it, with lane, outcome, failure reason and failed step;
- its status: `verified`, `failed` or `not_attempted`.

Replays also carry `scheduler_lane`, `target_structures`, `failure_reason` and `failed_step`.

**Metrics.** Computed the same way under every policy, so arms are comparable:
- `replay_structures_observed`, `_verified`, `_failed` and `_unattempted`;
- `runtime_behaviors_observed` and `runtime_behaviors_replay_validated`;
- `replay_browser_actions`;
- `replay_failure_reasons`;
- `replay_scheduler` (lane spend and replays, skipped equivalents, given-up structures).

## 3. Tests

Replay lab fixture: `development_apps/replay_lab.py`. Six decoy topic pages make the shallow-first order expensive. The server logs method, path and session for every request.

| Brief case | Lab page | Test and result |
|---|---|---|
| 1 created listener `<div>` | `/lab/div` | `/api/details` verified through a 3-step workflow of listener provenance |
| 2 replaced handler | `/lab/redefine` | `/api/second` verified on the revision, `/api/first` verified on the original handler; the two never share a key |
| 3 multi-step prerequisites | `/lab/multi` | `/api/finish` verified through a 4-step workflow: link → Begin → Continue → Finish |
| 4 two distinct structures | `/lab/pair` | `/api/reviews` and `/api/stock [sku]` both verified |
| 5 equivalent structures | `/lab/twins` | one structure produced by two controls; exactly one replay targets it |
| 6 application state changed | `/lab/claim` | the one-time voucher fails with `control_missing` at step 2; the failure observation is kept and the transition is not marked validated |
| 7 session and record identity | `/records/3`, `/cart` | `/api/records/{id}/history` verified in a new session with the same record (the server saw two sessions); the per-session cart fails with `record_identity_changed` |
| 8 dangerous action | `/lab/danger` | the "Delete all records" listener is never executed or replayed; no POST reached the server |

Tests:
- `tests/test_replay_scheduler_runs.py`: the cases above, end to end, plus a matched tight-budget comparison. At 90 browser actions, the structure policy reproduces at least 2 more distinct structures than the shallow policy for comparable replay spend, and the shallow lane still runs. In the probe run the shallow policy reproduced 1 of 10 structures and 0 of 6 runtime behaviors; the structure policy reproduced 5 of 10 and 1 of 6, with 37 vs 38 replay actions.
- `tests/test_replay_scheduler.py`: six browser-free unit tests covering:
  - structure normalization, with no values stored;
  - deep unverified structures ahead of redundant shallow ones;
  - verifying each structure once;
  - retrying on another workflow, then giving up;
  - lane fairness;
  - non-GET eligibility.

## 4. Crawl Maze: three arms × three seeds

Run directory: `agent1/experiments/replay_crawlmaze_3x3/`. The summary is `replay_summary.json`, produced by `experiments/summarize_replay_ablation.py`.

**Matched configuration.** Every run used:
- 180 s, 300 browser actions, 1,000 HTTP requests (30% held for replay), one worker;
- E2 extraction and frontier flags;
- Crawl Maze at `2a0dd0a`.

The runs were interleaved as seed pairs (R0, R1, R2 for seed 0, then seed 1, then seed 2).

**Seeds.** `--random-seed` only affects the resource spider's `random` frontier policy. These arms use FIFO, so the three seeds are independent repetitions, not differently randomized runs.

**Target reset.** Crawl Maze keeps no server-side state (no globals, sessions or database), and every run starts from a fresh browser context.

**Code.** The runs used fd7f3e8 plus this milestone's uncommitted diff (`+mapper-59e4d29853ce`). No code was edited during the runs.

| Arm | Markers /91 (each seed) | Via runtime actions | Runtime transitions replay-validated | Request structures reproduced | Validated workflows | Replay actions | Browser actions | HTTP | Elapsed (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R0: discovery off, shallow replay | 58 / 58 / 58 | 0 | – | 0 / 9 | 24 / 23 / 23 | 70.3 | 297 | 677 | 164.2 |
| R1: discovery on, shallow replay | 61 / 61 / 61 | 3 | **0 / 3** | 0 / 11 | 25 / 25 / 25 | 77 | 299 | 678 | 166.1 |
| R2: discovery on, structure replay | 61 / 61 / 61 | 3 | **3 / 3** | **6 / 11** | 21 / 21 / 21 | 76 | 298 | 670 | 170.6 |

All three seeds gave identical counts.

**Graph quality.** In all nine runs:
- incorrect state merges: 0;
- Graph A connections missing evidence: 0;
- unsafe or skipped listener elements executed: 0;
- replay failures: 0.

**Coverage.** Discovery adds the same three markers in every pair: +3, −0 against R0. These are the two created-`<div>` cases and the redefined handler. The replay policy does not change coverage.

**Functional validation.** Under the legacy order (R1), none of the three runtime-discovered transitions is attempted. Under the structure order (R2), all three are replayed in a fresh context through their 5-step workflows and validated. That includes the handler-revision step: the replay context rediscovered the replaced handler.

R2 also reproduces three 5-step snapshot behaviors that the legacy order never reaches: `multi-step-request-event-attribute`, `multi-step-request-event-listener` and `-listener-dom`. That makes 6 of 11 observed request structures reproduced, against 0 for R1. R1's validated replays are all shallow navigations, which issue no application requests.

The remaining five structures are `POST` and `PUT` requests:
- `listener-and-event-attribute-first`/`-second`;
- `two-listeners-first`/`-second`;
- `js-put`.

The structure lane does not promote them without `allow_post_forms`, and the shallow lane ran out of actions before reaching them at depth 4. They are reported as `not_attempted`, never as verified.

**Cost.** R2 validates 21 workflows against R1's 25, for the same replay spend (76 vs 77 actions). The structure lane spent 36 actions on 6 deep replays; the shallow lane spent 40 actions on 15. The four workflows given up are shallow navigations, each of which reproduces no request. Elapsed time rose by 4.5 s. Deeper replays take longer, but all runs stayed under the 180 s limit.

## 5. Conclusion

With listener discovery and request-structure replay together (R2), every runtime-discovered behavior is both reached and independently reproduced: 3 of 3, with prerequisites and handler revisions, in every seed. Coverage is unchanged and there are no integrity regressions. The cost is fewer, more meaningful validations: 21 instead of 25 workflows, but 6 instead of 0 reproduced request structures.

`--replay-policy structure` remains opt-in for now. On Crawl Maze it is better on every functional measure except the raw count of validated navigations. The next step toward a default is a second real application with many request structures. The whiteboard result in `RUNTIME_GENERALIZATION_REPORT.md` covers that.
