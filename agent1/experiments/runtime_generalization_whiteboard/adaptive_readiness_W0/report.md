# Agent 1 run agent1-20261031T211824Z

- Code revision: `fd7f3e888045c0a0bb9ba7f4102854814384f38a+mapper-4d06bb53e9d7`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:45173/`
- Elapsed: 34.288 seconds
- Browser actions (including setup/replay): 94
- Replay-validated navigation categories: 0
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 13
- Replay navigation success: 0/6
- Replay failures / untested paths: 6/7
- Graph connections with complete evidence: 555/555
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 2
- Redundant raw states: 5
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- None.

## Functional path-instance outcomes

- `workflow_312757fd4835bf2126` — + Create canvas: `failed` (path length 1)
- `workflow_d970a67a8832ad956b` — Invite: `failed` (path length 2)
- `workflow_8e2da7f90bccc45fd1` — Invite: `failed` (path length 3)
- `workflow_98d560e6632c9e4bcf` — ← All canvases: `not_tested` (path length 3)
- `workflow_2f46709f01ba68c72b` — ↗ Name your next canvas Owned by you · 10/31/2026: `not_tested` (path length 4)
- `workflow_d31cf57d3b978c6783` — Scroll viewport: `failed` (path length 2)
- `workflow_84571641f6172c2b8d` — ← All canvases: `failed` (path length 2)
- `workflow_ec479df8285206cd34` — + Create canvas: `not_tested` (path length 3)
- `workflow_36df036fe90efd9124` — Text: `not_tested` (path length 2)
- `workflow_8e573c3fd92a2d0d24` — Select: `not_tested` (path length 2)
- `workflow_babb96107c784fc4aa` — Rectangle: `failed` (path length 2)
- `workflow_b870fa3854eba5185d` — Line: `not_tested` (path length 2)
- `workflow_deee53fffc117eb69d` — Ellipse: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_831278b1747a0348` — ↗ Name your next canvas Owned by you · 10/31/2026 leads to Whiteboard

## Failed or blocked transitions

- `tr_b58131fdefc768fbc245` — ↗ Sprint retro Owned by you · 10/31/2026: RuntimeError: saved return path restored abd2186f5d59dcba, expected 6988b6058aa9b0c4
- `tr_73d64152760c7fed4b63` — ↗ Design review Owned by you · 10/31/2026: RuntimeError: saved return path restored abd2186f5d59dcba, expected 6988b6058aa9b0c4
- `tr_d1677e780d39ceb1152c` — Text: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_83b8cf94c85df14296e2` — Select: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_891324713cb9d3734a2b` — Rectangle: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_41ce510b479ef708eeef` — Line: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_6ff01b00ae81bba24337` — ↗ Sprint retro Owned by you · 10/31/2026: RuntimeError: saved return path restored 953d57c133a193aa, expected dc3abdbe23defa0d
- `tr_82d0a43e4662dfc62afa` — Ellipse: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_cf175b18d12151244c9e` — ↗ Design review Owned by you · 10/31/2026: RuntimeError: saved return path restored 95459740e2e6c1cf, expected dc3abdbe23defa0d

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
