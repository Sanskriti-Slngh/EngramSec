# Agent 1 perception ablation: report

Frozen agent `a9802e3` (`agent1/` tree `320a1f8`, unchanged). Preregistration: [AGENT1_PERCEPTION_ABLATION_PREREGISTRATION.md](AGENT1_PERCEPTION_ABLATION_PREREGISTRATION.md) (`34b66fc`). Trial-level aggregates: [evaluation/results/perception_ablation_scored.json](evaluation/results/perception_ablation_scored.json). Harness: [evaluation/perception_ablation.py](evaluation/perception_ablation.py). Contract tests: [tests/test_perception_ablation.py](tests/test_perception_ablation.py).

## 1. Answer

**Yes, for the functionality that perception actually blocks.** The two mechanisms already built into Agent 1 recover all of it on the annotated labs, up to the ceilings set by the fixed safety and scope rules:
- js_heavy_lab recall goes from 0.21 to **0.64** with readiness. The ceiling is 0.643.
- replay_lab recall goes from 0.68 to **0.96** with listener revisit. The ceiling is 0.96.
- transfer_library executes **7 of 9** functions instead of 3.

Every annotated capability still missed in the best arm is a legitimate refusal: scope (a `localhost` alias), the POST gate, or the dangerous-label filter.

**But perception is not the whole limitation, and the general-purpose configuration does not pass all preregistered gates.**
1. **No arm meets every gate.** Arm D (both mechanisms) meets both recall gates, replay_lab precision, and the safety gates. On js_heavy_lab it fails precision (0.69 < 0.75) and cost (3.2× time and 2.4× actions per matched capability).
2. **Readiness has a high, unconditional cost.** It waits on every page: stateful_lab runtime goes from 7 s to 27 s for no gain.
3. **Readiness lowers js_heavy_lab precision through a modeling defect.** One annotated navigation capability is split into four ACG capabilities.
4. **Perception cannot help where restoration blocks the path.** stateful_lab is unchanged in every arm. On Crawlground, listener observation finds no new controls on the pages it reaches, while the test pages behind the volatile results page stay unreachable. The one trial whose restoration happened to succeed reached 37 test pages instead of 4–6.

The limitation is perception **plus** restoration **plus** capability modeling, in that order of what was fixable here.

## 2. Arms and configuration

| Arm | Overrides on the comprehensive production configuration |
|---|---|
| A | none: legacy `coverage` policy; fresh mode; state-aware; `allow_post_forms=False`; shallow replay; 30% replay reserve; `settle_ms=350`; `robust_readiness=False`; `runtime_listener_observation=off`; `interaction_profile=basic`; no origin aliases; anonymous; 180 s / 500 actions / 100 transitions; no model calls; `acg_evidence` and `action_ledger` on |
| B | `robust_readiness=True` (bounded 2.5 s readiness replaces the fixed 350 ms settle) |
| C | `runtime_listener_observation="revisit"` (also installs the HTTP scope router; declared non-equivalence) |
| D | B + C |

- **Configuration check:** each trial stores the configuration it actually applied (`applied_config`), and all 60 matched their arm.
- **Order and repeats:** environments ran one at a time; arms rotated per trial (A B C D, then B C D A, then C D A B); 3 scored trials per arm and environment.
- **Diagnostics:** 1 diagnostic trial per arm and environment was used only to check the instrumentation. **None found any defect** (no metric errors, configurations applied as intended), so no amendment was made.

## 3. Phase 1 audit

What each mechanism can and cannot observe is in preregistration §3. The main points, confirmed by the runs:

- **Readiness** recovers controls that are disabled, busy or inserted within about 2.5 s of a navigation or action. It runs on *every* observation:
  - ≈ 0.3 s per page with visible controls;
  - ≈ 1.6–1.7 s per page on script pages without main controls (stateful_lab).
- **Listener observation:**
  - **Recovers:** direct click listeners on non-semantic elements, including elements created by an action and elements in open shadow roots, plus handler replacements on the same element (revisit mode).
  - **Cannot recover, by design:** delegated handlers, closed shadow roots, and listeners on pages that are never reached.
  - **Cost:** 0.07–1.2 s per run, at 86–1,778 DevTools calls.
- **Safety and scope.** Listener-derived controls pass the same dangerous-label filter (contract-tested). In the runs, the filter refused "Delete all records" on replay_lab in arms C and D (2 more dangerous-control skips than in A or B).
  - The cross-origin target check, the protected-input check and the POST gate cannot apply, because the target is unknown before the click. Scope is enforced by the request router that C and D install.
  - 0 completed out-of-scope requests and 0 destructive hits in any arm.
