# Next-step report

Implemented and measured a typed same-scope resource spider, shorter resource-aware readiness, and request provenance for restored prerequisites in the existing Agent 1 package. The strongest 180-second full-root Crawl Maze crawl fetched 16/91 independent marker paths (10 HTML, 3 JavaScript, 3 headers), with 32/32 replay attempts successful and 53 paths still untested. This is above the contemporaneous 3/91 legacy-settings run, but baseline variability (2–4/91) and non-identical exact source execution prevent a precise causal estimate. The 20-marker target was not met.

The change with clearest repeated evidence is readiness: three matched runs reached 11/91 each, observed 85 transitions versus 36, and attempted 31–32 replays versus 12 at the same wall budget. The spider contributed seven expected paths not fetched by the browser in its isolated run. The diverse replay scheduler failed to improve outcomes, so shallow replay is default. On the controlled JS lab, labeled area/control/request recall did not change; deepest replay path improved to four only in combined. The separate shop transfer repeat scored well but is not a fresh unseen-app result.

Graph A now represents typed source responses, references, and restored prerequisite request evidence. Final Crawl Maze audit: 2,198/2,198 graph connections had evidence and browser request count reconciled at 392/392. Secrets are excluded from committed artifacts; raw app traces remain ignored. API/model cost was $0.

The dominant measured blocker is breadth per wall time: just 16/91 expected paths reached, with 53 transitions left untested, 71 root reloads, and 56 restoration actions. The next most informative independent experiment is a matched scheduler that batches unseen same-scope HTML references by route novelty and restoration cost while preserving the current spider/readiness settings; score against frozen evaluator truth only after each run. Avoid further tuning using benchmark-only data.

Reproduce the primary run and post-run scoring with the commands in `COVERAGE_GENERALIZATION_REPORT.md`. The standard graph diagram is `agent1/experiments/resource_spider_ablation/combined_shallow_final/graph_a.mmd`. Full suite and commit status are recorded after final verification.

Final verification: the complete pytest suite passed after rerunning with loopback/browser permissions for its local fixtures. `git diff --check` passed; `.env` remains ignored and is not tracked. Total external model/API spending was $0.
