# State-aware exploration: whiteboard evaluation

## Diagnosis at 6c76b56

The saved W2final trace has 13 observed transitions and 9 additional failed attempts. Two observed actions submitted the same `+ Create canvas` form; the remaining creations came from restoring paths containing that same submission. React intercepted a form without an HTML method and issued `POST /api/canvases`. The browser action's request was attributed to the transition, but the restoration loop did not consult earlier action behavior. The replay scheduler excluded all 13 observed workflows because an exact path prefix issued a non-GET request. That was a conservative request-method rule, not evidence that all 13 workflows actually changed server state.

The original state-group audit flagged two groups. Independent inspection of their raw observations found 5 and 2 concrete canvas paths respectively. These groups were useful page-shape abstractions, but their shared shortest return paths could also return to the wrong canvas. The group audit alone is not a behavioral-equivalence test.

## Changes

Action records now retain a semantic identity, observed request methods, whether a write-capable request was observed, whether visible state changed, and explicit replay uncertainty. Identity includes the source route, record and session context, control location or link destination, form structure, interaction, frame, and observed handler revision. A GET navigation that returns to the starting page with changed content is treated as ambiguous. Ordinary search or XHR result changes alone are not classified as mutations. Neither a POST nor a visible UI change is declared a confirmed database mutation. The explorer defers an untested non-search form when other controls are available, suppresses a previously observed risky action in the same context, and refuses to use that action as a restoration prerequisite. A blocked restoration is `not_tested`, with its reason retained. The existing dangerous-action filter remains in place.

All replay policies now exclude recorded non-GET workflows, including writes observed during restoration, even if `allow_post_forms` is set. There is no verified reset adapter in Agent 1 yet: stateful replay remains **unavailable**, including on the resettable fixture. This is intentional; an operator resetting a database between experiments is not an attestation that each replay has its own correctly restored server and browser state.

Important limits: browser observations cannot reliably prove a request is read-only, detect every server mutation, or identify a late/background request's causal action. An invisible mutation through GET, a WebSocket, a delayed request, or a handler change that is not observed may escape this guard. Passive resource fetching can also execute a state-changing GET. Use the mapper only against targets for which those risks are authorized. The classification is a conservative aid, not a guarantee against side effects.

## Controlled whiteboard result

Each arm used the same 150-second limit, 300 browser actions, 1,000 shared HTTP requests, the same two named seed canvases and authenticated role, a fresh disposable database, one browser worker, no model, and the same listener/structure replay configuration. Each reset creates a fresh account and fresh record IDs; the identities are not literally identical across runs. A is the actual archived `6c76b56` code. B uses state-aware exploration with the record graph disabled; C adds record and template graph references. B and C use the same exploration policy. The baseline and C values below are independently reset runs; B is one run. The baseline is from the earlier matched run; the treatment values are from the final repeated run after narrowing the GET rule. Raw authenticated artifacts remain ignored locally.

| Measure | A baseline | B state-aware | C state + record graph, 3 repeats |
|---|---:|---:|---:|
| Seed canvases / new canvases | 2 / 9 | 2 / 1 | 2 / 1 each |
| Seed record paths observed | 0 / 2 | 2 / 2 | 2 / 2 each |
| Observed transitions | 13 | 43 | 43 / 43 / 41 |
| Fresh-context replays validated / attempted | 0 / 0 | 3 / 7 | 3 / 7 each |
| Remaining untested observed transitions | 13 | 36 | 36 / 36 / 34 |
| Suppressed repeat decisions | n/a | 18 | 14 / 17 / 11 |
| Unsafe restorations refused | n/a | 6 | 8 / 8 / 10 |
| Write-capable final actions observed | 4 | 4 | 4 each |
| Browser actions | 67 | 101 | 100 / 102 / 95 |
| Browser requests recorded | 556 | 871 | 874 / 873 / 872 |
| Typed resource GET attempts | 30 | 30 | 30 each |
| Elapsed seconds | 26.09 | 50.91 | 52.76 / 53.31 / 49.75 |
| Record references | unavailable | disabled | 3 each |

The two seeded-record navigations and a scroll were replayed; these are navigation/interaction results, not verified business functions. Four replays failed `state_mismatch`; their page-content or outcome checks differed, so they remain failures. One C run in the preceding treatment iteration originally reported one incomplete prerequisite-network claim for a restoration that stopped before its first required step. The later audit correction checks the executed prefix plus recorded error, rather than inventing missing steps; separate post-run reanalysis found 0 missing claims in each saved run. That earlier metric is preserved in `state_aware_whiteboard_final_20261031/summary.json`; its `posthoc_reanalysis.json` is explicitly a reanalysis. All final repeat runs recorded zero missing claims. The record-group audit reported zero in the treatments, but is structural and does not prove absence of all false merges.

