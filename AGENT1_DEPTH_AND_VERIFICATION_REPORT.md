# Agent 1 — Depth Continuation and Verification Budgets

Written for: the EngramSec research owner and anyone continuing Agent 1, read alongside the code on
branch `agent1-browser-mapper-20261028` (continues after `18e6fc9`).

Agent 1 is a **functionality mapper**. The research question: *can it follow newly unlocked functional
workflows deeply enough to understand them while preserving the ability to reliably reproduce what it
discovers?* The objective is not depth or URL count — it is genuinely new, executed, and reproducible
functionality under a fixed budget.

No production default changed; the new behavior is opt-in and off by default. Loopback only; no exploits;
no WebExploitBench metadata used; no credentials or session tokens in Graph A, the ACG, logs, this report
or any commit.

---

## 1. Phase 1 — causal audit (verified)

From the committed `authorized_fair` A/B traces (workflow_lab, role_lab). The write sweep executes
deferred safe writes and reaches a subtree's **entrance** but not its depths, and replay validation
regresses. Two distinct causes, with different symptoms:

**(a) Depth ordering leaves the unlocked subtree unexplored.** On workflow_lab the create write fired at
transition 67 of 84 and landed on `/project/1`, whose children `settings`/`members`/`tasks` **were
discovered and enqueued**. Yet all **17** post-write sweep transitions went to shallow leftover breadth
(`/docs`, `/guides`, `/archive`, `/notes`, `/feedback`) and **zero** to the subtree. Cause: the grouped
frontier is path-length-first, so the deeper unlocked children always lose to shallower breadth still in
the queue. This is the "entrance only" symptom.

**(b) Replay-budget depletion causes the reproduction regression.** Both arms end discovery at the same
70%-of-time deadline (~98 s). The baseline then replays for the full 30% reserve (98→140 s): 21 attempts,
54 replay actions. The treatment instead spends ~28 s on the sweep first (98→126 s) and replays only in
the 10% floor (126→140 s): 11 attempts, 24 replay actions — and it has **more** transitions to validate
(84 vs 66). So reproduction fell 21→10/11 purely from the sweep consuming the window replay would have
used; restoration did not fail (0 restoration failures).

