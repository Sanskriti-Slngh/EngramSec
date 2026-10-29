# Research next steps for Agent 1

Date: 2026-10-28

## Evidence boundary

These priorities use controlled-development results, public Crawlground aggregate/category scores, the post-freeze Google Security Crawl Maze aggregate evaluation, and published crawler research. They do not use WebExploitBench outputs, protected metadata, vulnerability locations, or exploit traces.

The current result has two sides. Interactive Crawlground coverage improved from 13/59 to 39/59 under the same serious action/transition limits. Yet the frozen mapper found only 4/91 expected Crawl Maze resource paths, and only 25/38 scheduled Crawlground replays succeeded. Agent 1 is therefore a substantially better interactive mapper, not a complete application-surface crawler.

## 1. General traditional reference and response discovery

**Measured weakness.** The independent Crawl Maze evaluator found 4.4% of applicable resources. Graph A contains anchors, browser navigation, and passive request traffic, but Agent 1 does not systematically register URL-bearing HTML attributes, response `Location`/`Link`/refresh hints, CSS `url()` references, form actions without a visible submit, or script/module resources as candidates. This is now the largest independently measured transfer gap.

**Method.** Add a passive, same-scope reference extractor modeled on the division of labor in ZAP: a fast traditional parser supplies typed candidates while the browser supplies JavaScript event/state discovery. Parse only URLs present in browser responses/DOM and retain source element/attribute/response evidence. Never guess endpoints. Classify resource fetch versus browser-navigation candidates so images and styles are not clicked as pages. Feed successful requests and navigations into the existing request-surface graph.

