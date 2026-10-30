# Replay and evidence audit

## Replay results

Every replay result stays attached to the complete path instance. The 180-second fixed FIFO repeats attempted 31–32 paths and succeeded every attempt. The adaptive readiness repeats attempted 24 paths each and succeeded 24/24, while leaving 79–80 transitions untested. The 300-second adaptive run attempted and succeeded 54/54, but left 98 of 152 observed transitions untested. The serious 54/54 rate is conditional attempt reliability, not complete replay coverage.

The normal 180-second adaptive runs included 1–2 expected marker paths in their successful replay network events. A matched diverse-replay variant included 5 expected marker paths in successful replay events in the first run and 6 in the repeat. One diverse run failed 1 of 22 attempts; the other succeeded 23/23. Diverse replay did not reduce the number of untested paths (80 and 82) or increase discovery beyond 25/91. It is a promising route/action diversity option, not a proven reliability improvement, and remains opt-in.

The explorer recorded 137 root reloads and 171 restoration actions in the 300-second run, compared with approximately 70–72 root reloads and 54–74 restoration actions in 180-second runs. This scale-up is expected with a larger state archive, but it consumes action budget. Adaptive budget reservation produced 28/28 replay successes and 71 untested transitions in one run, at 24/91 discovery; it traded one marker for four more replay attempts versus the 25-marker adaptive fixed-reserve run. It is not the selected default.

## Evidence integrity

The serious Graph A reports 1,876 complete connection-evidence records out of 1,876, zero missing evidence records, zero model calls, and zero external cost. Its internal false-merge audit reports 0, but this audit is structural and is not an independent semantic equivalence proof. The independent shop fixture evaluator separately confirmed distinct product-instance and context preservation at 1.0 for that fixture.

The resource nodes preserve source response URL, source type/element/header, reference relation, resource class, depth, queue decision, HTTP status, redirect outcome, extracted-reference counts, and elapsed evidence. Static candidates, safe fetched resources, browser-observed requests, UI transitions, and fresh-context replay outcomes remain distinct. A statically referenced resource is not an observed transition; a successful GET is not a verified business workflow.

The JavaScript AST pass operates only on bounded response text. It resolves literals and simple constant concatenations, emits unresolved evidence for non-static expressions, and does not execute code. API references are recorded with an observed-only decision unless an authorized browser action triggers their actual request; unknown HTTP methods are never silently submitted by the spider. Sensitive query values remain redacted by the preexisting evidence pipeline.

## Known audit limits

- Crawl Maze's independent marker scorer matches paths, not semantic business outcomes. It does not establish vulnerability coverage or complete functionality.
- Replay marker matches count matching successful network paths in complete replays. They do not mean the marker endpoint was the intended result of a business operation.
- 0 reported graph evidence gaps means required provenance fields were populated under the current schema; it is not proof that all relevant paths were discovered.
- The false-merge counter is a self-audit, not independent ground truth.
- Cross-context queue sharing reduced repeated budget-limit records in one ablation, but its one-marker difference does not establish an improvement in path recall.
- No benchmark target, authenticated user data, or API keys were exported into the committed report artifacts. Full graphs and traces remain ignored local files.

The serious run's inspectable Graph A is `agent1/experiments/serious_budget/adaptive_readiness_adaptive_ast_fifo_300s/graph_a.json`; its committed diagram is [`graph_a_serious_300s.mmd`](agent1/experiments/crawler_breakthrough_20261030/graph_a_serious_300s.mmd). The representative repeated 180-second diagram is [`graph_a_adaptive_180s.mmd`](agent1/experiments/crawler_breakthrough_20261030/graph_a_adaptive_180s.mmd). The repeated raw Graph A JSONs remain in their ignored local experiment directories.