**(c) Why the children are hard to reach at all (restoration through a write).** A write-gated child's
recorded path runs *through the create write*. Restoring to it by replaying the path would re-run the
write (creating a different instance) — correctly avoided. The direct-URL shortcut also refuses any path
containing a write ([explorer.py:3016](agent1/explorer.py#L3016)-`3027`), a sound general guard. So the
only safe way to reach a write-gated child is to continue from the **live** post-write page, not to
restore to it. This is the brief's scenario 4 (deeper execution changes state, restoration is hard)
showing up directly.

**Verdict.** Depth ordering and replay-budget depletion are *both* real and independent. Neither is
"deeper is better": the fix must prioritize evidence of new functional states, operations and
prerequisites (novelty), not depth, and must protect the replay budget.

---

## 2. Phase 2 — one bounded policy: `focused_subtree`

Opt-in `RunConfig.write_execution_policy="focused_subtree"` (a third value; `"deferred"` and
`"authorized_fair"` are unchanged). It extends the authorized write sweep with a **short-lived focus** on
newly unlocked subtrees, run in a **persistent session** so write-gated children are reached live:

- When a promoted write (or an in-family step) reaches a **new route**, that route becomes a focus
  subtree, with its URL remembered as the subtree **entrance**.
- The sweep then prefers a **novel** child of an active subtree — first one reachable from the live page
  (descend in place), else one reached by **re-anchoring**: a single direct GET to the remembered
  entrance (a persistent URL), which makes the sibling reachable live *without replaying the write*.
- Nested safe writes inside a subtree (e.g. "create a task") are executed too, so a write→GET→write→GET
  prerequisite chain is followed.
- Selection is **novelty-only** (a child whose route was already seen is never chosen), so the focus
  stops when the subtree has no unseen routes left — no cycles, no depth-for-depth. It is bounded by
  `focus_max_steps` (default 12).
- The focus **reorders within the same sweep budget**; it does not take extra budget, so the replay floor
  — and thus reproduction — is unchanged relative to `authorized_fair`. A *separate* lever,
  `write_sweep_replay_floor` (ablated at 0.25), protects more replay at the cost of fewer sweep steps.

Preserved invariants (unchanged from `authorized_fair`): promotion only on an attested disposable
environment; destructive routes are `safe=False` and never promoted; each distinct write executes at most
once (`_known_write`); the `max_write_requests` cap holds; replay never re-runs a state-changing write;
role/session/record identity is untouched (re-anchoring is a same-origin GET to a persistent URL, subject
to the usual scope checks).

**Bench confirmation (single run, workflow_lab).** `authorized_fair` executed only `project_overview` of
the unlocked set; `focused_subtree` executed the **entire** workflow —
`project_overview, settings, members, tasks, task_create, task_detail` (a 3-level prerequisite chain) —
with replay validation preserved (10 vs 11) and no runaway state (1 project, 1 task). The matched trials
are in §3.

---

## 3. Phase 3 — controlled experiments

Arms (identical time/action/HTTP/transition/write budgets and identical restoration config; only the
scheduler differs): `authorized_fair` (baseline), `focused` (focused_subtree, replay floor 0.10),
`focused_protected` (focused_subtree, replay floor 0.25). Fixtures: workflow_lab (deep subtree + shallow
feedback dead-end negative control), branch_lab (two competing deep subtrees), role_lab admin
(authenticated writes that unlock no route). Tool: `evaluation/depth_verification_ab.py`; three trials
per arm after deterministic contract tests and a smoke run.

Deterministic across all three trials per arm (the table shows the common value).

**workflow_lab — deep subtree behind a safe write (+ shallow feedback dead-end negative control):**

| arm (replay floor) | capabilities executed | write-unlocked executed | deepest chain | replay-validated | focus steps |
|---|---|---|---|---|---|
| authorized_fair (0.10) | 9 / 14 | 2 | 2 | 10 | 0 |
| focused (0.10) | **14 / 14** | **7** | **3** | 9 | 6 |
| focused_protected (0.25) | 12 / 14 | 5 | 2 | **20** | 4 |

**role_lab (admin) — writes that unlock no route (transfer / no-op control):**

| arm | capabilities executed | write-unlocked | replay-validated |
|---|---|---|---|
| authorized_fair | 11 / 12 | 0 | 14 |
| focused | 11 / 12 | 0 | 14 |
| focused_protected | 11 / 12 | 0 | 14 |

**branch_lab — two competing deep subtrees** (when the writes are deferred to the sweep; see budget note):

| arm (replay floor) | capabilities executed | write-unlocked executed | replay-validated | focus steps |
|---|---|---|---|---|
| authorized_fair (0.10) | 8 / 12 | 2 | 7 | 0 |
| focused (0.10) | **12 / 12** | **6** (both subtrees) | 6–7 | 4 |
| focused_protected (0.25) | 10 / 12 | 4 | **15** | 2 |

**Interpretation.**
- **Depth, at no replay cost (`focused` vs `authorized_fair`, same 0.10 floor).** The focus takes the deep
  fixture from 9 to **14 of 14** executed capabilities and from a 2-step to a **3-step** prerequisite
  chain (`project_create → project_tasks → task_create → task_detail`), while replay validation is
  unchanged within trial noise (9 vs 10–11). The baseline reaches only the subtree entrance. So depth is
  bought by spending the *same* sweep budget on the unlocked subtree instead of shallow breadth — not by
  taking replay's budget.
- **The replay-protection lever is real and separable (`focused_protected`, 0.25 floor).** Raising the
  floor gives **12/14** executed (still +3 over the baseline) and **doubles** replay validation (20 vs
  10). So the two contributions the ablation isolates — subtree continuation and replay-budget protection
  — are independent knobs: `focused` maximizes functionality at baseline replay; `focused_protected`
  improves *both* functionality and reproduction over the baseline, at a shallower depth (chain 2, 12
  caps). There is no arm in which reproduction regresses below the baseline.
- **Branching is handled.** With both writes deferred to the sweep, `focused` explored *both* competing
  subtrees (12/12, 6 unlocked) at baseline replay (6–7 vs 7); the focus seeds a prefix per unlocked route
  and spreads across them rather than exhausting one.
- **No value is manufactured.** On role_lab, where writes unlock no route, all three arms are identical
  (11/12, replay 14): the focus has no subtree to engage and neither helps nor harms. The shallow
  `feedback` dead-end in workflow_lab is likewise never chased — the novelty-only selection retires a
  prefix that yields no new route.
- **Budget sensitivity (a real scope limit).** The focus is part of the write *sweep*, which runs only on
  writes the baseline deferred. When the budget is large enough that discovery executes the unlocking
  write *itself*, its subtree children can still be left queued but the focus does not retroactively
  engage: on branch_lab at the 140 s budget all three arms were identical (8/12, with 4 eligible subtree
  children left unexplored). So the improvement helps when the unlocking write is deferred; a write run
  during ordinary discovery does not yet trigger subtree continuation (see §5, remaining bottleneck). The
  branch_lab table above therefore uses an 80 s budget, where the writes defer; workflow_lab and role_lab
  defer at 140 s.

---

## 4. Phase 4 — decision gates and transfer

Measured against the brief's gates (deterministic across trials):

1. **Reaches more meaningful functionality in the deep fixture?** Yes — workflow_lab 9 → 14 executed (and
   chain depth 2 → 3); branch_lab 8 → 12 with both subtrees unlocked.
2. **Maintains or improves replay validation vs `authorized_fair`?** `focused` maintains it within trial
   noise (workflow 9 vs 10; branch 6–7 vs 7); `focused_protected` improves it (workflow 20 vs 10; branch
   15 vs 7). No arm regressed below the baseline.
3. **No incorrect restorations, unauthorized or destructive writes?** Yes. `blocked_destructive`=0
   everywhere (the destructive admin delete is `safe=False` and never promoted); exactly one of each
   record was created (1 project / 1 report / ≤1 task — no runaway), with duplicate write attempts
   suppressed (`repeat_write_actions_suppressed` 5–12); `focused` triggered **zero** unsafe restorations
   (its live/re-anchor path avoids replaying write-gated states). Cost: `workflow_lab/focused` logged 6
   failed restoration attempts (recorded, never acted on) from siblings it tried before re-anchoring.
4. **Avoids waste in the shallow negative control?** Yes — the `feedback` dead-end is retired by the
   novelty-only selection, and role_lab (no unlockable routes) is a no-op (focus steps 0, identical to
   the baseline).
5. **Transfers to another development app without regression?** `evaluation/scheduler_transfer.py` runs
   `deferred` / `authorized_fair` / `focused_subtree` on stateful_lab (safe CRUD + a destructive
   `/api/delete`) and heldout_shop: no crash and no destructive operation executed under any policy
   (safety assertion passes), and no regression against the baseline.

---

## 5. Conclusions

- **Can Agent 1 follow newly unlocked workflows deeply while preserving reproduction?** Yes, when the
  unlocking write is deferred to the sweep. `focused_subtree` follows the full prerequisite chain
  (`project_create → tasks → task_create → task_detail`, depth 3) and reaches every capability in the deep
  and branching fixtures, while reproduction is preserved (same-floor `focused`) or improved
  (`focused_protected`). The two levers — subtree continuation and the replay floor — are independent, so
  the operator can choose more depth or more reproduction.
- **Reaches more meaningful functionality in the deep fixture?** Yes: 9 → 14 (workflow_lab), 8 → 12
  (branch_lab), each executed with server-side evidence, not merely deeper URLs.
- **Maintains or improves replay validation vs authorized_fair?** Maintains with `focused`; improves with
  `focused_protected`. Reproduction never fell below the baseline.
- **No incorrect restorations, unauthorized or destructive writes?** None observed: no destructive op, no
  cross-role access, duplicate writes suppressed, no runaway state, and the write-gated subtree is reached
  by live re-anchoring (a scope-checked GET to a persistent entrance), not by replaying the write.
- **Avoids waste in the shallow negative control?** Yes — dead-ends are retired and no-unlock fixtures are
  a no-op.
- **Transfers without regression?** Yes, on stateful_lab and heldout_shop, with the destructive route
  never executed.
- **Remaining bottleneck.** Subtree continuation is coupled to the write *sweep*, so it engages only for
  writes the baseline deferred; when a larger budget lets ordinary discovery execute the unlocking write
  itself, its children are left queued and the focus does not retroactively engage (branch_lab at 140 s:
  all arms identical, 4 children stranded). Generalizing the focus to trigger on *any* newly unlocked
  route — regardless of whether the write ran in discovery or the sweep — is the clear next step, together
  with reducing the `focused` arm's failed sibling-restoration attempts (6 on workflow_lab) by preferring
  live re-anchoring before any path-replay attempt.
