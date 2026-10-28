# Agent 1 integrated search-verification report

Date: 2026-10-28

## Outcome

The ordinary Agent 1 pipeline now discovers safe GET search forms from browser-observed field semantics, executes observed prerequisites, stores exact deterministic input plans in the ignored cache, and verifies search outcomes with two configured probes in two independent fresh browser contexts.

The final SiyuCMS run used the normal `agent1.cli map` command—not the dedicated historical validator—and automatically discovered:

`anonymous home → toggle search → Search GET form → query-specific result links`

The `Search` path was functionally verified. This establishes one anonymous SiyuCMS search workflow; it does not change the historical interpretation of the old 16 navigation categories.

## Implementation

- `agent1/search.py` recognizes safe GET search forms using observed input type, label, name, placeholder, description, method, and form shape. It contains no SiyuCMS selectors, routes, or result URLs.
- Configurable CLI options `--search-probe` and `--search-contrast` provide two distinct ordinary probes.
- Deterministic plans are saved in `agent1/.cache/` and artifacts retain protected plan references. A missing referenced plan raises an error rather than silently generating a different value.
- Search-related controls receive bounded priority so the existing frontier can cross observed prerequisites such as an icon-only toggle. The explorer still executes and records each control through the normal transition machinery.
- Each eligible search transition receives two paired-search replay records. Every record creates a fresh browser context and executes the complete prerequisite/action path for both probes.
- Functional verification requires query-bearing result-link labels for both probes and different result target sets. Changed URL, echoed input, title, or full-page content alone cannot verify the function.
- Navigation checks and functional checks remain separate. An echo-only fixture has successful navigation replays but an `unresolved` functional outcome.
- Standard Graph A now includes the full workflow path, both replay IDs, functional checks/evidence, protected plan references, and the actual primary/contrast replay observations.
- A grouped feature is promoted only after its transition satisfies all required replays; one successful path instance does not validate sibling instances.

## Independent regressions

Focused tests cover:

- Successful GET search with distinct result links: verified.
- Fake search that only echoes input: navigation-valid, functionally unresolved.
- Hidden form requiring an observed toggle: discovered with a two-action path and verified.
- Exact deterministic query replay: exploration plus two primary replays used `alpha`; the two contrast executions used `beta`; the default generated search value was never used.
- Missing protected plan: explicit failure rather than regenerated input.
- Standard Graph A replay observations and paired replay IDs.
- Existing wrong-record and cosmetic-content regressions remain passing.

Focused search suite: **4/4 passed**. The final full Agent 1 test suite passed **27/27**.

## Live SiyuCMS evaluation

Limits: one worker, GET only, anonymous, no model, no paid provider, two transitions, 60-second cap.

The initial integrated run functionally verified search, but the icon-only submit was represented as `unnamed button`; the existing volatile-label filter therefore omitted its feature node. This was a representation defect, not a replay failure. The generic fix derives `Search` from the observed search field when the submit lacks an accessible label.

Final corrective run (`siyucms_search_integrated_v2`):

- Observed paths: `toggle search` (length 1), `toggle search → Search` (length 2).
- Replay-validated navigation features: **2**.
- Verified functional workflows: **1** (`Search`).
- Search paired verification: **2/2** fresh contexts.
- All navigation replays: **3/3** (one toggle replay plus two search replays).
- Replay failures / untested paths: **0 / 0**.
- Graph evidence complete: **436/436** connections; missing: **0**.
- Browser actions, including discovery, restoration, probes, and replay: **25**.
- Elapsed: **12.823 seconds**.
- Model calls / external cost: **0 / $0**.

The earlier targeted milestone reported search verification 2/2 in 7.073 seconds and 16 verification actions, excluding main-explorer discovery. The integrated run is therefore functionally consistent but not a speed comparison: its 25 actions and 12.823 seconds include automatic discovery, prerequisite restoration, the toggle replay, paired search replays, checkpointing, and standard Graph construction.

## Artifacts and reproduction

- Standard Graph A: `agent1/experiments/siyucms_search_integrated_v2/graph_a.json`
- Readable diagram: `agent1/experiments/siyucms_search_integrated_v2/graph_a.mmd`
- Metrics/report: `agent1/experiments/siyucms_search_integrated_v2/metrics.json` and `report.md`
- The initial label-defect run remains preserved in `siyucms_search_integrated_v1`.

Exact command:

```bash
.venv/bin/python -m agent1.cli map \
  --url http://127.0.0.1:51707/ \
  --out agent1/experiments/siyucms_search_integrated_reproduction \
  --policy grouped --seconds 60 --max-transitions 2 --max-browser-actions 80 \
  --search-probe php --search-contrast Linux \
  --context-label siyucms:anonymous-search
```

## Limitations

The generic evaluator is deliberately conservative. It remains unproven for search results whose useful links do not contain the query text, forms with multiple required ordinary fields, relevance ranking, authenticated search, POST search, and non-link result widgets. Those cases remain unresolved rather than receiving weaker success criteria.

The next most informative test is a second independent real search UI whose result labels do not literally repeat the query, to determine whether another browser-observable non-echo signal can be added without increasing false positives.
