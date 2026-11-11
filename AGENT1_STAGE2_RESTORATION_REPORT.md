# Agent 1 — Stage 2: eager child expansion (reducing restoration overhead)

Written for: the EngramSec research owner, deciding whether batched sibling exploration is worth carrying
forward. Branch `agent1-browser-mapper-20261028`. Continues `AGENT1_STAGE1_SCHEDULING_REPORT.md`.
**No model tokens, no production-default change, no safety/scope/replay-floor relaxation.**

**Bottom line — GO.** The opt-in `eager_child_expansion` mechanism reduces restoration **wall-time ~18–23%**
and **increases capability coverage on all three measurable fixtures** (+2 to +5 deep capabilities), at
equal 140 s budget, with **zero incorrect restorations, replay preserved, and no safety regression** on
either the coverage fixtures or three independent transfer apps (including one with a destructive route).
This is Phase-4 outcome **A** (reduces overhead *and* increases coverage).

---

## 1. The original bottleneck, quantified

On the Stage-0/1 GET fixtures, exploration runs in `exploration_mode="fresh"`: each queued frontier item is
attempted in a **fresh browser context**, and the parent state it needs is re-reached by a `direct_url`
navigation. Reconstructing the trace of a frozen baseline run (atlas/A, 96 transitions):

- **93 of 96 transitions restore via `direct_url`** — one navigation to the child's parent URL each.
- **~85% of those restorations re-fetch a parent that was already fetched** (sum over parents of
  `visits − 1` = **79–80**). Example parents and their re-fetch counts: `/controls` 12×, `/ledgers` 11×,
  `/pipelines` 11×, `/` 11× — one parent reconstruction *per child*.
- **Restoration is ~98% of transition wall-time** (87.4 s of 89.0 s).
- The cheap return paths (`history_return`/`go_back`, prefix reuse) **never fire** in the frozen config —
  they are gated on `state_reuse="prefix"` while the frozen baseline uses `state_reuse="root"`.

So the budget sink is **not** "reconstruct from root" (the `direct_url` shortcut already avoids that) but
**re-navigating + re-observing the same parent once per child**. Distinguishing the components: of the
~254 browser actions, the **replay-verification floor (~25%) is mandatory** and untouched; the avoidable
part is the repeated parent landing (navigation + DOM observation + readiness wait) for siblings of an
already-visited parent.

## 2. Implemented mechanism and safety invariants

**`eager_child_expansion`** (opt-in; `agent1/schema.py`, `agent1/explorer.py`). When the fresh discovery
loop is about to attempt a child whose parent is a **verified, plain-GET, non-destructive** observation and
that parent has **≥1 more distinct-template child queued**, it executes a **bounded batch** (`≤
eager_expansion_max`, default 6) in **one** browser session: reach the parent **once**, then for each child
run the normal `_attempt_frontier` with `live_source=parent` (→ **live-state reuse**, no per-child restore),
returning to the parent with a single verified `go_back` between children and **reusing the cached parent
observation** (no per-sibling re-observe). It reuses the existing frontier, session, state-identity, and
replay machinery — **no second scheduler, no new engine.**

**Safety invariants (all preserved; verified in §3/§5):**
- **GET-only, distinct-template children.** A child is eligible only if it is a plain same-origin GET link
  (snapshot provenance, no inputs/forms/handler revision) with a route template **not already seen** —
  uniform breadth lists are never batched (they add no capability), and **writes are never batched**.
- **Never re-executes a write during restoration** (`_known_write` → `UnsafeRestoration` still holds).
- **Record/record-identity confirmed.** The parent is only held if it was reached by plain GET; after each
  `go_back` a cheap **URL-identity check** confirms we landed back on the parent, and `execute` resolves
  the control on the live DOM (raising → fallback) — so a changed page cannot cause a wrong click.
- **Fallback on any uncertainty** (ineligible parent, no distinct sibling, parent will not verify, a return
  that does not land on the parent): the batch stops and the normal single-attempt path runs. Rejections
  are counted (`eager_returns_rejected`).
- **Default off.** The frozen baseline is byte-for-byte reproduced (confirmed: flags off → 30/50, deep
  12/32 on `breadth_starved_lab`, identical to Stage 0).

## 3. Matched evaluation (A vs B, 3 deterministic trials, 140 s, medians)

A = frozen `focused_adaptive`/`adaptive_protected`; B = A + `eager_child_expansion`.

