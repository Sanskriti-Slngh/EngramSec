# Agent 1 state-tolerant restoration: preregistration

Status: **frozen before any diagnostic or scored comparison.** Evaluated agent: implementation commit `7c05be8`, `agent1/` tree `5b3fe75`; the harness refuses any other tree. Regression suite before this commit: 416 passed. Before this commit the contract had been exercised only by:
- unit and browser contract tests;
- two 60-second development smoke runs on the new `volatile_lab` fixture (one per policy), to check the wiring.

No comparative trial on stateful_lab, replay_lab, js_heavy_lab or Crawlground has run. Diagnostic trials (one per arm and environment) may only reveal instrumentation defects; any correction they force is committed as a labelled amendment before the scored trials. Changes after the first scored trial are reported as deviations.

## 1. Question

Can Agent 1 reliably execute a pending interaction after returning to a browser state whose irrelevant content has changed, while keeping strict record, session, prerequisite and safety guarantees?

The falsifiable form: an opt-in restoration contract (arm B) makes at least 80% of strictly rejected, oracle-safe volatile-state restorations executable, with **zero** incorrect-record restorations, unsafe write replays or scope changes, and no regression elsewhere (criteria in §7).

## 2. Step 1: established failure mechanism (development environments; from the perception ablation's scored arm C)

### 2.1 How restoration works today

**Fresh-mode restoration.** The agent replays the item's return path from the start URL. It then requires the restored page's *group signature* to equal the saved one.

**The group signature hashes:**
- the route pattern;
- grouped control shapes (link labels dropped, button labels instance-normalized);
- form shapes;
- session context and session markers (cookie and storage **key names**);
- a fingerprint of the main region's text.

That text is not digit-normalized, so any counter or clock changes the group.

### 2.2 Why the existing tolerance does not handle the failures

The existing tolerance is `_usable_return_screen`. It compares route, session, form shapes and grouped control shapes, and ignores text.
1. **Gate.** It runs only for search-related actions or when `robust_readiness=True`. Under the production defaults (perception arms A and C) it never runs.
2. **Where it was enabled (perception arms B and D), it still rejected the Crawlground failures** in 5 of 6 trials (58–59 per trial):
   - On every restored `/results` page, the snapshot's occlusion test drops one table link, "Link appears on scroll (IntersectionObserver)".
   - After the first scored hit, a timestamp column widens the table. The link then wraps onto two lines, and the centre of its bounding box falls on its own `<td>`. `elementFromPoint` returns that ancestor cell, and the extractor treats the link as covered.
   - The grouped control shapes therefore differ.
   - In perception D trial 2 the artefact did not occur (cause unverified; hypothesis: layout timing), and the tolerance accepted 38 restorations.
3. **It is unsafe as a general tolerance.**
   - It ignores URL query values and all text.
   - `record_instance` is `None` for query-identified records.
   - So it would accept `/records?id=2` in place of `/records?id=1` (contract test `test_existing_shape_tolerance_would_accept_the_query_borne_wrong_record`).
   - It also does not check that the target is unique, or that its handler is unchanged.

### 2.3 Failure inventory (per trial; all three trials identical in counts)

| Env | Failure | URL / route / session / forms | Controls | Content | Server state | Acting from it |
|---|---|---|---|---|---|---|
| Crawlground | 59 group mismatches, all on `/results` | identical; no record identity | one link dropped by the occlusion artefact (still in the DOM, not covered) | score summary, per-row mark, first-hit timestamp, hit count | **mutated by the agent's own test-page visits** (GET and POST), outside the target's row | safe for a link whose own row is unchanged; the link's request is fully specified by its `href` |
| stateful_lab | 3 group mismatches at `/` | identical | **a new record link** ("GET mutation") | the new record's name | irreproducible: `GET /counter` inserts a record | not equivalent: the affordance set changed |
| stateful_lab | 7 refused: return path contains an observed write (`Counter`, `Submit`) | n/a | n/a | n/a | — | refused by the write guard; progress needs an **isolated server reset**, which the agent does not have |
| replay_lab | 1 group mismatch at `/lab/claim` | identical | "Claim voucher" **removed** | "No vouchers left." | voucher consumed (irreproducible) | not equivalent |
| js_heavy_lab | 0 | — | — | — | — | — |

A matching label is never taken as equivalent state. In stateful_lab, "Beta" still links to `/records/2`, but the page's set of records changed, so that restoration stays refused.

## 3. Implementation contract (opt-in; production default unchanged)

**Configuration.**
- `RunConfig.restoration_policy`: `"strict"` (default, unchanged) or `"contract"`.
- `restoration_sample_interval_ms`: 300.

**Code.** The contract code is in [agent1/restoration.py](agent1/restoration.py). It is reached only where the strict group check has already failed after a restoration (`Explorer._restoration_contract`). The frontier, ranking, ACG, replay verifier and return-path write guard are unchanged. Under `"contract"`, each observation additionally records condensed region evidence in memory (text digests per text-bearing element, with container, identity and status flags, and positional probes of its controls). This evidence is never exported.

