# Agent 1: recovery of best results, WebExploitBench transfer, and one general fix

Branch `agent1-browser-mapper-20261028`. Reproductions ran on `f6f0178` (`agent1/` tree `5b3fe75`), WebExploitBench on a frozen worktree at `5dfee96` (same agent tree), and the fix comparison on `3e89299`. External model calls: 0. Cost: $0.

## 1. Historical results reproduce exactly on current code

Each historical configuration was rerun **verbatim**, copied from the historical `run.json` into [evaluation/recovery_historical_configs.json](evaluation/recovery_historical_configs.json). No evaluation overrides were added, and new config fields take their defaults. Scoring was post-run only:
- **Crawlground:** `results.json` from a fresh official container.
- **Crawl Maze:** the testbed's expected-path endpoint, via `experiments/score_crawlmaze_posthoc.py`.

| Configuration | Historical (code) | Reproduced, 3 trials | Actions | Elapsed |
|---|---|---|---:|---:|
| Crawlground serious: multidimensional policy, extended interactions, hybrid links, robust readiness, persistent, POST forms **on**; 600 s / 600 actions / 250 transitions | 39/59 (`2b8aa18` + uncommitted, later `decc0a2`) | **39 / 39 / 39** | 597–599 | 360–364 s |
| Crawl Maze integrated (arm R2 of `REPLAY_VALIDATION_REPORT.md`): above + typed spider, standards extraction, shared HTTP (1,000), listener revisit, structure replay, adaptive readiness, POST forms off; 180 s / 300 actions / 120 transitions | 61/91 (`fd7f3e8` + uncommitted, later `6c76b56`) | **61 / 61 / 61** | 298–299 | 170–171 s |

- No regression was found, so no regression fix was needed.
- The earlier Crawl Maze figures, 25/91 (180 s) and 37/91 (300 s), are superseded by 61/91. The current scorer reproduces both exactly from their stored graphs.
- The historical Crawlground configuration accepted 47 of its 54 restorations through the old shape tolerance (`robust_readiness` enables it). The restoration audit had shown that tolerance can accept a wrong record (`AGENT1_STATE_RESTORATION_EXPERIMENT.md` §1).

**New best: the integrated configuration, read-only, transfers to Crawlground.** Running the 61/91 Crawl Maze configuration at the Crawlground budget (600 s / 600 actions / 250 transitions / 2,000 HTTP), with POST forms **off**:
- **50 / 50 / 50 / 59** across three trials;
- 598–599 actions, 329 s;
- 12.0 actions per marker, against 15.3 for the historical 39/59 configuration, which needed POST forms on.

Categories: buttons 2/2, dynamic content 9/10, forms 6/12, frames 4/4, JS events 13/14, links 7/7, navigation 8/9, other 1/1. This configuration was frozen for WebExploitBench ([evaluation/wxb_frozen_config.json](evaluation/wxb_frozen_config.json)) before any WebExploitBench run.

## 2. Miss audits (first causal failure)

### Crawlground: 9 misses of the 50/59 configuration (identical in all three trials)

| First causal failure | Markers |
|---|---|
| Correct safety refusal (POST form, POST forms off) | forms.02 |
| Test page never reached: link observed 17–23 times, budget spent first | forms.03, .05, .08, .09, .11; js-events.14 |
| Page reached, trigger not observable: WebSocket-delivered link (local WebSockets blocked under scope routing); `location.replace` redirect | dynamic-content.06, navigation.05 |

The binding constraint is the action budget. Restoration consumed **148 of 598 actions** (25%): 90 root reloads plus replayed link chains, mostly 4 clicks deep. Restoration failures were not the issue (1 failure), but 43 of the restorations were accepted through the unsafe shape tolerance.

The historical 39/59 configuration's 20 misses split as follows:
- 9 pages never reached, also for budget reasons;
- 4 reached but the follow-up after hover, focus, dropdown or tab was never seen. One cause is confirmed: "Tab 1/2/3" share one control signature, because digits are normalized out of labels, so only one tab was explored;
- the rest were scroll, noscript, closed shadow DOM, timed redirects and a bot-detection check.

Evading bot detection is out of scope.

### Crawl Maze: 30 misses of the 61/91 configuration

| Class | Count | Disposition |
|---|---:|---|
| Correct safety refusals: POST/PUT/DELETE handlers, `ping` and CSP report beacons, POST form actions, automatic POST | ~14 | kept; never substituted with GET |
| Client-side framework routes (Angular, Polymer, React) never referenced | 7 | not addressed (needs framework execution) |
| String or `data:` references, GET-form edge cases | 5–7 | not addressed |
| `robots.txt`, `sitemap.xml` never consulted | 2 | **addressed** by bounded well-known discovery (§3) |

