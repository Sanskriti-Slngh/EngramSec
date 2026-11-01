# Related work and method comparison

Status: research review for the redesign. It extends [RESEARCH_REVIEW.md](RESEARCH_REVIEW.md) (2026-10-28), which covered Crawljax, FragGen, WebExplor, FormNexus, Go-Explore, active automata learning and Crawlee. Facts were checked against primary sources on 2026-10-31.

**Evidence tags:**
- **[full]** checked against the paper's full text;
- **[abs]** abstract or publisher metadata only;
- **[sec]** secondary sources only;
- **[unverified]** could not be confirmed and is not used as a fact.

Numbers are the authors' own results on their own subjects. None of them was reproduced here.

Section numbers are referenced from [PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) and [EXPLORATION_PLANNER_DESIGN.md](EXPLORATION_PLANNER_DESIGN.md).

## 1. Questions the review must answer

Agent 1 must, without a model at runtime and with only browser-level observation:
- **(Q1)** choose a state abstraction that neither merges distinct records nor splits one screen into many;
- **(Q2)** discover capabilities, not just URLs;
- **(Q3)** infer dependencies between capabilities;
- **(Q4)** verify functionality with a meaningful oracle;
- **(Q5)** restore or reset state so that verification is possible without damage;
- **(Q6)** spend a 100–500 action budget where information is.

Each method family below is assessed against these questions.

## 2. GUI and web application exploration

### 2.1 State-flow crawling: Crawljax, ATUSA, FEEDEX

- **Problem:** Ajax and SPA content has no URLs, so URL crawlers miss it.
- **Mechanism:**
  - **Crawljax** [full] fires events on candidate clickables and adds a state to a state-flow graph when the DOM differs, using edit distance with threshold τ or a chain of "comparators" that strip volatile parts. It backtracks via browser history or by reloading and replaying the event path (Mesbah, van Deursen, Lenselink, TWEB 2012).
  - **ATUSA** [full] adds generic DOM invariants as oracles: validity, error messages, back-button behavior (ICSE 2009).
  - **FEEDEX** [full] (Milani Fard & Mesbah, **ISSRE 2013**) scores states and events by coverage impact, path diversity, DOM diversity and model size to decide what to expand next.
- **Assumptions:** DOM difference ≈ state difference; reload + replay restores state; candidate elements are known in advance (configured).
- **Evidence:**
  - Crawljax reports accuracy and scalability on six sites, but no head-to-head baseline.
  - ATUSA detected 8 of 10 seeded faults on TUDU. It **reset the database with an SQL script before each run**, the earliest reset mechanism in this line of work.
  - FEEDEX reached 48.1% average statement coverage vs DFS 37.6%, BFS 43.8% and random 40.4% on six apps.
  - In WebExplor's ICSE 2021 comparison, Crawljax reached 20.1% average branch coverage vs 59.8% for WebExplor.
- **Cost:** low per decision; the cost is in replays for backtracking.
- **SPA weaknesses:**
  - DOM-diff equivalence is the same over/under-splitting problem as our group signature (audit §2.2).
  - Replay-based backtracking corrupts stateful apps, exactly as on the whiteboard.
  - The default candidate set misses delegated handlers.
- **Complement:** Agent 1 already is a Crawljax descendant. FEEDEX is the closest prior art to our static priority scores. Its gain over BFS (48% vs 44%) shows that a *feature-weighted* frontier helps, but modestly. That supports changing the decision unit rather than re-weighting (planner §2).

### 2.2 Curiosity and reinforcement learning: WebExplor, QExplore, Q-testing, Humanoid

- **Problem:** guiding exploration toward new behavior without hand-written rules.
- **Mechanism:**
  - **WebExplor** [full] (Zheng et al., ICSE 2021): Q-learning with a curiosity reward that favours rarely visited states (similarity threshold 0.8), plus an online DFA that redirects exploration when no new state has been found for two minutes.
  - **QExplore** (Sherin et al., JSS 2023) [abs; numbers unverified]: Q-learning-guided search.
  - **Q-testing** [abs] (Pan et al., ISSTA 2020): Android curiosity with a learned state comparison at the "functional scenario" level.
  - **Humanoid** [full] (Li, Yang, Guo, Chen, ASE 2019): learns from human traces which element to interact with.
- **Evidence:**
  - WebExplor: 59.8% average branch coverage vs DIG 53.2%, SUBWEB 53.0%, Random 29.5% and Crawljax 20.1% on six apps (30 min × 15 runs). It was **not best on every app**: DIG and SUBWEB won on Splittypie and Retroboard (React).
  - Humanoid's authors state that the learned model was **not the main reason** for its coverage gain.
