# Agent 1 comprehensive benchmark evaluation — preregistration

Status: **frozen before any scored run; awaiting the user's approval before the first scored trial.** It was written after the evidence-capture preflight (§3) and target setup verification (§5), neither of which mapped a scored environment. It is committed before the first scored trial. A change requested at approval is committed as a separate, labelled pre-run revision. Any change after the first scored trial is recorded as a deviation in the final report, never edited in here.

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

Rejected alternatives, chosen before any run: per-environment historical configurations (persistent mode, origin aliases, POST forms, robust readiness). They were tuned per fixture during development. The production CLI defaults are what a new user gets, and they match the earlier external protocol. Consequences, declared in advance:
- POST form submission is disabled everywhere, so capabilities that need a POST form are safety-gated by configuration (Phase 5 category 4, *legitimate refusal*).
- Fresh mode restores by reloading the root, so stateful flows that cannot be restored that way are refused as unsafe restorations.
- Strict-origin scope applies with no aliases.

## 2. Benchmark matrix

Track A = development, white-box: failure analysis permitted. Track B = WebExploitBench: evaluation-only. No environment is described as completely blind. The two never-run targets (JetLinks, White-Jotter) are the only ones Agent 1 has never seen; they are still not "unseen by the authors", since the benchmark is public.

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
| PrestaShop | B | e-commerce CMS (PHP) | mapped blind once (2026-10-28); evaluation-only | none: discovery metrics only | `targetctl down`/`up` per trial | 3 |
| ComfyUI | B | canvas/graph ML UI, WebSocket | mapped blind once (2026-10-28); evaluation-only | none | `targetctl down`/`up` per trial | 3 |
| SiyuCMS | B | CMS (PHP) | **development/validation; not held out** | none | `targetctl down`/`up` per trial (tmpfs DB → identical init) | 3 |
| JetLinks | B | IoT platform (Java SPA) | never built/run before | none | `targetctl down`/`up` per trial | 3 |
| White-Jotter | B | library management (Java/Vue) | never built/run before | none | `targetctl down`/`up` per trial | 3 |
| 10 gated WebExploitBench targets | B | — | — | — | — | **NOT EVALUATED — ACCESS RESTRICTED** |

Not evaluated, declared in advance:
- The 10 gated targets: no approved access; no attempt is made to obtain them or infer their contents.
- Authenticated whiteboard mapping: no credentials are authorized in this milestone, so only the anonymous surface is mapped. Capabilities behind login are recorded as prerequisite failures with cause "credentials not supplied by protocol".
- Any target whose setup fails within the limits in §6: recorded as a setup failure with the exact error, never retried with raised resource limits.

## 3. Evidence-capture preflight (behaviour preservation)

[evaluation/comprehensive_preflight.py](evaluation/comprehensive_preflight.py) runs the frozen configuration with instrumentation off and on, twice each, interleaved (off, on, off, on). It covers stateful_lab, js_heavy_lab, replay_lab, phase2_lab (WebSocket) and coverage_lab. Per pair it compares: executed browser actions, HTTP request sequences (server log and recorded network), legacy transition records, exploration decisions (source group, action, result group, status, error), replays, and the canonicalized final Graph A. The off-vs-off and on-vs-on pairs measure natural run-to-run variation.

**Result:** no capture-attributable behaviour change was observed. Aggregate results are in [evaluation/results/comprehensive_preflight.json](evaluation/results/comprehensive_preflight.json).

| Fixture | Terminated by | Off vs on | Off vs off (natural) |
|---|---|---|---|
| stateful_lab | frontier exhausted (16 actions) | identical: actions, decisions, HTTP, transitions, replays, Graph A | identical |
| js_heavy_lab | frontier exhausted (31) | identical | identical |
| replay_lab | frontier exhausted (172) | identical except server-side request *order* at one index (same multiset) | same order difference |
| phase2_lab | 180 s ceiling | action sequences identical as prefixes; 380 vs 379 and 395 vs 394 actions | 380 vs 395 actions |
| coverage_lab | 180 s ceiling | action sequences identical as prefixes; 373 vs 373 and 373 vs 376 actions | 373 vs 373 (on vs on: 373 vs 376) |

**Diagnosis of the time-bounded differences.** No exploration decision differs before the deadline. The differences are only:
- how many actions fit before the 180 s deadline;
- which transitions the time-bounded replay phase validated (`observed` vs `replay_validated`).

Both vary at least as much between identical-configuration runs. Capture adds only per-observation work (disabled-control extraction, evidence bookkeeping); the wall-time differences were within ±1 s.

**Design difference, declared:** with capture on, an out-of-scope WebSocket is refused and counted (`ws_out_of_scope_refused`) instead of connected. This is stricter scope enforcement, not a decision change. It is reported per trial, and any non-zero count is a disclosed deviation from capture-off behaviour.