## 3. The one general fix: cost-aware, safe restoration

Implemented in `3e89299`, all opt-in:
- **`restoration_shortcut="direct_url"`.** A state reached only through plain same-origin GET links is restored with one navigation to its exact URL, instead of a root reload plus the replayed chain. Such a path has no handler revision, listener provenance, inputs or form fields, and no step ever seen writing or changing state. The arrival must reproduce the saved group or pass the restoration contract; otherwise path replay runs as before. Record identity is the exact URL.
- **`restoration_policy="contract"`** replaces the unsafe shape tolerance with the action starting-state contract.
- **`well_known_discovery`** (the step-2 discovery improvement): `/robots.txt` and `/sitemap.xml` are fetched once, within the same scope and budgets, and robots `Allow`/`Disallow` literal paths become references.

Tests: 9 new (eligibility, write and state-change exclusion, scope, redaction, fallback, robots parsing, seeding). The full suite passed: 425.

### Matched comparison (3 trials per arm; medians; identical budgets and settings except the fix fields)

[evaluation/results/recovery_fix_comparison.json](evaluation/results/recovery_fix_comparison.json).

| Measure | Crawl Maze baseline | Crawl Maze fix | Crawlground baseline | Crawlground fix |
|---|---:|---:|---:|---:|
| Reference markers | 61/91 (×3) | **63/91** (×3) | 50/59 (×3) | **54/59** (×3) |
| Browser actions | 299 | 297 | 598 | 599 |
| Capabilities observed or better | 96 | 111 | 107 | 110 |
| **Capabilities reproduced** | 20 | **33** | **23** | 16 |
| Replay-validated workflows | 20 | **33** | **24** | 17 |
| Request structures verified | 6 | 6 | 8 | 5 |
| Restoration actions / root reloads | 74 / 68 | **50 / 40** | 148 / 90 | 189 / 103 |
| Old shape-tolerance acceptances | 0 | 0 | 43 | **0** |
| Contract refusals (reason) | — | 0 | — | 23 (`target_context_changed`) |
| Contract overhead | — | 0.7 s | — | 8.4 s |
| Reproduced capabilities per 100 actions | 6.7 | **11.1** | **3.8** | 2.7 |

**Crawl Maze: a functionality-per-action gain.**
- +2 markers.
- Reproduced capabilities +65% (20 → 33) at the same action count.
- Direct-URL restoration cut restoration actions by a third and root reloads by 41%, and the freed budget went to replay.

**Crawlground: more reach, less reproduction.**
- +4 markers, all pages the baseline never reached (forms.05, .09, .11; js-events.14). None lost.
- The gain came from the contract, not the shortcut:
  - the shortcut fired 8 times and saved 3 actions;
  - the contract refused 23 restorations to `/results` rows that had changed because their test was already hit;
  - the old tolerance had accepted those and re-explored finished tests.
- Each refusal is paid for after the restoration, so restoration rose to 189 actions and replay validation fell (24 → 17 workflows, 23 → 16 reproduced capabilities).
- The 43 unsafe shape-tolerance acceptances are gone.

**Against the stated goal (executed and reproduced functionality per action), the verdict is mixed:**
- clearly positive on Crawl Maze;
- negative on Crawlground's reproduced functionality, despite more reach and safer restoration.

The Crawlground cost has an evident next step that was not implemented in this bounded milestone: decide `target_context_changed` *before* paying for the restoration, by comparing the live or last-known target row to the saved one.

**Integrity.** Crawl Maze fix trial 3 and all three Crawlground fix trials spanned host sleep (lid closed, on battery). The agent's budgets use monotonic time, and the marker counts come from the testbeds' own scorers, so outcomes are valid. Their wall-time and elapsed figures are excluded from cost comparisons (`host_sleep_affected` in each `trial.json`).

### Development-app transfer check (1 trial per arm, integrated 180 s configuration)

[evaluation/results/recovery_fix_dev_regression.json](evaluation/results/recovery_fix_dev_regression.json).

| Fixture | Baseline | Fix |
|---|---|---|
| replay_lab (annotations) | recall 0.96; 30 capabilities, 26 reproduced; 126 actions | identical |
| heldout_shop (surface truth) | 11 capabilities, 11 reproduced; 185 actions | identical |
| volatile_lab (server ledger) | 6/14 functions; 13 capabilities, 11 reproduced; 237 actions | 6/14 functions; 16 capabilities, 11 reproduced; 243 actions |