**Checks.** The contract accepts only if every check holds; otherwise it refuses with reasons (`RestorationRefused`, recorded per decision):
1. **Location, record and session:**
   - same exact URL (route, path instance and query values);
   - same session context and markers;
   - same form schemas, with the exact action URL;
   - a single frame only.
2. **Target:**
   - exactly the recorded control: kind, role, interaction, label, exact target, method, fields, component, frame and DOM position;
   - the same inline handler, listener handler locations and behavior revision;
   - present, safe and enabled;
   - no new same-signature or same-label control that the matcher could confuse with it.
3. **Affordances:** the same multiset of all controls, safe or not. Two exceptions:
   - A control missing from the snapshot counts as present only if a DOM probe finds it at its recorded position with the same label and target, shown, enabled, and not covered by an unrelated element. This is the occlusion artefact; an overlay or modal is not excused.
   - A control that appears or disappears while the restored page is passively re-observed, or that lives in a container whose text changes on its own, counts as volatile.
4. **Scoped text** must be unchanged:
   - the target's functional container (form, row, list item, article, section, …);
   - identity regions (title, h1–h3, breadcrumb, `aria-current`, hidden input values);
   - status regions (alert, status, `aria-live`, outcome classes).

   A container that changes on its own refuses the target.
5. **Other text:**
   - **Contextual tier** (buttons, script, listener-derived and form controls): every other difference must be *passively volatile*, meaning it changes on its own across up to three passive samples, 300 ms apart.
   - **Declarative tier** (a same-origin GET link with no inline or observed handler): stable differences outside the scopes in 4 are tolerated and counted (`outside_scope`).
6. Differences that cannot be localized (shadow DOM, text the region evidence does not see), or missing prior evidence, are refused.

Return-path writes (`UnsafeRestoration`) are checked before the contract and are not relaxed by it.

**Explicit assumption (the falsifiable core).** For a declarative link, the action's target and meaning are fixed by its exact `href`, the session and the page's identity regions. For any other action, meaning may depend on any page content, so only passively volatile differences are tolerated.

**Known limits, declared in advance:**
- Session equivalence uses key names, as in the strict policy. Two principals with the same key names and identical pages cannot be told apart by either policy.
- Region evidence covers the main document only; frames are refused.
- Volatility slower than the roughly 600 ms sampling window is refused, not tolerated.

## 4. Adversarial contract tests (passed before this commit)

[tests/test_restoration_contract.py](tests/test_restoration_contract.py), 21 tests:

| Case | Expected and observed |
|---|---|
| live clock, unchanged controls | contextual: refused on one sample (`needs_samples`), accepted after passive samples show the clock region changing; a clock that stops changing is refused |
| changing score counter | declarative link outside the counter: accepted (`outside_scope`); contextual button: refused; link whose own row changed: refused (`target_context_changed`) |
| carousel | action outside it: accepted (volatile region and controls); slide link: refused, because the explorer's matcher normalizes digits and offers "slide 2" for "slide 1" (`target_changed`) |
| two records, same controls | query id: `record_identity_changed`; same URL with a different heading or hidden id: `page_identity_changed`, for both tiers; record in the target's card: `target_context_changed` |
| two sessions, identical page | different markers or context: `session_changed` |
| changed handler or meaning | same route shape, different exact target: `target_changed`; inline handler, listener handler location or revision changed: refused |
| disabled after a prerequisite | `target_disabled` |
| GET that mutates server state | unflagged, adds a record link: `affordance_added`; flagged (`possible_state_change`) in the return path: `UnsafeRestoration` before the contract, no step executed |
| return path with an observed write | `UnsafeRestoration` before the contract |
| two same-label controls, different targets | `target_ambiguous`; swapped positions: `target_changed` |
| occlusion artefact / overlay | covered only by its own cell: present; covered by an unrelated element: `affordance_removed` |
| frames, missing evidence, unlocalized change | refused |

Browser tests check, on the fixture, that region evidence detects clock and carousel volatility and that the wrapped-link artefact is reproduced and resolved by the probe.

## 5. Arms, environments, state and order

| Arm | Overrides on the comprehensive primary configuration (`FROZEN` + `INSTRUMENTATION`) |
|---|---|
| A | `runtime_listener_observation="revisit"` (perception arm C, the recommended perception configuration) |
| B | A + `restoration_policy="contract"` |

**Shared settings:**
- legacy coverage policy; 180 s / 500 actions / 100 transitions;
- fresh mode; no POST forms; no origin aliases; anonymous; no model calls.
- Readiness stays off in both arms. `robust_readiness=True` also enables the old shape tolerance, which would confound restoration with perception.
- Contract test `test_arms_differ_only_in_restoration_policy...` asserts that the arms differ only in `restoration_policy`.

