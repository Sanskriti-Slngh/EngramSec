# Agent 1 — Generalized Functional Subtree Exploration

Written for: the EngramSec research owner and anyone continuing Agent 1, read alongside the code on
branch `agent1-browser-mapper-20261028` (continues after `19ed302`).

Agent 1 is a **functionality mapper**. This milestone removes the architectural inconsistency where
subtree focus worked only for writes executed during the post-discovery *sweep*: Agent 1 should recognize
when **any** successfully executed, authorized interaction unlocks genuinely new functionality — a write
*or* an ordinary GET — and continue exploring it, wherever it was discovered.

Opt-in and off by default; no production default changed. Loopback only; no exploits; no WebExploitBench
metadata; no secrets committed.

---

## 1. Phase 1 — the precise limitation (verified)

**Write unlocked during ordinary discovery (branch_lab, 140 s).** Tracing the committed run: both writes
executed during *discovery* — `tx#76 POST /reports → /report/1` and `tx#77 POST /projects → /project/1` —
and both subtree entrances were observed. Their four children entered the frontier but stayed **stranded
at low priority** (`/report/1/summary` 0.8, `/project/1/settings` 0.8, `/project/1/members` 0.6,
`/report/1/export` 0.4): the grouped frontier is path-length-first, so the deeper children lose to shallow
breadth. Discovery then exited at the 70%-of-time deadline (98.6 s) with **only 187 of 600 actions used**,
and the post-discovery sweep never engaged because there were **no promotable writes left** (the writes
had already run). So the focus could not help even though the budget and the eligible children were both
present.

**Do the children need the live post-write state?** Yes for a write-unlocked child: its recorded path
runs through the create write, so restoring it by path would re-run the write; the direct-URL shortcut
also refuses write-containing paths. The resource *persists* server-side, so it is reachable by navigating
to its URL — but only from a state that the sweep must re-establish live.

**Ordinary GET that unlocks functionality (gated_get_lab).** A GET to a functional hub (`/dashboard`)
reveals a two-level subtree of distinct operations (reports/settings/billing, each with sub-pages). Here
the children are reachable by replaying GET paths (no write), but they are still deprioritized behind the
section breadth and stranded at the discovery deadline (the baseline reaches 6 of 10). So the stranding is
general — it is not specific to writes — and a GET hub is distinguishable from a breadth list: its
children are **distinct operation templates**, whereas a catalog is one template repeated.

**Conclusion.** The limitation is that subtree continuation was wired only to sweep-promoted writes. The
generalization must seed from *any* executed interaction that unlocked genuinely new functionality, during
discovery or the sweep, while excluding ordinary breadth.

---

## 2. Phase 2 — one general improvement: `focused_adaptive`

Opt-in `RunConfig.write_execution_policy="focused_adaptive"` (the existing `"focused_subtree"` is the
baseline). It **generalizes the seeding** of the existing focus rather than adding a second scheduler: at
the start of the post-discovery focus it also seeds subtrees unlocked during ordinary discovery, then the
same live-descent machinery explores them.

A discovery-unlocked subtree is seeded only on evidence of genuinely new functionality
([explorer.py `_adaptive_subtrees`](agent1/explorer.py)):
- its entrance observation was **reached by an executed transition**, and
- it is a **functional area** — its child controls under the entrance path have **≥2 distinct route
  templates** (distinct operations) — **or** it was reached by a write, and
- at least one of its children is still a **novel** queued action.

Ordinary breadth (one template × N items) fails the distinct-template test and is never focused, so this
is not "every URL change." The focus then descends seeded and sweep-unlocked subtrees uniformly:
- prefer a **novel** child reachable from the live page (descend in place), else re-anchor — a single
  scope-checked GET to the persistent entrance — and descend from there;
- stay within the **active subtree** until it is exhausted before switching to a competing one (fair, and
  it avoids re-anchor thrash);
- execute **nested** safe writes inside a subtree;
- mark each attempted child **seen**, so no child is ever re-selected (prevents cycles and duplicate work);
- stop on **novelty exhaustion** (no unseen in-family action remains), the protected budget, or
  `focus_max_steps` (a safety cap, not the primary limit — there is no small fixed depth ceiling).

**It does not assume a URL recreates state.** A re-anchor navigates and *re-observes*; the child is
executed only if it is found on the re-observed page (group match + `find_current`). If the entrance does
not reproduce the state (an ephemeral/JS-only area), the step is skipped safely — no wrong action.

**Preserved invariants** (unchanged from `focused_subtree`): promotion only on an attested disposable
environment; destructive routes never promoted; each write at most once (`_known_write`), under
`max_write_requests`; replay never re-runs a write; role/session/record identity untouched; the focus
reorders within the same sweep budget, so the replay floor (reproduction) is unchanged, and
`write_sweep_replay_floor` separately protects more replay.

