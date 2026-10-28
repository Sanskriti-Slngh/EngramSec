# Agent 1 run agent1-20261028T131710Z

- Code revision: `778bbbda008081c489afdaee836c6397c4cff93a+mapper-16472af09339`
- Policy: `grouped`
- Target: `http://127.0.0.1:57699/multi`
- Elapsed: 7.766 seconds
- Browser actions (including setup/replay): 19
- Validated feature workflows: 2
- Replay success: 3/3
- Unsupported connections: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Replay-validated workflows

- `feature_1602109b73b067f2` — Complete setup leads to Workspace setup
- `feature_28d7c625339a2261` — Prepare workspace leads to Workspace setup

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
