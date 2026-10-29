# Agent 1 JS-heavy generalization milestone

Date: 2026-10-29

## What was proved

- P0 reproducibly missed hydration: 3/11 areas, 3/14 controls, and 0/12 request surfaces.
- P1 readiness/origin instrumentation reached all structural areas, controls, and request surfaces, captured initial bootstrap traffic separately, accepted only the configured local alias, and rejected external/unlisted origins.
- Corrected P2 produced fresh-context replay paths for 11/11 areas in all three repeats, with deepest path 5, 100% attempted replay reliability, zero known critical merges, and zero secret-value leaks.
- P2 reduced mean root reloads from 37.7 to 30 and exploration restoration actions from 23 to 0 versus P1. It used 127.3 actions versus P1's 111.3 because it discovered and replayed more transitions.
- On pinned public Crawlground, P2 reached 5/59 markers versus 1/59 for both P0 and P1. This is transfer evidence, not high coverage.

## What failed or remains unproved

- The first readiness rule stabilized too early; the failed probe is preserved.
- Early P2 runs recorded incomplete live prerequisites and then crossed anonymous/member contexts during restoration. Their replay reliability was 85% and 60%. Both bugs were fixed; the failures remain preserved.
- P2's final strict-budget Crawlground replay was only 17/27, with 10 failures and three untested paths. Hover, scroll, focus/keyboard, iframe, shadow DOM, and several nonstandard event classes remain unsupported.
- No claim of completeness, universal superiority, business-function correctness, or vulnerability coverage follows from these results.
- A randomized policy was not added within the two-iteration boundary. The next scheduler experiment must include one because the USENIX SoK found randomized baselines competitive.

## Implementation

- Bounded readiness traces and classifications on every observation.
- Explicit loopback origin aliases; no inferred equivalence or global allowlist disable.
- Initial navigation network evidence separated from action-triggered requests.
- Persistent live-state discovery with archived-path fallback and session-context reset.
- Actual live prerequisite provenance; fresh-context replay remains independent.
- Backward-compatible Graph A/checkpoint defaults and focused safety regressions.

## Evaluation and cost

Corrected matched results and denominators are in `GENERALIZATION_BASELINE.md`. Total measured browser experiment/test runtime was under 12 minutes, below the 20-minute cap. External API/model calls: 0. External cost: $0. The public testbed clone was about 568 KB before its small Node dependency install; no large framework was installed.

## Reproduce

```bash
.venv/bin/python experiments/run_generalization_lab.py \
  --out agent1/experiments/repro-p2 --variant p2 \
  --seconds 60 --max-transitions 30 --max-browser-actions 140
```

Run regressions:

```bash
.venv/bin/python -m pytest tests -q
```

## Next highest-value question

Can safe scroll and hover-disclosure plugins raise independently replayed Crawlground/gesture-fixture coverage under the same total action budget without reducing replay reliability or creating state/context merges? See `RESEARCH_NEXT_STEPS.md` for the matched ablation.
