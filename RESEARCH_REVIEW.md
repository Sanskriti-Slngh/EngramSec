# Focused comparative review

Reviewed 2026-10-28. This is a design decision record, not a claim that EngramSec is better than the compared systems.

## Decision

Implement a small Playwright state-flow mapper rather than wrapping a research system. Reuse these established ideas:

- Crawljax: browser-fired events, candidate controls, state-flow graph, plugin-style evidence output.
- FragGen: near-duplicate handling should be reversible and fragment/control aware, not URL-only or a blind whole-page threshold.
- WebExplor and Go-Explore: remember useful frontier states, return by a known path without exploration, then branch.
- Active automata learning: distinguish an input/action alphabet from observable outputs and validate reset/replay assumptions.
- FormNexus: send compact form/control relations and feedback to a model instead of full HTML.

The first implementation deliberately omits RL training, visual fragment segmentation, and exact automata learning. They add substantial state/action abstraction and reset assumptions before the basic evidence/replay loop has been measured.

## Systems reviewed

### Crawljax — selected external baseline

Mechanism: a real browser extracts configured candidate elements, fires events, compares resulting DOM states, and incrementally builds a state-flow graph. The CLI defaults to anchors/buttons and supports state/depth/time caps; plugins produce DOMs, screenshots, and an overview graph. This is website-only dynamic analysis.

Implementation inspected: the public repository's `CandidateElementExtractor`, `Crawler`, state-vertex factories, crawl overview plugin, and CLI configuration. The shallow-cloned head was `5771f6161c645c75f710a8cdc14e3c6898727e06` (2023-06-19); the latest packaged release found was 5.2.3 (2023). Java 17 was installed during preflight, but Maven was absent and the official CLI archive advertised by its Maven metadata was about 987 MB. The FragGen path also loads OpenCV native code.

Reported/known limits: default state identity is DOM-oriented; useful form values often require configuration; replayable feature semantics and prerequisites are not the CLI's primary output. Repository issues document native OpenCV/build failures for FragGen and questions about current maintenance.

Decision: retain it as the established state-flow comparison in the literature review, but do not spend the experiment budget on its unusually large/legacy setup. It was not run, so there is no Crawljax-versus-Agent-1 performance claim. Reimplement only the narrower evidence schema, replay validation, protected inputs, and checkpoint interface required here.

