# Agent 1 focused SiyuCMS interaction report

Date: 2026-10-28
Branch: `agent1-browser-mapper-20261028`

## Outcome

Agent 1 completed and independently replayed one anonymous SiyuCMS function beyond opening a page: search. The complete observed path was:

`anonymous home → toggle search → exposed GET search form → fill search field → submit → query-specific result links`

The `php` workflow had supported functional evidence in 2/2 fresh browser contexts. Each replay also submitted the contrasting ordinary query `Linux`. `php` produced six result-link labels containing the query; `Linux` produced one different query-matching result link. Their result target sets and meaningful-content fingerprints differed in both replays. A click, HTTP status, title, or echoed input was not used as sufficient evidence.

This is one verified anonymous search workflow, not a claim of broader SiyuCMS coverage.

## Content-filtering checks

The five paired browser fixtures were first run against the unchanged implementation. A and D passed; B, C, and E failed (`.FF.F`), reproducing three risks:

- **A — view count only: rejected as a defect.** A changing view count beside unchanged article content remained equivalent, as intended for this workflow.
- **B — article content beside a view counter: reproduced and fixed.** Removing the closest `div` erased the article as well as the counter, causing different articles to compare equal.
- **C — meaningful record date: reproduced and fixed.** A meaningful `<time>` record date was normalized away by the global date/clock expression.
- **D — explicitly cosmetic clock: rejected as a defect.** A clock explicitly marked `data-volatile` remained equivalent, as intended.
- **E — carousel content: reproduced and fixed.** Removing whole carousel regions silently erased differing featured content.

The smallest general fixes were to retain carousel regions; never remove a `div` merely because it contains a view icon; retain ordinary `<time>` elements and calendar/clock text; and reserve cosmetic removal for explicit DOM markers. Render-runtime durations remain narrowly normalized. Raw body observations are still retained separately.

Final content-filter fixture result: 5/5 passed. The focused extraction/toggle/cosmetic set passed 7/7. The single final full suite passed 23/23.

## Interaction and validation changes

- Common implicit toggles declared with `onclick`, `aria-controls`, `data-toggle`, `data-target`, or an ID beginning `toggle-` can now be registered as observed controls. Missing accessible labels fall back to an observed element ID, with separators normalized. This exposed SiyuCMS's icon-only `toggle-search` prerequisite without a target-specific selector.
- Supplied deterministic input references are now recorded as `input-plan:...`, not inaccurately as model-cache values.
- `experiments/run_siyucms_search_validation.py` executes only observed safe controls, preserves the prerequisite/action path and raw observations, and evaluates non-echo result evidence plus a contrasting query.
- The first direct attempt to click the covered search input failed. Browser hit-testing showed a sibling `text-content` region above the input. That failed attempt is retained in the evidence; executing the observed toggle resolved it.

## Replay measurements

- Fresh-context navigation reproduced: **2/2**
- Fresh-context functional outcome supported: **2/2**
- Validation failures: **0**
- Unresolved: **0**
- Untested paths in this selected workflow: **0**
- Browser actions in the two verification contexts: **16**
- Verification-run elapsed time: **7.073 seconds**
- Local-model calls: **0**
- Groq/OpenAI calls: **0**
- External cost: **$0**
- Focused iteration wall time: approximately **7 minutes**, below the 60-minute cap

Three bounded discovery sessions were used, followed by the two verification contexts. No additional live target experiments were run afterward.

## Graph A and evidence

- Compact Graph A: `agent1/experiments/siyucms_search_milestone/graph_a.json`
- Readable diagram: `agent1/experiments/siyucms_search_milestone/graph_a.mmd`
- Raw observations, action/network evidence, failed discovery attempt, and replay checks: `agent1/experiments/siyucms_search_milestone/evidence.json`

Graph A keeps `navigation_reproduced` and `functional_outcome_supported` separate and retains the vocabulary for `validation_failure`, `unresolved`, and `untested`. Both replay instances retain their own result links, targets, content fingerprints, and checks; grouped success is not projected onto untested instances.

## Exact reproduction command

With SiyuCMS running at the configured local URL:

```bash
.venv/bin/python experiments/run_siyucms_search_validation.py --url http://127.0.0.1:51707/ --out agent1/experiments/siyucms_search_milestone
```

## Limitation and next step

The outcome rule is strong for this observed search UI because result-link labels contain the submitted query and a contrast changes both targets and content. It is not a universal relevance judgment, and it does not evaluate authenticated or state-changing behavior.

The single most informative next step is to integrate this paired-query, non-echo outcome assertion into the main exploration/replay pipeline so an automatically discovered search action can receive the same path-instance validation without a targeted runner.
