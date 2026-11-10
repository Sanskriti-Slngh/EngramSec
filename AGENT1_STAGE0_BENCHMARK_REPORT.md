# Agent 1 — Stage 0: breadth-starved benchmark + baseline

Written for: the EngramSec research owner, deciding whether to proceed to Stage 1 (comparing deterministic
vs LLM-assisted exploration). Branch `agent1-browser-mapper-20261028`, from `7af31e3`. Continues
`AGENT1_LLM_AUGMENTATION_DECISION.md`. **No core-explorer change, no model tokens, no safety relaxation.**

**Bottom line.** The benchmark is **valid** — it produces 20/50 reachable, non-destructive capabilities
left uncovered, every one attributable to exploration inefficiency (not auth/writes/JS/bugs). **But the
root cause is not breadth over-enumeration** (that is only ~11 % of the budget here); it is the explorer's
*descent ordering* (one hub exhausted before the next) plus per-capability restoration cost — both
**deterministic** problems. The slice where an LLM could be *uniquely* useful is small (6/50 = 12 %, the
semantically-ambiguous list) and is itself deterministically reachable. **Decision: GO for a Stage-1
A-vs-B comparison (frozen vs a cheap deterministic ordering/pruning rule); NO-GO on the LLM arm (C) until
the deterministic arm's residual is shown to be concentrated in the semantic slice.**

---

## 1. Premise validation — no existing application is suitable

Checked all 17 environments in `evaluation/results/agent1_comprehensive_summary.json` plus the fixture
sources. A suitable benchmark needs all three: (a) significant repeated-template waste, (b) reachable
functionality left uncovered within budget, (c) the miss not caused by auth/writes/restoration/bugs.

| Candidate | (a) breadth waste | (b) reachable miss | (c) clean cause | Verdict |
|---|---|---|---|---|
| branch/gated/workflow_lab (dev) | yes | **no — saturated** (12/12, 14/14) | yes | fails (b) |
| coverage_lab | yes (47 redundant acts) | yes | **no** — deep fn behind POST `/session`,`/admin` + JS tabs | fails (c) |
| hybrid_lab | yes (33 redundant) | yes | **no** — POST member area + stateful chain + JS tab | fails (c) |
| crawl_maze | **no (0 redundant)** | yes | n/a | fails (a) |
| crawlground | minor (11) | yes | **no** — 59 *failed* interaction-gated markers | fails (c) |
| Track B real apps (prestashop, comfyui, jetlinks, white-jotter, siyucms) | unknown | unknown | **NOT MEASURABLE — no capability ground truth** | cannot attribute |

Attribution (column c) rests on fixture *structure*, which is config-independent, so the old-config
summary suffices for the check. No existing application isolates breadth-attributable misses from
auth/write/JS confounds, so one fixture was built.

---

## 2. The fixture — `development_apps/breadth_starved_lab.py`

GET-only, server-rendered, stdlib; **no auth, no POST/write, no JS-gating, no destructive routes**, so any
miss is attributable to prioritization alone. Fully deterministic (matched trials identical). Realistic,
neutral labels — no "important"/"duplicate"/"workflow" clues; functional hubs interleaved among breadth in
the nav so no hardcoded route order is rewarded.

- **Breadth (6 sections):** products, articles, media, people, archive, directory — each a single repeated
  template of 80 entries. Each section yields exactly two capabilities (index + "an item"); visiting the
  2nd..80th item yields no new capability (the honest value of a uniform catalog).
- **Functional hubs (template-distinct), 2–3 levels deep:** `/reports` (4 types × 2 views), `/settings`
  (4 areas × 1 sub), `/ops` (3 areas × 1 sub). Each hub index links to ≥2 distinct child templates, so a
  template-aware rule can recognise it *once reached*.
- **Ambiguous list:** `/updates` is structurally one template (`/updates/<id>`), but 6 of 40 items are
  "releases" with a deeper changelog; only item *content* distinguishes a release from a note. No
  structural tell at the list — template counting cannot flag it.

Ground truth (evaluation-only, never seen by the explorer): 50 capabilities = 18 shallow + 32 deep
(26 template-distinct + 6 semantic-only). Self-test confirms all 50 are GET-reachable and releases are
gated only by item content (non-release changelog → 404).

---

## 3. Measured baseline — frozen `focused_adaptive` / `adaptive_protected`, 3 matched trials, 140 s

Identical budget to the depth experiments (`MATCHED` + `adaptive_protected`: replay floor 0.25,
`restoration_shortcut="direct_url"`). Deterministic across trials (exec 30/29/30).

| Metric | Value (median of 3) |
|---|---|
| Functional capabilities executed | **30 / 50** (60 %) |
| Deep capabilities | **12 / 32** (template-distinct 12/26, **semantic-only 0/6**) |
| Max workflow depth reached | 3 (full chains do complete — on the one hub it finishes) |
| Per-hub: settings / reports / ops / updates-deep | **9/9 · 4/13 · 2/7 · 0/6** |
| Time to first deep workflow | 17.2 s |
| Redundant breadth (past 2 samples) | ~15 actions / ~15 s (**~11 % of wall-clock**) |
| Replays validated / attempts / failures | 22 / 26 / 4 (`control_missing`) |
| Restoration actions (direct-URL) | 83 (79 accepted, 80 actions saved, 0 fallback) |
| Replay actions / root reloads | 59 / 39 |
| Transitions attempted / total browser actions | 96 / 251 |
| Restoration errors (`transitions_failed`, `unsafe_restorations_suppressed`) | 0 / 0 |
| State-changing requests (safety) | **0** (no writes exist; none fired) |

