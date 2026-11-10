# Agent 1 — Stage 1: can a cheap deterministic scheduler recover the missed deep functionality?

Written for: the EngramSec research owner, deciding whether the Stage-0 residual justifies semantic
(LLM) guidance. Branch `agent1-browser-mapper-20261028`. Continues `AGENT1_STAGE0_BENCHMARK_REPORT.md`.
**No model tokens, no production-default change, no safety/scope/replay-floor change.**

**Research question.** Can a cheap deterministic exploration policy recover the deep functionality missed
by `focused_adaptive` without increasing the wall-clock budget or sacrificing replay quality?

**Bottom line.** **No — not materially, and the experiment relocates the bottleneck.** The opt-in policy
(fair hub rotation + bounded stagnation) buys a *reproducible but tiny* **+1 deep capability** on each of
two held-out variants (atlas 13→14/26, orchard 11→12/30), at unchanged budget and replay quality, zero
state-changing requests. The ablation shows the Stage-0 hypothesis was **wrong about the lever**: the
12-step focus cap is *not* binding (the sweep already stops at 5–7 focused steps), so lifting it does
nothing; fair rotation only *redistributes* coverage across hubs (it even regresses one variant by 1);
stagnation mostly *repairs* rotation's own re-anchor cost. The residual that remains is **dominated by
restoration overhead and insufficient focused descent — deterministic traversal cost, not semantic
ambiguity.** The semantic slice (release changelogs) is missed by *every* arm but is a *minority* of the
residual and is itself mostly "never-visited-list-item", addressable by a cheap content-token rule before
any LLM. **Decision: NO-GO for LLM integration.** Highest-value next step is deterministic: cut
per-capability restoration cost so the sweep converts budget into descents.

---

## Phase 1 — The frozen test

Two held-out variants in `development_apps/breadth_starved_variants.py`, built before the policy was
written and frozen (a `dataclass(frozen=True)` spec each; `tests/test_breadth_starved_variants.py`, 10
tests, pins ground truth and GET-reachability). Each preserves the Stage-0 **workload** — breadth lists
that compete for budget, functional hubs 2–3 levels deep, one structurally-ambiguous list whose releases
carry a deeper changelog — while changing everything an arm could latch onto, so neither arm tunes to an
instance:

| | sections | hubs (arity × depth) | ambiguous list | releases | inventory (deep) |
|---|---|---|---|---|---|
| **atlas** | 6 (regions…crews) | ledgers 3×2, controls 4×1, pipelines 2×1 | `/bulletins` (36) | 5 | 44 (26 = 21 td + 5 sem) |
| **orchard** | 6 (orchards…buyers) | yields 4×2, policies 2×2, jobs 3×1 | `/releases` (44) | 6 | 48 (30 = 24 td + 6 sem) |

Scoring is identical to Stage 0 and frozen before the comparison: executed = server-recorded capability
ledger ∩ ground truth; deep split into **template-distinct** (td, under functional hubs — a template-aware
rule can target) and **semantic-only** (release changelogs — the list is one template; only the item's
link text "Release *n*" vs "Note *n*" distinguishes a release, a realistic neutral label, not a hint). No
priority hints or ground-truth labels are exposed to the explorer.

---

## Phase 2 — One minimal, opt-in scheduler change

Three opt-in flags on `RunConfig` (`agent1/schema.py`), **all default off → the frozen baseline is
byte-for-byte reproduced** (arm A below confirms it). They only reorder item selection inside the
*existing* `_authorized_write_sweep` focus loop (`agent1/explorer.py`), under the **same** sweep budget and
replay floor, reusing the existing frontier/focus/novelty/restoration/replay machinery. No second
scheduler, no scope or safety change.

- `focus_to_budget` — let the focus run until the real wall-clock/action/transition ceiling instead of
  stopping at the fixed `focus_max_steps=12` cap.
- `fair_subtree_rotation` — round-robin the **expensive re-anchor steps** across competing seeded hubs
  (stay on a hub only while it has a *free, live-reachable* novel child), rather than exhausting one
  subtree before switching. Implies `focus_to_budget`.
- `focus_stagnation_limit` — drop a hub from the active set after *N* consecutive focused steps that reach
  no new observation (bounded deprioritization of a stalled branch).

---