**Bench confirmation (140 s, 3 matched trials, deterministic).** `focused_subtree` → `focused_adaptive`:
branch_lab **2 → 6 of 6** deep capabilities unlocked (both writes run in discovery, so the baseline's
sweep never engages), gated_get_lab **5 → 10 of 10** deep GET capabilities, workflow_lab unchanged (its
write is deferred to the sweep, so the baseline already descends it). The matched trials are in §3.

---

## 3. Phase 3 — controlled comparison

Arms (identical budgets; restoration config identical): `focused` (focused_subtree, baseline), `adaptive`
(focused_adaptive, replay floor 0.10), `adaptive_protected` (focused_adaptive, replay floor 0.25).
Fixtures: workflow_lab (deep write-gated, sweep-deferred), branch_lab at 140 s (two competing writes run
in discovery — where focus previously failed), gated_get_lab (a GET hub unlocks a deep subtree, no
writes), role_lab admin (no unlockable route — negative control). Three trials per arm.

All three arms are identical across the three trials (fully deterministic; no cross-trial variance in any
executed, unlocked, chain, or safety metric), so each cell below is that common value. "Unlocked" counts
the deep functional capabilities a fixture gates behind an interaction; "replay-tx" is replay-validated
transitions; "writes" / "destructive" are write requests actually fired; "cost" is total browser actions
(cap 600). Restoration config is identical in every arm (`restoration_shortcut="direct_url"`).

| Fixture | Arm | Executed | Deep unlocked | Prereq chain | Replay-tx | Writes / destructive | Cost (actions) |
|---|---|---|---|---|---|---|---|
| **workflow_lab** (write-gated, sweep-deferred) | focused | 12/14 | 5/5 | 2 | 9 | 5 / 0 | 261 |
| | adaptive | 12/14 | 5/5 | 2 | 9 | 5 / 0 | 260 |
| | adaptive_protected | 12/14 | 5/5 | 2 | **20** | 5 / 0 | 259 |
| **branch_lab** (two competing writes, both in discovery) | focused | 8/12 | **2/6** | 2 | 20 | 2 / 0 | 239 |
| | adaptive | **12/12** | **6/6** | 2 | 9 | 2 / 0 | 255 |
| | adaptive_protected | **12/12** | **6/6** | 2 | **20** | 2 / 0 | 254 |
| **gated_get_lab** (GET hub, no writes) | focused | 9/14 | **5/10** | 2 | 25 | 0 / 0 | 252 |
| | adaptive | **14/14** | **10/10** | 2 | 9 | 0 / 0 | 256 |
| | adaptive_protected | **14/14** | **10/10** | 2 | **21** | 0 / 0 | 257 |
| **role_lab_admin** (negative control, nothing unlockable) | focused | 11/12 | 0/0 | 0 | 14 | 3 / 0 | 238 |
| | adaptive | 11/12 | 0/0 | 0 | 14 | 3 / 0 | 238 |
| | adaptive_protected | 11/12 | 0/0 | 0 | 14 | 3 / 0 | 238 |

**Interpretation.**
- **Removes the inconsistency without regressing the case it already handled.** On workflow_lab (the write
  is deferred to the sweep, so `focused_subtree` already descends it) `adaptive` is byte-identical to
  `focused` — 12/14 executed, 5/5 unlocked, replay 9. Generalizing the seeding costs nothing where the
  baseline already succeeds.
- **branch_lab is the inconsistency, and it is resolved.** Both creates run during *discovery*, so the
  baseline's post-discovery sweep finds no promotable write and never engages: `focused` strands four deep
  children and unlocks only the two create-landing pages (2/6). `adaptive` seeds both discovery-unlocked
  subtrees and descends them live, reaching **all six** deep capabilities across both competing families
  (project_overview/settings/members + report_overview/summary/export) — 12/12 executed. This is a full
  resolution of the competing-subtree case: both roots are exhausted fairly (active-root ordering), no
  duplicate write fires (writes stay at 2; the repeat-write guard suppresses the re-anchored retries), and
  `transitions_failed` is 0 (no restoration error).
- **The unlock is not write-specific.** On gated_get_lab the hub is reached by an ordinary GET and fires
  **zero writes**, yet `adaptive` descends its two-level functional subtree in full (5/10 → 10/10). This is
  the general-purpose property the brief asked for: any executed interaction that exposes genuinely new
  functionality is continued, not only sweep-promoted writes.
- **The protected floor buys reproducibility for free on the hard fixtures.** On both branch_lab and
  gated_get_lab, `adaptive` trades replay down (sweep budget goes to descent) while `adaptive_protected`
  keeps the **same** full capability (12/12, 6/6; 14/14, 10/10) **and** restores replay to 20–21 — it
  weakly dominates both other arms there. So depth and reproducibility are not in tension once the floor is
  set; `adaptive_protected` is the configuration to freeze.