- **Assumptions:** many episodes per application; a stable state abstraction for counting visits; a resettable environment.
- **Cost:**
  - training-free curiosity is cheap per step but needs long runs (30-minute budgets × 15);
  - learned priors need training data.
- **SPA weaknesses:**
  - visit counts depend entirely on the abstraction;
  - curiosity rewards cosmetic churn;
  - there is no notion of entity or capability.
- **Complement:**
  - Adopt *count-based novelty* only as a prior for `bind_affordance` questions.
  - Do not adopt Q-learning. Our budgets are 100–500 actions per application and one run each, and the evidence that learned components drive the gains is weak (Humanoid's own analysis).

### 2.3 Model abstraction and refinement: APE, Stoat, FragGen

- **Problem:** a fixed state abstraction is either too coarse (merges behaviorally different screens) or too fine (state explosion).
- **Mechanism:**
  - **APE** [full] (Gu et al., ICSE 2019) represents the state/action abstraction as a decision tree of attribute "reducers". It refines or coarsens it at runtime, CEGAR-style; for example, an action is refined when it produces non-deterministic transitions (threshold 3).
  - **Stoat** [full abs+intro] (Su et al., FSE 2017) builds a stochastic FSM and mutates it with Gibbs sampling toward coverage.
  - **FragGen** [abs] (Yandrapally & Mesbah, TSE 2023) uses fragment-level, threshold-free state equivalence.
- **Evidence:**
  - APE, over 15 apps × 5 one-hour runs, against Monkey, Sapienz and Stoat: +26–78% activity coverage, +17–22% method coverage, 62 (intro) / 61 (evaluation) unique crashes vs 44, 40 and 31.
  - Stoat: 17–31% more code covered by its models than other modelling tools; ~3× the crashes of Monkey and Sapienz.
  - FragGen: 123% more near-duplicates detected than whole-page techniques; crawl models +62% precision and +70% recall.
- **Assumptions:** non-determinism of transitions is a usable refinement signal; the abstraction attributes are available (Android view tree / DOM).
- **Cost:**
  - APE is moderate: decision-tree maintenance;
  - FragGen is high: visual segmentation, OpenCV, large-DOM cost.
- **SPA weaknesses:** server-side state causes non-determinism unrelated to abstraction. Refinement must separate "abstraction too coarse" from "environment state changed", which requires reset or controlled states.
- **Complement: central to the proposal.** The ACG's view abstraction `α` is per-template, starts coarse, and is refined on contradiction evidence (model §2.2). That is APE's mechanism, with the refinement signal widened from non-determinism to *capability/operation disagreement*. FragGen motivates ComponentState as a separate layer. We take the idea, not the visual pipeline.

### 2.4 Security crawlers: jÄk, Enemy of the State, Black Widow, Deemon

- **Problem:** reaching the server-side attack surface, including stateful workflows.
- **Mechanism:**
  - **jÄk** [full] (RAID 2015) hooks JS APIs to see event-handler registration, network APIs and dynamic URLs. It clusters pages into a navigation graph.
  - **Enemy of the State** [full] (Doupé et al., USENIX Security 2012) infers a server-side state machine *black-box*: if an identical request returns a different response, some earlier request changed state, and a heuristic finds which one.
  - **Black Widow** [full] (Eriksson, Pellegrino, Sabelfeld, S&P 2021) has three parts:
    1. navigation modelling with the steps needed to reach each page;
    2. traversal that replays workflows leading to forms;
    3. **inter-state dependencies by black-box taint tracking**: it submits unique tokens and detects where they reappear.
  - **Deemon** [full] (CCS 2017) identifies **state-changing requests** from a property graph of execution traces and DB queries. Correction to a common description: it is **not black-box**. It needs PHP/MySQL instrumentation and recorded Selenium traces, and it snapshots and restores the app VM between tests.
- **Evidence:**
  - jÄk passed 89% of WIVET dynamic tests vs 20–44% for other crawlers.
  - Enemy of the State: +0.5% to +140.7% coverage over w3af with the same fuzzer, on 8 PHP apps.
  - Black Widow:
    - +63% to +280% server-side line coverage against each scanner individually (Arachni, ZAP, Skipfish, jÄk, w3af, Enemy of the State, Wget);
    - +6% to +62% per app against the *union* of all other scanners, including **PrestaShop +62.0%**;
    - best on 9 of 10 apps (Drupal lost due to logout/permission behavior).
  - Deemon: 14 unknown CSRF vulnerabilities in 4 of 10 apps.
- **Assumptions:**
  - Enemy of the State assumes state changes only via user requests (the authors removed time-driven changes from three apps) and has no Ajax support.
  - Black Widow assumes its injected tokens are reflected.
  - Deemon assumes white-box access.
- **Cost:** moderate (Black Widow: about 1.6 requests/s, as reported in the Witcher paper).
- **SPA weaknesses:** server-rendered assumptions; HtmlUnit (Enemy) has no JS; token reflection fails for data that is never re-rendered as text.
- **Complement: the strongest prior art for Q3 and Q5.**
  - Black Widow's unique-token tracking is a *black-box producer→consumer inference*. It is the UI-level counterpart of RESTler's API-level inference, and it was demonstrated on PrestaShop. The ACG adopts it in privacy-safe form (§9).
  - Enemy of the State's "same request, different response ⇒ hidden state change" is the right *detector* for undeclared state changes. The model uses it to flag `SERVER_WRITE_POSSIBLE` regardless of HTTP method (model §6.2).
  - Deemon shows that reliably identifying state-changing requests needs privileged evidence. Hence adapter-side effect digests are reserved for evaluation and authorized environments (model §6.4).
  - Drupal's logout failure in Black Widow is the same hazard our danger filter addresses.

### 2.5 Feature-level and intent-driven systems (all LLM-based)

- **Problem:** testing *features* rather than states or URLs. This is the closest framing to ours.
- **Mechanism:**
  - **AutoE2E** [full] (Alian, Nashid, Shahbandeh, Shabani, Mesbah, ICSE 2025) explores the app, has an LLM (GPT-4o or Claude 3) infer candidate features (entity CRUD and configuration actions), scores each feature's likelihood by observation frequency, and generates one test per feature.
  - **VISCA** [abs] (2025) adds multimodal LLM component abstraction.
  - **YuraScanner** [abs] (NDSS 2025) and **Hoyen** [sec] (2025) use LLMs to derive user tasks to drive security scanning.
  - **DroidAgent** [full] (ICST 2024, "Intent-Driven Mobile GUI Testing with Autonomous Large Language Model Agents") sets its own task goals.
  - **NNetNav** [abs] and **OS-Genesis** [abs] explore first and label trajectories afterwards.
- **Evidence:**
  - AutoE2E:
    - **E2EBench**: 8 apps (PetClinic, Conduit, Taskcafe, Dimeshift, MantisBT, EverTraduora, Saleor Storefront/Dashboard) with 13–130 ground-truth features each, derived by front-end instrumentation;
    - 79% average feature coverage vs Crawljax-based generation 12.0%, BrowserGym/GPT-4o 9.5%, OpenDevin 7.9%, AutoGPT 6.1%;
    - feature-inference precision 0.55, recall 0.72;
    - mean feature-chain length 3.4 actions.
  - VISCA: 92% on E2EBench.
  - YuraScanner: 12 new XSS vs 3 for Black Widow on 20 apps.
  - DroidAgent: 60.7% activity coverage vs Humanoid's 51.4% (its realistic-task counts differ between versions [unverified]).
- **Assumptions:** an LLM at runtime; feature semantics from natural-language labels.
- **Cost:** model calls per state/action; non-determinism; data leaves the machine with hosted models.
- **SPA weaknesses:**
  - AutoE2E's own precision of 0.55 means about half its inferred features are wrong;
  - label-based semantics are language- and app-dependent.
- **Complement:**
  - **Every 2024–2026 feature-level mapper found relies on an LLM.** Agent 1's constraint (no paid calls, no runtime inference) means we must get capability semantics from *behavior* (operations, effects, entity flow) instead. Our model is designed around that (model §5.3). This is a genuine methodological gap the redesign targets, not a solved problem.
  - **E2EBench is directly usable** as feature-level ground truth for validation, alongside our fixtures (evaluation plan §3.3; added in §10 below).
  - AutoE2E's feature definition (CRUD over entities, chains of about 3–4 actions) is close to our behavioral-class × entity granularity, though AutoE2E names features with an LLM and we do not (model §5.6). It suggests our capability granularity is the one others have found annotatable.

### 2.6 What the benchmarking literature says

- **Themis** [full] (Su, Wang, Su, FSE 2021):
  - 6 Android tools on 52 real crash bugs over more than 10,920 CPU hours;
  - 18 bugs were found by no tool, and each tool missed 53.8–71.2%;
  - **no tool consistently outperformed the others**, and results were driven by exploration strategy, **state-abstraction criteria** and small heuristics;
  - its listed challenges are deep use-case scenarios, specific text inputs, settings changes, specific interaction patterns and external app interaction.
- **Liu, Yang, Zhang, Xie (2026)** [abs] compare model-based, RL and LLM strategies under six state abstractions for web GUI testing:
  - no strategy wins on all dimensions;
  - fine-grained abstractions favour model-based exploration;
  - code coverage correlates only weakly with failure discovery.

These are the strongest arguments for the evaluation plan's cross-environment, multi-metric design. Single-benchmark wins do not transfer, and abstraction choices dominate outcomes.

## 3. Model-based testing, automata learning and invariant inference

### 3.1 Model-based testing and EFSM inference

- **Problem:** generating tests systematically from a model of the system's behavior.
- **Mechanism:**
  - **Model-based testing** (taxonomy: Utting, Pretschner, Legeard, STVR 2012 [abs]; the number of dimensions is reported as 6 or 7 depending on version [unverified]) derives tests from a behavioral model by coverage criteria (states, transitions, guards).
  - **EFSMs** add data guards and updates to transitions.
  - **MINT** (Walkinshaw, Taylor, Derrick, EMSE 2016) [abs] infers EFSMs *passively from traces* by state merging with ML classifiers for guards.
- **Assumptions:** the model exists (MBT) or traces cover the behavior (passive inference); data guards are learnable from observed values.
- **Evidence:** MBT is mature in industry. MINT was evaluated on three systems [numbers unverified].
- **Cost:** low once a model exists; passive inference is cheap but limited by the traces.
- **SPA weaknesses:** no model is given; guards over data we refuse to store (values) can only be inferred over value *classes* and hashes.
- **Complement:**
  - The ACG *is* an EFSM-like model: capabilities are guarded transitions over entity and session conditions.
  - MBT coverage criteria (all capabilities, all `requires` edges, all equivalent interfaces) define the verification agenda once exploration saturates.
  - Passive EFSM inference is the template for inferring `requires` conditions from availability contrasts (model §5.5).

### 3.2 Active automata learning and abstraction

- **Problem:** learning an exact behavioral model of a black box.
- **Mechanism:**
  - **L\*** (Angluin 1987) [abs] learns a minimal DFA from membership and equivalence queries, in time polynomial in the number of states and the counterexample length.
  - **TTT** (Isberner, Howar, Steffen, RV 2014) [abs] removes redundancy, has linear space and is robust to long counterexamples.
  - **LearnLib** (CAV 2015) [abs] and ALEX provide web adapters.
  - **Mappers** (Aarts, Jonsson, Uijen, Vaandrager, FMSD 2015) [abs] abstract concrete data values into a small alphabet so learning becomes feasible.
  - **Tomte** [sec] builds the mapper by counterexample-guided abstraction refinement.
  - **RALib** (Cassel et al., FAoC 2016) [abs] learns register automata with data guards via tree queries.
- **Evidence:** applied to TCP, SSH, TLS, EMV cards and industrial components [sec; which applications the CACM survey names is unverified]. Mapper-based learning was shown on SIP and TCP in ns-2 [sec].
- **Assumptions:**
  - **a reliable reset before every membership query**;
  - a finite, meaningful input alphabet;
  - deterministic behavior;
  - equivalence queries approximated by conformance testing, which is expensive.
- **Cost:** query counts grow with states × alphabet × counterexample length. That is far beyond 100–500 browser actions for an application with dozens of templates and forms.
- **SPA weaknesses:** every assumption fails for live web applications without isolation: server state persists, the alphabet includes data, and timing makes behavior non-deterministic.
- **Complement:**
  - Do not run L\*/TTT.
  - **Adopt two ideas:**
    1. *mappers*: the ACG's abstraction of concrete values (IDs → entity instances via HMAC, inputs → value classes) is a mapper;
    2. *counterexample-guided refinement*: a failed reproduction or a split test is a counterexample that refines `α`, as in Tomte and APE.
  - Under L3 isolation (snapshot per experiment), *small, local* L\*-style learning of a single component's behavior becomes plausible. One example is the states of a share dialog. It remains an option for later, not a core mechanism.

### 3.3 Likely-invariant inference: Daikon

- **Problem:** inferring specifications from executions.
- **Mechanism:** Daikon [full abstract] (Ernst et al., SCP 2007) reports properties from a template grammar (constants, ranges, ordering, containment and so on) that held over all observed executions.
- **Assumptions:** observed executions are representative; the results are *likely* invariants.
- **Cost:** low per template.
- **SPA weakness:** our observations are sparse (a few per template).
- **Complement:** pre- and postconditions as likely invariants over view facts (`affordance present ⇔ role = admin`, `list count increased after create`). These are always tagged `OBSERVED` and promoted only by a contrast experiment (model §5.5).

## 4. API and UI evidence fusion

- **Problem:** UI exploration sees *what the user sees*; API traffic reveals *what the application does*; neither alone gives capabilities and dependencies.
- **Mechanism:**
  - **RESTler** [full] (Atlidakis, Godefroid, Polishchuk, ICSE 2019) reads an OpenAPI spec and infers **producer–consumer dependencies** (request B consumes an ID produced by request A). It prunes sequences the service rejects.
  - **Morest** [full abstract] (ICSE 2022) maintains a RESTful-service **property graph** refined by execution feedback.
  - **EvoMaster** [abs] (Arcuri, TOSEM 2019) performs search-based generation.
  - **AFLNet** [abs] (ICST 2020) builds a protocol state machine using **response codes as state identifiers**.
- **Evidence:**
  - RESTler: 28 bugs in GitLab plus bugs in Azure and Office365 services, all confirmed and fixed.
  - Morest vs EvoMaster, RESTTestGen and RESTler: 152.7–232.5% more operations successfully requested and 26.2–103.2% more lines covered.
  - **AFLNet's five-year retrospective** [full]: state feedback covered 35.7× more states but did **not** significantly improve code coverage (significant on 1 of 12 subjects, worse on 2). The authors attribute this partly to response codes being a poor state definition.
- **Assumptions:** RESTler and Morest need a spec; their oracle is mainly HTTP 500.
- **Cost:** low per request, but spec-dependent.
- **SPA weaknesses:**
  - there is no spec;
  - endpoints are discovered only through UI-triggered traffic;
  - authentication and CSRF tokens are needed;
  - GraphQL and WebSocket traffic do not fit REST resource patterns.
- **Complement: central.**
  1. The ACG's `Operation` nodes are a spec *learned from observed traffic* (method, route pattern, parameter names, response shape), extending today's `request_structure_key`.
  2. Producer→consumer inference uses identifier-flow tokens (model §4.2) instead of a spec.
  3. Morest's "property graph refined by feedback" is structurally what the ACG is, with UI evidence added.
  4. AFLNet's retrospective is a warning: **a state abstraction that is easy to compute (response codes, route patterns) can inflate state counts without improving what is learned.** This is why the evaluation scores capabilities and identity accuracy, not state counts.

## 5. Exploration, hierarchy and information gain

### 5.1 Hierarchical RL and HTN planning

- **Problem:** long-horizon tasks decompose into subgoals.
- **Mechanism:**
  - **Options** (Sutton, Precup, Singh, AIJ 1999) [abs]: temporally extended actions with initiation set, policy and termination condition.
  - **MAXQ** (Dietterich, JAIR 2000) [abs]: decomposes a value function over a task hierarchy.
  - **HTN planning (SHOP2**, Nau et al., JAIR 2003) [abs]: decomposes tasks into subtasks in execution order with method preconditions.
- **Assumptions:**
  - options and MAXQ need learning (many episodes);
  - HTN needs a hand-written method library.
- **Cost:** learning is high; HTN is low at runtime but needs authored methods.
- **SPA weaknesses:** no reward signal for "understanding"; app-specific method libraries would violate the universal-engine rule.
- **Complement:**
  - The planner uses an **HTN-like structure with a small, application-independent method library**: the question kinds (planner §4) are methods with preconditions (generator rules), decompositions (restore → act → oracle) and termination (verdict).
  - This keeps hierarchy without learning and without app-specific knowledge.
  - Our earlier "hierarchy" (URL-area tours) was spatial and gave no coverage gain ([HIERARCHICAL_EXPLORATION_REPORT.md](HIERARCHICAL_EXPLORATION_REPORT.md)). The proposed hierarchy is over *functional questions*.

### 5.2 Go-Explore

- **Problem:** "detachment" (forgetting promising frontiers) and "derailment" (failing to get back to them).
- **Mechanism:** Go-Explore [full preprint] (Ecoffet et al., Nature 2021) keeps an archive of cells (low-dimensional state representations), selects a promising one, *returns* to it (by restoring simulator state or with a goal-conditioned policy) and explores from it.
- **Evidence:** Montezuma's Revenge 43,791 (robustified) vs prior state of the art 11,618 and human 4,753; Pitfall 6,954 vs 0.
- **Assumptions:** a restorable simulator, or a learned return policy; cell representations that capture progress.
- **SPA weaknesses:** no simulator restore; browser context restore ≠ server state.
- **Complement:**
  - Agent 1's return paths already implement "first return, then explore".
  - The redesign upgrades *return*: plan over reproduced edges, direct-URL teleports and adapter snapshots (planner §5.3). At L3+, adapter snapshots are the web equivalent of simulator restore.
  - The *cell* representation is the ViewState under `α`, refined as in §2.3.

### 5.3 Active learning, expected information gain and discovery estimation

- **Problem:** choosing the most informative next query under a budget.
- **Mechanism:**
  - **Expected information gain** (Lindley 1956; review: Chaloner & Verdinelli 1995) [abs]: choose the experiment maximizing expected entropy reduction of the posterior.
  - **BALD** (Houlsby et al., 2011) [full]: writes it as a difference of predictive entropies.
  - **Count-based exploration** (Bellemare et al., NeurIPS 2016), **ICM curiosity** (Pathak et al., ICML 2017) and **RND** (Burda et al., ICLR 2019) [abs]: intrinsic-reward proxies for novelty in RL.
  - **Species-discovery estimators** (Good–Turing; Chao): estimate the probability that the next sample is new from the number of singletons. Applied to software testing as "STADS" (Böhme, ACM TOSEM 2018). The STADS citation comes from the author's knowledge; it was not re-checked in this review.
- **Assumptions:**
  - EIG needs a probabilistic model of outcomes;
  - species estimators assume sampling from a fixed population, which is approximately true per area.
- **Cost:** for Bernoulli/Beta claims, EIG has a closed form and is negligible; Good–Turing is O(1).
- **SPA weaknesses:** priors are poorly calibrated early; the abstraction determines what "new" means.
- **Complement:**
  - EIG over binary claims observed through noisy experiment channels (plus discovery-outcome entropy) is the planner's value function, plus an `Unlock` term for prerequisite value (planner §5.2).
  - Good–Turing gives the per-area saturation and stopping rule (planner §5.4).
  - Count-based novelty survives only as a prior.
  - ICM and RND are rejected: they need learned networks and many episodes, and they reward unpredictability rather than understanding.

## 6. Test oracles

- **Problem:** deciding whether an observed behavior is correct, or at least that the claimed function happened.
- **Mechanism:**
  - The oracle survey (Barr et al., TSE 2015) [full] groups oracles as *specified* (317 papers), *derived* (245), *implicit* (76) and *handling the lack of an oracle* (56).
  - **Metamorphic testing** (Chen et al., CSUR 2018) [abs] checks relations between outputs of related inputs.
  - ATUSA's generic DOM invariants are implicit oracles.
- **Assumptions:** derived and metamorphic oracles need relations known to hold.
- **SPA weaknesses:** implicit oracles (crashes, HTTP 500, console errors) say nothing about whether a create worked.
- **Complement:** the **oracle ladder** (model §4.3) consists of derived and metamorphic oracles that need no application knowledge:
  - *differential input*: our paired search, a metamorphic relation over queries;
  - *cross-view consistency*;
  - *round-trip*;
  - *inverse operation*;
  - *operation conformance*.

  Black Widow's reappearing tokens are a cross-view oracle in disguise. UI outcome signals (today's `.success` / `role=alert`) are demoted to observation evidence.