## Phase 3 — Matched A/B (+ ablation), 3 deterministic trials per arm per variant, 140 s

Arms share the frozen `MATCHED` + `adaptive_protected` config (`focused_adaptive`, replay floor 0.25,
`restoration_shortcut="direct_url"`). Only the opt-in flags differ. Medians of 3 trials; trials are
deterministic. `A` = baseline (flags off); `capcap` = +cap-lift; `rotate` = +fair rotation; **`full` = B**
(rotation + stagnation, limit 2).

### atlas (deep 26 = 21 td + 5 sem)

| arm | exec | deep | td | **sem** | actions | restore | root-reload | replay-valid | focus steps | AUC/req | AUC/time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A (baseline) | 31/44 | 13/26 | 13/21 | **0/5** | 256 | 87 | 38 | 23 | 5 | 0.466 | 0.48 |
| capcap | 31/44 | 13/26 | 13/21 | 0/5 | 256 | 87 | 38 | 23 | 5 | 0.464 | 0.48 |
| rotate | 32/44 | 14/26 | 14/21 | 0/5 | 252 | 84 | 40 | 22 | 6 | 0.467 | 0.47 |
| **full (B)** | **32/44** | **14/26** | **14/21** | **0/5** | 252 | 84 | 40 | 22 | 6 | 0.467 | 0.48 |

### orchard (deep 30 = 24 td + 6 sem)

| arm | exec | deep | td | **sem** | actions | restore | root-reload | replay-valid | focus steps | AUC/req | AUC/time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A (baseline) | 29/48 | 11/30 | 11/24 | **0/6** | 256 | 86 | 40 | 22 | 6 | 0.372 | 0.38 |
| capcap | 29/48 | 11/30 | 11/24 | 0/6 | 257 | 86 | 41 | 22 | 6 | 0.373 | 0.39 |
| rotate | 28/48 | 10/30 | 10/24 | 0/6 | 245 | 80 | 39 | 22 | 6 | 0.361 | 0.31 |
| **full (B)** | **30/48** | **12/30** | **12/24** | **0/6** | 254 | 84 | 40 | 22 | 7 | 0.377 | 0.39 |

**Coverage by hub (median executed / total), A vs full** — fair rotation *moves* budget between hubs:

- atlas: ledgers **3→6**/9, controls **8→6**/8, pipelines 2/4, bulletins **0/5**.
- orchard: yields **3→4**/12, policies **6→3**/6, jobs **2→5**/6, releases **0/6**.

**Time to first capability per hub** is unchanged by the policy (e.g. atlas ledgers 3.8 s, controls 6.7 s,
pipelines 2.9 s, bulletins 8.7 s in both A and full) — discovery reaches each hub at the same time; the
policy only changes how the *post-discovery* budget is split.

**Safety / replay (all arms, both variants):** state-changing requests **0**, transitions_failed **0**,
unsafe_restorations_suppressed **0**, replay-validated **22–23** (floor held; replay quality unchanged).
Wall-clock **~140–142 s** every arm — equal budget. Destructive actions **0**.

**Does B meet the bar "an actual increase, not merely moving coverage"?** Marginally. B gives a
*reproducible* +1 deep on both variants — but `rotate` alone *loses* 1 on orchard, and the whole effect is
within ±1 capability. It clears the bar only by a hair, and does not change the residual's shape.

---

## Phase 4 — Diagnosis

**Attribution (the ablation).**

- **Lifting the 12-step cap does nothing** (`capcap` ≡ `A` on both variants). The focus sweep already
  stops at **5–7 focused steps**, far below 12 — it runs out of in-family frontier items (and budget on
  restoration), not out of step allowance. *This refutes the Stage-0 report's lead hypothesis that
  `focus_max_steps=12` was the binding constraint; on these variants it is slack.*
- **Fair rotation redistributes, it does not add** (`rotate`: atlas +1, orchard **−1**). The hub-coverage
  rows show it clearly spreading budget off the first-descended hub onto the others, but the extra
  re-anchors cost actions (orchard restore 86→80, AUC-over-time 0.38→**0.31**), so net coverage is flat-to-
  negative and high-variance across variants.
