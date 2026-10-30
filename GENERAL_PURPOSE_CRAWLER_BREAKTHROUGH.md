# General-purpose crawler breakthrough

Date: 2026-10-30
Branch: `agent1-browser-mapper-20261028`
Starting commit: `defbb1d`
End state: uncommitted until the final checkpoint described below

## Result

Agent 1 now combines the existing browser explorer with a run-scoped, recursive, typed resource frontier; bounded JavaScript AST reference extraction; and an opt-in adaptive readiness policy. On the same full-root Google Security Crawl Maze denominator, the prior serious run reached 16/91 markers. The updated fixed-readiness FIFO run reached 21/91, and the adaptive-readiness candidate reached 25/91 in all three 180-second repeats. A 300-second adaptive run reached 37/91. The 25/91 result clears the 25-marker initial target; 37/91 is substantial progress, but it remains below 50/91 and is not a claim of completeness.

The main evidence-backed gain is adaptive readiness, not a more elaborate resource queue. At 180 seconds it reduced interactive-readiness wait from approximately 62 seconds to 32–34 seconds and produced 25 rather than a 20–21 marker fixed-readiness range. The price was more discovered transitions and fewer total replay attempts: 24/24 attempts succeeded, but 79–80 transitions remained untested. The diverse replay policy reached more marker destinations through successful replays in two runs, but one of those runs had a failed replay and the untested count did not fall.

## Comparable Crawl Maze results

All runs began at `http://127.0.0.1:3460/`, used one browser worker, the same category denominator (CSS 1, headers 4, HTML 57, JavaScript 27, misc 2), 300 browser actions, 120 transitions, and 180 seconds unless marked otherwise. Resource GET total was 100; the common class caps were document 70, script 20, stylesheet 10, other asset 20. The target was the isolated public Google Security Crawl Maze development testbed. Expected locations were queried only by the separate post-run scoring script.

| Configuration | Budget | Any fetched | Referenced | Spider fetched | Browser fetched | Replay | Untested transitions | Resource GETs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Historical pre-change serious | 180 s, 300 actions | 16/91 | 22/91 | 8/91 | 11/91 | 32/32 | 53 | 100 |
| Current typed frontier, FIFO, fixed readiness | 180 s | 21/91 | 27/91 | 15/91 | 11/91 | 32/32 | 53 | 89 |
| Current FIFO repeat 2 | 180 s | 20/91 | 26/91 | 14/91 | 11/91 | 31/31 | 52 | 88 |
| Current FIFO repeat 3 | 180 s | 21/91 | 27/91 | 15/91 | 11/91 | 31/31 | 54 | 89 |
| Adaptive readiness repeat 1 | 180 s | 25/91 | 35/91 | 17/91 | 14/91 | 24/24 | 79 | 91 |
| Adaptive readiness repeat 2 | 180 s | 25/91 | 35/91 | 17/91 | 14/91 | 24/24 | 79 | 91 |
| Adaptive readiness repeat 3 | 180 s | 25/91 | 35/91 | 17/91 | 14/91 | 24/24 | 80 | 91 |
| Adaptive + diverse replay, repeat 1 | 180 s | 25/91 | 35/91 | 17/91 | 14/91 | 23/23 | 80 | 91 |
| Adaptive + diverse replay, repeat 2 | 180 s | 25/91 | 35/91 | 17/91 | 14/91 | 21/22 | 82 | 91 |
| Adaptive, serious budget | 301.7 s, 600 actions, 200 GETs | 37/91 | 52/91 | 27/91 | 23/91 | 54/54 | 98 | 166 |

The historical baseline and this iteration share the target, root, nominal time/action limits, and denominator. The historical graph did not record the newly introduced per-class limits or extractor configuration, so the cross-commit difference should be read as a bundled implementation comparison. Within-iteration ablations below isolate several components.

At serious budget, the post-run category totals were: HTML 31/57 fetched (34 referenced, 24 by spider and 19 by browser); headers 3/4 fetched; JavaScript 3/27 fetched by the browser and 14 referenced; CSS 0/1 and misc 0/2 fetched. The 37/91 union includes overlap and is not the sum of spider and browser counts. Only 2/91 expected marker paths appeared as Graph A UI states, and 6/91 appeared in successfully replayed network paths in the diverse-replay repeat. Marker reach is a URL-path proxy, not confirmed functional coverage.

## Discovery funnel and efficiency