- **Defects found, none corrected (no agent code changed):**
  1. Enabling listener observation silently installs the HTTP scope router, so C and D also change request delivery and scope strictness.
  2. The router's block counter is not exported without an HTTP budget. The harness measures scope from the agent's own network records instead.
  3. Under readiness, the ACG splits one navigation capability by source state (§6). This is a modeling issue, not a perception defect.

## 4. Results (3 scored trials per cell; values identical across trials unless a range is shown)

Costs use the driver's **monotonic** runtime, which on macOS excludes host sleep (deviation P1, §8).

### 4.1 Annotated labs

| Env | Arm | Recall | Precision | Matched | Capabilities | Actions | Runtime (s) | s per matched | actions per matched |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| stateful_lab | A | 0.29 | 1.00 | 2 | 2 | 16 | 7.4 | 3.7 | 8.0 |
| | B | 0.29 | 1.00 | 2 | 2 | 16 | 27.3 | 13.7 (3.7×) | 8.0 |
| | C | 0.29 | 1.00 | 2 | 2 | 16 | 7.2 | 3.6 | 8.0 |
| | D | 0.29 | 1.00 | 2 | 2 | 16 | 27.4 | 13.7 (3.7×) | 8.0 |
| js_heavy_lab | A | 0.21 | 1.00 | 3 | 3 | 31 | 15.9 | 5.3 | 10.3 |
| | B | **0.64** | 0.69 | 9 | 13 | 220 | 152.5 | 16.9 (3.2×) | 24.4 (2.4×) |
| | C | 0.21 | 1.00 | 3 | 3 | 31 | 16.2 | 5.4 (1.0×) | 10.3 (1.0×) |
| | D | **0.64** | 0.69 | 9 | 13 | 220 | 153.5 | 17.1 (3.2×) | 24.4 (2.4×) |
| replay_lab | A | 0.68 | 0.77 | 17 | 22 | 172 | 84.1 | 4.9 | 10.1 |
| | B | 0.68 | 0.77 | 17 | 22 | 172 | 85.8 | 5.0 (1.0×) | 10.1 (1.0×) |
| | C | **0.96** | 0.80 | 24 | 30 | 229–230 | 114.2 | 4.8 (0.96×) | 9.6 (0.95×) |
| | D | **0.96** | 0.80 | 24 | 30 | 230 | 122.2 | 5.1 (1.03×) | 9.6 (0.95×) |

### 4.2 Perception and failure measures (annotated labs; medians)

| Env | Arm | Listener controls observed / executed / never executed | Listener actions ok / no effect | Revision actions | Controls gained during readiness | Readiness wait (s) | Listener cost (s) | Restoration failures | Action failures |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| stateful_lab | A–D | 0 / 0 / 0 | 0 / 0 | 0 | 0 | 0 (A, C) / 13.4 (B, D) | ≤ 0.1 | **10** (7 unsafe refused + 3 mismatch), all arms | 10 |
| js_heavy_lab | A | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| | B, D | 0 | 0 | 0 | **60** | 46.7–46.8 | 0 / 0.7 | 0 | 0 |
| | C | 0 | 0 | 0 | 0 | 0 | 0.13 | 0 | 0 |
| replay_lab | A, B | 0 | 0 | 0 | 0 | 0 / 43.1 | 0 | 1 | 1 |
| | C, D | **6 / 5 / 1** | 6 / 1 | **1** | 0 | 0 / 57.0 | 0.8–0.9 | 1 | 1–2 |

The listener-derived control never executed on replay_lab is "Delete all records", refused by the dangerous-label filter.

### 4.3 transfer_library (author evaluator; 9 functions)

| Arm | Functions executed | Replay-validated | Documents 2xx | Static 2xx | Capabilities | Listener actions ok | Readiness wait (s) |
|---|---|---|---|---|---:|---:|---:|
| A | 3/9 (F1–F3) | 1/9 | 54/107 | 37/64 | 27 | 0 | 0 |
| B | 3/9 | 1/9 | 54/107 | 37/64 | 24–27 (the 24 is the sleep-affected trial 2) | 0 | 71 |
| C | **7/9** (+ F4 revision, F5 created `<div>`, F6 `<div>` at load, F7 open shadow root) | 2–3/9 | 51/107 | 34/64 | 32 | 5 | 0 |
| D | **7/9** | 1–2/9 | 50/107 | 33/64 | 32 | 5 | 73 |

- **F9 (delegated row handler):** not recovered, as predicted; delegation hosts are never candidates.
- **F8 (frame listener):** not recovered, because its host page `/desk/frame` was never reached within the budget, not because of frame perception.
- **Fixed-budget trade-off:** listener actions displace about 3–4 document and static fetches.