- **Stagnation is mostly damage control** (`full` − `rotate`: atlas +0, orchard **+2**). Dropping a stalled
  hub stops rotation from paying repeated re-anchors into an exhausted branch, recovering orchard's
  regression. It is not an independent source of new coverage.
- **Combined (B vs A): +1 deep on both.** Real, reproducible, small.

**Scheduling limitation vs the ~72 %-of-actions restoration overhead.** Restoration is ~**84–87** actions
plus ~**40** root-reloads of ~**254** total — roughly a third of actions, and with the 25 % replay reserve
the sweep has little left, which is why only **5–7** descents happen regardless of ordering. Fair rotation
changes *which* 5–7 deep caps are descended, not *how many*. **The bottleneck is per-capability
restoration cost, not descent ordering and not the step cap** — ordering was already near its ceiling.

**Which missed capabilities still require semantic distinctions, and can deterministic exploration reach
them in equal time?** The residual after B, classified by whether the miss's *immediate parent* page was
reached:

| | td stranded (parent reached) | td undiscovered | **sem stranded** | **sem undiscovered** |
|---|---|---|---|---|
| atlas (12 missed) | 7 | 0 | 1 | 4 |
| orchard (18 missed) | 10 | 2 | 1 | 5 |

- The **majority** of the residual is **td-stranded** (7 / 10): functional-hub children whose parent was
  reached but not descended — pure restoration/descent cost, **no semantics needed**; deterministic
  exploration *could* reach them with cheaper restoration (same time).
- The **semantic** residual is a **minority** (5 / 6 of the ~12–18 missed): release changelogs under the
  one-template list. Only **1 per variant is stranded** (one click from a visited release page); the other
  **4–5 are "undiscovered"** — the specific release item (e.g. `/releases/13`) was never visited, because
  the explorer samples the 36–44-item uniform list shallowly and releases are interspersed. Reaching them
  needs the *list item* prioritized by its link text ("Release" ≠ "Note") — a **content-token** signal a
  cheap deterministic rule can read; it does not require an LLM.

---

## Decision

**NO-GO for semantic LLM guidance.** The gate for GO was: the deterministic improvement leaves a
*substantial, repeatable residual caused by semantic ambiguity* rather than time, restoration cost, or
ordinary traversal ordering. It does the opposite — the deterministic improvement is marginal (+1), and
the residual it leaves is **dominated by restoration cost and unfinished functional descent** (td-stranded
7–10), with the semantic slice a **minority** that is itself mostly unvisited list items reachable by a
content-token heuristic. An LLM would be paying inference to fix a traversal-cost problem.

**Next highest-value deterministic experiment (Stage 2, if pursued):** attack restoration cost so the
focus sweep converts its budget into *more* descents (it manages only 5–7 of a possible 24–30). Concretely
and cheaply, both opt-in and safety-neutral:

1. **Expand the frontier on restored pages** / descend a hub's children eagerly on first visit, so a
   re-anchor yields several descents, not one — directly targets the 7–10 td-stranded caps.
2. **A content-token list rule:** on a one-template list, prioritize items whose anchor-text token differs
   from the list's dominant token ("Release" vs "Note"). Deterministic, no model; targets the
   semantic-undiscovered slice. *Only if this rule is run and a substantial residual still concentrates in
   the semantic slice would an LLM classifier be worth testing* — i.e. the LLM arm stays gated behind a
   cheaper deterministic control, consistent with the model-scaling saturation finding.

Measured against this report's baseline, Stage 2 must again show an *actual* coverage increase (not
redistribution), at equal wall-clock, with replay-validated and state-changing-requests unchanged.

---

## Limitations

- Two in-process loopback variants; the policy is validated as *coverage-neutral-to-slightly-positive and
  safety-neutral*, not across real applications (Track B remains unmeasurable — no capability ground
  truth).
- The +1 deep gain is within trial-to-trial noise magnitude; it is reproducible as a *median* across 3
  deterministic trials but should not be over-read as a robust win.
- The semantic slice is 5–6 caps per variant by construction; a fixture with a larger semantic slice could
  be built, but inflating it — or defeating novelty dedup to manufacture breadth waste — would be the
  artificial obstacle the Stage-0 brief forbids. On fair GET apps the semantic-only share is a minority.
- These flags are opt-in and off by default; production behavior is unchanged. They are not recommended
  for default-on — the measured effect does not justify it.