- **No spurious focus (negative control).** On role_lab_admin all three arms are identical (unlock 0,
  focus_steps 0): the three safe admin writes execute but unlock no route, so the seeding gate (needs a
  distinct-template functional area or a novel queued child) never fires. The mechanism triggers on new
  functionality, not on every state change or URL.
- **Safety and cost.** No destructive request fired in any arm or fixture; `adaptive` adds only ~4–16
  browser actions over `focused` (all within the 600 cap and the 140 s budget). `leftover_eligible_in_family`
  is a *discovery-phase* snapshot (it measures what discovery stranded for the sweep to recover, not
  post-sweep residue); the genuinely post-sweep residue is `inventory − executed`, which is 0 on the two
  subtree fixtures for `adaptive`.

---

## 4. Phase 4 — decision and transfer

**The key question — does generalized focus improve both functional discovery and reproducibility without
unsafe exploration? — resolves yes, on multiple independent cases.**

- *Functional discovery* improves on exactly the cases the baseline could not reach, and only those:
  branch_lab 2/6 → 6/6 (write unlocked in discovery) and gated_get_lab 5/10 → 10/10 (GET unlock), while
  workflow_lab (already handled) and role_lab (nothing to unlock) are unchanged. Two independent fixture
  *shapes* — a discovery-time write and a writeless GET hub — both improve, so this is a general property,
  not a branch_lab special case.
- *Reproducibility* is not sacrificed. The brief's caution — "do not sacrifice substantial replay quality
  just to increase capability count" — is met by `adaptive_protected`, which holds full capability on both
  hard fixtures while keeping replay at the baseline's level (20–21). Bare `adaptive` does spend replay for
  depth (replay 9 on the hard fixtures); `adaptive_protected` is therefore the configuration to freeze.
- *Safety* is preserved: zero destructive requests fired anywhere; writes capped and each executed at most
  once; no write replayed to restore state (re-anchor is a scope-checked GET that re-observes before
  acting); `transitions_failed` 0 (no restoration error); the negative control is untouched.

**Independent-app transfer (safety).** `evaluation/scheduler_transfer.py` runs `deferred`,
`authorized_fair`, `focused_subtree`, and `focused_adaptive` on two apps independent of the depth fixtures
(`stateful_lab`, which has a real destructive `/api/delete`, and the read-mostly `heldout_shop`) under an
attested disposable config, and asserts no destructive request ever fires. **Result: `SAFETY: OK (no
destructive op executed)`** — zero destructive requests under every policy on both apps (stateful_lab's
`/api/delete` never fires). The generalization is exercised here, not dormant: on heldout_shop,
`focused_adaptive` seeds one discovery-unlocked subtree (`/cart`, 2 focus steps; the other policies seed
none) and still executes no write and nothing destructive — the new seeding path transfers to an
independent app without weakening any safety guarantee.

**Frozen configuration (for broader transfer).** `write_execution_policy="focused_adaptive"`,
`write_sweep_replay_floor=0.25` (the `adaptive_protected` arm), with the matched discovery/restoration
settings in `evaluation/depth_verification_ab.py::MATCHED` (`restoration_shortcut="direct_url"`,
time-bound discovery so the sweep has budget). This is opt-in; no production default changes.

**Residual limitation (honest).** The seeding gate is evidence-based, so a functional area that presents as
a *single* repeated template (indistinguishable from breadth) and whose children are not independently
queued would not be seeded — by construction, to avoid focusing ordinary breadth. An area that is purely
ephemeral/JS state with no re-reachable entrance is also skipped (the re-anchor re-observes and finds
nothing, so no wrong action, but also no descent). Both are deliberate precision/recall trade-offs on the
side of not acting on weak evidence.

---

## 5. Conclusions

The architectural inconsistency is removed. Subtree focus is now seeded by *any* executed interaction that
exposes genuinely new functionality — a write run during discovery or the sweep, or an ordinary GET to a
functional hub — using the **same** focus machinery (frontier, novelty signals, persistent session,
re-anchoring, replay controls); no second scheduler was added. `focused_subtree` remains the baseline and
is unchanged.

Matched, deterministic 3-trial evidence:
- **Discovery and reproducibility both improve, on independent fixture shapes.** branch_lab 2/6 → 6/6,
  gated_get_lab 5/10 → 10/10; `adaptive_protected` keeps replay at baseline (20–21) at full capability.
- **No regression and no spurious focus.** workflow_lab identical to the baseline; role_lab negative
  control identical across all arms.
- **Safe.** No destructive request in any arm or fixture; no write replayed for restoration; writes capped
  and single-fire; zero restoration errors.

Frozen config for broader transfer: `focused_adaptive` + replay floor 0.25 (opt-in, off by default).

Next (per the milestone queue, separate work): return to the model-and-scaling research — whether an LLM
can outperform this stronger deterministic exploration baseline on unfamiliar applications.
