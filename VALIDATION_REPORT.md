# Agent 1 interactive workflow validation report

Date: 2026-10-28

Branch: `agent1-browser-mapper-20261028`

Iteration start: 2026-10-28 09:13:59 EDT
Iteration end: 2026-10-28 09:39:38 EDT (about 26 minutes wall time; below the four-hour cap)

## Outcome

Agent 1 now distinguishes navigation replay from functional verification at the exact path-instance level. It records cosmetic-normalized meaningful content, explicit page outcome signals, raw replay observations, bounded form attempts, functional status, untested paths, and graph-connection evidence completeness. A reproducible error remains evidence but is not counted as a successful function.

Independent fixtures demonstrate two replayable functional workflows: an ordinary constrained form submission and a multi-step workspace setup whose fresh-context replay must repeat its cookie-setting prerequisite. A separate outcome fixture produces one functionally verified path, one reproduced validation failure, and one advertised but untested action in the same Graph A.

The historical SiyuCMS result of 16 is retained but relabeled accurately: it is 16 replay-validated navigation categories, not 16 completed functional workflows.

## Review findings verified

1. **Verified.** All 16 historical feature descriptions are link/navigation categories such as login, registration, product detail, article detail, and download routes. The old schema had no functional outcome representation.
2. **Verified in code and reproduced.** Replay checked group signature, normalized route, and title. Alternating same-URL search results replayed as success, and a fresh context that opened record 1 instead of the observed record 2 also passed.
3. **Verified in code and reproduced.** Body text was stored as an excerpt but omitted from both signatures. Different search results and validation feedback collapsed while URL, controls, forms, and title stayed unchanged.
4. **Verified.** The old merge audit compared route/control/form/session structure closely related to grouping. It reported no problem while independent fixture ground truth found two incorrect merges.
5. **Verified.** The old model path ranked controls only; `_fill_form` used fixed generated values. The earlier small-model result did not test form interpretation or feedback correction.
6. **Verified.** `unsupported_connections` was exactly failed replay count, not missing-evidence analysis. It remains only as a backwards-compatible alias; new reports use `replay_failures` and `graph_connections_missing_evidence` separately.

The cosmetic-change concern did **not** reproduce against the old mapper: changing timestamps already stayed in one structural state. The new content layer initially over-split SiyuCMS because of framework runtimes and view counters, so narrowly observed cosmetic normalization was added and tested rather than broadly deleting numbers.

## Independent fixture design

The mapper is run as a website-only client. It does not import fixture behavior or expected results.

- `tests/fixtures/interactive_app.py` serves the browser application.
- `tests/fixtures/ground_truth.py` separately declares evaluator expectations.
- `experiments/run_validation_fixtures.py` runs the mapper and then evaluates saved artifacts/events.
- `experiments/evaluate_validation_artifacts.py` re-evaluates preserved evidence without changing it.

Cases cover alternating search results at one URL, failed/successful form validation, a required multi-step setup, wrong-instance replay, timestamp/view-count cosmetics, and a combined Graph A outcome example. Server state is reset between cases; every mapper replay starts in a fresh browser context.

## Before measurement: unchanged mapper

Preserved run: `agent1/experiments/validation_baseline_778bbbd_v2/`

Post-run evaluation: `posthoc_evaluation_v2.json` (`raw_evidence_changed: false`)

Across the five matched cases:

- Replay: 7/7 reported successful; 0 reported failures.
- Independent navigation-validation false positives: 2 (alternating search result and wrong record).
- Functional false positives: 1 (reproduced invalid form submission counted by the historical “validated workflow” metric).
- Functional false negatives: 1 (successful prerequisite-backed completion existed but had no functional representation).
- Incorrect merges: 2.
- Unnecessary splits: 0.
- Browser actions: 43.
- Functional/evidence-completeness metrics: unavailable in schema 1.0.

This baseline rejects the idea that high replay success alone established correct workflows: all replay checks passed while independent ground truth identified wrong content and an unsuccessful operation.

## Representation and validation changes

