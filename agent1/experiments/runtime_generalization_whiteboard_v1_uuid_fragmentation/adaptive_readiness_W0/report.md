# Agent 1 run agent1-20261031T211543Z

- Code revision: `fd7f3e888045c0a0bb9ba7f4102854814384f38a+mapper-59e4d29853ce`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:45173/`
- Elapsed: 54.178 seconds
- Browser actions (including setup/replay): 150
- Replay-validated navigation categories: 0
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 39
- Replay navigation success: 0/10
- Replay failures / untested paths: 10/29
- Graph connections with complete evidence: 852/854
- Graph connections missing evidence: 2
- Incorrect state merges found by audit: 2
- Redundant raw states: 10
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- None.

## Functional path-instance outcomes

- `workflow_b6842a3c478db9c335` — + Create canvas: `failed` (path length 1)
- `workflow_5b85b8c304bbfa1c6b` — Invite: `failed` (path length 2)
- `workflow_accef8fe6aeba69183` — Invite: `failed` (path length 3)
- `workflow_ae89cbcb8e4983c9aa` — ← All canvases: `not_tested` (path length 3)
- `workflow_e77bf69e829664e9be` — ↗ Name your next canvas Owned by you · 10/31/2026: `not_tested` (path length 4)
- `workflow_2e15e50bd9b42965f0` — Scroll viewport: `failed` (path length 2)
- `workflow_fe63b308e7fe0e08b0` — ← All canvases: `failed` (path length 2)
- `workflow_c21424a568899f6888` — + Create canvas: `failed` (path length 3)
- `workflow_55833b0f1bb2603695` — Invite: `failed` (path length 4)
- `workflow_06a2d02da3cb91a82e` — Invite: `not_tested` (path length 5)
- `workflow_169cb48fdb5bcbdf7a` — ← All canvases: `not_tested` (path length 5)
- `workflow_3ae912d63f835ae2dc` — Scroll viewport: `not_tested` (path length 6)
- `workflow_dc0311bca1e033ccff` — + Create canvas: `not_tested` (path length 6)
- `workflow_7fb870fa0dc880b875` — Invite: `not_tested` (path length 7)
- `workflow_1c305f9658abf62c38` — Invite: `not_tested` (path length 8)
- `workflow_506b8722cf6e831ea6` — ← All canvases: `not_tested` (path length 8)
- `workflow_f8471f46d986ac7ce4` — + Create canvas: `not_tested` (path length 9)
- `workflow_cc1f28acd2d93b566c` — Invite: `not_tested` (path length 10)
- `workflow_1b48b2ddc02ed1e7d4` — Text: `not_tested` (path length 3)
- `workflow_3f1075f8912eb77bf8` — Select: `failed` (path length 3)
- `workflow_9de6d08c6ecaaacca5` — Rectangle: `failed` (path length 3)
- `workflow_b2a29e97cc549b6caf` — Invite: `not_tested` (path length 4)
- `workflow_4ded5819f8f609b6a3` — ← All canvases: `failed` (path length 4)
- `workflow_62f8a9bc9db62ad4a8` — + Create canvas: `not_tested` (path length 5)
- `workflow_639850e3de35cdcd27` — Invite: `not_tested` (path length 6)
- `workflow_56b2aff2be15e354fa` — Invite: `not_tested` (path length 7)
- `workflow_8bf64563a4c536f995` — ← All canvases: `not_tested` (path length 7)
- `workflow_86bd539e895c8f3651` — + Create canvas: `not_tested` (path length 8)
- `workflow_6a39c8942608c45aac` — Invite: `not_tested` (path length 9)
- `workflow_90e771433e03237dc7` — Invite: `not_tested` (path length 10)
- `workflow_add4e65c0b9c962226` — ← All canvases: `not_tested` (path length 10)
- `workflow_b4ffae7a9435951431` — + Create canvas: `not_tested` (path length 11)
- `workflow_5a2c6460e1858064ac` — ← All canvases: `not_tested` (path length 10)
- `workflow_a419f8ba020c3c95a7` — + Create canvas: `not_tested` (path length 11)
- `workflow_eac988a05235101e54` — Text: `not_tested` (path length 10)
- `workflow_addf1207103f3c9fef` — Select: `not_tested` (path length 10)
- `workflow_08881c861eb9cf1ff6` — Rectangle: `not_tested` (path length 10)
- `workflow_10fa843406498b5289` — Line: `not_tested` (path length 10)
- `workflow_7e7b1f3611398a8781` — Ellipse: `not_tested` (path length 10)

## Observed but not replay-validated

- `feature_0ee68376a678d4eb` — + Create canvas leads to Whiteboard
- `feature_370641639ee87e53` — ← All canvases leads to Whiteboard
- `feature_569a5a9319a62443` — ← All canvases leads to Whiteboard
- `feature_5ac443ac642f4cf3` — Invite leads to Whiteboard
- `feature_5d80e8a1d743eefd` — Invite leads to Whiteboard
- `feature_6f45eff81e5b9668` — ← All canvases leads to Whiteboard
- `feature_71cd5e81e513f76a` — + Create canvas leads to Whiteboard
- `feature_831278b1747a0348` — ↗ Name your next canvas Owned by you · 10/31/2026 leads to Whiteboard
- `feature_cd25f1f7e5aa9b33` — ← All canvases leads to Whiteboard
- `feature_d47d38f5699a310e` — Invite leads to Whiteboard
- `feature_d5547c483a4cb393` — + Create canvas leads to Whiteboard
- `feature_f39f7b35534be50a` — Invite leads to Whiteboard
- `feature_fe6070d3519e2640` — + Create canvas leads to Whiteboard
- `feature_fe9a3793aa251db2` — ← All canvases leads to Whiteboard

## Failed or blocked transitions

- `tr_f83fcc9a398812b60638` — ↗ Sprint retro Owned by you · 10/31/2026: RuntimeError: saved return path restored 158c4499a9634164, expected 6988b6058aa9b0c4
- `tr_e37300db9d272a36bb21` — ↗ Design review Owned by you · 10/31/2026: RuntimeError: saved return path restored 158c4499a9634164, expected 6988b6058aa9b0c4
- `tr_4fe83d11882fc8d4e4c0` — Text: RuntimeError: saved return path restored ef993a812ae017a5, expected c8cc24d73269a8af
- `tr_f6da3917e26a7dd9b02a` — Select: RuntimeError: saved return path restored ef993a812ae017a5, expected c8cc24d73269a8af
- `tr_d2eb2881bdd6a0dc844b` — Rectangle: RuntimeError: saved return path restored ef993a812ae017a5, expected c8cc24d73269a8af
- `tr_31f7c8af4002e1fad923` — Line: RuntimeError: saved return path restored ef993a812ae017a5, expected c8cc24d73269a8af
- `tr_dff861cc1b8460049699` — Ellipse: RuntimeError: saved return path restored ef993a812ae017a5, expected c8cc24d73269a8af
- `tr_d74cc557fb69714c8a7e` — Scroll viewport: RuntimeError: saved return path restored ef993a812ae017a5, expected 9c1439487ef8e1b2
- `tr_a38e0897f78b96395af7` — ← All canvases: RuntimeError: saved return path restored ef993a812ae017a5, expected 9c1439487ef8e1b2
- `tr_74c2e7a39ffb8526d7c8` — Line: RuntimeError: return-path control missing: a96b655d943a3002
- `tr_3bced5233e8be87fc503` — ↗ Sprint retro Owned by you · 10/31/2026: RuntimeError: return-path control missing: 2d6a750e9da6abc8

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- HTTP discovery budget exhausted; exploration stopped before replay.
- HTTP verification budget exhausted; remaining transitions left untested.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