---

## 4. Root-cause analysis — why 20 capabilities are missed

Every missed capability is **stranded** (its parent hub/index was reached, so its link was observable);
**none** was undiscovered, blocked, or auth/write/JS-gated (diagnosis is stable across all 3 trials):

| Missed class | Caps | Cause |
|---|---|---|
| template-distinct, stranded | 14 (reports views + funnel, ops) | **descent ordering + restoration cost** |
| semantic-only, stranded | 6 (release changelogs) | `/updates` not seeded (one template) → never descended |
| undiscovered / blocked | 0 | — |

**(a) The dominant cause is descent ordering, not breadth.** The baseline fully descends `settings` (9/9)
and then runs out of budget, leaving `reports` 31 %, `ops` 29 %, `updates` 0 %. This is `focused_adaptive`'s
`active_root` rule — exhaust one seeded subtree before switching — spending the whole budget on the first
hub. A round-robin across seeded hubs would spread budget so every hub gets partial depth.

**(b) Breadth is already well-handled.** Only 32 of 96 transitions target breadth and each breadth *item*
template is visited ~1× (novelty dedup works); redundant breadth is ~15 actions. **Max coverage
recoverable by eliminating redundant breadth alone ≈ +5–7 caps** (~15 actions ÷ ~2–3 actions/cap) — i.e.
30→~35/50, **partial**. Breadth over-enumeration — the exact failure mode the Stage-1 LLM breadth
classifier was meant to fix — is *not* the bottleneck on a GET app under `focused_adaptive`.

**(c) Restoration is a large, structural cost.** 83 restoration + 59 replay + 39 root-reload ≈ 72 % of the
251 actions. Each deep capability costs a direct-URL re-anchor; descending a 3-level hub is action-expensive.
This is inherent to breadth-first-with-restoration and is a deterministic scheduling property.

**Could a simple deterministic rule solve it without an LLM? Largely yes.** Round-robin seeded-hub descent
(spreading budget across reports/ops/settings/updates) plus a light stagnation cap on uniform lists would
plausibly recover the **14 template-distinct** stranded caps with no model. The only part a deterministic
*template* rule cannot target is the **6 semantic-only** release changelogs (the list has no structural
tell) — but even those are reachable by brute descent of all 40 update items, so the LLM's unique value
there is *efficiency*, not new capability.

---

## 5. Benchmark validity and limitations

**Valid:** 20/50 reachable, non-destructive capabilities uncovered, all attributable to exploration
inefficiency; zero auth/write/JS/restoration/safety confounds (statechg 0, txfail 0); deterministic;
realistic, unlabelled. It cleanly separates template-distinct (deterministically targetable) from
semantic-only (needs content) missed functionality.

**Limitations (stated plainly, not worked around):**
- It demonstrates uncovered functionality from inefficiency, but **not** from *breadth over-enumeration*
  specifically — `focused_adaptive` already suppresses breadth here, so the waste surfaces as ordering +
  restoration. This refines (and partly refutes) the Stage-decision premise that breadth waste is the
  lever.
- The semantic-ambiguous slice is 6/50; a fixture could be built with a larger semantic slice, but
  inflating it, or defeating novelty dedup to manufacture breadth waste, would be an "artificial obstacle"
  the brief forbids. The honest regime is that semantic-only gains are a minority on fair GET apps.
- One fixture, in-process, loopback; transfer claims require the held-out variant in §6.

---

## 6. Smallest fair Stage-1 comparison (condition met → specified)

Build **one held-out variant** of the fixture (different section names, hub arity, and release positions)
so no arm tunes to this instance; evaluate on the variant, 3 matched trials, **equal end-to-end wall-clock
including model latency**.

- **A — frozen `focused_adaptive`/`adaptive_protected`** (baseline; this report).
- **B — cheap deterministic rule** (no model): round-robin descent across seeded hubs + a stagnation cap
  that stops a uniform list after k non-novel samples. Targets the 14 template-distinct stranded caps.
- **C — stagnation-gated LLM semantic classifier** (on ambiguous lists / nav labels only, invoked when a
  one-template list resists the structural rule): targets the 6 semantic-only caps.

Measure for every arm: functional coverage (by class), deep caps, workflow depth, replays validated,
restoration errors, browser actions/requests, **model calls / tokens / $ / latency**, and safety
(state-changing requests must stay 0). **C is justified only if it beats B by recovering most of the
semantic-only slice at acceptable cost/latency with no replay or safety regression; if C ≈ B, the LLM is
not justified.**

---

## 7. GO / NO-GO for Stage 1

- **GO — arms A vs B (deterministic).** The benchmark is valid and the recoverable coverage (≈14 of 20
  missed caps) is deterministic-shaped (ordering + restoration). The cheapest, highest-information next
  step is to confirm a deterministic ordering/pruning rule recovers it — no tokens, no new risk.
- **NO-GO (conditional) — arm C (LLM), for now.** The LLM's *unique* headroom on a fair GET benchmark is
  bounded at 6/50 (12 %), is itself deterministically reachable, and costs latency under the equal
  wall-clock constraint. Escalate to C only if arm B leaves a residual concentrated in the semantic-only
  slice. This matches the model-scaling report's saturation finding and the brief's rule not to spend
  inference without evidence.

**Next action:** implement arm B (a bounded, deterministic descent-ordering + stagnation change, gated
opt-in, no safety change) and run A vs B on the held-out variant. Hold arm C until B's residual is
measured. Stopping Stage 0 here; no LLM implementation begun.
