# Agent 1 run agent1-20261031T211642Z

- Code revision: `fd7f3e888045c0a0bb9ba7f4102854814384f38a+mapper-59e4d29853ce`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:45173/`
- Elapsed: 36.274 seconds
- Browser actions (including setup/replay): 95
- Replay-validated navigation categories: 0
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 13
- Replay navigation success: 0/8
- Replay failures / untested paths: 8/5
- Graph connections with complete evidence: 527/530
- Graph connections missing evidence: 3
- Incorrect state merges found by audit: 2
- Redundant raw states: 2
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- None.

## Functional path-instance outcomes

- `workflow_593fbe1baee184c790` — + Create canvas: `failed` (path length 1)
- `workflow_4cd1dff8e90763a804` — Invite: `failed` (path length 2)
- `workflow_0dcc13f9adff16f3a5` — Invite: `failed` (path length 3)
- `workflow_b86fa3f36e52412050` — ← All canvases: `failed` (path length 3)
- `workflow_a4cdcb717f6e744259` — ↗ Name your next canvas Owned by you · 10/31/2026: `failed` (path length 4)
- `workflow_29177a5cc6f87983fd` — Scroll viewport: `failed` (path length 2)
- `workflow_497e13d872a109d969` — ← All canvases: `failed` (path length 2)
- `workflow_ddc3e14e62e148de70` — + Create canvas: `not_tested` (path length 3)
- `workflow_6886aedf32a163c75e` — Text: `not_tested` (path length 2)
- `workflow_a82ed3c036a703264e` — Select: `not_tested` (path length 2)
- `workflow_cd57f14105714ee26e` — Rectangle: `not_tested` (path length 2)
- `workflow_73546a6c03dc1442c7` — Line: `failed` (path length 2)
- `workflow_5265ed3ef0856df76c` — Ellipse: `not_tested` (path length 2)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_6e68688c798a925f5261` — ↗ Sprint retro Owned by you · 10/31/2026: RuntimeError: saved return path restored abd2186f5d59dcba, expected 6988b6058aa9b0c4
- `tr_13614bd128be7524c3f1` — ↗ Design review Owned by you · 10/31/2026: RuntimeError: saved return path restored abd2186f5d59dcba, expected 6988b6058aa9b0c4
- `tr_13b2cbc87615a6b4279e` — Text: RuntimeError: return-path control missing: a96b655d943a3002
- `tr_552acdd0cbd93c057f70` — Select: RuntimeError: return-path control missing: a96b655d943a3002
- `tr_816e8a725f7a23e8daf5` — Rectangle: RuntimeError: return-path control missing: a96b655d943a3002
- `tr_993e0138df911bdf9315` — Line: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_0c1da1b616d0ccd6877b` — ↗ Sprint retro Owned by you · 10/31/2026: RuntimeError: saved return path restored 953d57c133a193aa, expected dc3abdbe23defa0d
- `tr_b837e39b50fee1f0f9fe` — Ellipse: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_4293cb8932c72878ee96` — ↗ Design review Owned by you · 10/31/2026: RuntimeError: saved return path restored 95459740e2e6c1cf, expected dc3abdbe23defa0d

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