- No regression on any fixture.
- volatile_lab shows a different limit in persistent mode. About 100 of the 120 transitions went to `/clock`: its live clock changes the page's state identity on every observation, so the same buttons reappear as "new" states, and `/board` was never reached. Only 2 restorations were needed in either arm, so the fix had nothing to act on.
- Volatile text also inflates state identity under persistent exploration. That is a state-abstraction problem, not restoration, and is left for later.
- The first attempt at this check failed in the harness: a duplicate `context_label` keyword meant no agent started. The failure record was kept, the harness fixed, and the check rerun.

## 4. WebExploitBench (five public targets, one trial each, frozen configuration)

All five runs:
- loaded the frozen worktree's agent (`agent1_module` recorded per run);
- passed reset-integrity checks (teardown exit 0, mount profile matched the frozen profile);
- were restricted to loopback, with no origin aliases, no credentials and no model calls.

| Target | Actions | Time | Page routes / UI states | Request endpoints | Spider resources | Transitions executed / with app requests | Capabilities: observed+ / reproduced / verified | Stop reason |
|---|---:|---:|---|---:|---:|---|---|---|
| PrestaShop | 28 | 17 s | 1 / 1 | 0 | 0 | 16 / 0 | 0 / 0 / 0 | frontier empty: 64 of 101 first-page controls link to the configured non-loopback host (scope refusals) |
| ComfyUI | 29 | 40 s | 1 / 6 | 3 | 44 | 24 / 14 | 4 / 1 / 0 | **HTTP budget (2,000) exhausted** at 40 s |
| SiyuCMS | 31 | 70 s | 6 / 14 | 114 | 164 | 21 / 0 | 18 / 2 / 0 | **HTTP budget exhausted** at 70 s |
| JetLinks | 2 | 2 s | 1 / 2 | 0 | 0 | 0 / 0 | 0 / 0 / 0 | root URL returns 404; nothing reachable from the start page |
| White-Jotter | 595 | 511 s | 6 / 60 | 22 | 14 | 248 / 11 | 172 / 10 / 0 | action budget |

- **Pages and endpoints discovered** and **functions executed or reproduced** are the agent's own evidence only. None is a coverage percentage: without independent ground truth, the share of each application captured cannot be established.
- **Vulnerable-function reachability: NOT MEASURABLE.** Reading the benchmark's officially supplied challenge metadata for a post-run evaluator was denied by this session's permission policy. No location ground truth was accessed, and none was guessed.
- **Budget finding:** on two of five real applications, the HTTP budget sized for the testbeds ran out within about a minute, so actions and time went unused. That is input for the scaling experiment.

### Safety finding: read-only was claimed but not enforced

On White-Jotter, with POST forms disabled, the agent issued `POST /api/register` twice (HTTP 200, two accounts created) and `POST /api/login` once:
- The read-only gate checked only the HTML form's `method` attribute.
- These forms are intercepted by script, which sends the POST itself.

The effect was confined to the disposable container, which was torn down and verified. Values were the agent's dummy fills. This is a **policy-enforcement bug**, fixed in §5.

## 5. Exploration permissions vs vulnerability conclusions

Implemented in `12e0a7e`. The full suite passes: 432 tests.

The design keeps exploration permission separate from vulnerability conclusion. Agent 1 may exercise functionality the operator has authorized. It never concludes anything about security.

**Write policy** ([agent1/write_policy.py](agent1/write_policy.py)), enforced where requests leave the browser:

| Mode | When | Behaviour |
|---|---|---|
| `read_only` | `allow_post_forms=False` (the default) | every non-GET/HEAD/OPTIONS browser request is aborted (`net::ERR_ACCESS_DENIED`) and logged, whether it comes from a form or from script |
| `disposable` | `write_policy="disposable"` + `allow_post_forms=True` + an `environment_attestation` set by the harness **only after reset-integrity verification** | writes allowed up to `max_write_requests` (50) and logged; `DELETE` and destructive-looking routes (delete, drop, wipe, purge, reset, ...) stay blocked unless `allow_destructive` |
| `legacy_post_forms` | `allow_post_forms=True` alone | the historical un-gated behaviour, kept only so earlier configurations reproduce exactly |

Two existing protections are unchanged:
- the dangerous-label filter on controls;
- the rule that state-changing workflows are never replayed.

**Capability security evidence** ([agent1/security_evidence.py](agent1/security_evidence.py)) is written per run as `capability_evidence.json` by the harness. It is derived from the ACG export, and the frozen `acg/1` contract and the language-independent model package are unchanged. Each record has:
- trigger, network effect (method, route shape, parameter names) and response;
- `state_change`: `possible_confirm_separately`, `blocked_by_policy` or `none_observed`;
- heuristic `security_relevance`, labelled as a keyword match;
- `vulnerability_status: not_assessed`, always.

