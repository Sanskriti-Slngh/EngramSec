# Agent 1 run agent1-20261031T212130Z

- Code revision: `fd7f3e888045c0a0bb9ba7f4102854814384f38a+mapper-92ca26704465`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:45173/`
- Elapsed: 25.224 seconds
- Browser actions (including setup/replay): 67
- Replay-validated navigation categories: 0
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 13
- Replay navigation success: 0/0
- Replay failures / untested paths: 0/13
- Graph connections with complete evidence: 549/549
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 2
- Redundant raw states: 5
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- None.

## Functional path-instance outcomes

- `workflow_14831fd7a0e5343b3d` — + Create canvas: `not_tested` (path length 1)
- `workflow_43f86123b3cf1e1104` — Invite: `not_tested` (path length 2)
- `workflow_7c462530f358913852` — Invite: `not_tested` (path length 3)
- `workflow_8113f29ccf0cb9e775` — ← All canvases: `not_tested` (path length 3)
- `workflow_314bdb9341e90bdb6e` — ↗ Name your next canvas Owned by you · 10/31/2026: `not_tested` (path length 4)
- `workflow_33bc554609c986f63f` — Scroll viewport: `not_tested` (path length 2)
- `workflow_c453879e54d2a08cbb` — ← All canvases: `not_tested` (path length 2)
- `workflow_c941e3dcbd66611abe` — + Create canvas: `not_tested` (path length 3)
- `workflow_5b5781a080712b5513` — Text: `not_tested` (path length 2)
- `workflow_2aa16ec85388ddbac3` — Select: `not_tested` (path length 2)
- `workflow_8c0ca8f89c56272e4b` — Rectangle: `not_tested` (path length 2)
- `workflow_23cee0eedcd8e4ff08` — Line: `not_tested` (path length 2)
- `workflow_894194110e4df7726a` — Ellipse: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_6d517433cc2a313d` — + Create canvas leads to Whiteboard
- `feature_831278b1747a0348` — ↗ Name your next canvas Owned by you · 10/31/2026 leads to Whiteboard
- `feature_b1442d30a35432db` — Invite leads to Whiteboard
- `feature_f9caf80d5acc3d64` — ← All canvases leads to Whiteboard

## Failed or blocked transitions

- `tr_0444b8d710d7ee4f214a` — ↗ Sprint retro Owned by you · 10/31/2026: RuntimeError: saved return path restored abd2186f5d59dcba, expected 6988b6058aa9b0c4
- `tr_bf27ad14670256577a29` — ↗ Design review Owned by you · 10/31/2026: RuntimeError: saved return path restored abd2186f5d59dcba, expected 6988b6058aa9b0c4
- `tr_f155bd71c8c5108c65f7` — Text: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_ee60e79693e38292ba7c` — Select: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_2eda9076e07625523204` — Rectangle: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_bebfc3a3fbeae76c033a` — Line: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_8e9fc7a1ecb857e07226` — ↗ Sprint retro Owned by you · 10/31/2026: RuntimeError: saved return path restored 953d57c133a193aa, expected dc3abdbe23defa0d
- `tr_75d7fd7da6613b573378` — Ellipse: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_ff7adc28e91e02e02fed` — ↗ Design review Owned by you · 10/31/2026: RuntimeError: saved return path restored 95459740e2e6c1cf, expected dc3abdbe23defa0d

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