| Env | Reference |
|---|---|
| volatile_lab (new; [development_apps/volatile_lab.py](development_apps/volatile_lab.py)) | server-side ledger: 14 functions; desk annotations with the record requested |
| stateful_lab | annotations (7) |
| replay_lab | annotations (25) |
| js_heavy_lab | annotations (14) |
| Crawlground | testbed markers (59); test pages reached, reported separately from markers |

**State, order and timing:**
- In-process fixtures start in a fresh child process with state created from code. Crawlground starts as a fresh official container with the comprehensive evaluation's reset-integrity checks.
- One environment at a time. Arm order alternates per trial: A B, B A, A B.
- The driver measures monotonic and wall time. A gap above 5 s flags host sleep, and cost uses monotonic time.
- The harness refuses to run unless `agent1/` is clean and equal to the preregistered tree.

## 6. Measures (per trial; medians, min and max over 3)

**Restoration:**
- attempts and successes; failures by class (group mismatch, contract refusal by reason, unsafe-restoration refusal, missing return-path control, different record, absent control);
- contract evaluations, accepted by tier, tolerated differences by kind;
- evaluation and region-capture milliseconds.

**Oracle** (author-declared, independent of the contract code; [evaluation/restoration_ab.py](evaluation/restoration_ab.py) `oracle`). Every strict rejection is classified from the recorded saved and restored observations:
- arm A: each group mismatch;
- arm B: each contract evaluation.

The classes are `safe_volatile`, `unsafe:*` (different context, form changed, target unavailable, target row changed, wrong record, carousel target), `server_state_changed` (affordance set changed) and `unclassified`. Each environment's rule:
- volatile_lab: by route and action, comparing the target row and the current record.
- Crawlground `/results`: only scoreboard tokens may differ, and the target's row must be unchanged.
- Otherwise: an added or removed control means `server_state_changed`.

**Wrong context and wrong record:**
- accepted restorations whose recorded pair differs in URL, session or title (audit);
- volatile_lab annotations requested for a record other than the one shown on the page the action was planned from;
- accepted `unsafe:*`.

**Coverage:**
- capabilities;
- annotation recall and precision;
- Crawlground markers by category and test pages reached;
- volatile_lab functions executed;
- route patterns reached;
- reproduced and replay-validated workflows.

**Cost:** browser actions, agent elapsed time, and driver wall and monotonic time.

**Safety and scope:**
- state-changing requests (exploration and replay);
- non-GET requests replayed during restoration;
- destructive-endpoint hits;
- dangerous controls skipped;
- out-of-scope requests recorded and completed;
- known mutating GETs repeated (stateful_lab `/counter`).

## 7. Success criteria (development-stage only)

**Hard requirements.** Arm B fails outright if any is violated, whatever its coverage:
- H1: 0 accepted restorations classified `unsafe:*`, 0 wrong-record annotations and 0 audit failures;
- H2: 0 non-GET requests replayed during restoration, and state-changing requests in replay not above A;
- H3: out-of-scope requests completed not above A, in every environment, and 0 destructive-endpoint hits.

**Then:**
- S1: pooled over environments and trials, at least 80% of B's `safe_volatile` strict rejections are accepted.
- S2: Crawlground restoration failures per trial: B's median is at most 50% of A's.
- S3: more functional areas within the same budget:
  - Crawlground test pages reached, median B > A, with markers median B ≥ A;
  - volatile_lab functions executed, median B > A.
- S4: no regression on each annotated lab:
  - median recall B ≥ A − 1/n (n annotated capabilities);
  - median precision B ≥ A − 0.05.
- S5: acceptable cost:
  - contract overhead (evaluation plus region capture) is at most 10% of agent elapsed time;
  - browser actions and monotonic time per unit of reference coverage (matched capability, marker or function) are at most 1.5× A, wherever both are defined.

**Production default.** This milestone never changes it. The report recommends a default change only if H1–H3 and S1–S5 all hold.

**Predictions (recorded before running):**
- volatile_lab: B accepts the clock buttons (contextual), the board task links (declarative) and the non-carousel showcase buttons. It never accepts a desk restoration after the current record changed.
- Crawlground: B accepts most `/results` link restorations; the artefact is resolved by the probe. Rows already hit are refused.
- stateful_lab: unchanged. The 7 write-guard refusals remain, and the root mismatches are refused as `affordance_added`. Progress needs an isolated reset.
- replay_lab: the claim mismatch is refused (`affordance_removed`). js_heavy_lab: no change.

## 8. Integrity

- Agent code changes are limited to the opt-in contract. The default (`strict`) is unchanged and contract-tested.
- No WebExploitBench runs, traces, metadata or target-specific fixes. ComfyUI outcomes are not used. No paid models.
- Every trial is preserved, including failures and negative results. Three repeats support no significance claim.
- Results go to `evaluation/results/restoration_ab_{phase}.json`. Raw runs are git-ignored.
