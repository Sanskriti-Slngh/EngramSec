# Agent 1 paired-search false-positive challenge

Date: 2026-10-28

## Outcome

The generic paired-search verifier was tested against four independent black-box websites with evaluator truth kept in a separate module. The unchanged verifier produced one false positive and one false negative. A general before/after link-target rule reduced the measured errors to zero on these four cases without using target-specific selectors, paths, result regions, or literal query matching.

This is a focused regression result, not proof that arbitrary search interfaces are correctly understood.

## Independent cases and unchanged baseline

The mapper accessed each fixture only through Chromium. Evaluator truth was applied after each saved run.

- Functional literal results: `functional_verified` — correct.
- Echo-only broken search: `unresolved` — correct.
- Broken search with permanent Alpha/Beta sidebar links: `functional_verified` — **false positive**.
- Functional search with “Operations handbook” and “Deployment manual” results: `unresolved` — **false negative** because titles did not contain the probes.

Baseline totals: **1 false positive, 1 false negative**, 64 browser actions, 5.057 seconds, and $0 external cost.

## General fix

For each probe in each fresh browser context, Agent 1 now preserves the observation immediately before the final search submission and the resulting observation. It compares browser-observed link targets as follows:

1. Subtract all targets already present on the actionable pre-submit screen.
2. Require both probes to introduce at least one link target.
3. Require each probe to contribute at least one introduced target absent from the other probe's result.
4. Require the two pre-submit link-target sets to match, so unrelated changing navigation makes the outcome unresolved.
5. Repeat the complete paired check in two independent contexts and require the introduced target evidence to be consistent across both replays.

Meaningful-content differences are still recorded but are not sufficient. Query echo, title, URL, HTTP success, and literal query occurrence are not functional-success checks.

Graph A retains four verification observations per replay: primary-before, primary-result, contrast-before, and contrast-result. It also records baseline targets, introduced links, probe-only targets, per-replay checks, and cross-replay consistency.

## Corrected measurement

- Functional literal results: `functional_verified` — correct.
- Echo-only broken search: `unresolved` — correct.
- Permanent-sidebar broken search: `unresolved` — correct.
- Functional nonliteral results: `functional_verified` — correct.

Corrected totals: **0 false positives, 0 false negatives**, 64 browser actions, 5.213 seconds, and $0 external cost.

Focused regressions passed **14/14**, including the existing exact-plan, hidden-toggle, wrong-record, and cosmetic-content checks. The final full Agent 1 suite passed **31/31**.

## SiyuCMS compatibility

No new live SiyuCMS run was necessary. Existing artifacts and results were preserved unchanged. An offline check of the previously captured `siyucms_search_integrated_v2` browser observations found, in both old replay contexts:

- Primary probe: 7 targets introduced after the recorded search screen, 6 unique to the primary result.
- Contrast probe: 2 targets introduced, 1 unique to the contrast result.

This supports compatibility with the new evidence rule but is not reported as a new live verification because the old artifact did not retain distinct pre-submit observations for both probes.

## Artifacts and reproduction

- Unchanged baseline: `agent1/experiments/search_verifier_adversarial_baseline/summary.json`
- Corrected final measurement: `agent1/experiments/search_verifier_adversarial_link_delta_final/summary.json`
- Fixture website: `tests/fixtures/search_adversarial_app.py`
- Separate evaluator truth: `tests/fixtures/search_adversarial_ground_truth.py`

Exact comparison commands:

```bash
.venv/bin/python experiments/run_search_verifier_fixtures.py \
  --out agent1/experiments/search_verifier_adversarial_reproduction

.venv/bin/python -m pytest \
  tests/test_agent1_search.py tests/test_agent1_search_adversarial.py -q
```

## Remaining limitations

- Search results represented only as non-link widgets remain unresolved.
- Results whose targets were already linked before submission remain unresolved.
- Query-dependent content behind an unchanged target remains unresolved.
- Dynamic navigation or unstable result targets can conservatively prevent verification.
- A site that consistently injects unrelated, probe-dependent links could still imitate the evidence; the two-context consistency check reduces but does not eliminate that risk.
- Four synthetic cases do not establish a general false-positive rate.
