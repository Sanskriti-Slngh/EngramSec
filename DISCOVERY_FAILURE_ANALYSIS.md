# Discovery failure analysis

This report separates the mapper's runtime evidence funnel from the evaluator's post-run matching. Expected-path matching was performed only after exploration by `experiments/score_crawlmaze_posthoc.py`; the mapper did not receive the expected path list.

## Largest observed losses

The serious 300-second run began at the Crawl Maze root and reached 37/91 paths under the post-run scorer. The generic funnel was:

| Stage | Expected paths | Interpretation |
|---|---:|---|
| Expected denominator | 91 | Five public testbed categories; used by evaluator only. |
| Candidate reference or browser observation | 52 | Evidence contained a matching expected path. |
| Not referenced | 39 | Largest loss: no matching literal candidate or successful browser request existed in Graph A. |
| Queue admitted | 36 | The evaluator's subset of matching references admitted for safe GET fetch. |
| Spider attempted and succeeded | 27 | All expected paths reached by the spider returned successful responses. |
| Browser requested successfully | 23 | Browser network evidence reached these paths. |
| UI state reached | 2 | Matching path was represented as a browser state; this is not a functional-outcome measure. |
| Successfully replayed path network | 3 | Matching expected paths occurred in completed replay traffic. |

The union was 37/91. Sixteen of the 52 referenced expected paths were not queue-admitted, and nine admitted expected paths were not attempted before the run ended. These are evaluator-side path counts, not a mapper label or policy input. In aggregate runtime evidence, 166 resource GETs were attempted, 164 succeeded, and 2 failed; 224 references were extracted, 168 new unique references were emitted from 164 response bodies, and 166 candidates were queued. No expected marker paths were used to tune the implementation.

## Stage-by-stage diagnosis

### Candidate generation and extraction

The highest ceiling is still candidate generation: 39 expected paths had no matching reference or browser request. The 180-second adaptive repeats grew expected references from 27/91 under fixed readiness to 35/91, mostly by visiting more application pages and response-producing branches, but this left 56/91 unreferenced. A depth-6 traversal did not help: it extracted more references but the union fell to 17/91; the depth-3 baseline produced no depth-limited evidence. This argues against simply following longer static chains.

AST parsing did not improve the Crawl Maze score against the legacy regex parser under the matched 180-second configuration (both 21/91, 27 references, 15 spider paths). The parser is retained for syntax-aware coverage and conservative unresolved-expression records, not as a claimed marker-score improvement.

### Queue admission and fetch

The run-scoped spider fetched recursively discovered same-scope candidates and protected the total GET budget. In the common 100-GET configuration, document cap 70 created 13–21 class-limited records across repeats. Removing the cap by raising documents to 90 used all 100 GETs but scored 19/91, versus 21/91 at 89 GETs with class quotas; it is not a win. At 300 seconds the 200-GET budget produced 166 GETs and 37/91, while 39 paths still had no candidate. More requests alone cannot cross that reference-generation ceiling.

The shared run frontier reduced repeated class-budget records (16 versus 566 in a single no-shared run), but marker outcomes were 21 versus 22 in those single runs. That one-marker difference is within run variation and does not establish a coverage benefit from sharing. Sharing remains the less wasteful queue implementation; the score effect is unresolved.

### Browser observation and UI reachability

The 300-second graph had 134 grouped states, 129 distinct routes, 152 observed transitions, 838 browser network events, and 2/91 evaluator-matching UI states. This is not complete application-area recall: the Crawl Maze marker denominator scores specific request paths, while the UI graph represents other reachable states too. HTML, header, and JavaScript reference categories were all present in Graph A; many browser-visible actions remained unattempted or did not result in a matching path.

### Scheduling and waiting

Route-diverse, marginal-yield, random, and FIFO resource ordering all scored the same 21/91 set in the matched 180-second matrix. Their action totals varied by only four actions, and replay attempts were 32–33. More elaborate URL frontier scoring did not solve missing references.

Adaptive readiness, by contrast, reached 25/91 in three repeats and reduced interactive readiness waiting by roughly 30 seconds. It also generated 18–19 more transitions, leaving 79–80 untested rather than 52–54. In the 300-second run, 137 root reloads and 171 restoration actions consumed substantial budget. The 180-second adaptive configuration improved discovery, but replay completeness did not improve.

### Replay

Every fixed FIFO attempt succeeded (31–32/31–32), and every normal adaptive shallow attempt succeeded (24/24). The serious run succeeded 54/54. This high conditional reliability coexists with 98 untested transitions; it must not be reported as broad replay coverage. Diverse replay touched more matching marker destinations in successful replays (5 and 6) than shallow scheduling (1–2) in two runs, but one repeat failed 1 of 22 replay attempts and left 82 transitions untested. The measured case for diverse scheduling is destination variety, not improved replay reliability or completeness.

## Largest supported bottleneck

The largest measured gap is still unreferenced surfaces (39/91 in the serious run), followed by safe queue admission (16 evaluator-matching references not admitted) and work allocation from admitted to attempted (9 not attempted). Readiness accounted for a measurable share of wall time, and optimizing it yielded more candidate-generating page visits. Depth and queue-order experiments did not help. The next development loop should improve generally observed URL-bearing structures and browser-triggered runtime evidence, while keeping API candidates with uncertain methods unsubmitted and replay outcomes path-specific.

This does not establish that the app has only 39 missing HTML attributes or that changing any specific target URL would be safe. The category results and visible response evidence are diagnostics only; no per-path evaluator output was fed to the mapper.