A preliminary treatment, kept separately, created one canvas and observed both seed records but replayed 0/0 because the record cards were buttons and the form's novelty score still won. It also recorded 10 incomplete audit claims for intentionally refused restoration steps. The ordering and audit were corrected before the final comparison. No model calls or external API spending occurred.

## Fixture and reset boundaries

`development_apps/stateful_lab.py` is a separate SQLite-backed operator fixture. It contains a method-less JS POST create, two existing records, same-label forms, read-only POST search, a GET that inserts a record, an update, and a dangerous delete. The mapper does not read fixture source or evaluator database. The operator owns its database and reset function. The browser regression checks actual server request and database behavior, one create at most, one visible GET mutation at most, both original record paths, distinct identities, shared template reference, nonconflated controls, blocked delete, and no write-capable replay even with POST exploration enabled. It does not prove that an invisible GET mutation is detectable.

Reproduce the disposable whiteboard evaluation, assuming the two existing application images, `postgres:16-alpine`, Docker, Playwright, and the documented schema at the path in the runner:

```sh
.venv/bin/python experiments/run_stateful_whiteboard.py --output agent1/experiments/state_aware_whiteboard_new
```

The runner refuses to replace existing containers bearing its names, creates its own network and unmounted database, publishes only to loopback, resets only that database, and removes only its own resources. It uses an archived 6c76b56 baseline and writes authentication state only to a temporary directory. The local output directory must not exist. Fixture checks: `.venv/bin/python -m pytest -q tests/test_action_behavior.py tests/test_state_aware_lab.py`.

Re-run the explicitly separate evidence reanalysis after the whiteboard run:

```sh
PYTHONPATH=. .venv/bin/python experiments/audit_stateful_runs.py agent1/experiments/state_aware_whiteboard_new
```

## Crawl Maze regression

A single matched 180-second run against the pinned local revision `2a0dd0a` used the previous 300-action / 1,000-request configuration. Post-run independent scoring found **61/91** fetched markers, the same aggregate as the prior three runs. It recorded 102 observed transitions, 23/23 successful replay attempts, 79 untested paths, 300 browser actions, and no missing graph-evidence claims in 174.5 seconds. Two runtime-discovered behaviors were observed and independently reproduced, versus three in each previous matched run. Thus the marker total did not regress, but the runtime-behavior count did. The run is not evidence that all dynamic interaction coverage was preserved. The captured graph and post-run evaluation are local ignored artifacts; the committed `summary.json` contains aggregate counts only.

Subsequent changes narrowed the GET ambiguity rule and restored the original interaction priority outside competing non-search forms; the final policy has not been rerun on Crawl Maze within the browser-time budget. One safety hardening after the measured run treats a failed non-GET request as write-capable because failure does not establish whether the server committed it. Post-run inspection found zero failed non-GET action events in this Crawl Maze run, so this change would not alter any classification from its recorded events; it has not itself been rerun on Crawl Maze. One earlier diagnostic run was interrupted before completion and is not scored.

The whiteboard database count independently verifies the number of newly created canvases, not the effect of each invite or every request. The fixture's read-only POST is deliberately classified as write-capable with mutation unconfirmed; its visibly changing GET is classified as possible state change, not confirmed mutation. No independent oracle was added to Agent 1, and there is no defensible whiteboard-wide false-positive or false-negative classification rate from these observations.

Three older fixture assertions expected POST replay solely because `allow_post_forms` was enabled. They now assert that the observed POST, outcome evidence and refused prerequisite are retained without a replay or a functional-success claim. Existing GET search and wrong-record tests continue to exercise independent replay checks.

## Test status and resume compatibility

The final full-suite invocation completed **169/169 passing**. After it started, a small resume-compatibility safeguard was added: for pre-classification checkpoints it reconstructs write-capable evidence from saved source observations and requests, including requests that failed after being sent. The full-suite process had already loaded the earlier code; the final safeguard was checked separately with **4/4 passing** focused, browser-free action-behavior tests and `compileall`. It has not been included in another full-suite or live-browser run. The existing browser evidence therefore applies to the immediately preceding mapper revision, not this last compatibility-only change.