### 4.4 Crawlground (testbed's own scoring, 59 markers)

| Arm | Markers per trial | Capabilities per trial | Actions per trial | Restoration failures per trial | Test pages reached | js-event markers | Readiness wait (s) | Sleep-affected trials |
|---|---|---|---|---|---|---|---:|---|
| A | 3, 4, 3 | 20, 22, 20 | 290, 332, 305 | 59, 59, 59 (all from `/results`) | 4, 5, 4 | 0/14 | 0 | t0 |
| B | 4, 4, 4 | 23, 23, 23 | 341, 341, 336 | 59, 59, 58 | 6, 6, 6 | 0/14 | 54 | t0 |
| C | 3, 4, 3 | 21, 22, 20 | 311, 327, 300 | 59, 59, 59 | 5, 5, 4 | 0/14 | 0 | none |
| D | 4, 4, **5** | 23, 23, **61** | 341, 341, 315 | 59, 59, **0** | 6, 6, **37** | 0, 0, **1**/14 | 54–58 | none |

**Readiness (B):** about +1 marker and +2 capabilities over A in every trial; 2 more test pages reached.

**Listener revisit (C):** indistinguishable from A. On the pages it reached, all 41–43 listener-bearing elements were already semantic snapshot controls (skip reason `represented_by_snapshot`), so there were 0 new candidates.

**Variability.** Crawlground varies across trials even without host sleep (A: 3–4 markers, 20–22 capabilities), unlike the in-process labs. D trial 2 is an outlier, analysed in §7. With n = 3 and that variability, the B-vs-A difference (+1 marker) is suggestive, not established.

## 5. Separating the effects

**Readiness (B − A):**
- **js_heavy_lab:** +6 matched (`open_workflow`, `continue_setup`, `open_workspace`, `workspace_detail`, `load_late_reports`, `open_reports`). 60 controls became enabled or visible during readiness waits, and `enter_member_mode` became visible and was then correctly refused as a POST form.
- **No recall change elsewhere** among the annotated labs and transfer_library.

**Listener revisit (C − A):**
- **replay_lab:** +7 matched.
  - 4 reached only via listener-derived controls: `load_details`, `save_item`, `wizard_continue`, `wizard_finish`.
  - 1 via a handler-revision action: `check_loans_second`.
  - 2 whose button was already executed in A, but whose effect is now visible because the revealed listener element is extracted: `reveal_details`, `wizard_begin`.
- **transfer_library:** +4 functions.
- **js_heavy_lab:** no change, because its missing controls are semantic buttons hidden by timing, not by listeners.

**Interaction (D vs B and C):** none. D equals B on js_heavy_lab and C on replay_lab and transfer_library. Its only differences are cost and two extra unmatched capabilities on js_heavy_lab, inherited from B.

**No improvement is attributed to listeners that readiness explains.** Readiness alone recovers nothing on replay_lab or transfer_library; listeners alone recover nothing on js_heavy_lab. The attributions are disjoint.

**Explored, not accumulated.** Newly visible functionality is executed:
- js_heavy_lab B: 10 of 13 distinct controls executed. The 3 not executed are the POST member form (refused) and two cross-origin links (refused).
- replay_lab C and D: 5 of 6 listener controls executed; the sixth is the dangerous "Delete all records" (refused).
- transfer_library C and D: 1 listener control advertised but not executed.

## 6. Why the gates fail where they do

**js_heavy_lab precision (0.69).** With readiness, the ACG builds 13 capabilities, of which 9 match.
- Most of the unmatched ones are **splits of a single navigation**. The home link "JS Lab" becomes several ACG capabilities, because after hydration the same navigation records the `/api/bootstrap` request with different component-state effects depending on the source page. "Open workflow" is also duplicated once.
- No unmatched capability is spurious functionality.
- Earliest cause: capability modeling (category 8), surfaced by readiness rather than caused by a perception error.

**js_heavy_lab cost (3.2× time, 2.4× actions per matched capability).**
- Arm A's cost per matched capability is artificially low: it finds 3 trivial navigation capabilities, then empties its frontier at 12 s.
- With readiness the agent explores the hydrated application for the full exploration window (220 actions). 31% of the runtime (46.7 s) is readiness waiting.
- The gate fails as specified. In actions per matched capability (2.4×) it fails by a smaller margin.

**stateful_lab (no change in any arm).** The misses are verified restoration failures. A state-changing GET mutates the start page, so 7 restorations are refused as unsafe and 3 fail on state mismatch, identically in all arms. **Perception improved nothing because nothing was hidden from perception.** Readiness only added 20 s of waiting.

## 7. Where restoration, not perception, blocks exploration