## 7. State restoration and reproducible execution

- **Problem:** returning to a known state to repeat or verify, without contamination.
- **Mechanism and evidence:**
  - **ATUSA:** SQL reset script per run [full].
  - **Deemon:** VM snapshot/restore between tests [full].
  - **TimeMachine** [abs] (Dong et al., ICSE 2020): snapshots the whole Android system at interesting states and restores the most progressive one when progress stalls. Its reported numbers come from a summary only [unverified].
  - **Nyx** [full abstract] (USENIX Security 2021): VM snapshot restore thousands of times per second.
  - **Atropos** [full] (USENIX Security 2024): Nyx snapshot of a PHP app *including the DB* after initialization, restored after every input.
    - On average ≥ 32% more bugs than the state of the art, with no false positives.
    - Its stated limitation: resetting after every input misses bugs that need chained inputs.
  - **Test-isolation studies:**
    - PolDet (ISSTA 2015) detected state-polluting tests (324 reported, 194 relevant, across 6,105 tests), covering heap and filesystem but not DBs.
    - VMVM (ICSE 2014) cut isolation overhead by 62% on average.
    - Luo et al. (FSE 2014): 12% of 161 flaky-test fixes were order dependency, 74% of those fixed by cleaning shared state.
    - **TEDD** (FSE 2019) argues that multi-tier web apps make per-test isolation hard, and detects dependencies in Selenium suites instead.
  - **No dedicated empirical study** of DB snapshot/reset strategies for web end-to-end isolation was found. Our L3 design choices (template DBs, file copies) are engineering judgment that we must measure ourselves.