- Raw body text remains preserved. A separate meaningful-content view removes semantic cosmetics such as `<time>`, common debug toolbars, carousel regions, explicit volatile regions, rendered runtime durations, and view-count elements.
- Both raw and grouped signatures include the resulting content fingerprint. “Result Alpha” and “Result Beta” remain different; runtime duration and marked timestamp/view-counter changes collapse.
- Observations record explicit visible outcome signals from outcome attributes, ARIA alert/status/live regions, and conventional success/error classes. Page-provided `success` or `result` signals may support functional verification; `validation_error` never does.
- Replay now checks group, route, normalized title, content fingerprint, and exact outcome-signal fingerprints, and saves the raw replay observation.
- Functional status is per transition/path instance: `functional_verified`, `validation_failure`, `navigation_only`, `unresolved`, `failed`, or `not_tested`.
- A grouped feature is fully replay-validated only when every recorded evidence transition for that feature has a successful replay. Validated, failed, and untested transition IDs remain visible separately.
- Graph connection completeness independently checks advertised-control/source observation, source/action registration, action/result observation, and replay/raw-observation/check evidence. This establishes evidence presence, not behavioral truth.
- Metrics separately report navigation categories, functional workflows, validation failures, replay attempts/success/failure/untested, and graph evidence completeness. The historical `unsupported_connections` name is no longer used for evidence completeness.

