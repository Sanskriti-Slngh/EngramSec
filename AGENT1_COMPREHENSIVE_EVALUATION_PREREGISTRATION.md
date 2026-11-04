# Agent 1 comprehensive benchmark evaluation — preregistration

Status: **revision 1 (pre-run), frozen before any scored run; awaiting the user's explicit approval of the revised protocol before the first scored trial.**

- Revision 0 (`c2d55f5`) was written after the evidence-capture preflight (§3) and target setup verification (§5). Neither mapped a scored environment.
- Revision 1 applies the corrections the user requested on reviewing revision 0. It is listed in §12 and committed separately. No scored trial has run.
- Any change after the first scored trial is recorded as a deviation in the final report, never edited in here.

This milestone is an assessment of the current implementation, not a development sprint. No exploration strategy, threshold or parameter is changed during or after the evaluation. Weaknesses found are reported and analysed, not fixed.

## 1. Frozen agent

| Item | Value |
|---|---|
| Repository revision of the evaluated agent | `a9802e32023f317f2b24fe2d89b14d27823ab541` (`agent1/` tree `320a1f888cc2ea5a2b7d53c7e72b826e7a04d4f1`). The preregistration commit changes only `evaluation/`, `.gitignore` and this file. |
| Entry point | `agent1.explorer.Explorer(...).run()` then `agent1.exporter.write_outputs`, the same calls `agent1.cli map` makes |
| Policy | legacy frontier, `policy="coverage"` (`exploration_policy` left at `legacy`; no tour or hybrid policy) |
| Configuration | `agent1.cli map --policy coverage --seconds 180 --max-transitions 100 --max-browser-actions 500`; every other field is the CLI/RunConfig default. This is identical to the 2026-10-28 frozen WebExploitBench protocol ([WEBEXPLOITBENCH_EVALUATION.md](WEBEXPLOITBENCH_EVALUATION.md)). Defined in [evaluation/comprehensive_config.py](evaluation/comprehensive_config.py). |
| Notable defaults this implies | `exploration_mode=fresh`, `state_aware_exploration=True`, `record_aware_graph=True`, `allow_post_forms=False`, `replay_policy=shallow`, `replay_reserve_fraction=0.30`, `settle_ms=350`, `action_timeout_ms=5000`, `robust_readiness=False`, `interaction_profile=basic`, no origin aliases, no runtime listener observation, no storage state (anonymous) |
| Varies per target | start URL (the application root) and the descriptive context label `comprehensive:<env>:anonymous`. Nothing else. |
| Model usage | provider `none`; 0 model calls; no paid calls |
| Seeds | none. The legacy frontier has no random component (`resource_frontier_policy=fifo`, `resource_random_seed=0`). Trials differ only by timing and target behaviour. |
| Instrumentation | `acg_evidence=True`, `action_ledger=True` (evidence-only), enabled **only because** the preflight in §3 shows they do not change legacy behaviour |
| Browser/tooling | Python 3.12.13, Playwright 1.64.1 (Chromium headless), one browser worker |
| Host | Docker 10 CPU / 7.65 GiB memory limit (not raised); ~400 GB disk free |

Rejected alternatives, chosen before any run: per-environment historical configurations (persistent mode, origin aliases, POST forms, robust readiness). They were tuned per fixture during development. The production CLI defaults are what a new user gets, and they match the earlier external protocol. This production-default evaluation is the **primary scored track**. Consequences, declared in advance:
- POST form submission is disabled everywhere. A missed capability is attributed to this refusal only from the agent's own evidence (§7, 4C): a matching control recorded with skip reason `post_forms_disabled`. It is then reported as a *legitimate safety refusal*, separately from technical mapping failures.
  - Correction to revision 0: it is **not** assumed that the labs' write capabilities are POST-gated.
  - In the preflight, the three capability-annotated labs recorded no `post_forms_disabled` skip at all. Their write actions are script-driven (`fetch`), which this gate does not cover. Among the preflight fixtures, only coverage_lab recorded such skips (122 per run).
  - A write capability missed in those labs is therefore analysed as a technical miss, unless the evidence shows a refusal.
- A supplementary, separately reported write diagnostic (§9) measures what the POST gate hides on isolated in-process fixtures. It does not change the primary track.
- Fresh mode restores by reloading the root, so stateful flows that cannot be restored that way are refused as unsafe restorations.
- Strict-origin scope applies with no aliases.

## 2. Benchmark matrix

Track A = development, white-box: failure analysis permitted. Track B = WebExploitBench: evaluation-only. Track S = supplementary diagnostic, never pooled with A or B. No environment is described as completely blind. The two never-run targets (JetLinks, White-Jotter) are the only ones Agent 1 has never seen; they are still not "unseen by the authors", since the benchmark is public.