- **Assumptions:** the snapshot captures all relevant state (DB, files, caches, queues); restore is cheap relative to an experiment.
- **SPA weaknesses:** client and server state both matter; external services are outside the snapshot.
- **Complement:**
  - The isolation-level design (model §6.1) mirrors this spectrum: browser context (current) → disposable instance → DB snapshot (ATUSA-style) → full-stack snapshot (Deemon/Atropos/TimeMachine) → transaction rollback.
  - Atropos's limitation (per-input reset loses chained state) is why the planner *chains* experiments from a snapshot rather than restoring after every action: restore once per experiment, not once per step.
  - TimeMachine's "restore the most progressive state" is Go-Explore with real snapshots. It is exactly what L3/L4 enable for prerequisite-heavy capabilities.

## 8. Comparison matrix

Scale: ● strong, ◐ partial, ○ none or not applicable.

| Approach | Q1 abstraction | Q2 capabilities | Q3 dependencies | Q4 oracle | Q5 reset | Q6 budget use | Runtime cost | Model-free | Main SPA weakness |
|---|---|---|---|---|---|---|---|---|---|
| Crawljax / FEEDEX | ◐ DOM diff | ○ | ○ | ◐ invariants (ATUSA) | ◐ reload+replay | ◐ feature-weighted | low | ● | DOM-diff over/under-splitting |
| WebExplor / Q-learning | ◐ similarity | ○ | ○ | ◐ errors | ◐ episodic reset | ● long runs | medium | ● (no LLM) | needs many episodes |
| APE / Stoat | ● refinement | ○ | ○ | ◐ crashes | ◐ restart | ◐ | medium | ● | refinement confused by server state |
| FragGen | ● fragments | ○ | ○ | ◐ fragment oracles | ○ | ○ | high | ● | visual pipeline cost |
| jÄk | ◐ clusters | ○ | ○ | ○ | ○ | ◐ | low | ● | needs handler-registration hooks |
| Enemy of the State | ◐ link vectors | ○ | ● server state changes | ○ | ○ | ◐ | medium | ● | no JS |
| Black Widow | ◐ | ◐ workflows | ● token flow | ◐ | ◐ replay | ◐ | medium | ● | reflection-dependent |
| Deemon | ● (white-box) | ◐ state-changing requests | ● | ◐ | ● VM | ○ | high | ● | needs instrumentation and traces |
| AutoE2E / VISCA | ◐ (LLM) | ● features | ◐ chains | ◐ generated | ○ | ◐ | high (LLM) | ○ | precision 0.55; LLM |
| L\* / TTT / RALib | ● exact | ○ | ● | ● conformance | required | ○ query-hungry | very high | ● | reset and determinism assumptions |
| MBT (EFSM) / MINT / Daikon | ◐ | ◐ | ◐ guards | ● from the model | ◐ | ● coverage criteria | low | ● | needs a model or traces |
| RESTler / Morest | ○ (API) | ◐ operations | ● producer–consumer | ◐ HTTP 500 | ◐ | ● | low | ● | needs a spec |
| Go-Explore | ◐ cells | ○ | ○ | ○ | ● if restorable | ● | low | ● | needs restore |
| EIG / BALD / Good–Turing | — | — | — | — | — | ● | negligible | ● | calibration |
| HTN / options | — | ◐ structure | ◐ | — | — | ● | low (HTN) | ● | method library |
| TimeMachine / Nyx / Atropos | — | — | — | — | ● snapshots | ◐ | medium–high | ● | snapshot completeness |