**Canonicalization note:** the comparison was refined after the first off-vs-off pair. Port-hashed identifiers (control ids, raw state signatures, record ids) differ between any two runs, so they are dropped and ports are normalized. The behaviour comparisons (actions, decisions, HTTP) did not depend on this.

**Decision:** `acg_evidence` and `action_ledger` are enabled in all scored runs. The action ledger is required for the recall-vs-budget curves, and the evidence sink for the live ACG (Phase 7).

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
- **Retry rule.** A failed *setup* is retried at most once per trial, and both attempts are recorded. A *mapping* run is never retried, and a failed, killed or incomplete trial is reported as such.
- **Run order.** Track A in-process fixtures, then Track A external environments, then Track B in the order SiyuCMS, PrestaShop, ComfyUI, JetLinks, White-Jotter. All trials of one environment run before the next environment starts.
- Initial-state equivalence is checked, not assumed. Each trial records the first observed state group and its control count, plus a configuration digest. Differences across trials are reported.

## 6. Budgets and hard limits

| Limit | Value |
|---|---|
| Exploration (agent) | 180 s, 500 browser actions, 100 transitions (agent-enforced; early termination when the frontier empties is allowed and reported) |
| Hard wall limit per trial (harness kills the child process) | 600 s, recorded as `hard_timeout` |
| Hard setup limit per trial | 900 s (`targetctl up` + readiness), recorded as `setup_failure` |
| Hard limit per environment (all trials) | 3 h |
| Docker | existing 7.65 GiB limit; one target at a time; memory sampled every 5 s during runs |
| Disk | abort setup if free disk < 50 GB |
| Expected total | ~3–5 h wall, dominated by Track B setup |

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

VERIFIED is the frozen ACG status, which requires paired-search or cross-view evidence. A same-URL/fingerprint replay is never counted as verification.

**4D Ground-truth metrics:**
- Capability annotations (stateful, js_heavy, replay labs): frozen M1a recall and precision (`score_capabilities`, unchanged); M1b; incorrect capability merges; splits; incorrect record merges.
- Surface truth (coverage_lab, heldout_shop): `experiments/evaluate_coverage.py`.
- transfer_library: `experiments/evaluate_transfer_library.py`.
- Crawl Maze: expected-path coverage over the fixed 5-category denominator.
- Crawlground: server-scored markers over all tests.
- whiteboard: record-identity metrics only.

Everything else is **NOT MEASURABLE**. Track B capability recall is NOT MEASURABLE (no ground truth).

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

**4G Canonical vs role-conditioned:**
- Canonical = the frozen M1a against the historical annotations, unchanged.
- Role-conditioned (author-defined, reported separately): a (capability, role) pair is covered when the capability has a frozen M1a match, and the matching or an operation-equivalent observed ACG capability exists in an ACG role whose cookie names include the annotated role's. Anonymous means no session cookies. It can never exceed the canonical value.
- Alternative precision: `role_aware_precision`, reported separately.

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
- Legitimate safety refusals (destructive label, POST disabled by the frozen configuration, no credentials by protocol) are separated from technical failures.
- Missing ground truth (NOT MEASURABLE) is separated from mapping failures.
- Track B is classified only at the mechanism level visible in the agent's own outputs: termination cause, failed-action error classes, blocked-by-scope counts, advertised-unexecuted reasons. Application internals are not inspected and no fix is proposed for a specific target.

## 9. Phase 6 and 7 plans

- **Phase 6.** One generalization row per architecture category. Columns: environments; results; the failure categories observed; whether evidence comes from more than one application. A single successful fixture is never generalized to its category.
- **Phase 7.** For every trial, three representations are compared:
  - historical Graph A (states, actions, workflows, features, edges);
  - offline ACG reconstruction (`import_run_artifact` + `materialize`);
  - live ACG (`LiveACG` synced from the run's evidence sink).

  The comparison covers content counts, statuses and gaps, plus, on annotated labs, recall: Graph A feature action-based recall, offline M1a and live M1a. A richer graph is not counted as a more complete map, and an observation is not counted as verification.

## 10. Analysis and reporting

Deliverables:
- `AGENT1_COMPREHENSIVE_BENCHMARK_REPORT.md`, covering the 15 sections of the brief;
- `evaluation/results/agent1_comprehensive_summary.json`;
- answers to Q1–Q10;
- at most five prioritized research opportunities. None is implemented in this milestone.

After the evaluation, the full regression suite is run. Only reports and aggregate artifacts are committed and pushed, to the existing branch; there is no merge to main and no force-push. The report is honest even if results are disappointing.
