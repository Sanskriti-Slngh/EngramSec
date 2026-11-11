# Agent 1 — LLM augmentation: research decision

Written for: the EngramSec research owner, deciding whether to invest in LLM-assisted exploration on top
of the frozen `focused_adaptive` + protected-replay deterministic baseline (branch
`agent1-browser-mapper-20261028`, from `7af31e3`). This is a **decision report only** — no mechanism was
implemented and no model budget was spent; the diagnosis is offline analysis of committed traces plus a
literature scan.

**Bottom line (GO/NO-GO).** **Conditional GO for one cheap offline/shadow experiment; NO-GO for live LLM
integration or any model sweep now.** The diagnosis finds a concrete, literature-backed, high-return
mechanism (stagnation-gated *template-level* breadth classification), but also shows the current fixtures
are already coverage-saturated, so an LLM advantage can only be demonstrated on a **breadth-starved
held-out application that does not yet exist in the suite**. Build that fixture and run a model-light
shadow test first; escalate to a bounded online A/B only if the shadow test clears its gate.

---

## 1. Remaining deterministic bottlenecks (measured, not assumed)

Offline analysis of the committed matched traces
(`evaluation/results/depth_verification_ab_generalized.json` and the per-trial `run.json`s under
`agent1/experiments/recovery_transfer/depth_verification/generalized/`), frozen arm
`adaptive_protected`, deterministic so trials are identical:

**(A) Breadth over-exploration — the dominant waste.** Classifying every executed discovery transition by
route template (numeric/id segments collapsed) and counting visits past a 2-sample cap on
non-functional templates:

| Fixture | Executed tx | Breadth-wasted tx | Reclaimable time | LLM calls that time funds (@2.1 s) |
|---|---:|---:|---:|---:|
| gated_get_lab | 98 | 60 (61%) | 56.2 s | ~27 |
| branch_lab | 97 | 69 (71%) | 64.9 s | ~31 |
| workflow_lab | 96 | 59 (61%) | 56.2 s | ~27 |
| role_lab_admin | 87 | 56 (64%) | 57.4 s | ~27 |

Top breadth templates are the fixtures' catalog/section lists (`/wiki` 18×, `/catalog` 22×, `/workspace`
18×, `/notes`, `/guides`…), each a single control template that yields no new functional capability after
the first couple of samples. The median transition is **0.93 s**; the explorer stops these lists only when
the time budget runs out, not by recognizing them as breadth. So ~60–70 % of the action budget is spent
re-confirming breadth, and on a larger app it would spend *more* before exhausting budget.

**(B) Nested-write depth — a tiny, deterministic-fixable gap.** The only genuinely missed functional
capabilities in the entire matched suite:
- `workflow_lab`: `task_create`, `task_detail` — a *nested* write (project → task-create form → task
  detail). The task-create control **was observed** but deferred by the −45 write penalty; free budget
  alone does not rescue it (the write stays low-priority, exactly the Phase-1 branch_lab pattern), so this
  needs deeper write-chaining, not an LLM.
- `role_lab_admin`: `admin_user_delete` — **destructive, correctly never executed** (a safety success, not
  a miss).
- `branch_lab`, `gated_get_lab`: **nothing missed** (12/12, 14/14).

**Consequence that frames everything below.** The big inefficiency (A) is *efficiency*, not *coverage*: on
these fixtures the budget is just enough to saturate functional coverage, so pruning breadth would free
time with nothing left to discover. An LLM *coverage* win is only possible where breadth is large enough
to starve functional depth within the wall-clock — a regime the current suite does not contain.

---

## 2. Relevant published techniques and tradeoffs

The 2024–2026 literature has converged on a clear pattern for exactly this problem — a cheap non-LLM
explorer by default, the model invoked sparingly:

- **Temac** ([multi-agent web GUI testing](https://fugumt.com/fugumt/paper_check/2506.00520v1_enmode)):
  runs an ordinary explorer first and brings in LLM agents **only when coverage stagnates**; +12.5–60.3 %
  code coverage on six web apps. Directly supports stagnation-gated calls.
- **LLMDroid** ([Android](https://www.citedrive.com/en/discovery/llmdroid-enhancing-automated-mobile-app-gui-testing-coverage-with-large-language-model-guidance/)):
  transitions to LLM guidance when coverage growth slows; ~$0.49/hr with GPT-4o. Confirms the economics of
  sparse invocation.
- **LLM-Explorer** ([mobile](https://arxiv.org/html/2505.10593v1)): LLM maintains *knowledge*, not every
  action; **9×–148× cheaper** than per-action LLM exploration. Supports "LLM abstracts, heuristics act."
- **2026 empirical web-GUI-testing study** ([arXiv 2409.10741](https://www.arxiv.org/pdf/2409.10741)):
  **state abstraction** — detecting pages with the same functionality to avoid repeated testing — is the
  critical lever for exploration efficiency. This is precisely bottleneck (A).
- **VETL / Chouette / CrawlMLLM**: VLM + curiosity bandit finds ~25 % more unique actions; GPT-4+Selenium
  beats monkey testing on branch coverage — but these *replace* the explorer and are vision-heavy, against
  the brief's "augment, don't fork."
- **Plan-MCTS / WebSynthesis** ([ACL 2026](https://aclanthology.org/2026.acl-long.1157.pdf),
  [arXiv 2602.14083](https://arxiv.org/html/2602.14083v1)): plan-space search and LLM world models — strong
  on WebArena task success, but heavy and task-goal-oriented, not coverage mapping; wrong tool here.

Tradeoff summary: the high-value, low-risk, augmentation-shaped idea in the literature is **LLM for
semantic state abstraction / breadth detection, gated on stagnation** — not per-action planning or a
vision agent.

---

## 3. Ranked candidate mechanisms

All three augment the existing frontier/novelty/replay machinery; none forks a separate agent.

**#1 — Stagnation-gated, template-level breadth classifier (semantic state abstraction).**
When a *newly-encountered* route template has been sampled k times with no new control template or
capability, call the LLM **once** on that template's page: "is this a breadth list (sample and stop) or a
functional area (keep descending)?" One call retires an entire template.
- *Benefit:* reclaims the ~60–70 % breadth budget measured in §1, redirecting it to functional depth.
- *Cost:* ~1 call per distinct breadth template ≈ 10–25 calls/run; at the prior-measured ~$0.0013/call
  (gpt-5.4-mini) ≈ <$0.03/run. **Economics under equal wall-clock are strongly positive:** 2.1 s/call vs
  0.93 s/action, and one call prunes ~16 breadth actions (~15 s) ⇒ ~7× time return.
- *Risk:* misclassifying a functional area as breadth would *lose* coverage (false-negative is the
  dangerous direction). Mitigation: only ever *cap sampling*, never skip a template entirely; keep the
  deterministic seed as a floor.
- *Interaction with `focused_adaptive`:* complementary and clean — it feeds the existing frontier a
  "breadth, deprioritize" signal; the `_adaptive_subtrees` seeding gate is the natural call site (it
  already classifies functional-area-vs-breadth heuristically; the LLM sharpens that one decision).

**#2 — LLM write-chain / form-value prioritizer.**
Targets gap (B): decide when a deferred nested write (e.g. `task_create`) is worth executing and with what
values.
- *Benefit:* narrow — recovers 1 capability on 1 current fixture; more on write-heavy apps.
- *Cost:* few calls/run; safety-sensitive (writes).
- *Risk:* high — touches the write path, destructive/rollback guarantees, the whole reason writes are
  penalized. A simpler deterministic fix (deeper write-chaining in the sweep) likely captures most of the
  benefit without an LLM.
- *Interaction:* overlaps the existing write policy; would need re-validation of every safety invariant.
  **Lower EV; prefer the deterministic fix first.**

**#3 — LLM per-action ranker (the prior approach).**
- *Status: effectively already tested and rejected.* `AGENT1_MODEL_AND_SCALING_REPORT.md` §3: gpt-5.4-mini
  0.75 top-1 / 0.873 MRR, but only **2–6 of 85** better than the novelty heuristic (the closest analogue to
  the live scorer), at 2.1 s/call. Per-action at 2.1 s vs 0.93 s/action is **budget-negative under equal
  wall-clock** before any accuracy benefit. Do not pursue.

---

## 4. Selected hypothesis (falsifiable)

> **H:** Augmenting `focused_adaptive` with a stagnation-gated, template-level LLM breadth classifier
> (mechanism #1) increases *functional* capability coverage per fixed wall-clock on applications whose
> breadth is large enough to starve functional depth — by reclaiming breadth budget and redirecting it to
> functional descent — **without** losing coverage, degrading replay, or executing unsafe actions.

Falsified if, on a breadth-starved held-out app, the LLM-augmented arm does **not** reach more functional
capabilities than `adaptive_protected` at equal wall-clock (including model latency), or if it loses any
functional capability the baseline reaches, or regresses replay/safety.

---

## 5. Experimental protocol and success/failure criteria

Staged, cheapest-first. **Do not skip to online.**

**Stage 0 — build the missing regime (no model).** The current fixtures saturate, so first build 1–2
held-out dev fixtures with *large* breadth (many single-template lists) **and** deep functional structure
such that `adaptive_protected` provably runs out of wall-clock before reaching functional depth (verify:
baseline functional coverage < 100 % with breadth dominating the action log). Without this, no experiment
can show an LLM coverage win. Hold these out from all tuning.

**Stage 1 — offline shadow test (model-light, the real gate).**
1. *Classifier accuracy:* run mechanism #1's single prompt on cached page snapshots for every distinct
   template across the existing traces + new fixtures (~20–30 templates × a few apps ≈ <100 calls). Score
   breadth-vs-functional against ground truth. **Gate: ≥90 % precision on the functional class** (a
   functional area must almost never be called breadth).
2. *Budget-conversion simulation:* replay each trace with breadth capped at k per the classifier's labels,
   and count functional capabilities reachable in the reclaimed action budget (pure simulation, no live
   run). **Gate: ≥ +2 functional capabilities on at least one held-out breadth-starved app.**

**Stage 2 — bounded online A/B (only if both Stage-1 gates pass).**
Arms: `adaptive_protected` vs `adaptive_protected + #1`. 3 trials each, identical start state / permissions,
**equal end-to-end wall-clock including model latency** (the LLM-arm's time budget is debited by real call
latency). Held-out apps only. Measure: functional coverage, replay-validated workflows, restoration
errors, destructive actions (must stay 0), model calls, tokens, $ (SpendingLedger), browser requests,
actions. **Success:** higher functional coverage at equal wall-clock with no replay/safety regression on
≥2 independent apps. **Failure:** no coverage gain, or any safety/replay regression.

Controls reused from the existing harness: `evaluation/depth_verification_ab.py` budget matching,
`restoration_shortcut="direct_url"`, the providers' "rank only observed, safe ids" contract, and the
`SpendingLedger` $10 cap.

---

## 6. Estimated implementation and evaluation cost

| Item | Effort | Model spend |
|---|---|---|
| Stage 0 — breadth-starved held-out fixtures (1–2) | ~0.5 day | $0 |
| Stage 1 — shadow classifier + budget-conversion simulator | ~1–1.5 days | <$0.20 (<100 calls) |
| Stage 2 — bounded online A/B (only if gated) | ~1–1.5 days | <$1 (≤~600 calls) |
| **Total to a decision** | **~2–3.5 days** | **<$1.20**, far under the $10 cap |

No GPU/fine-tune (the model-scaling report already showed training is unjustified on this data). Risk of
wasted spend is near zero because Stage 1 is model-light and gates Stage 2.

---

## 7. Recommendation — conditional GO

**GO** to Stage 0 + Stage 1 (build the breadth-starved held-out fixture and run the model-light shadow
test). This is the smallest experiment that can actually falsify H, costs <$0.20, and reuses existing
infrastructure. **NO-GO** to any live LLM integration, per-action ranking, or model sweep now — the
prior offline study already rejected the per-action ranker, and the current fixtures cannot demonstrate a
coverage win regardless of model quality.

**Escalate to Stage 2** only if Stage 1 clears both gates (≥90 % functional precision **and** ≥ +2
functional capabilities in simulation on a breadth-starved app). If Stage 1 fails either gate, the honest
conclusion is that deterministic `focused_adaptive` + protected replay is at or near the achievable
frontier for these application shapes, and LLM assistance should be shelved until genuinely diverse,
large real applications (not author-built fixtures) are available — consistent with the model-scaling
report's data-saturation finding.

Nothing here changes a production default or spends budget. Existing work is preserved; implementation is
deferred pending the Stage-1 result.
