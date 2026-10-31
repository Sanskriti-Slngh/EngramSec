# Agent 1 run agent1-20261031T211902Z

- Code revision: `fd7f3e888045c0a0bb9ba7f4102854814384f38a+mapper-4d06bb53e9d7`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:45173/`
- Elapsed: 41.062 seconds
- Browser actions (including setup/replay): 107
- Replay-validated navigation categories: 0
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 13
- Replay navigation success: 0/8
- Replay failures / untested paths: 8/5
- Graph connections with complete evidence: 557/557
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 2
- Redundant raw states: 5
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- None.

## Functional path-instance outcomes

- `workflow_c79a546d6be8b032c1` — + Create canvas: `failed` (path length 1)
- `workflow_5b1360ccfb0e94fa49` — Invite: `failed` (path length 2)
- `workflow_e0eb09047ecd57ebd8` — Invite: `failed` (path length 3)
- `workflow_f9efd7ae81e5140098` — ← All canvases: `failed` (path length 3)
- `workflow_6a53acc5d715f30bc7` — ↗ Name your next canvas Owned by you · 10/31/2026: `failed` (path length 4)
- `workflow_1b6658b31fd11e3437` — Scroll viewport: `failed` (path length 2)
- `workflow_e4f3529527f8c52362` — ← All canvases: `failed` (path length 2)
- `workflow_5310404331f2b32615` — + Create canvas: `not_tested` (path length 3)
- `workflow_8bd489d1e9fb6ff6f6` — Text: `not_tested` (path length 2)
- `workflow_b21efb24e4b326177e` — Select: `not_tested` (path length 2)
- `workflow_e3c9c0373e8f5af3d6` — Rectangle: `failed` (path length 2)
- `workflow_f01632e769d720aa30` — Line: `not_tested` (path length 2)
- `workflow_1f66f53ea9bc9fcdbd` — Ellipse: `not_tested` (path length 2)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_a710d1fde05fdb2c209b` — ↗ Sprint retro Owned by you · 10/31/2026: RuntimeError: saved return path restored abd2186f5d59dcba, expected 6988b6058aa9b0c4
- `tr_4abe8012fed4c496030a` — ↗ Design review Owned by you · 10/31/2026: RuntimeError: saved return path restored abd2186f5d59dcba, expected 6988b6058aa9b0c4
- `tr_5ad4e206ca2f2938e47d` — Text: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_90dd64811b3d24f24974` — Select: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_e647d87504f9aa2cac4f` — Rectangle: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_e2f95b4fb0810e8b59f8` — Line: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_538d32d7b321a8ae1935` — ↗ Sprint retro Owned by you · 10/31/2026: RuntimeError: saved return path restored 953d57c133a193aa, expected dc3abdbe23defa0d
- `tr_8d4161cd0b7823893991` — Ellipse: RuntimeError: saved return path restored 7d9afa587aa194b8, expected cda05ca0ff85111a
- `tr_a81455265caaa236d6f1` — ↗ Design review Owned by you · 10/31/2026: RuntimeError: saved return path restored 95459740e2e6c1cf, expected dc3abdbe23defa0d

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