No single approach covers Q1–Q6. The ones that score on capabilities (AutoE2E) need an LLM. The ones that score on dependencies need either a spec (RESTler) or token reflection (Black Widow). The ones that score on reset need infrastructure (snapshots).

## 9. Combinations with real architectural leverage

1. **APE-style refinement + Black Widow token flow + RESTler producer–consumer → layered identity and dependency inference (Q1, Q3).**
   - Refinement keeps the abstraction minimal.
   - Token flow, over our own submitted canary values and HMAC-hashed identifiers from responses and URLs, links producers to consumers across UI and API.
   - Neither stores values. Black Widow showed the UI-level variant on PrestaShop; RESTler showed the API-level variant needs only ID-flow evidence plus a spec, which we replace with learned operations.
   - *Leverage:* entities, instance identity and `enables` edges from one evidence mechanism.
   - *Risk:* IDs only rendered server-side as text. Canary tokens cover that for data we create.
2. **Morest-style property graph + MBT coverage criteria → the ACG as a learned, testable model (Q2, Q4).**
   - The graph is refined by execution feedback.
   - Once an area saturates, MBT criteria (all capabilities, all `requires`, all equivalent interfaces) define what remains to verify.
   - *Leverage:* exploration and verification share one model.
3. **EIG/BALD value + Good–Turing saturation + HTN-structured question methods → the planner (Q6).**
   - Closed-form value, no learning.
   - Stopping with a stated confidence.
   - Hierarchy over functional questions rather than URL areas.
   - *Leverage:* the decision unit changes; the FEEDEX/WebExplor-style re-weighting the audit found insufficient is not repeated.