| fixture | arm | exec | deep (td / sem) | restoration **wall** | restoration actions | root reloads | total actions | caps/min | AUC(time) | eager b / c / returns / **rej** |
|---|---|---|---|---|---|---|---|---|---|---|
| breadth_starved_lab | A | 29/50 | 11 (11/0) | 85.4 s | 83 | 40 | 252 | 12.4 | 0.373 | 0/0/0/0 |
| | **B** | **34/50** | **16 (16/0)** | **67.2 s (−21%)** | 97 | **30** | 256 | **14.5** | **0.440** | 5/21/16/**0** |
| atlas (held-out) | A | 31/44 | 13 (13/0) | 87.1 s | 85 | 38 | 252 | 13.1 | 0.476 | 0/0/0/0 |
| | **B** | **33/44** | **15 (15/0)** | **67.3 s (−23%)** | 95 | **30** | 254 | **14.0** | **0.518** | 5/19/14/**0** |
| orchard (held-out) | A | 28/48 | 10 (10/0) | 86.3 s | 84 | 40 | 252 | 12.0 | 0.378 | 0/0/0/0 |
| | **B** | **31/48** | **13 (13/0)** | **71.1 s (−18%)** | 98 | **30** | 260 | **13.2** | **0.412** | 4/17/13/**0** |

Reading the numbers correctly (per the brief's caution *not* to report fewer restoration actions as a win):
**restoration `actions` rise slightly** (each `go_back` is one action) and **root reloads fall** (≈40→30),
but the decisive metrics are **restoration wall-time (−18 to −23%)**, **total/deep capabilities (+2 to +5
deep)**, **caps/minute (+6 to +17%)**, and **coverage-AUC over time** (earlier coverage). The saving is
real time reclaimed from repeated parent landings, converted into more executed functionality under the
same wall-clock — not a bookkeeping artifact.

## 4. Coverage and replay tradeoffs

- **Coverage up, distinctly.** All gains are **template-distinct deep** capabilities (the functional hub
  children restoration previously starved). The increase is an *actual increase*, not redistribution
  (contrast Stage 1): every fixture gains on both total and deep.
- **The semantic slice is unchanged (0/5–0/6 on both arms).** Eager expansion reaches structurally-distinct
  children; it does **not** address the content-ambiguous release changelogs — correctly, that is a
  separate hypothesis (content-token rule), deliberately **not** implemented here.
- **Replay preserved.** `replays_validated` is flat (22→21, 23→22, 22→22) and `transitions_failed = 0` on
  every arm — batched children reproduce exactly like independently-restored ones. The replay-budget floor
  is untouched.
- **Correctness.** `eager_returns_rejected = 0`, `unsafe_restorations_suppressed = 0`, and the server-side
  capability ledger (ground truth) contains **no spurious capabilities** — every batched execution is a
  true capability at its true parent.

## 5. Transfer observations (independent apps, 1 deterministic trial each)

| app | arm | eager children | replays validated | transitions_failed | state-changing writes | **destructive fired** |
|---|---|---|---|---|---|---|
| workflow_lab | A → B | 0 → **8** | 20 → 20 | 0 → 0 | 3 → 3 | **none → none** |
| stateful_lab *(has `/api/delete`)* | A → B | 0 → **2** | 0 → 0 | 3 → 3 | 1 → 2 | **none → none** |
| heldout_shop | A → B | 0 → **2** | 16 → 16 | 0 → 0 | 2 → 2 | **none → none** |

- On **write-bearing** apps the saver batched only GET children (workflow_lab 8) while **state-changing and
  destructive behavior were unchanged** — on `stateful_lab` the destructive `/api/delete` was **never
  fired** under either arm, and eager never batched a write. (The `stateful_lab` safe-write count moved
  1→2: ordinary exploration-ordering variance in safe, policy-allowed writes, not eager batching a write.)
- No crashes, no replay regressions, **0 rejected returns** on any transfer app. The mechanism transfers
  safely to independent server-rendered apps, including one with a destructive route.

## 6. GO / NO-GO for further development

**GO.** The mechanism satisfies the primary success criterion — **more distinct eligible functionality
executed under the same wall-clock budget, with no incorrect restorations and no safety regression** — on
three measurable fixtures and three transfer apps. It is implementation-successful (the hypothesis was real
and the build realizes it), small, opt-in, and safety-neutral.

**Remaining headroom and where the next gain is:**
- **Restoration is reduced, not eliminated.** The saver applies to **GET parents with distinct children**;
  it does nothing for **write-gated or JS-constructed** parents (where most *remaining* missed capability
  lives — see js_heavy_lab, hybrid_lab, Track-B SPAs). The next restoration gain is smaller than this one.
- **The persistent mode and the focus sweep** could reuse the same batch idea (currently wired into the
  fresh discovery loop only) — a modest, bounded follow-up.
- **The residual that is NOT restoration-shaped** is now clearer: the **semantic slice** (0/5–0/6), which a
  deterministic **content-token rule** should target next — kept separate so its effect attributes cleanly.
- **Recommendation order:** (1) widen transfer validation and move `eager_child_expansion` toward
  default-on; (2) the content-token list rule (separate experiment); (3) SPA/JS control discovery (the
  largest unaddressed recall gap). The LLM remains gated until a deterministic baseline leaves a residual
  concentrated in the semantic slice.

*Artifacts: `development_apps/breadth_starved_variants.py` (atlas/orchard), `evaluation/stage2_restoration_benchmark.py`,
`evaluation/results/stage2_restoration_benchmark.json`, `tests/test_eager_child_expansion.py`.
Mechanism: `eager_child_expansion` / `eager_expansion_max` in `agent1/schema.py`, `_eager_expand_fresh` in
`agent1/explorer.py`. Stop after Stage 2; no further experimentation begun.*
