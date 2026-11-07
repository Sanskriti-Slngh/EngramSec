# Agent 1 — State-Changing Workflow Exploration & Scheduling

Written for: the EngramSec research owner and anyone continuing Agent 1, read alongside the code on
branch `agent1-browser-mapper-20261028` (continues after `79c288c`).

Agent 1 is a **functionality mapper**, not a vulnerability detector. The question here is whether the
write-action deferral and the discovery/replay budget split stop it from discovering and reproducing
deeper functionality — the functionality that only exists after a safe, authorized state change.

No production default changed; the one new behavior is opt-in and off by default. Loopback only; no
exploits; no WebExploitBench vulnerability metadata used; no credentials or session tokens in Graph A,
the ACG, logs, this report, or any commit.

---

## 1. Phase 1 — scheduler diagnosis (verified, not inferred)

Audited the grouped/multidimensional frontier, the −45 write penalty
([explorer.py:2226](agent1/explorer.py#L2226)), the discovery/replay budget split
([explorer.py:1904](agent1/explorer.py#L1904)–`1946`), and the discovery termination conditions
([explorer.py:2337](agent1/explorer.py#L2337)). Evidence comes from the existing matched role_lab traces
and a **read-only** terminal-frontier capture (`record_unexecuted_frontier`, which records the leftover
frontier and the exit reason without changing any scheduling decision). Tool:
`evaluation/scheduler_diagnosis.py`.

**Findings (admin arm; user arm identical in shape):**

| question | measured answer |
|---|---|
| safe writes discovered | 3 (`order_create`, `profile_update`, `admin_settings_update`) |
| of those, executed | **0** (zero non-GET requests fired in the whole run) |
| when they became available | observation 24 of 111 — early |
| what was chosen after they were available | **43 link actions, 0 writes** |
| their priority at termination | **−42.0** (form-submit base 3.0 minus the 45 penalty) |
| discovery exit reason | **exploration time deadline** (77 s = 70% of 110 s) |
| budget actually used at exit | 171 / 260 actions — **34% of the action budget unused** |
| restoration failures | **0** |
| safety blocks | only `admin_user_delete` (destructive) is safety-blocked — correct |
| still queued when discovery ended | the 3 safe writes, plus ~41 replay-untested paths |

**Verified cause: priority, not budget, restoration, or safety.** The safe writes sit at −42, below every
navigation link, so discovery keeps choosing links; discovery then stops at the 70%-of-time exploration
deadline — with a third of the action budget still unspent and the writes still queued. It is therefore
not frontier exhaustion (eligible write actions remain), not a hard budget cap (headroom remained), not a
restoration failure (none), and not safety (the safe writes passed; only the destructive delete is
blocked). The −45 penalty is the operative cause.

**Is the penalty preventing functional discovery?** It demonstrably prevents write *execution* (0 of 2–3
safe writes). Whether that also costs *functional discovery* depends on whether a write unlocks further
functionality. role_lab's writes mutate content on already-mapped routes and unlock no new route, so
there the penalty costs the write capabilities themselves. Phase 3 adds a fixture where a safe write
unlocks a deeper subtree, to measure the discovery cost directly.

---

## 2. Phase 2 — one bounded improvement: an authorized write sweep

Opt-in `RunConfig.write_execution_policy="authorized_fair"` (default `"deferred"` keeps today's behavior).
After ordinary discovery finishes, and only on an **operator-attested disposable environment**, a bounded
sweep ([explorer.py `_authorized_write_sweep`](agent1/explorer.py)) promotes the **safe** writes still
queued in the frontier, executes each one, and explores whatever they unlock — then replay runs as usual.
The write deprioritization during normal discovery is unchanged; this only gives the queued writes a fair
turn afterward, which is exactly where the diagnosis showed the budget was going unused.

It preserves every required invariant:
- **Strict read-only** — `would_allow` returns false unless the mode is `disposable`, so a read-only run
  promotes nothing.
- **Disposable attestation + caps** — the sweep runs only when `effective_write_policy=="disposable"` and
  an `environment_attestation` is present; every write still passes `WritePolicy.decide`, so the
  `max_write_requests` cap holds.
- **Destructive restrictions** — destructive routes are `safe=False` and fail `would_allow`, so they are
  never promoted (and still blocked at the request level).
- **No uncontrolled replay of writes** — each distinct write executes at most once (`_known_write`);
  replay still excludes state-changing workflows.
- **Role/session isolation** — unchanged; the sweep touches neither the session nor `context_label`.
- **Replay budget** — a `write_sweep_replay_floor` (default 10%) is held back so replay is not starved.
- **Evidence** — writes execute through the normal path, so prerequisite and state-change evidence in
  Graph A / the ACG is recorded exactly as before.

A write is prioritized only when the environment and the action are authorized; the penalty is not
removed globally.

---

## 3. Phase 3 — matched A/B (baseline vs authorized_fair)

Identical budgets, write policy, attestation and limits in both arms; the only difference is
`write_execution_policy`. Fixtures: `workflow_lab` (anonymous; a safe write unlocks a deeper subtree, a
second safe write unlocks only a dead-end — the negative control) and `role_lab` (authenticated admin;
safe writes that unlock no new route). Tool: `evaluation/workflow_scheduling_ab.py`; the read-only
frontier recorder is on in both arms, so deferred writes are counted directly.

Deterministic across all three trials per arm; the table shows the common value.

| metric | workflow_lab base | workflow_lab treat | role_lab(admin) base | role_lab(admin) treat |
|---|---|---|---|---|
| capabilities executed | 5 / 14 | **9 / 14** | 8 / 12 | **11 / 12** |
| safe writes executed | 0 | 2 | 0 | 3 |
| writes still queued at discovery end | 2 | 2 | 3 | 3 |
| write-unlocked capabilities executed | 0 | 2 | 0 | 0 |
| replay-validated transitions | 21 | 10 | 14 | 13 |
| browser actions / executed capability | 48.8 | 30.0 | 30.8 | 27.4 |
| projects created (no runaway) | 0 | 1 | — | — |
| duplicate writes suppressed | 0 | 3 | 0 | 2 |
| destructive operations executed | 0 | 0 | 0 | 0 |
| restoration failures | 0 | 0 | 0 | 2 |

**Interpretation.**
- **role_lab (writes that unlock no route).** The sweep executes the three safe admin writes the baseline
  leaves deferred (0 → 3: `order_create`, `profile_update`, `admin_settings_update`), raising executed
  capability 8 → 11 (recall 0.67 → 0.92). Because these writes are terminal — they change content on
  already-mapped routes and open no subtree — the sweep diverts almost no replay budget: reproduction is
  essentially unchanged (14 → 13). A clean gain.
- **workflow_lab (a write that unlocks a subtree) + negative control.** The baseline never creates a
  project, so the entire `/project/*` subtree is 404 and undiscovered — it executes 5 capabilities and
  **zero** of the unlocked set. The treatment executes the create write and reaches `project_overview`, a
  route the baseline cannot see at all, plus the feedback write; executed capability rises 5 → 9. The
  **negative control confirms the method does not manufacture value**: `feedback_submit` unlocks only the
  dead-end `feedback_thanks`, whereas `project_create` unlocks the real `project_overview`. The cost is
  reproduction: replay-validated transitions fall 21 → 10, because the sweep reuses budget the baseline
  would spend on replay to execute and explore the unlocked subtree. This tradeoff is largest exactly when
  a write unlocks a large subtree, and it is tunable (the replay floor and the total budget), not a
  fundamental loss.
- **Reached the subtree entrance, not its depths.** The treatment reliably executes the unlocking write
  and maps the subtree's entrance (`project_overview`), but under this budget it does not reach
  `settings`/`members`/`tasks`: inside the sweep, those deeper links still lose to shallower navigation
  under the same path-length-first ordering diagnosed in Phase 1. So the sweep opens the door; fully
  walking the room needs more post-discovery budget or a depth-first sweep order (see §5).
- **Safety held in every trial.** No destructive operation ever executed (`blocked_destructive`=0; the
  admin delete is `safe=False` and is never promoted); exactly one project was created (no runaway
  state); duplicate write attempts were suppressed (no redundant state changes); prerequisite and
  state-change evidence recorded normally; role/session context unchanged.

---

## 4. Phase 4 — transfer and ResourceCache correctness

**Scheduler transfer.** `evaluation/scheduler_transfer.py` runs both policies on two independent
development apps under identical disposable+attested config. On `stateful_lab` (server-rendered CRUD with
safe creates/updates **and** a destructive `/api/delete`) both policies run without crashing and the
destructive route is never executed (`blocked_destructive` gate intact, no destructive request fires, no
destructive entry in the server log). On `heldout_shop` (an independent, read-mostly site) both policies
run cleanly; `authorized_fair` promoted two safe writes but executed **zero new** ones — they had already
run during discovery and `_known_write` suppressed re-execution, so there were no redundant state changes.
Across both fixtures and both policies the harness's safety assertion passed: **no destructive operation
executed**. The scheduler transfers without regression and preserves safety.

**ResourceCache safety (kept separate from the scheduler change).** The static-asset cache from the
previous milestone was hardened and tested so its contribution is not confused with scheduling, and so it
can never serve session-dependent data:
- only `script`/`stylesheet`/`font`/`image` GETs are eligible — never `xhr`/`fetch` (mutable APIs) or
  `document` (pages);
- a response is not stored if it is non-200, `no-store`/`no-cache`/`private`, or `Vary: Cookie` /
  `Vary: Authorization` / `Vary: *` (session-dependent);
- `Set-Cookie` is stripped and never replayed;
- the cache is **per run** (one per Explorer), so one account's assets can never be served to another —
  there is no shared or global store.

Covered by `tests/test_resource_cache.py` (eligibility, Vary, per-instance isolation, bounds).

---

## 5. Conclusions

- **Is the write penalty demonstrably preventing functional discovery?** Yes. Phase 1 proved it prevents
  write *execution* (0 of 3 safe writes on role_lab, each pinned at priority −42, discovery ending with a
  third of the budget unused). Phase 3 showed the downstream cost: when a write gates further
  functionality, the deferral leaves that whole subtree undiscovered — the baseline executes **zero**
  unlocked capabilities and `/project/*` stays 404 and invisible. So the penalty costs both the writes and
  anything behind them.
- **Does improved scheduling uncover deeper functionality?** Yes. The sweep executes the create write and
  reaches `project_overview` (invisible to the baseline) and executes the three safe admin writes the
  baseline defers; executed capability rose 5 → 9 and 8 → 11 across the two fixtures.
- **Does it improve execution and reproduction, not merely action counts?** Execution: clearly (+4 and +3
  capabilities, and fewer actions per executed capability — 48.8 → 30.0, 30.8 → 27.4). Reproduction: it is
  *preserved* for terminal writes (role_lab 14 → 13) and *traded* for discovery when a write opens a large
  subtree that the sweep then explores (workflow_lab 21 → 10). So it is not action inflation — more
  distinct capabilities are executed — but reproduction of the long tail is a tunable cost, not a free win.
- **Safety and runtime tradeoffs.** No invariant was violated in any trial: no destructive operation
  executed, writes only on an attested disposable environment and under the request cap, duplicate writes
  suppressed, no cross-role access, replay never re-ran a write, and reset was by process isolation.
  Runtime: the sweep spends post-discovery budget (role_lab +55 actions, workflow_lab +26) within the same
  total limits, drawn from the replay reserve — which is the source of the reproduction tradeoff above.
- **Is the approach general enough to adopt?** As an **opt-in**, yes. It is bounded, authorization-gated,
  preserves every required invariant, helps exactly where the diagnosis predicted, and transfers safely to
  independent fixtures (§4). It should stay opt-in rather than default, because the replay tradeoff means
  it is worth enabling specifically when mapping authorized state-changing functionality with adequate
  budget, not for every run.
- **What bottleneck remains afterward?** Depth. The sweep reliably opens a write-gated subtree but, under a
  bounded budget, reaches its entrance and not its depths, because the same path-length-first ordering that
  deprioritized the write also deprioritizes the deep links it unlocks; and the sweep trades replay budget.
  The next step is a depth-first post-discovery exploration of freshly unlocked areas plus an adaptive
  replay reserve, so newly executed workflows are both fully mapped and reproduced.