4. **Go-Explore return + TimeMachine/Atropos snapshots + ATUSA-style DB reset, behind an adapter → isolation levels (Q5).**
   - Restore once per experiment, chain within it (avoiding Atropos's per-input limitation).
   - Verify the start state independently.
   - *Leverage:* stateful capabilities become verifiable where containment is attested; elsewhere the `f6744ba` refusal stands.
5. **Enemy-of-the-State change detection + derived/metamorphic oracles → method-independent effect classification and verification (Q4).**
   - Same request, different response ⇒ hidden state change, regardless of method.
   - Differential, cross-view and round-trip oracles confirm effects.
   - *Leverage:* replaces "non-GET ⇒ write" and `.success` ⇒ verified.

**Rejected combinations:**
- RL policy learning (WebExplor/Q-testing/ICM/RND): too many episodes per application, and weak evidence that learned components drive the gains.
- Full L\*/TTT learning: reset and query cost.
- FragGen's visual pipeline: cost.
- LLM feature inference (AutoE2E and later): violates the engine constraint. It may still serve as an *offline evaluation baseline* if explicitly approved (evaluation plan §3.4).

## 10. Consequences for the other documents

- E2EBench (AutoE2E's 8 apps with instrumented feature ground truth) is added as a candidate **validation** set for capability recall in [GENERALIZATION_AND_EVALUATION_PLAN.md](GENERALIZATION_AND_EVALUATION_PLAN.md) §3.3. Its feature definitions are close to our capability granularity, but its annotation method (front-end instrumentation plus a feature grammar) differs, so the matching rules must be adapted and reported.
- Canary-token round-trips (our own unique submitted values, tracked by HMAC) are part of the identifier-flow evidence in [PROPOSED_APPLICATION_MODEL.md](PROPOSED_APPLICATION_MODEL.md) §4.2.
- Themis and the 2026 web-GUI study justify the evaluation rule that no single-environment improvement is accepted as evidence of generality.

## References

Full citations, URLs and per-item verification notes are in [RELATED_WORK_SOURCES.md](RELATED_WORK_SOURCES.md). The principal sources:
- Crawljax (TWEB 2012); ATUSA (ICSE 2009); FEEDEX (ISSRE 2013); WebExplor (ICSE 2021, arXiv 2103.06018); QExplore (JSS 2023); Black Widow (S&P 2021); jÄk (RAID 2015); Enemy of the State (USENIX Security 2012); Deemon (CCS 2017, arXiv 1708.08786); Witcher (S&P 2023); Atropos (USENIX Security 2024); AutoE2E (ICSE 2025, arXiv 2408.01894); VISCA (arXiv 2506.04161); YuraScanner (NDSS 2025);
- APE (ICSE 2019); Stoat (FSE 2017); Humanoid (ASE 2019, arXiv 1901.02633); Q-testing (ISSTA 2020); Themis (FSE 2021); TimeMachine (ICSE 2020); DroidAgent (ICST 2024, arXiv 2311.08649); NNetNav (arXiv 2410.02907); OS-Genesis (ACL 2025);
- L\* (Inf. & Comp. 1987); TTT (RV 2014); LearnLib (CAV 2015); Aarts et al. (FMSD 2015); Tomte (ICTAC 2015); RALib (FAoC 2016); Vaandrager (CACM 2017); MINT (EMSE 2016); Daikon (SCP 2007); Utting et al. (STVR 2012);
- RESTler (ICSE 2019); Morest (ICSE 2022, arXiv 2204.12148); EvoMaster (TOSEM 2019); AFLNet (ICST 2020) and "AFLNet Five Years Later" (arXiv 2412.20324);
- Options (AIJ 1999); MAXQ (JAIR 2000); SHOP2 (JAIR 2003); Go-Explore (Nature 2021, arXiv 2004.12919); Bellemare et al. (NeurIPS 2016); Pathak et al. (ICML 2017); Burda et al. (ICLR 2019); Houlsby et al. (arXiv 1112.5745); Lindley (1956); Chaloner & Verdinelli (1995); Böhme, STADS (TOSEM 2018);
- Barr et al. (TSE 2015); Chen et al. (CSUR 2018); Nyx (USENIX Security 2021); PolDet (ISSTA 2015); VMVM (ICSE 2014); Luo et al. (FSE 2014); TEDD (FSE 2019); FragGen (TSE 2023); Liu et al. (arXiv 2606.16650).
