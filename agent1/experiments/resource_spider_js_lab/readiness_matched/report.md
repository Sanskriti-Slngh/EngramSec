# Agent 1 run agent1-20261030T040318Z

- Code revision: `decc0a2788a8f8c91c4d65427ef36da8c2d581c5+mapper-ea5b01ebeb1f`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:49838/`
- Elapsed: 60.416 seconds
- Browser actions (including setup/replay): 87
- Replay-validated navigation categories: 5
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 25
- Replay navigation success: 10/10
- Replay failures / untested paths: 0/21
- Graph connections with complete evidence: 427/427
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 1
- Redundant raw states: 3
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_21cb4c89afa576c2` — Overview opens /shallow/a
- `feature_38abb14282d03e97` — News opens /shallow/b
- `feature_3fdf7d4ac7486ad3` — Load late reports leads to JavaScript Readiness Lab
- `feature_4e99c95dbd8a7ac6` — Load late reports leads to JavaScript Readiness Lab
- `feature_572196394a692cc5` — Overview opens /shallow/a

## Functional path-instance outcomes

- `workflow_ebc5e4b75d88bd5a5c` — Public alias area: `navigation_only` (path length 1)
- `workflow_ffcea0ff8cf643fb35` — Load alias data: `not_tested` (path length 2)
- `workflow_93ec59a22983afc206` — Overview: `navigation_only` (path length 2)
- `workflow_619436a807b86f40ce` — Refresh status: `unresolved` (path length 1)
- `workflow_18c6e3f213d4e3644a` — Open workflow: `unresolved` (path length 1)
- `workflow_ee1bbe36245844d72e` — Continue setup: `not_tested` (path length 2)
- `workflow_178c809563ffe20701` — Open workspace: `not_tested` (path length 3)
- `workflow_09bfa82a8279cabf7e` — Workspace detail: `not_tested` (path length 4)
- `workflow_e7cf73bc78eb27e9ec` — Load late reports: `unresolved` (path length 1)
- `workflow_da9e88293fa05b87b1` — Open reports: `navigation_only` (path length 2)
- `workflow_214725dff74a6140c6` — Overview: `navigation_only` (path length 1)
- `workflow_2c59bf70c4abbddbd1` — News: `navigation_only` (path length 1)
- `workflow_1853864feafee61092` — JS Lab: `navigation_only` (path length 1)
- `workflow_a6c0c62e93b2ae28d8` — Open workflow: `not_tested` (path length 2)
- `workflow_f99c612eedcdc14cac` — Load late reports: `unresolved` (path length 2)
- `workflow_435f4a9b6c75ec1786` — Continue setup: `not_tested` (path length 3)
- `workflow_cfc446751ab2dd48be` — Public alias area: `not_tested` (path length 4)
- `workflow_81d017b5839e6effba` — News: `not_tested` (path length 2)
- `workflow_b177295a41f398b1e5` — Open workflow: `not_tested` (path length 2)
- `workflow_985ee0c910ec6a13fb` — Public alias area: `not_tested` (path length 3)
- `workflow_26bc8ec8a6f893c210` — JS Lab: `not_tested` (path length 2)
- `workflow_996a1a285f60e079b2` — Open workflow: `not_tested` (path length 3)
- `workflow_4d0c30aa98e772c1c8` — Public alias area: `not_tested` (path length 2)
- `workflow_7c1ac7e95ba6658f38` — Load late reports: `not_tested` (path length 3)
- `workflow_54e34e4c488fbed180` — Open workspace: `not_tested` (path length 4)
- `workflow_eeed1f79a892a7f9ea` — Public alias area: `not_tested` (path length 2)
- `workflow_a334bffdf1fe115d68` — Public alias area: `not_tested` (path length 3)
- `workflow_a0a7834a7af1d9b5c4` — Open reports: `not_tested` (path length 3)
- `workflow_196ba9dc7d6350d41f` — Open reports: `not_tested` (path length 4)
- `workflow_9069f4a899afc71204` — Refresh status: `not_tested` (path length 2)
- `workflow_825e6724b46fd0b517` — Refresh status: `not_tested` (path length 2)

## Observed but not replay-validated

- `feature_1a030fea4681f1de` — JS Lab opens /
- `feature_57596745286f0170` — Continue setup leads to JavaScript Readiness Lab
- `feature_65aaa97a2117e3ad` — Open workspace opens /workspace
- `feature_66d712baf9e36c1c` — News opens /shallow/b
- `feature_6b4971396990b395` — Public alias area opens /alias-area
- `feature_805a5ea26d66d287` — Workspace detail opens /workspace/detail
- `feature_9c45708a2b4eccc1` — Open workflow leads to JavaScript Readiness Lab
- `feature_a1b7f7dfecb37603` — Open reports opens /reports
- `feature_a90ee4fc4b1202df` — Load late reports leads to JavaScript Readiness Lab
- `feature_c449436cb1de966e` — Continue setup leads to JavaScript Readiness Lab
- `feature_d321ac671fa5a6b9` — Open workflow leads to JavaScript Readiness Lab

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