**stateful_lab (verified).** Restoration failures are identical in all four arms: 7 unsafe restorations refused plus 3 group mismatches, after the state-changing GET. No control is hidden from perception; arms B, C and D add only cost.

**Crawlground (verified, with one natural experiment).**
- In 11 of 12 trials, 58–59 actions fail with "saved return path restored X, expected Y", all launched from `/results`. That page shows a live score ("0 / 59 controls reached"), so the saved state can no longer be restored after the first scored visit.
- In those trials the agent reaches 4–6 of 59 test pages. Listener observation therefore never sees the JavaScript-event test pages, where its candidates would be: across all observations of the visited pages, 41–43 listener nodes were found and all were already snapshot controls.
- **D trial 2 is the only trial with 0 restoration failures.** Both runs take the same first 7 actions; at the 8th (`window.open()` from `/results`) trial 1's restoration fails and trial 2's succeeds. Trial 2 then reaches **37** test pages, sees 18 non-click listener nodes and 1 listener candidate, gains 4 controls during readiness, finds **61** capabilities and hits the first JavaScript-event marker (1/14).
- Why the volatile counter matched in that one trial is a hypothesis: most likely a timing race between the score update and the re-observation.
- What the trace does establish: on this testbed, restoration, not perception, decides whether newly perceivable functionality is ever reached. Even with 37 test pages reached, markers rose only from 4 to 5. Most Crawlground markers need interactions beyond reaching the page, so the remaining gap is not perception alone either.

**transfer_library F8 (verified).** The frame-listener function's host page `/desk/frame` was never reached in any arm within the exploration window. That is a reach and budget limit, not frame perception.

## 8. Deviations

| ID | What | Effect |
|---|---|---|
| P1 | The host returned to battery power and slept during the scored phase (lid or power, outside the harness). 17 of 60 trials ran partly across sleep, flagged by the driver's wall-vs-monotonic gap. | Preregistration §8 named driver *wall* time for the cost gate. Wall time includes sleep, so cost uses the driver's **monotonic** runtime, which excludes it. Sleep-affected in-process trials reproduced their unaffected repeats exactly, except transfer_library B trial 2 (24 vs 27 capabilities). |
| P2 | At 4% battery, the driver was paused at a clean boundary: after Crawlground B trial 0 was recorded, during the next container setup, with no mapping started. It resumed automatically on AC power at 18:56. | The empty `crawlground/C/trial_0` directory was removed on resume. No mapping trial was rerun or lost. |
| P3 | Crawlground A trial 0 and B trial 0 were sleep-affected, and sleep *did* change Crawlground's result (A trial 0: 3 markers / 20 capabilities vs 4 / 22 unaffected). | Reported per trial; clean-trial medians are given alongside all-trial medians in §4.4. |

No agent code, arm setting, threshold or scorer was changed after any trial. Diagnostics found no instrumentation defect, so the comparison was frozen as preregistered.

## 9. Trade-offs

- **Readiness:** large gains on late-hydrating client-rendered applications. It costs 0.3–1.7 s on *every* observation, including server-rendered pages that gain nothing. It also exposes modeling splits that lower precision. It is a blunt instrument.
- **Listener revisit:** large gains on listener-driven widgets, at negligible cost (about 1 s per run). It keeps safety: listener-found destructive controls are refused. The costs are a stricter, router-mediated request path (a confound), a few displaced resource fetches under a fixed budget, and no help for delegated handlers or unreachable pages.
- **Neither** addresses restoration (stateful_lab, Crawlground) or the POST, scope and safety ceilings.

## 10. Recommendation

1. **Enable listener revisit (arm C) as the general-purpose perception default.** Its recall gains do not depend on readiness, its cost is negligible, and it adds no safety or scope violations in these trials. Before that, the router side effect should be made explicit and measured on its own. Changing defaults is outside this milestone and is not done here.
2. **Do not enable readiness globally in its current form.** It recovers hydration-blocked controls, but at an unconditional per-page cost and with precision loss through ACG splits. The next step is to make it conditional: wait only when the page signals initialization (busy state, all controls disabled, a rapidly changing control fingerprint), not on every observation. Separately, address the navigation split in the ACG.
3. **The binding constraint after perception is restoration.** stateful_lab and Crawlground show it directly. Per this milestone's scope, no restoration redesign or scheduler experiment was run.

These are development-stage results on fixtures the agent was developed against. They are not evidence of generalization.

## 11. Regression

Full regression suite after the ablation: **390 passed, 0 failed** (8 min 29 s). That is the comprehensive milestone's 384 plus the 6 ablation contract tests.

`git diff a9802e3 -- agent1` is empty: the evaluated agent is unchanged, and no implementation correction was needed or made.