**White-Jotter under each mode** (frozen configuration otherwise; the read-only and disposable runs both spanned host sleep):

| Mode | Writes | Registration capability record |
|---|---|---|
| before the fix (`5dfee96`) | `POST /api/register` ×2 and `POST /api/login` sent with POST forms "off" | `possible_confirm_separately`, but under a policy that claimed read-only |
| `read_only` (`12e0a7e`) | both blocked before reaching the server; 0 sent | `POST /api/register` with params `email, name, password, phone, username`; `blocked_by_policy`; relevance account lifecycle + authentication; `not_assessed` |
| `disposable`, attested `disposable:targetctl-reset-verified:white-jotter` | 3 allowed and logged (register ×2, login ×1); 0 destructive; reset verified after teardown | `POST /api/register` → 200; `possible_confirm_separately`; account lifecycle + authentication; `not_assessed` |

So in disposable mode the registration capability is exercised and recorded as the target record: trigger, `POST /api/register`, HTTP 200, "possible account creation, confirm separately", authentication and account lifecycle, not assessed. In read-only mode the same capability is still mapped, marked as blocked by policy rather than dropped.

The agent did not go on to use the new account to explore authenticated areas. That workflow (register → log in → explore, in disposable mode only) is a natural next step that was not attempted here.

**Cost of enforcement on the testbeds** (1 trial each, `12e0a7e`, read-only):

| Testbed | Before (reproduced) | Enforced read-only | Writes blocked |
|---|---|---|---|
| Crawl Maze integrated 180 s | 61/91 | **61/91** | 5: four script POSTs and one PUT to `/test/javascript/interactive/*`, none of which ever scored |
| Crawlground integrated 600 s | 50/59 | **49/59** | 1: `POST /score/forms/12-xhr-post` |

- `forms.12-xhr-post` is a marker whose trigger *is* a script POST. The 50/59 included it only through the enforcement gap. The honest read-only figure for this configuration is 49–50/59.
- Crawlground's other difference (`links.02` lost, `forms.09` gained) is ordinary run-to-run ordering in a single trial.

## 6. Costs

- $0 external spend.
- Reproductions: about 50 min of browser time.
- WebExploitBench: about 12 min of agent time plus setup.
- Host sleep (lid closed, on battery) interrupted the fix comparison; affected trials are flagged and kept out of cost comparisons.

## 7. Conclusions and remaining gaps

1. **The best historical results reproduce exactly** (39/59, 61/91), and the read-only integrated configuration is a new reproducible best on Crawlground: 50/59, or 49/59 under enforced read-only.
2. **The one general fix is a net gain on Crawl Maze only.**
   - Crawl Maze: +2 markers and +65% reproduced capabilities at equal actions.
   - Crawlground: +4 markers, but 23 → 16 reproduced capabilities.
   - Its safety contribution (no reliance on the wrong-record-prone shape tolerance) holds on both.
   - Direct-URL restoration, the contract and well-known discovery all stay **opt-in**.
   - Next step: refuse changed-context restorations *before* paying for them.
3. **WebExploitBench transfer is limited by scope configuration and budgets, not by the restoration fix.**
   - Two targets exhausted a testbed-sized HTTP budget in about a minute.
   - PrestaShop's links point to a non-loopback host.
   - JetLinks' root returns 404.
   - Vulnerable-function reachability is NOT MEASURABLE until the evaluator is permitted to read the official location ground truth.
4. **Read-only is now enforced.** Disposable, attested environments can exercise state-changing functionality with logging, a cap and destructive blocking. Each capability carries security evidence with vulnerability status left to a downstream assessor.
5. **Open gaps:**
   - state-identity inflation from volatile text under persistent exploration (volatile_lab `/clock`);
   - tab and step labels collapsing to one control signature;
   - WebSocket-delivered content under the scope router;
   - an authenticated workflow (register → log in → explore) in disposable mode.

## 8. Deviations

- **D1.** The first attempt at the development-app transfer check failed in the harness (duplicate `context_label`); no agent started. The record is kept, the harness was fixed, and the check was rerun.
- **D2.** Host sleep (lid closed, on battery) affected:
  - Crawl Maze fix trial 3;
  - all three Crawlground fix trials;
  - both White-Jotter policy runs.

  Outcomes stand; timing from these trials is excluded.
- **D3.** Reading WebExploitBench `challenge.json` and `vulnerability/` for the post-run evaluator was denied by the session's permission policy. It was not worked around.
- **D4.** Three existing tests asserted the read-only gap (script POSTs reaching the server with POST forms off). They were updated to the enforced behaviour, each with a comment.