The outcome semantics follow page-provided browser evidence rather than an LLM judgment. The focused standards references were [WAI-ARIA alert](https://www.w3.org/TR/wai-aria-1.2/#alert), [WAI-ARIA status](https://www.w3.org/TR/wai-aria-1.2/#status), and the [WHATWG pattern constraint](https://html.spec.whatwg.org/multipage/input.html#the-pattern-attribute). The content normalization and path-instance policy are EngramSec adaptations, not claims from those standards.

## After measurement: final deterministic layer

Preserved run: `agent1/experiments/validation_content_outcomes_v3/`

Across the same five cases:

- Replay: 6/8 navigation successes; 2 correct failures for nondeterministic search and wrong-record replay.
- Verified functional workflows: 2 (constrained form and multi-step completion).
- Independent functional false positives: 0.
- Independent functional false negatives: 0.
- Independent navigation-validation false positives: 0.
- Incorrect merges: 0.
- Unnecessary splits: 0, including changing timestamps and view counts.
- Graph connections with complete required evidence: 49/49; missing evidence: 0.
- Browser actions: 53.
- Model calls/tokens/cost: 0/0/$0.

The combined `outcomes` case adds one explicit success and one validation failure (both 2/2 reproducible navigation replays) while leaving an ordinary action visibly `not_tested`. It is a diagram demonstration, not included in the five-case before/after totals.

## Targeted local-model assistance

Model assistance is limited to ordinary values for currently observed, non-sensitive field IDs. The structured response must copy an `fld_...` ID exactly. Passwords, files, credentials, tokens, destructive actions, and invented field IDs are rejected. Retries are capped at one. Artifacts store protected cache references, not proposed raw values; every executed attempt and its observed feedback is preserved. Functional validation remains deterministic.

The target fixture deliberately rejects the deterministic ordinary value and exposes a visible validation message identifying the acceptable demo value.

- Initial `llama3.2:latest` run: negative result preserved. Two calls (588 input/277 output tokens) supplied no valid observed field IDs, so fallback reproduced the failure.
- Tightened contract, run 1: deterministic produced `validation_failure`, 0 verified; llama used one feedback retry to produce `validation_failure → functional_verified`, 1/1 replay. Two calls, 690 input/60 output tokens, 11 browser actions, 4.675 seconds, $0.
- Fresh-instance repeat: same outcome. Two calls, 678 input/56 output tokens, 11 browser actions, 6.453 seconds, $0.

This supports the narrow claim that the installed 3B local model helped this observed-feedback fixture after the structured-ID contract was corrected. It does not establish general form competence, and it does not rehabilitate the previous 0.5B control-ranking experiment or generalize its failure to other free models.

## SiyuCMS application

Final bounded anonymous run: `agent1/experiments/siyucms_validation_v4/`

- Elapsed: 60.375 seconds; browser actions: 46; model calls/cost: 0/$0.
- Observed transitions: 13; transition failures: 1.
- Replay: 9 attempted, 9 navigation successes, 0 failures, 4 observed paths untested.
- Fully replay-validated navigation categories: 4.
- Verified functional workflows: 0.
- Functional status: 8 navigation-only, 1 unresolved, 4 not tested.
- Graph connections with complete evidence: 2,321/2,321.

The first content-sensitive Siyu run correctly revealed an over-sensitive implementation: 40/40 source restorations failed because a rendered framework debug panel changed. A second isolated a floating runtime badge; a third showed article view counters incrementing. The final normalization excludes those semantically identified cosmetic elements while preserving record/result text, and the fixture regressions guard both sides.

No account credentials or reset contract were available. Live POST forms remained disabled. Therefore this run demonstrates conservative anonymous navigation replay and evidence accounting only—not authenticated or state-changing SiyuCMS functionality.

## Graph A example

- JSON: `agent1/experiments/validation_content_outcomes_v3/outcomes/graph_a.json`
- Readable Mermaid: `agent1/experiments/validation_content_outcomes_v3/outcomes/graph_a.mmd`
- Full report: `agent1/experiments/validation_content_outcomes_v3/outcomes/report.md`

The diagram shows green `functional_verified`, orange `validation_failure`, and gray `not tested` path/action nodes. The JSON retains all exact advertisement, transition, replay, path-instance, and connection-evidence records.

## Testing and cost

The final suite covers evidence invariants, session/form grouping differences, content/cosmetic fingerprints, model field-ID rejection, spending controls, compact model inputs, state-changing prerequisites, resume behavior, same-URL result changes, constrained form success, multi-step completion, wrong-record rejection, cosmetics, and connection evidence. The preserved V0 suite remains separate.

External API spend remains cumulatively $0. Groq and OpenAI were not called. Paid access remains disabled. Ollama calls are local and free; the two successful model comparisons used four total calls, 1,368 input tokens, and 116 output tokens. The negative first model run used another two calls, 588 input and 277 output tokens.

No credentials, `.env`, browser authentication state, or raw model values are committed. Full raw/checkpoint/trace artifacts remain local and ignored; compact metrics/reports and the representative Graph A are checkpointed.

## Limitations

- Explicit success/result signals are strong browser evidence but still depend on honest application markup. An HTTP 200 or click alone never proves success.
- Cosmetic normalization is deliberately narrow and can still cause false splits on unseen volatile widgets or hide a genuinely meaningful counter if markup incorrectly presents it as a view counter.
- Fixture ground truth is independent of mapper rules, but it is a small synthetic suite, not proof of correctness on arbitrary applications.
- Evidence completeness proves required artifacts exist and cross-reference correctly; it does not prove the underlying application claim is true.
- State grouping remains reversible and conservative. The independent fixture evaluator, not the structural self-audit, supplies measured merge/split error counts.
- Model correction has two successful repeats on one form pattern. Broader form types and multilingual feedback remain untested.

## Exact reproduction commands

```bash
cd /Users/sanskritisingh/EngramSec

.venv/bin/python -m pytest -q
env PYTHONPATH=engramsec_v0 .venv/bin/python -m pytest engramsec_v0/tests -q

.venv/bin/python experiments/run_validation_fixtures.py \
  --out agent1/experiments/validation-reproduction \
  --seconds 12 --max-transitions 8

.venv/bin/python experiments/evaluate_validation_artifacts.py \
  agent1/experiments/validation_baseline_778bbbd_v2 \
  --out agent1/experiments/validation_baseline_778bbbd_v2/reanalysis-new.json

.venv/bin/python experiments/run_model_form_comparison.py \
  --out agent1/experiments/model-form-reproduction \
  --model llama3.2:latest --seconds 30

.venv/bin/python -m agent1.cli map \
  --url http://127.0.0.1:51707/ \
  --out agent1/experiments/siyucms-validation-reproduction \
  --policy grouped --seconds 60 --max-transitions 40 --max-browser-actions 200
```

Resume and focused-deepen commands remain documented in `agent1/README.md`. A resumed run preserves the original run identity, raw observations, path-level status, and spending/model accounting.