| Env | Track | Category | Prior exposure | Ground truth | Reset per trial | Trials |
|---|---|---|---|---|---|---|
| stateful_lab | A | server-rendered CRUD, destructive control | development | capability annotation (7) | fresh in-process server + fresh SQLite snapshot | 3 |
| js_heavy_lab | A | client-rendered SPA, 2 roles | development | capability annotation (14; anonymous+member) | fresh in-process server, state reset | 3 |
| replay_lab | A | catalog/search/records, equivalent interfaces | development | capability annotation (25) | fresh in-process server, state reset | 3 |
| phase2_lab | A | prerequisite chain + WebSocket diagnostic | development | server-state diagnostic only | fresh in-process server | 3 |
| coverage_lab | A | multi-area site | development | surface truth (areas/controls/requests) | fresh in-process server | 3 |
| heldout_shop | A | small e-commerce | development (formerly validation; **not held out**) | surface truth | fresh in-process server | 3 |
| transfer_library | A | resource/link discovery, boundary traps | development | transfer evaluator (documents/static/functionality) | fresh in-process servers, state reset | 3 |
| restoration_lab | A | restoration contract fixture | development | none (discovery only) | fresh in-process server | 3 |
| hybrid_lab | A | catalog + setup chain fixture | development | none (discovery only) | fresh in-process server | 3 |
| Crawl Maze | A | crawler testbed | development (repeatedly used) | official expected-path endpoint, 5 root categories (queried only post-run) | stateless Flask restart, loopback | 3 |
| Crawlground | A | crawler testbed, interaction-gated markers | development (transfer-checked) | server-side marker hits (`/results.json`, post-run) | fresh container from official image (no score volume), loopback | 3 |
| whiteboard | A | collaborative whiteboard (user's own app) | development | template/entity annotation only (`capabilities_annotated=false`) | disposable stack, fresh DB + schema; anonymous | 3 |
| PrestaShop | B | e-commerce CMS (PHP) | mapped blind once (2026-10-28); evaluation-only | none: discovery metrics only | `targetctl down`/`up` per trial + reset-integrity checks (§5) | 3 |
| ComfyUI | B | canvas/graph ML UI, WebSocket | mapped blind once (2026-10-28); evaluation-only | none | `targetctl down`/`up` per trial + reset-integrity checks (§5) | 3 |
| SiyuCMS | B | CMS (PHP) | **development/validation; not held out** | none | `targetctl down`/`up` per trial + reset-integrity checks (§5); DB on tmpfs (verified) | 3 |
| JetLinks | B | IoT platform (Java SPA) | never built/run before | none | `targetctl down`/`up` per trial + reset-integrity checks (§5) | 3 |
| White-Jotter | B | library management (Java/Vue) | never built/run before | none | `targetctl down`/`up` per trial + reset-integrity checks (§5) | 3 |
| 10 gated WebExploitBench targets | B | — | — | — | — | **NOT EVALUATED — ACCESS RESTRICTED** |
| *Supplementary (Track S, §9)*: in-process Track A fixtures selected by rule | S | write diagnostic, `allow_post_forms=True` | development | as primary | fresh child process (verified) | 3 |

Not evaluated, declared in advance:
- The 10 gated targets: no approved access; no attempt is made to obtain them or infer their contents.
- Authenticated whiteboard mapping: no credentials are authorized in this milestone, so only the anonymous surface is mapped. Capabilities behind login are recorded as prerequisite failures with cause "credentials not supplied by protocol".
- Any target whose setup fails within the limits in §6: recorded as a setup failure with the exact error, never retried with raised resource limits.

## 3. Evidence-capture preflight (behaviour preservation)

[evaluation/comprehensive_preflight.py](evaluation/comprehensive_preflight.py) runs the frozen configuration with instrumentation off and on, twice each, interleaved (off, on, off, on). It covers stateful_lab, js_heavy_lab, replay_lab, phase2_lab (WebSocket) and coverage_lab. Per pair it compares: executed browser actions, HTTP request sequences (server log and recorded network), legacy transition records, exploration decisions (source group, action, result group, status, error), replays, and the canonicalized final Graph A. The off-vs-off and on-vs-on pairs measure natural run-to-run variation.

**Result, stated at two separate levels.** Aggregate results are in [evaluation/results/comprehensive_preflight.json](evaluation/results/comprehensive_preflight.json). The per-transition counts below were recomputed from the raw preflight runs (git-ignored) for revision 1.

1. **Action-selection equivalence: established on all five fixtures.** In every pair (off/on and off/off, on/on), the executed browser-action sequences are identical over their common length. The source and result state groups of every transition in that common prefix are also identical.
2. **Exact state/group and record equivalence: established only on the three fixtures that end by exhausting their frontier.** On stateful_lab, js_heavy_lab and replay_lab, the following are identical off vs on and run to run: the full transition records, replays, recorded HTTP, decisions, and the canonical final Graph A. The one exception is replay_lab's server-side request order, which differs at one index in every pair, including off-vs-off; the multiset is the same. On phase2_lab and coverage_lab (180 s ceiling), exact equivalence is **not** established and is not claimed.

| Fixture | Terminated by | Actions (off0, on0, off1, on1) | Action sequences | Transition groups (common prefix) | Transition status differences: off-vs-off / on-vs-on / off-vs-on | Final Graph A, records, replays |
|---|---|---|---|---|---|---|
| stateful_lab | frontier exhausted | 16, 16, 16, 16 | identical | identical | 0 / 0 / 0, 0 | identical |
| js_heavy_lab | frontier exhausted | 31, 31, 31, 31 | identical | identical | 0 / 0 / 0, 0 | identical |
| replay_lab | frontier exhausted | 172 ×4 | identical | identical | 0 / 0 / 0, 0 | identical (server request order differs at one index in every pair) |
| phase2_lab | 180 s ceiling | 380, 379, 395, 394 | identical over common length | identical | 1 / 4 / 3, 4 | differ in every pair, incl. off-vs-off |
| coverage_lab | 180 s ceiling | 373, 373, 373, 376 | identical over common length | identical | 6 / 6 / 6, 6 | differ in every pair, incl. off-vs-off |

**Observed natural variability (identical configuration)**, reported separately from capture effects:
- On the two time-bounded fixtures, three things vary between identical-configuration runs:
  - how many actions fit before the deadline: phase2_lab 380 vs 395 off-vs-off, 379 vs 394 on-vs-on; coverage_lab 373 vs 376 on-vs-on;
  - which transitions the time-bounded replay phase validated (status `observed` vs `replay_validated`);
  - the server-side HTTP sequences, which are not even multiset-equal.
- The off-vs-on differences fall in the same range. A capture effect smaller than this natural variability cannot be excluded by four runs, and none is claimed absent.
- Capture adds per-observation work (disabled-control extraction, evidence bookkeeping). Wall-time differences off vs on stayed within the off-vs-off range. The largest spread was replay_lab: 82.9 / 84.3 / 90.6 / 81.8 s for off0 / on0 / off1 / on1, so 7.7 s between the two capture-off runs.

**Stricter WebSocket scope enforcement, reported separately.** With capture on, every WebSocket goes through Playwright's WebSocket route:
- in-scope sockets are connected through it;
- out-of-scope sockets are refused and counted (`ws_out_of_scope_refused`) instead of connected.

This is a deliberate behaviour difference, not equivalence:
- The preflight did **not** exercise it: the only WebSocket fixture (phase2_lab) opens same-origin sockets, and the preflight did not save sink counters, so no refusal count was measured there.
- Every scored trial records `ws_out_of_scope_refused`. A non-zero count is a disclosed difference from capture-off behaviour on that target.

**Canonicalization note:** the comparison was refined after the first off-vs-off pair. Port-hashed identifiers (control ids, raw state signatures, record ids) differ between any two runs, so they are dropped and ports are normalized. The behaviour comparisons (actions, decisions, HTTP) did not depend on this.

**Decision:** `acg_evidence` and `action_ledger` are enabled in all scored runs. The basis is action-selection equivalence on all five fixtures, plus exact equivalence on the three frontier-exhausted fixtures. The action ledger is required for the recall-vs-budget curves, and the evidence sink for the live ACG (Phase 7).

## 4. Access restrictions and integrity rules (confirmed)

- WebExploitBench is evaluation-only. Not read at any time: `challenge.json`, `vulnerability/`, `_common/` verifiers, evaluator internals, exploit solutions, reports, canaries. `targetctl` reads its own configuration; Agent 1 and the harness do not.
- No exploitation or vulnerability-confirmation actions. No credentials. No destructive actions: the frozen dangerous-label filter is unchanged and POST forms are disabled. No state-changing replays beyond the frozen agent's own (already restricted) replay rules.
- Loopback only. Before each Track B trial the harness verifies that every published port of the target's compose project is bound to `127.0.0.1`. The trial is stopped (recorded as a setup failure) if not. Crawlground runs in its official image published on `127.0.0.1` only, because its server binds all interfaces.
- Benchmark traces, outputs, metadata, failures and derived artifacts are never used to tune, train or change Agent 1. Track B failure analysis stays at the level of aggregate mechanism categories: protected vulnerability locations are not inspected, and no per-target fix is designed.
- Raw run directories (`agent1/experiments/comprehensive_*/`) are git-ignored. Only aggregate numbers, with no URLs, labels, payloads, identifiers or credentials, are committed for Track B.
- A mapper coverage score is **not** a WebExploitBench/CAGE exploitation score, and no CAGE score is computed.
- No route or button count is reported as functional recall.

## 5. Setup and reset procedure

- SiyuCMS: the 7-day-old stack was backed up first. The stack keeps MySQL on tmpfs, so the dump is the only copy. The backup has three parts:
  - `mysqldump --all-databases`, verified by restore into a throwaway container: all 28 table row counts identical;
  - a `docker commit` of the web container;
  - the compose file and port override.

  It is stored outside the repository (`~/engramsec_backups/siyucms_pre_comprehensive_20261103/`, with RESTORE.md). Each trial then uses `targetctl down` + `up`, which re-initializes the database from the benchmark's SQL.
- JetLinks and White-Jotter: built once with `targetctl build`, sequentially. Build time, image size and failures are recorded as setup cost, separately from mapping time. They are started one target at a time, and no two Track B targets run simultaneously.
- Crawl Maze and Crawlground: the previous `/private/tmp` checkouts were partly deleted by OS temp cleanup. They were re-cloned at the previously pinned commits (Crawl Maze `2a0dd0a7…`, Flask 3.1.3; Crawlground `ba52303a…`, official Dockerfile) into `~/engramsec_targets/`.
- **Benchmark tooling state, disclosed.** The local WebExploitBench checkout (`ae88196`) carries three pre-existing local patches from earlier milestones:
  - `scripts/targetctl` lower-cases names with `tr` (bash 3.2 compatibility);
  - `scripts/targetctl` publishes ports on `127.0.0.1` instead of `0.0.0.0` (loopback isolation);
  - the SiyuCMS Dockerfile points `apt` at `archive.debian.org` (build compatibility).

  None of these touches application code, challenge metadata or verifiers.
- **Infrastructure-only change made during setup (before any scored run).** PrestaShop's official post-up hook needs bash ≥ 4.4 (it expands an empty array under `set -u`); macOS ships bash 3.2, so the hook failed and `targetctl up` exited 1.
  - The hook registers the published loopback origin as the shop's domain. The 2026-10-28 PrestaShop run was therefore very probably deployed without it, which plausibly explains its 50 controls "blocked as cross-origin" toward an internal host. This is a likely deployment artifact of that earlier run, not a measured fact.
  - For this evaluation, `targetctl` and its hooks run under Homebrew bash 5.3 (keg path `/opt/homebrew/opt/bash/bin`, unlinked: the user's default `bash` is unchanged). This applies to every Track B target. No benchmark file is edited for it, and Agent 1 is unaffected.
  - Consequence: PrestaShop results are **not comparable** with the 2026-10-28 run. The difference is reported, not hidden.
- **Harness bugs found by setup verification (no mapping), fixed before any scored run:**
  - `targetctl` prints its URL JSON-escaped (`http:\/\/…`), so the URL parser was fixed;
  - a stale Crawl Maze server from 2026-10-30 still held port 3460, so the harness now refuses an already-occupied port;
  - Postgres reports ready during its first-start initialization, so the whiteboard schema load is retried.
- Setup measurements (no mapping) are in `evaluation/results/comprehensive_setup.json`. Each target was started fresh, loopback-only was verified, memory was sampled at ready and 30 s later, and the target was then stopped:

| Target | Build (one-time) | New images | Start → ready | Containers | Memory at ready / +30 s |
|---|---:|---|---:|---:|---|
| SiyuCMS | prebuilt | — | 18.9 s | 4 | 515 / 514 MB |
| PrestaShop | prebuilt | — | 32.1 s | 4 | 837 / 837 MB |
| ComfyUI | prebuilt | — | 18.9 s | 3 | 657 / 656 MB |
| JetLinks | 136 s | 1.5 GB, 434 MB, 79 MB | 273.1 s | 8 | 2,707 / 2,769 MB |
| White-Jotter | 206 s | 1.5 GB, 533 MB | 27.2 s | 5 | 1,230 / 1,232 MB |
| Crawlground | 11 s (official Dockerfile) | 278 MB | 1.4 s | 1 | 23 MB |
| whiteboard | prebuilt (user's images) | — | 6.3 s | 3 | 216 MB |
| Crawl Maze | venv (Flask 3.1.3) | — | 1.0 s | host process | — |

  Every target fits within the unchanged 7.65 GiB Docker limit, one at a time. "Ready" means the application root answered HTTP with status < 500. Application-level readiness beyond that is not assumed. If a target is still initializing, that shows up in the run as startup readiness failures.
- **Trial-reset integrity (revision 1).** `targetctl down` runs `docker compose down` **without** `-v`, so it does not remove volumes. The harness therefore checks the reset itself instead of trusting it ([evaluation/comprehensive_eval.py](evaluation/comprehensive_eval.py), `External`).
  - **Before startup:** it records the exit status of the pre-start teardown. It confirms that no container of the project remains, in any state, and that no named (compose-declared) project volume exists.
  - **After startup:** it records every container ID, the volume names and the mount profile of each service: tmpfs destinations, volume and bind destinations with read/write mode. It then checks three things:
    - IDs and volume names are disjoint from every earlier trial of the environment, including a resumed run;
    - the mount profile equals the frozen profile;
    - no named volume is attached.
  - **After the trial:** it records the teardown exit status, residual containers and leftover trial volumes.
  - **Any violation** is a `reset_failure`. The trial is **not mapped**; one setup retry is allowed, as for any setup failure, and both attempts are recorded. Nothing proceeds silently.
  - Crawlground and the whiteboard stack get the same checks. Their containers are removed with `docker rm -f -v`.
  - **In-process fixtures** reset by process isolation: each trial is a new Python process, and fixture state is created from code (stateful_lab: a SQLite database built from a fixed script in a new temporary directory). Each trial records the initial server-log length (must be 0) and an initial-state digest (must be identical across trials). It also checks after the trial that the fixture's port is closed.
- **Reset verification, done before any scored run (no mapping).** `comprehensive_eval reset-verify` gave each Docker-backed environment two fresh start/stop cycles, one target at a time, and froze its mount profile. The profile is git-ignored; only digests and counts are in [evaluation/results/comprehensive_reset_verification.json](evaluation/results/comprehensive_reset_verification.json). Mounts were read with `docker inspect` only. No benchmark application file, metadata or verifier was opened.

| Target | Containers | Data directories | Named volumes | Writable bind mounts | IDs / volumes disjoint across cycles | Profile identical | Teardown exit | Residual after teardown |
|---|---:|---|---:|---|---|---|---|---|
| SiyuCMS | 4 | database on tmpfs (1) | 0 | 1: Docker socket of the benchmark's evaluator sidecar | yes / yes | yes | 0, 0 | 0, 0 |
| PrestaShop | 4 | database on tmpfs (1) | 0 | 1: same | yes / yes | yes | 0, 0 | 0, 0 |
| ComfyUI | 3 | application data on tmpfs (2) | 0 | 1: same | yes / yes | yes | 0, 0 | 0, 0 |
| JetLinks | 8 | Postgres, Elasticsearch, Redis, application data on tmpfs (5) | 0 | 1: same | yes / yes | yes | 0, 0 | 0, 0 |
| White-Jotter | 5 | MySQL and Redis on tmpfs (2) | 0 | 1: same | yes / yes | yes | 0, 0 | 0, 0 |
| Crawlground | 1 | anonymous volume, removed with the container | 0 | 0 | yes / yes | yes | 0, 0 | 0, 0 |
| whiteboard | 3 | Postgres anonymous volume, removed with the container | 0 | 0 | yes / yes | yes | 0, 0 | 0, 0 |

  - **Conclusion.** For all five WebExploitBench targets, every application data directory is tmpfs. Application containers without a data mount are recreated each trial (new IDs), so their writable layer is discarded. The only writable host mount is the benchmark's own evaluator sidecar's Docker socket: benchmark infrastructure, not application state. It is neither used nor inspected by the harness.
  - Two observations, disclosed:
    - Each SiyuCMS verification cycle took about 32 minutes of wall time, although startup itself took 18–20 s and the teardown had exit 0. A timed re-check of one cycle afterwards took 56 s to start and 7 s to stop, so the delay is attributed to the Docker host, not to the reset logic. Each trial records its own setup and teardown time, and the 3 h per-environment limit applies.
    - `docker inspect` necessarily lists mount *paths*, including those of the benchmark's verification infrastructure. None of their contents were read.
- **Retry rule.** A failed *setup* is retried at most once per trial, and both attempts are recorded. A *mapping* run is never retried, and a failed, killed or incomplete trial is reported as such.
- **Run order.** Track A in-process fixtures, then Track A external environments, then Track B in the order SiyuCMS, PrestaShop, ComfyUI, JetLinks, White-Jotter. All trials of one environment run before the next environment starts.
- Initial-state equivalence is checked, not assumed. Each trial records the first observed state group and its control count, plus a configuration digest. Differences across trials are reported.

## 6. Budgets and hard limits

| Limit | Value |
|---|---|
| Exploration (agent) | 180 s, 500 browser actions, 100 transitions (agent-enforced; early termination when the frontier empties is allowed and reported) |
| Hard wall limit per trial (harness kills the child process) | 600 s, recorded as `hard_timeout` |
| Hard setup limit per trial | 900 s (`targetctl up` + readiness), recorded as `setup_failure` |
| Reset integrity | any failed check in §5, recorded as `reset_failure`; the trial is not mapped |
| Hard limit per environment (all trials) | 3 h |
| Docker | existing 7.65 GiB limit; one target at a time; memory sampled every 5 s during runs |
| Disk | abort setup if free disk < 50 GB |
| Expected total | ~3–5 h wall for the primary tracks, dominated by Track B setup; plus ~0.5 h for Track S |

## 7. Metric definitions

All metrics are computed after the run from the agent's own outputs ([evaluation/comprehensive_metrics.py](evaluation/comprehensive_metrics.py)). Ground truth is touched only by the scorer.

**4A Discovery (every environment):**
- route templates and grouped states (Graph A);
- areas = distinct (route template, title);
- ACG templates and view states;
- unique control signatures observed / executed;
- advertised-unexecuted controls;
- affordances and affordance families (ACG);
- browser request structures = distinct (method, route template, sorted query-parameter names);
- ACG operations (HTTP, WebSocket);
- client-only capabilities (observed, no operation);
- entity types and instances;
- roles;
- resource references.

**4B Capabilities (every environment, from the offline ACG reconstruction):**
- distinct capabilities ≥ observed;
- by behavioural class;
- unidentified;
- equivalent interfaces (one capability bound to > 1 affordance);
- role-conditioned counts;
- learned dependencies (predicates).

Incorrect merges and splits are reported only with ground truth.

**4C Evidence status:**
- advertised (unexecuted controls, by skip reason);
- hypothesized;
- attempted-failed (failed affordances);
- executed-no-effect;
- observed, reproduced, verified;
- refuted;
- blocked (capabilities/affordances);
- blocked by safety (`dangerous_label_or_target`, POST disabled), by scope (`cross_origin`), by authentication (prerequisite unmet);
- unknown = advertised but not selected.

**Refusal split (revision 1).** Every advertised-unexecuted control is counted under exactly one cause:
- *safety refusal by configuration or protocol*: `post_forms_disabled`, `dangerous_label_or_target`, `requires_protected_or_file_input`;
- *scope refusal*: `cross_origin`, plus out-of-scope HTTP and WebSocket counts;
- *technical*: `frame_not_observable`;
- *not selected*.

On the annotated labs, each missed annotated capability is attributed from the agent's own evidence:
- **legitimate safety refusal**: at least one advertised control matches the capability's annotated entry point or operation, and every matching control carries a safety skip reason;
- **over-conservative safety refusal**: the dangerous-label filter refused a capability annotated as having no server effect. This is a technical Phase 5 category-4 failure, not legitimate;
- **scope refusal**;
- **mixed**: some matching controls were refused and some were not;
- **not safety-limited**;
- **no matching advertised control**.

Only the first counts as a legitimate refusal. The primary metric keeps the full annotated denominator. `annotation_recall_excluding_safety_refusals` is a supplementary view, reported next to it.

VERIFIED is the frozen ACG status, which requires paired-search or cross-view evidence. A same-URL/fingerprint replay is never counted as verification.

**4D Reference-based metrics.** No environment in this evaluation has independently established application ground truth. The reference data and their status:
- **Capability annotations (stateful_lab, js_heavy_lab, replay_lab).** These are frozen, author-curated *development* annotations. Each declares `independent: false`: a single annotator, the agent's developer, read the fixture source; there was no second annotator or adjudication; frozen 2026-11-01. They are **not** independently established ground truth. The resulting metrics are called **annotation-based recall and precision**: frozen M1a (`score_capabilities`, unchanged), M1b, incorrect capability merges, splits, incorrect record merges. They measure agreement with the author's own model of a fixture the author also designed.
- Surface truth (coverage_lab, heldout_shop): `experiments/evaluate_coverage.py`.
- transfer_library: `experiments/evaluate_transfer_library.py`.
- Crawl Maze: expected-path coverage over the fixed 5-category denominator.
- Crawlground: server-scored markers over all tests.
- whiteboard: record-identity metrics only.

- Surface truth (coverage_lab, heldout_shop) and the transfer_library evaluator are also author-written. Crawl Maze and Crawlground are scored by the testbeds' own third-party references.

Each trial records the basis of its reference (`reference_basis`). Everything else is **NOT MEASURABLE**.

**Track B reporting (revision 1).** PrestaShop, ComfyUI, SiyuCMS, JetLinks and White-Jotter have no independent capability ground truth. **Without it, we cannot establish what percentage of each application's functionality Agent 1 captured.** No discovery count is reported as, or converted into, a coverage percentage, recall or completeness figure. Track B results are reported in six separate sections and never combined into a single score:
1. **Functional inventory:** capabilities (≥ observed, by behavioural class), operations (HTTP, WebSocket), client-only capabilities, affordances and families, request structures, templates, states, controls observed/executed, equivalent interfaces, session contexts.
2. **Evidence quality:** observed / reproduced / hypothesized / executed-no-effect / attempted-failed / refuted, replay attempts and validations, failed actions by error class, capture gaps.
3. **Unidentified operations:** capabilities without a behavioural class, and operations bound to no capability.
4. **Blocked functionality:** the refusal split above (safety, scope, technical, not selected), blocked capabilities and affordances, out-of-scope HTTP and WebSocket.
5. **Entity identity:** entity types and instances. Their correctness is NOT MEASURABLE without annotation.
6. **Verification status:** VERIFIED count (paired-search/cross-view only) and claims by status.

Ground-truth-free growth curves are reported as counts, with no AUC and no normalization to a final value.

**4E Curves and efficiency:**
- Recall at 0%, 10%, …, 100% of the action budget (500) and of the wall budget (180 s). Each point is computed from the evidence stamped (action ledger) at or before that point. Once the run ends, the final value carries forward.
- Normalized trapezoidal AUC, versus actions and versus wall time.
- Final recall reported separately. Precision and false positives (unmatched ACG capabilities) at the same checkpoints.
- AUC only where a capability or marker denominator exists (the 3 capability-annotated labs). Track B gets ground-truth-free growth curves (capabilities, operations, templates) with **no AUC**.

Efficiency fields:
- actions on unique discovery: an observed transition that yields a new state group or a new request structure;
- redundant transitions; failed actions (by error class);
- restoration actions and root reloads;
- verification (replay) actions;
- failed restorations: unsafe restorations refused, stale live states, startup readiness failures;
- readiness wait;
- HTTP by source: navigation, action, replay, passive, budget used/blocked;
- waiting vs executing: an estimate, labelled as such;
- capabilities per 100 actions and per minute;
- termination cause.

Fewer actions are never reported as an improvement on their own.

**4F Repeatability:**
- every trial's status, including failures;
- median / min / max;
- pairwise Jaccard overlap of role-free capability identity sets;
- whether executed-action sequences are identical;
- initial-state and configuration equivalence.

Three deterministic repetitions support no statistical-significance claim, and none is made.

**4G Canonical vs session-conditioned (terminology corrected in revision 1):**
- ACG "roles" and the annotations' role entries are **cookie-name session contexts**. No independent annotation of semantic authorization roles exists. All such metrics are therefore called *session-conditioned* and must not be read as authorization-role coverage. Affected fields: discovery `session_contexts`; capabilities `session_conditioned`; annotation-based `session_conditioned.recall`; `session_aware_precision_alt`.
- Canonical = the frozen M1a against the historical annotations, unchanged and retained as the primary measure.
- Session-conditioned (author-defined, reported separately): an annotated (capability, session context) pair is covered when the capability has a frozen M1a match, and the matching or an operation-equivalent observed ACG capability exists in an ACG session context whose cookie names include the annotated context's. Anonymous means no session cookies. It can never exceed the canonical value.
- Alternative precision: `role_aware_precision` (scorer name unchanged), reported as `session_aware_precision_alt`.

Historical annotations and frozen precision are not changed. Capabilities are never merged because of shared labels, endpoints or templates, and never split only because sessions differ.

**Safety:**
- state-changing requests issued (exploration, replay);
- dangerous controls skipped;
- out-of-scope HTTP blocked; redirect scope violations; out-of-scope WebSockets refused;
- for annotated labs: destructive-endpoint hits, repeated write-endpoint hits, unsupported functional claims.

## 8. Phase 5 failure taxonomy (author-defined)

The original brief's ten categories were lost when it was interrupted. These ten were defined by the user and the author for this milestone, from the causal chain, before any scored run:

1. **Observation failure.** Agent 1 never sees the relevant control or state.
2. **Extraction failure.** The browser observes it, but the extractor does not represent it.
3. **Candidate-generation failure.** The capability never enters the exploration frontier.
4. **Safety-gating failure.** The capability is blocked by safety restrictions, correctly (*legitimate refusal*) or incorrectly (*technical failure*).
5. **Execution failure.** The action is attempted but does not execute correctly.
6. **Prerequisite/state failure.** Required authentication, session state or preceding actions are missing.
7. **Evidence-capture failure.** The action occurs, but its requests, responses or effects are not captured.
8. **Capability-modeling failure.** The evidence exists, but the ACG merges, splits or classifies it incorrectly.
9. **Restoration/replay failure.** Agent 1 cannot reliably return to the correct state or record.
10. **Verification failure.** Agent 1 cannot independently establish whether the expected behaviour occurred.

Rules:
- Each missing capability gets exactly one **earliest causal failure**; downstream symptoms are listed separately.
- Each analysis records: expected behaviour, actual observation, missing evidence, first failure, root cause, responsible subsystem (extractor / explorer / executor / ACG / restoration / safety / infrastructure), generality, and confidence.
- Legitimate safety refusals (destructive label, POST disabled by the frozen configuration, no credentials by protocol) are separated from technical failures. The automatic evidence-based attribution in §7 (4C) is the starting point for Phase 5, and an over-conservative refusal counts as a technical category-4 failure. The §9 diagnostic can corroborate an attribution but never replaces it.
- Missing ground truth (NOT MEASURABLE) is separated from mapping failures.
- Track B is classified only at the mechanism level visible in the agent's own outputs: termination cause, failed-action error classes, blocked-by-scope counts, advertised-unexecuted reasons. Application internals are not inspected and no fix is proposed for a specific target.

## 9. Supplementary safe-isolated write diagnostic (Track S, revision 1)

**Purpose:** to measure what the production POST gate hides, without changing the primary evaluation or granting a global POST permission.

- **Configuration:** the frozen configuration plus `allow_post_forms=True` (`POST_DIAGNOSTIC_OVERRIDE`), passed only to the diagnostic's child processes. `FROZEN` is not modified. Origin scope, the dangerous-label filter, the protected/file-input filter and the replay restrictions are unchanged.
- **Environments, selected by a preregistered rule:** in-process Track A fixtures where any primary trial recorded at least one `post_forms_disabled` skip (`--envs auto`). The harness refuses any Docker or external target, including every WebExploitBench target, Crawlground, Crawl Maze and the whiteboard. From the preflight, coverage_lab is expected to qualify; heldout_shop and hybrid_lab contain POST forms and may qualify.
- **Isolation, verified per trial:**
  - The fixture server runs inside the trial's own child process on an ephemeral `127.0.0.1` port.
  - The POST handlers of these fixtures keep no persistent server-side state: they set a cookie or redirect. stateful_lab's SQLite file lives in a new temporary directory.
  - Each trial records an empty initial server log and an initial-state digest, which must match across trials. After the child exits, the fixture port must be closed.
  - A trial failing any check is reported as `isolation_unverified` and excluded.
- **Reporting:** a separate summary (`evaluation/results/agent1_post_diagnostic_summary.json`) and a separate report section, as deltas against the primary trials:
  - previously `post_forms_disabled` controls now executed;
  - capabilities and reference metrics gained;
  - state-changing requests issued.

  It is **never** pooled into primary numbers and never used to change Agent 1 or its defaults.
- **Order and budget:** after all primary trials; 3 trials per selected fixture, with the same 180 s / 500 / 100 budget.

## 10. Phase 6 and 7 plans

- **Phase 6.** One generalization row per architecture category. Columns: environments; results; the failure categories observed; whether evidence comes from more than one application. A single successful fixture is never generalized to its category.
- **Phase 7.** For every trial, three representations are compared:
  - historical Graph A (states, actions, workflows, features, edges);
  - offline ACG reconstruction (`import_run_artifact` + `materialize`);
  - live ACG (`LiveACG` synced from the run's evidence sink).

  The comparison covers content counts, statuses and gaps, plus, on annotated labs, recall: Graph A feature action-based recall, offline M1a and live M1a. A richer graph is not counted as a more complete map, and an observation is not counted as verification.

## 11. Analysis and reporting

Deliverables:
- `AGENT1_COMPREHENSIVE_BENCHMARK_REPORT.md`, covering the 15 sections of the brief;
- `evaluation/results/agent1_comprehensive_summary.json`;
- answers to Q1–Q10;
- at most five prioritized research opportunities. None is implemented in this milestone.

In the report, a WebExploitBench result is never phrased as coverage, completeness or recall. A session-conditioned metric is never phrased as role or authorization coverage. An annotation-based metric is never phrased as ground-truth accuracy.

After the evaluation, the full regression suite is run. Only reports and aggregate artifacts are committed and pushed, to the existing branch; there is no merge to main and no force-push. The report is honest even if results are disappointing.

## 12. Revision log

**Revision 1 (pre-run, 2026-11-04).** Requested by the user on reviewing revision 0. No scored trial had run. `agent1/`, `FROZEN`, the exploration policy and all thresholds are unchanged.
1. **Safety-limited vs. technically undiscovered** (§1, §7 4C, §8). There is an evidence-based refusal split and attribution for missed capabilities. Revision 0's assumption that the labs' write capabilities are POST-gated is corrected. The supplementary write diagnostic is added as Track S (§9).
2. **Trial-reset integrity** (§5). The harness now does the following:
   - checks the teardown exit status;
   - checks for residual containers and named volumes before startup;
   - records container IDs, volume names and the mount profile for every trial;
   - checks them against the frozen profile and against earlier trials;
   - records `reset_failure` instead of proceeding.

   `reset-verify` confirmed tmpfs data directories on all five WebExploitBench targets.
3. **Session terminology** (§7 4G). Role-derived metrics are renamed session-conditioned. Canonical M1a is retained.
4. **Preflight conclusion** (§3). Action-selection equivalence (all five fixtures) is now distinguished from exact state/group equivalence (three frontier-exhausted fixtures only). Natural variability and the stricter WebSocket scope enforcement are reported separately.
5. **Reference-data limitations** (§7 4D). The annotations are frozen, author-curated, non-independent development annotations. The metrics are renamed annotation-based recall and precision.
6. **WebExploitBench conclusions** (§7). No coverage percentages; an explicit NOT MEASURABLE statement; six separate report sections.
7. **Integrity** (§1, §4). The primary configuration is unchanged: legacy coverage policy, 180 s, 500 actions, 100 transitions, no model calls, no credentials, production safety defaults, evaluation-only WebExploitBench.

Harness changes in revision 1 are limited to `evaluation/comprehensive_{eval,metrics,summary,setup}.py`. The new tests are in `tests/test_comprehensive_harness.py`.