**Why it should work.** ZAP explicitly recommends running the traditional Spider and Client Spider together because their discovery mechanisms are complementary ([Spider](https://www.zaproxy.org/docs/desktop/addons/spider/), [Client Spider rationale](https://www.zaproxy.org/blog/2026-07-06-client-spider-now-recommended/)). The Crawl Maze misses are exactly the reference classes a traditional spider targets.

**Complexity/tradeoffs.** Medium. HTML parsing is cheap, but correct base-URL handling, refresh semantics, CSS parsing, deduplication, and resource-versus-page classification matter. Passive resource retrieval can inflate request counts without yielding useful UI states. Response bodies and headers require strict size/type bounds and secret-safe evidence.

**Matched experiment.** Freeze the 91-path local Flask denominator. Compare browser-only, anchor-hybrid, full typed-reference extraction, and reference extraction without active resource fetch under 180 seconds/300 actions, three repeats. Primary measures: expected request-surface recall, navigable-area recall, request cost, and replayed paths. Re-run the controlled JS lab to detect regressions.

**Falsifier.** Reject or narrow the method if expected-resource recall does not materially rise, if most additional traffic is outside scope/duplicate, or if interactive surface recall/replay falls after charging all requests.

## 2. Diverse, restoration-cost-aware replay scheduling

**Measured weakness.** Final Crawlground replay was 25/38 and left 211 observed paths untested. Restoration used 168 actions. The scheduler still orders mainly by path length and exact result group, so similar shallow destinations can consume verification budget before distinct event/frame/form branches.

**Method.** Allocate replay budget across unique destination routes, interaction classes, request structures, frame/session contexts, and prerequisite-prefix clusters. Estimate cost from recorded navigation/fill/action history and choose marginal evidence novelty per expected action. Retain a minimum quota for deep/high-cost paths so a cheap-only policy cannot starve them. This is a deterministic adaptation of Go-Explore's archive/return separation, not RL.

**Why it should work.** Agent 1 already has archives and exact action-cost accounting; scheduling can improve without changing discovery. Go-Explore demonstrates the value of separately returning to archived states before exploring/validating branches ([paper](https://arxiv.org/abs/2004.12919)).

**Complexity/tradeoffs.** Medium. Diversity proxies can reward superficial route variation; cost estimates can become self-fulfilling. Replay evidence must remain at the path instance, never promoted to a whole group.

**Matched experiment.** Freeze one discovery Graph A, then replay the identical transitions with shallow-first, randomized, destination-diverse, and cost/diversity policies under identical 200-action budgets across three seeds. Measure distinct route/interaction/request/context classes replayed, success rate, restoration actions, and untested important classes.

**Falsifier.** Reject if distinct replay-complete coverage does not improve on both controlled and Crawlground-like development data, if gains disappear after restoration accounting, or if wrong-instance false positives appear.

## 3. Resource-type-aware readiness and event-listener evidence

**Measured weakness.** Crawl Maze used 181.5 seconds for only 38 transitions/103 actions; many passive pages paid the 1.6-second no-control wait. Conversely, JavaScript listeners registered after load can lack inline/ARIA evidence. Local semantic inference recovered many Crawlground events but produced a severe 1/59 negative ablation before it was component-gated.

**Method.** First, make readiness conditional on document/resource type, recent mutation rate, and whether a page has scripts capable of delayed insertion. Passive HTML/resource pages should stabilize quickly; hydrating applications keep bounded mutation/actionability observation. Second, evaluate Chromium DevTools event-listener metadata as optional evidence for nonstandard targets, sampling only bounded main-content elements. Compare it against the current semantic/geometric inference rather than combining blindly.

**Why it should work.** Playwright's actionability guidance favors waiting for the specific action, not universal page stability. ZAP's 2026 Client Spider changes similarly emphasize adaptive waits and page-component crawling ([changelog](https://www.zaproxy.org/docs/addons/client/changelog/)). Direct listener metadata could reduce ambiguous gesture candidates.

**Complexity/tradeoffs.** Medium-high. CDP is Chromium-specific and per-node listener inspection can be expensive. Fast passive readiness can miss delayed meta/script navigation. This must be an ablation with startup-failure and missed-mutation counters.

**Matched experiment.** Use frozen passive, 250 ms/1 s hydration, delayed navigation, and mutation fixtures plus Crawl Maze. Compare universal readiness, resource-aware readiness, semantic gestures, and bounded listener metadata. Track actions/minute, delayed-control recall, ineffective gestures, and startup failures.

**Falsifier.** Reject resource-aware waits if delayed-control recall declines; reject listener metadata if its runtime/action savings do not exceed semantic inference or if coverage does not transfer.

## 4. Remaining interaction/state methods

After the three experiments above, rank remaining gaps from new evidence: drag/drop and pointer sequences, closed shadow roots, canvas/visual fallback, deeper nested frames, and fragment-aware identity. FragGen-style component correspondence remains attractive for state explosion, but the final Crawlground run had 201 raw and 201 grouped states with no measured critical false merge; resource recall and replay budget are currently larger measured failures. Full WebExplor-style RL/curiosity remains unjustified until deterministic reference, readiness, and scheduling approaches plateau ([FragGen](https://arxiv.org/abs/2110.14043), [WebExplor](https://arxiv.org/abs/2103.06018)).

## Agent boundary

Agent 1 owns safe origin-scoped observation, typed reference/control/request discovery, context-aware state identity, prerequisite archives, independent replay, and honest unresolved/blocked reporting. It may perform ordinary safe/disposable interactions to establish reachability.

Future planning and security-testing agents own vulnerability hypotheses, goal selection beyond coverage, credential acquisition/authorization, attack payload generation, destructive or privilege-changing approval, exploit execution, and impact confirmation. Agent 1 should expose a reproducible surface and its evidence; it should not infer vulnerability or attempt every possible gesture/payload.

## Single next experiment

Implement typed passive reference extraction first and evaluate it blind on the frozen Crawl Maze denominator. It is the highest-impact hypothesis because it targets the largest independent failure (87/91 missed resource paths) and complements, rather than retunes, the now-effective interactive engine.