In the serious 300-second run, post-run matching found 52/91 expected paths referenced by evidence, 36 admitted to the fetch queue, 27 expected paths attempted and successfully fetched by the spider, 23 successfully requested by the browser, and 2 present as UI states. Thirty-nine expected paths were not represented by any extracted reference or observed browser request. A further sixteen referenced paths were not queue-admitted and nine admitted paths were not attempted in this run's window. The spider made 166 GET attempts and received 164 successful responses; 2 requests failed. It extracted 224 typed references, admitted 166 unique resource candidates, and discovered 168 new unique references across 164 body-bearing responses (1.02 new references/response). Spider marker yield was 27/166 = 0.163 expected marker paths per GET.

At 180 seconds, the fixed FIFO run fetched 15 expected marker paths in 89 GETs (0.169 marker paths/GET), up from the historical 8/100 (0.080). The adaptive 180-second runs fetched 17 expected marker paths in 91 GETs (0.187). Browser fetches grew from 11 to 14. The 300-second run's time curve was 6 markers by 30 seconds, 15 by 60, 25 by 120, 34 by 180, and 37 by 300. This is a single run's cumulative curve; it is not a 600-second experiment.

The adaptive 180-second runs recorded about 85 seconds of passive readiness and 32–34 seconds of interactive readiness, versus about 79–80 and 62–62.5 seconds in the fixed repeats. Thus interactive wait fell by about 48%, while total measured readiness wait fell by about 17%. Adaptive mode yielded more transitions (103–104 versus 83–85), but replay attempted fewer of them. In the 300-second run there were 137 root reloads and 171 restoration actions. Root restoration remains an important action-cost target.

## Transfer and regression evidence

- The controlled JavaScript readiness lab was rerun twice at its established 60-second, 30-transition, 140-action configuration. Both runs retained 11/11 applicable areas, 1.0 control recall, 1.0 request-surface recall, 16 independent prerequisite paths replayed, 1.0 replay reliability, deepest replay path 4, and zero sensitive-value leaks. The second run exercises adaptive readiness through the opt-in policy.
- The disposable held-out-shop fixture was run with the typed spider enabled and its ordinary disposable form interactions allowed. Its separate post-run evaluator reported 8/8 applicable areas, 11/11 controls, 8/8 request structures, 18/18 replays, 1.0 instance/context/path recall, and 0 missing Graph A evidence connections. Request precision was 0.944; this is the known development shop, not a previously unused holdout.
- Historical full-root Crawlground performance remains 39/59. This iteration did not rerun its marker scorer, so preservation under that scorer is unverified. The existing Crawlground configuration did not enable the new spider and retains fixed readiness by default; this avoids silently changing its measured policy.
- No previously unused real application was available within the authorized local target set. The unrelated local service was not accessed. The known shop and JS lab are transfer checks, not held-out generalization evidence.

## Integrity, cost, and sources

The independent scorer ran only after each Graph A was closed. Agent 1 did not load expected marker URLs or labels. Static JavaScript analysis runs only on delivered same-scope response text; it does not execute scripts. Computed references remain unresolved, API candidates are not submitted as generic resource GETs, and external origins remain excluded. Graph A retained raw observations, resource provenance, request structures, path-specific replay outcomes, and unresolved records. The final serious graph reports 1,876/1,876 complete evidence connections and 0 self-audited false merges; the merge audit is structural and does not prove all state equivalence.

External model/API calls: 0. External spending: $0.00. All new Crawl Maze and fixture experiments were local. The experiment runner writes each run's configuration manifest and metrics. Raw checkpoints, traces, and Graph A JSON remain in the ignored local experiment directories; Graph A diagrams and aggregate reports are committed.

The implementation follows the complementary static/browser crawling model in [ZAP's Traditional Spider documentation](https://www.zaproxy.org/docs/desktop/addons/spider/) and [quick start](https://www.zaproxy.org/docs/desktop/addons/quick-start/). Static JavaScript extraction uses [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) and its [JavaScript grammar](https://github.com/tree-sitter/tree-sitter-javascript), without interpreting application code.

See [DISCOVERY_FAILURE_ANALYSIS.md](DISCOVERY_FAILURE_ANALYSIS.md), [COVERAGE_ABLATIONS.md](COVERAGE_ABLATIONS.md), [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md), and [REPLAY_AND_EVIDENCE_AUDIT.md](REPLAY_AND_EVIDENCE_AUDIT.md) for detail.

Committed Graph A diagrams and aggregate scoring artifacts are in [the evidence package](agent1/experiments/crawler_breakthrough_20261030/README.md). The full machine-readable Graph A files remain at the ignored local paths listed in that README.