Sources: [Crawljax repository](https://github.com/crawljax/crawljax), [original dynamic Ajax crawling paper](https://repository.tudelft.nl/record/uuid%3Af7a5f58d-5d36-4105-8ac2-385c0f18cf1a), [CLI/getting started](https://github.com/crawljax/crawljax/wiki/Getting-started), [5.2.3 releases](https://github.com/crawljax/crawljax/releases), [FragGen integration notes and limits](https://github.com/crawljax/crawljax/issues/541).

### FragGen

Mechanism: segment pages into visual/DOM fragments; compare fragment structure and localized visuals to identify clones and near-duplicates; diversify actions by fragment; generate fragment-based regression oracles. It is website-only but relies on browser screenshots, DOMs, VIPS-style segmentation, APTED, image comparisons, and OpenCV.

Reported results: on the authors' datasets, 123% more near-duplicates than whole-page methods, model precision/recall improvements of 62%/70%, nearly 100% same-version action replay, and 98.7% visible-change detection. Those tasks and datasets differ from verified feature-workflow coverage.

Implementation inspected: Crawljax's `FragGenStateVertexFactory`, `HybridStateVertexImpl`, fragmentation plugin, and example. It captures screenshots, injects visual style data, segments pages, and uses structural edit distance/native image support. Published limits include no frame support, high memory/CPU cost on large DOMs, and limited non-Chrome testing.

Decision: do not run it in the first slice. Preserve raw observations and fragment/control signatures so a later ablation can add it without losing data.

Sources: [paper](https://arxiv.org/abs/2110.14043), [IEEE record](https://ieeexplore.ieee.org/document/9765776), [Crawljax implementation issue](https://github.com/crawljax/crawljax/issues/541).

### WebExplor

Mechanism: clusters/preprocesses pages into states, uses curiosity reward based on visit counts with Q-learning, and maintains an online DFA. When local exploration stalls it resets, replays a shortest path to a high-curiosity transition, then resumes exploration. It is website-only in concept.

Reported results: the paper reports higher failure detection/code coverage on six projects, a commercial SaaS system, and top websites; 12 confirmed commercial failures and 3,466 web exceptions/errors. Evaluation used 30-minute trials repeated 15 times and more than 300 CPU-hours. Public search did not reveal the original implementation; a later evaluation framework says it reimplements the baseline.

Assumptions/limits: a stable state abstraction and resettable environment; training cost; reported code coverage may require application instrumentation and is not the current website-only feature metric.

Decision: reuse visit-count novelty and reset/replay-to-frontier, not Q-learning. The requested budget is better spent measuring a deterministic archive first.

Sources: [ICSE paper](https://arxiv.org/abs/2103.06018), [later baseline evaluation artifacts](https://zenodo.org/records/15077395).

### FormNexus

Mechanism: builds a Form Entity Relation Graph from text, DOM relations, and visual proximity, then uses LLM feedback loops to infer and mutate form constraints. It is website-only but its released workflow requires ChromeDriver and an OpenAI key.

Reported results: GPT-4 configuration reached 89% form submission-state coverage and 83% successful submissions in the paper, with sizable GPU/server hardware noted in the repository. This targets form testing, not global workflow discovery.

Decision: reuse compact relational form summaries and feedback capture only. Do not adopt the full pipeline or paid GPT-4 dependency.

Sources: [paper](https://arxiv.org/abs/2402.00950), [source repository](https://github.com/parsaalian/webform-testing).

### Go-Explore

Mechanism: archive interesting states and their trajectories; select a promising cell, return without exploratory noise, then branch; optionally robustify the found trajectory. The reference implementation targets Atari/robotics and often relies on simulator state restore, so it is not directly a website crawler.

Applicability: browser cookies do not restore server state, so EngramSec must replay setup actions and check outcomes rather than restore a browser snapshot. The archive/return separation is still directly useful.

Decision: adapt the archive and deterministic return-path idea; replace simulator restore and imitation learning with fresh-context browser replay.

Sources: [paper](https://arxiv.org/abs/2004.12919), [reference code](https://github.com/uber-research/go-explore).

### Active automata learning (LearnLib/ALEX/AALpy)

Mechanism: issue membership queries to a system under learning over a defined input alphabet, observe outputs, and use equivalence approximations/counterexamples to refine a DFA/Mealy-style model. ALEX supplies Selenium/HTTP adapters for web applications; LearnLib includes caches, conformance tests, abstract-to-concrete symbol mappings, and reset-aware oracles.

Assumptions/limits: the action alphabet and output abstraction must be finite/useful, membership queries need reliable reset and reproducible data, and forms introduce large data domains. Those are exactly the uncertain pieces here.

Decision: borrow action/output separation and replay-based counterexample checks. Do not force an exact learned automaton before state identity and reset behavior are measured.

Sources: [LearnLib](https://learnlib.de/), [ALEX](https://learnlib.de/alex/), [ALEX source](https://github.com/LearnLib/alex), [AALpy paper](https://link.springer.com/article/10.1007/s11334-022-00449-3).

### Practical crawler libraries and newer agentic tools

Crawlee offers maintained Playwright crawling, persistent request queues, retries, and session/concurrency management. It is strong infrastructure for URL/content crawling, but it does not supply evidence semantics, state grouping, or full workflow replay. Newer LLM QA tools such as Explorbot are closer in product shape but introduce model dependence and do not provide a stable external scientific baseline for this experiment.

Decision: use Playwright directly for Agent 1. Also run Crawlee 1.11 with one worker as the practical external executable baseline. The adapter queues visible same-origin links and adds fresh-context path replay, but deliberately does not pretend to provide Crawljax-style event/state semantics or form coverage.

Sources: [Crawlee architecture](https://crawlee.dev/python/docs/next/concepts/architecture-overview), [PlaywrightCrawler API](https://crawlee.dev/js/api/3.11/playwright-crawler), [Explorbot repository](https://github.com/testomatio/explorbot).

## Benchmark conditions

The public AgentCyberRange/WebExploitBench repositories are Apache-2.0 and describe SiyuCMS among released benchmark targets. CAGE explicitly separates target packages from the framework and applies contamination gates to exported traces. Exact distribution/leaderboard conditions for the already-running local instance were not present in this repository. Therefore benchmark-specific optimization, target source inspection, verifier inspection, vulnerability hints, and answer artifacts remain out of scope. Experiments use only the rendered website and mapper evidence; independent fixtures are used for fast correctness tests.

Sources: [WebExploitBench/CAGE public target instructions](https://github.com/AgentCyberRange/CAGE/blob/main/examples/agent_pentest_bench/README.md), [AgentCyberRange responsible-use and repository overview](https://github.com/AgentCyberRange), [CAGE framework description](https://github.com/AgentCyberRange/CAGE).
