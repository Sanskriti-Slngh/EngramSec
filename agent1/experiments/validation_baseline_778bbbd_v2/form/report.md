# Agent 1 run agent1-20261028T131707Z

- Code revision: `778bbbda008081c489afdaee836c6397c4cff93a+mapper-16472af09339`
- Policy: `grouped`
- Target: `http://127.0.0.1:57699/form`
- Elapsed: 2.333 seconds
- Browser actions (including setup/replay): 7
- Validated feature workflows: 1
- Replay success: 1/1
- Unsupported connections: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Replay-validated workflows

- `feature_678bea2f095ad481` — Create registration leads to Registration

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
