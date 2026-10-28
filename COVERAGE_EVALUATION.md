# Independent coverage evaluation

`experiments/evaluate_coverage.py` accepts only a completed Graph A and separately maintained ground truth. Agent 1 never imports this evaluator, the ground-truth file, application source, expected routes, or expected labels. Evaluation happens after the browser and Graph A run have ended.

## Development corpus

`development_apps/coverage_lab.py` is a disposable local black-box application with independently declared truth in `coverage_lab_ground_truth.json`. It contains disclosed controls, two record instances, JavaScript-only state, Fetch requests, a deep setup path, cosmetic duplication, an observed member session, an ineffective control, a protected blocked form, and an out-of-scope origin. A separate held-out local application is evaluated only after the mapper is frozen.

## Metrics and denominators

- State/interface recall: applicable independently labeled reachable areas found / applicable areas.
- Control/action recall: applicable actionable controls advertised or executed / applicable controls.
- Request-surface recall: expected reachable `(method, route pattern, parameter-name set)` structures observed / applicable structures.
- Prerequisite-path coverage: applicable areas reached by a recorded independently replayed path / applicable areas.
- Instance/context preservation: expected record instances and browser-observed session-marker contexts found, with record states checked for distinct identity.
- Replay reliability: successful fresh-context navigation replays / attempted replays.
- Efficiency: sum of covered areas, controls, and request structures per browser action and per elapsed minute.
- Request precision: observed action-attached request structures matching a ground-truth method/path divided by all recorded structures. This is diagnostic because ordinary root navigations may be valid but not separately enumerated.

Blocked, outside-scope, and applicable items have separate labels. Applicable results are `covered_replayed`, `covered_structural_not_replayed`, or `missed`; blocked observations are `discovered_blocked`; excluded origins are `outside_access_scope`. Unknown evidence is not silently credited.

The evaluator does not infer functional success from HTTP 200 or replay. An ineffective control is intentionally part of control recall while remaining behaviorally ineffective. Mapper-reported merge audits and evidence-reference audits are shown separately from evaluator ground truth.

## Reproduction

```bash
.venv/bin/python experiments/run_coverage_lab.py \
  --out agent1/experiments/coverage_lab_run \
  --policy grouped --seconds 60 \
  --max-transitions 30 --max-browser-actions 140
```

To rescore a frozen graph without running a browser:

```bash
.venv/bin/python experiments/evaluate_coverage.py \
  agent1/experiments/coverage_lab_run/graph_a.json \
  development_apps/coverage_lab_ground_truth.json \
  --out agent1/experiments/coverage_lab_run/coverage_evaluation.json
```

The denominator deliberately excludes inaccessible backend-only and outside-origin surfaces. Adding them as ordinary mapper misses would misstate UI discovery recall.
