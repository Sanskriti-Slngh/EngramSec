# Agent 1 run agent1-20261030T203015Z

- Code revision: `5710c01fbcd2b09fab0886cbc0eedf65b0b1510e+mapper-4e6344388315`
- Policy: `multidimensional`
- Target: `http://127.0.0.1:3460/`
- Elapsed: 19.991 seconds
- Browser actions (including setup/replay): 43
- Replay-validated navigation categories: 10
- Verified functional workflows: 0
- Reproduced validation failures: 0
- Functional outcomes unresolved/untested/failed: 0
- Replay navigation success: 10/10
- Replay failures / untested paths: 0/0
- Graph connections with complete evidence: 229/229
- Graph connections missing evidence: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Fully replay-validated navigation categories

- `feature_2e19750bfe9e891e` — misc/ opens /javascript/misc/
- `feature_3699dc387e5599e0` — known-files/ opens /misc/known-files/
- `feature_41ba3209725933d5` — manifest.html opens /html/manifest.html/
- `feature_4719d72f368a294c` — refresh/ opens /headers/refresh/
- `feature_7d1756ba5d7cb6e4` — HTML opens /html/
- `feature_93ea1e291784ce15` — JavaScript opens /javascript/
- `feature_9fe133e4cf904946` — Misc opens /misc/
- `feature_a272edaa1ef4a316` — sitemap.xml.html opens /misc/known-files/sitemap.xml.html/
- `feature_c06bd8289171ed68` — Response headers opens /headers/
- `feature_e1efb4ee365f95fc` — string-variable.html opens /javascript/misc/string-variable.html/

## Functional path-instance outcomes

- `workflow_a6efd5acb891ec57d1` — Response headers: `navigation_only` (path length 1)
- `workflow_42071210abd66f5f6a` — refresh/: `navigation_only` (path length 2)
- `workflow_ceed8a3fe7b2773d2a` — Misc: `navigation_only` (path length 1)
- `workflow_7982cc2398f16f59f9` — known-files/: `navigation_only` (path length 2)
- `workflow_43273fc827d917de4e` — sitemap.xml.html: `navigation_only` (path length 3)
- `workflow_7f978512905c21313e` — JavaScript: `navigation_only` (path length 1)
- `workflow_1b99adf9b7d6ddb90e` — misc/: `navigation_only` (path length 2)
- `workflow_aa29945f8c7c5a3e25` — string-variable.html: `navigation_only` (path length 3)
- `workflow_4a921c7f9d2cafc3eb` — HTML: `navigation_only` (path length 1)
- `workflow_848aeb201cc1cd0359` — manifest.html: `navigation_only` (path length 2)

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- None.

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
- unsupported_connections is retained only as a backwards-compatible failed-replay alias; use replay_failures and graph_connections_missing_evidence for distinct claims.
