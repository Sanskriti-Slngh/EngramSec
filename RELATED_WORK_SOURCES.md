# Related-work sources and verification notes (verified 2026-10-31)

Companion to [RELATED_WORK_AND_METHOD_COMPARISON.md](RELATED_WORK_AND_METHOD_COMPARISON.md).

Verification tags:
- **[V-full]**: checked against the paper's full text (author PDF, arXiv, or proceedings PDF).
- **[V-abs]**: checked against the primary abstract, publisher metadata, or Crossref record only.
- **[V-sec]**: supported only by secondary sources (later papers, summaries, project pages).
- **UNVERIFIED**: could not be confirmed. Do not cite as fact.

"Correction" marks a place where the recollection in the brief was wrong or incomplete.

---

## Web crawling / GUI exploration

### 1. Crawljax [V-full]
- **Citation:** A. Mesbah, A. van Deursen, S. Lenselink. "Crawling Ajax-Based Web Applications through Dynamic Analysis of User Interface State Changes." *ACM TWEB* 6(1), Art. 3, March 2012. DOI 10.1145/2109205.2109208. https://people.ece.ubc.ca/amesbah/resources/papers/tweb-final.pdf
  - Expanded from Mesbah, Bozdag, van Deursen, ICWE 2008.
- **(a) Mechanism:**
  - The crawler finds candidate clickables in the DOM, fires events on them, and adds a new node to a state-flow graph whenever the DOM changes.
  - It decides whether a state is new by comparing DOMs. One option is Levenshtein edit distance with a similarity threshold τ (τ = 0 means any change is a new state).
  - The other option is a chain of "comparators" that filter parts of the DOM before comparing, for example stripping timestamps (Roest et al. 2010).
  - To backtrack, it uses browser history where available. Otherwise it reloads the app and replays the recorded event path from the initial state (Dijkstra shortest path is an optimization).
  - The concurrent variant "forward-tracks" new browser nodes to the target state instead.
- **(b) Evaluation:**
  - Accuracy and scalability were measured on six sites (C1–C6). For example, C1 took 14 s and C2 took 26 s to crawl.
  - Concurrent crawling was tested on Google AdSense (GWT). Going from 1 to 5 browsers cut runtime by up to 65%. More than 5 browsers gave no significant further gain.
  - The paper has no head-to-head baseline tool comparison.
- **(c) Limitations:** The authors say more case studies are needed to generalize the correctness and scalability results. Public sites change over time, which threatens repeatability.

### 2. ATUSA [V-full]
- **Citation:** A. Mesbah, A. van Deursen. "Invariant-Based Automatic Testing of AJAX User Interfaces." *ICSE 2009*, pp. 210–220. ACM SIGSOFT Distinguished Paper. https://people.ece.ubc.ca/amesbah/resources/papers/icse09.pdf
  - A journal extension with D. Roest appeared in IEEE TSE as "Invariant-Based Automatic Testing of Modern Web Applications." The exact year (2011 online vs. 2012 issue) is UNVERIFIED.
- **(a) Mechanism:**
  - Crawljax infers the state-flow graph.
  - Generic DOM invariants act as oracles: DOM validity, error messages, discoverability, back-button compatibility.
  - Application-specific invariants can be added as plugins.
  - A test suite is generated that covers the crawled paths.
- **(b) Evaluation:**
  - **TUDU (study 1):**
    - Coverage: 73% server-side and 75% client-side, per the paper text. Table 1 appears to show 35% for client-side, so this is ambiguous; cite the text.
    - Faults: 8 of 10 seeded faults were detected. The two missed faults were swallowed by the JS engine and never reached the DOM.
    - Effort: under 30 minutes of setup. Crawling and testing took under 6 minutes, analysing 332 clickables and 34 states.
  - **CJZ (study 2):** a small commercial project, used to show that application-specific invariants catch real development faults.
- **(c) Note relevant to state reset:** The TUDU database was reset to its original state with an SQL script before each test run.

### 3. FEEDEX [V-full]
- **Correction:** the venue is **ISSRE 2013**, not ASE 2013.
- **Citation:** A. Milani Fard, A. Mesbah. "Feedback-Directed Exploration of Web Applications to Derive Test Models." *IEEE ISSRE 2013*, pp. 278–287. https://people.ece.ubc.ca/amesbah/resources/papers/issre13.pdf
- **(a) Mechanism:** During crawling, the tool scores states and events using code-coverage impact, navigational (path) diversity, page structural (DOM) diversity, and test-model size. It uses these scores to decide in advance which state to expand and which event to fire next.
- **(b) Evaluation:**
  - Six web apps were tested against exhaustive DFS, BFS, and random (RND) exploration.
  - FEEDEX reached 48.13% average statement coverage, versus 37.55% for DFS, 43.82% for BFS, and 40.44% for RND.
  - Reported min–max improvements:
    - 10–28% in coverage
    - 7–4000% in path diversity
    - 23–130% in DOM diversity
    - 38–86% fewer edges
    - 42–61% fewer distinct paths
- **(c) Limitations:** Only six apps were studied, so generalization is limited.

### 4. WebExplor [V-full]
- **Citation:** Y. Zheng, Y. Liu, X. Xie, Y. Liu, L. Ma, J. Hao, Y. Liu. "Automatic Web Testing Using Curiosity-Driven Reinforcement Learning." *ICSE 2021*, pp. 423–435. arXiv 2103.06018. https://arxiv.org/abs/2103.06018
- **(a) Mechanism:**
  - Curiosity-driven RL generates action sequences. The reward favours rarely visited states.
  - States are pre-processed with a similarity threshold of 0.8.
  - A DFA is built incrementally online. It gives high-level guidance when no new state has been found for 2 minutes.
- **(b) Evaluation:**
  - **Research benchmark:** six apps from DIG's prior work: dimeshift, pagekit, splittypie, phoenix-trello, retroboard (React), and petclinic.
  - **Setup:** 30-minute budget, 15 repetitions.
  - **Baselines:** Crawljax, Random (Monkey-style), DIG (APO and MPO page objects), and SUBWEB (APO and MPO).
  - **Average branch coverage:**

    | Tool | Avg. branch coverage |
    |---|---|
    | WebExplor | 59.8% |
    | Crawljax | 20.1% |
    | Random | 29.45% |
    | DIG (APO / MPO) | 53.2% / 50.4% |
    | SUBWEB (APO / MPO) | 53.0% / 49.3% |

  - **Average unique failures:** WebExplor 6.5; Crawljax 1.2; Random 1.4; the others 2.0–2.7.
  - WebExplor was **not** best on every app. DIG and SUBWEB had higher coverage on Splittypie and Retroboard.
  - **Other results:** 12 previously unknown failures in a commercial SaaS app, and 3,466 exceptions/errors across the top-50 real-world sites.
- **(c) Limitations:** Randomness was mitigated with 15 runs. Results depend on hyperparameter choices.

### 5. QExplore [V-abs for bibliographic data; numbers UNVERIFIED]
- **Citation:** S. Sherin, A. Muqeet, M. U. Khan, M. Z. Iqbal. "QExplore: An exploration strategy for dynamic web applications using guided search." *JSS* vol. 195, art. 111512, January 2023 (online 2022). DOI 10.1016/j.jss.2022.111512. https://doi.org/10.1016/j.jss.2022.111512
  - Bibliographic data confirmed via Crossref and DBLP.
- **(a) Mechanism [V-sec]:** Q-learning-inspired guided exploration that needs little or no prior knowledge of the application.
- **(b) Evaluation [V-sec only]:**
  - Six open-source apps plus one industrial app.
  - Reported higher coverage and more diverse DOM states, navigational paths, and error states than Crawljax and WebExplor.
  - **Exact numbers: UNVERIFIED.** The abstract was not retrievable because ScienceDirect returned 403.

### 6. Black Widow [V-full]
- **Citation:** B. Eriksson, G. Pellegrino, A. Sabelfeld. "Black Widow: Blackbox Data-driven Web Scanning." *IEEE S&P 2021*. DOI 10.1109/SP40001.2021.00022. https://www.cse.chalmers.se/~andrei/bw21.pdf
- **(a) Mechanism:** Three pillars:
  1. **Navigation modelling:** a JS dynamic-analysis crawler covering anchors, forms, frames, and fired events, annotated with the steps needed to reach each page.
  2. **Traversal:** it can retrace workflows, such as replaying the steps leading up to a form submission.
  3. **Inter-state dependencies:** black-box end-to-end taint tracking. It submits unique tokens and detects where they reappear in pages.
- **(b) Evaluation:**
  - **Subjects:** 10 apps. Older: phpBB, SCARF, Vanilla, WackoPicko. Modern: Drupal, HotCRP, Joomla, osCommerce, **PrestaShop**, WordPress.
  - **Baselines:** Arachni, Enemy of the State, jÄk, Skipfish, w3af, ZAP, plus Wget as a crawl reference.
  - **Coverage measure:** server-side lines of code (Xdebug).
  - **Against each scanner individually** (aggregated over all apps), coverage improved by 63% to 280%:

    | Scanner | Improvement |
    |---|---|
    | Arachni | +63.3% |
    | ZAP | +132.1% |
    | Skipfish | +148.7% |
    | jÄk | +152.4% |
    | w3af | +167.6% |
    | Enemy of the State | +178.8% |
    | Wget | +280.3% |

  - **Against the union of all other scanners,** coverage improved by 6% to 62% per app. Drupal was +5.5% and PrestaShop +62.0%.
  - Highest coverage on 9 of 10 apps. Drupal was the exception, due to logout and permission behaviour.
  - Also reported: "average 23%" coverage improvement.
  - **Vulnerabilities:** 25 found, 6 previously unknown, in HotCRP, osCommerce, PrestaShop, and WordPress. No false positives.

### 7. jÄk [V-full]
- **Citation:** G. Pellegrino, C. Tschürtz, E. Bodden, C. Rossow. "jÄk: Using Dynamic Analysis to Crawl and Test Modern Web Applications." *RAID 2015*, LNCS 9404, pp. 295–316. https://publications.cispa.saarland/538
- **(a) Mechanism:**
  - Hooks JavaScript APIs to detect event-handler registration, use of network APIs (XHR, etc.), and dynamically generated URLs and forms.
  - Builds a navigation graph whose nodes are clusters of similar pages.
- **(b) Evaluation:**
  - The abstract says it explored a surface "86% larger than existing approaches" against four scanners on 13 apps.
  - The body actually lists five tools: Skipfish, w3af, Wget, the state-aware crawler (Enemy of the State), and Crawljax 3.5.1.
  - **WIVET dynamic tests (45 total):**
    - jÄk passed 89% (40 of 45).
    - Other crawlers ranged from 20% (Crawljax) to 44% (w3af); Wget passed 0%.
    - On event-based tests, jÄk passed 96%, versus about 16% for the others.
- **(c) Limitations:** As dynamic analysis, it cannot find URLs in JS that never executes, such as unattached functions.

### 8. Enemy of the State [V-full]
- **Citation:** A. Doupé, L. Cavedon, C. Kruegel, G. Vigna. "Enemy of the State: A State-Aware Black-Box Web Vulnerability Scanner." *USENIX Security 2012*, pp. 523–538. https://sites.cs.ucsb.edu/~vigna/publications/2012_USENIX_WebState.pdf
- **(a) Mechanism:**
  - Infers the server-side state machine from outside the app.
  - Pages are abstracted as link vectors stored in a prefix tree and clustered.
  - A state change is inferred when an identical request returns a different response. A heuristic then finds which earlier request changed the state.
  - The inferred machine drives w3af's fuzzing plugins.
- **(b) Evaluation:**
  - **Subjects:** 8 PHP apps: Gallery, phpBB v2/v3, SCARF, Vanilla, WackoPicko v2, WordPress v2/v3.
  - **Baselines:** w3af, Skipfish, and a Wget baseline.
  - Over w3af, which uses the same fuzzer, coverage increased by between about 0.5% and 140.71%.
  - Example coverage over the Wget baseline, WackoPicko v2: state-aware scanner +241.86%, Skipfish +194.77%, w3af +101.15%.
- **(c) Assumptions and limitations:**
  - Assumes the app's state changes only through user requests. The authors modified three apps to remove time-driven state changes.
  - No AJAX support (HtmlUnit).
  - Inferred state machines become very complex for large apps.

### 9. Deemon [V-full]
- **Citation:** G. Pellegrino, M. Johns, S. Koch, M. Backes, C. Rossow. "Deemon: Detecting CSRF with Dynamic Analysis and Property Graphs." *ACM CCS 2017*, pp. 1757–1771. DOI 10.1145/3133956.3133959. arXiv 1708.08786. https://arxiv.org/abs/1708.08786
- **(a) Mechanism:**
  - Replays user-action traces recorded with Selenium IDE against an instrumented app (PHP interpreter tracing, DB queries, HTTP).
  - Builds a unified property graph of execution traces, data flows, and architecture tiers.
  - Uses graph traversals to find **state-changing HTTP requests** and their parameters, then generates and runs security tests.
  - The app VM is snapshotted and restored between tests.
- **(b) Evaluation:** 10 open-source apps (Bitnami VMs). Found 14 previously unknown CSRF vulnerabilities in 4 of them, enabling account and site takeover and DB integrity compromise.
- **(c) Limitations — Correction:**
  - It is **not black-box**. It needs server-side instrumentation, and the prototype supports PHP with MySQL.
  - It depends on recorded user traces rather than autonomous exploration.

### 10a. Witcher [V-full]
- **Citation:** E. Trickel, F. Pagani, C. Zhu, L. Dresel, G. Vigna, C. Kruegel, R. Wang, T. Bao, Y. Shoshitaishvili, A. Doupé. "Toss a Fault to Your Witcher: Applying Grey-box Coverage-Guided Mutational Fuzzing to Detect SQL and Command Injection Vulnerabilities." *IEEE S&P 2023*, pp. 2658–2675. DOI 10.1109/SP46215.2023.10179317. https://pagabuc.me/docs/oakland23_witcher.pdf
- **(a) Mechanism:**
  - Grey-box coverage-guided fuzzing of web endpoints, with coverage taken from instrumented interpreters.
  - "Fault escalation": instrumented DB and shell sinks turn injection attempts into detectable faults.
  - "Output-derived input guidance" feeds observed outputs back into input generation.
- **(b) Evaluation:**
  - 18 apps in PHP, Python, Node.js, Java, Ruby, and C.
  - Found 23 of 36 known vulnerabilities (64%) plus 67 new ones, 4 with CVEs.
  - Coverage beat Burp (solo) and Burp seeded with Witcher's URLs on every app, by more than 100% on four apps.
  - Compared with Black Widow and WebFuzz on unique lines covered only, because those tools target XSS.
  - Throughput: about 142 requests/s, versus 1.6 for Black Widow, 6.8 for Burp, and 22.5 for WebFuzz.
- **(c) Limitations:**
  - Grey-box, so it needs server instrumentation.
  - Focuses on one page at a time, so it is less likely to trigger multi-page states.

### 10b. Atropos [V-full]
- **Citation:** E. Güler, S. Schumilo, M. Schloegel, N. Bars, P. Görz, X. Xu, C. Kaygusuz, T. Holz. "Atropos: Effective Fuzzing of Web Applications for Server-Side Vulnerabilities." *USENIX Security 2024*, pp. 4765–4782. https://usenix.org/system/files/usenixsecurity24-guler.pdf
- **(a) Mechanism:**
  - Snapshot-based, feedback-driven fuzzing of PHP apps, built on **Nyx**.
  - A snapshot is taken after initialization, including the DB. The VM is restored to it after **every** fuzzing iteration, so filesystem, sessions, memory, and DB state are all reset.
  - Infers request key/value structure from interpreter feedback.
  - Uses 8 bug oracles placed at instrumented PHP sinks.
- **(b) Evaluation:**
  - On average finds at least 32% more bugs than the state of the art, with no false positives.
  - Compared against static tools (SonarQube, Progpilot, Psalm, phpcs-security-audit) and dynamic tools (Witcher, wfuzz, ZAP, Wapiti, WebFuzz).
  - Found 7 previously unknown vulnerabilities exploitable without authentication.
- **(c) Limitations:**
  - Needs hours of compute.
  - Resetting after every input misses bugs that need inputs chained without a reset.
  - Supports only 8 vulnerability classes.

### 11. AutoE2E [V-full]
- **Citation:** P. Alian, N. Nashid, M. Shahbandeh, T. Shabani, A. Mesbah. "Feature-Driven End-To-End Test Generation." *ICSE 2025*. arXiv 2408.01894. https://arxiv.org/abs/2408.01894
- **Correction / important:** AutoE2E **relies on LLMs** (GPT-4o or Claude 3) for feature inference. It is not model-free.
- **(a) Mechanism:**
  - Explores the app and has the LLM infer candidate features (entity CRUD and configuration operations) from observed actions.
  - Scores how likely each feature exists by how often it is observed.
  - Generates one end-to-end test per feature.
  - Also introduces **E2EBench**: 8 apps with ground-truth features obtained by instrumenting front-end code and mapping action logs to features through a "feature grammar":

    | App | Features |
    |---|---|
    | PetClinic | 23 |
    | Conduit | 17 |
    | Taskcafe | 32 |
    | Dimeshift | 21 |
    | MantisBT | 27 |
    | EverTraduora | 41 |
    | Saleor Storefront | 13 |
    | Saleor Dashboard | 130 |

- **(b) Evaluation:**
  - Average feature coverage 79%; total 72% across all features.
  - Feature-inference precision 0.55, recall 0.72, F1 0.62.
  - Baseline feature coverage:

    | Tool | Feature coverage |
    |---|---|
    | AutoE2E | 79% |
    | Crawljax test generation | 12.0% |
    | BrowserGym (GPT-4o) | 9.5% |
    | OpenDevin | 7.9% |
    | AutoGPT | 6.1% |
    | WebCanvas | 0% (generated no tests) |

  - That is +558% over Crawljax and +731% over BrowserGym.
  - Average feature-chain length in the benchmark is 3.4 actions. AutoE2E's tests average 3.8, versus 2.9 for Crawljax.
- **(c) Limitations:**
  - One-to-one mapping between tests and features.
  - Assertions are generated from the entire state after each action.
  - Benchmark representativeness and subjectivity in feature extraction are acknowledged threats.

### 12. APE [V-full]
- **Citation:** T. Gu, C. Sun, X. Ma, C. Cao, C. Xu, Y. Yao, Q. Zhang, J. Lu, Z. Su. "Practical GUI Testing of Android Applications via Model Abstraction and Refinement." *ICSE 2019*. https://helloqirun.github.io/papers/icse19_tianxiao.pdf
- **(a) Mechanism:**
  - The GUI model's state and action abstraction is a decision tree of attribute "reducers".
  - It is refined or coarsened at runtime, CEGAR-style.
  - Example trigger: a model action is refined if it causes non-deterministic transitions (threshold α = 3).
- **(b) Evaluation:**
  - 15 large Google Play apps, 1-hour runs, 5 runs each.
  - Against Monkey, Sapienz, and Stoat, APE had consistent relative improvements of:
    - 26–78% in average activity coverage
    - 17–22% in method coverage
    - 14–26% in instruction coverage
  - Unique crashes: APE **62** in the introduction and **61** in the evaluation section (the paper is internally inconsistent), versus Monkey 44, Sapienz 40, Stoat 31.
  - On 1,316 apps at 30 minutes each, it found 537 unique crashes.

### 13. Stoat [V-full abstract and intro]
- **Citation:** T. Su, G. Meng, Y. Chen, K. Wu, W. Yang, Y. Yao, G. Pu, Y. Liu, Z. Su. "Guided, Stochastic Model-Based GUI Testing of Android Apps." *ESEC/FSE 2017*, pp. 245–256. DOI 10.1145/3106237.3106298. https://github.com/tingsu/stoat
- **(a) Mechanism:**
  - Builds a stochastic GUI model (a probabilistic FSM) using dynamic weighted exploration plus static analysis.
  - Uses Gibbs sampling to mutate and refine the model toward code and model coverage and sequence diversity.
  - Injects system-level events at random.
- **(b) Evaluation:**
  - 93 open-source apps.
  - Its models covered 17–31% more code than those of existing modelling tools.
  - About 3× more unique crashes than Monkey and Sapienz.
  - 20 reported crashes confirmed, 8 fixed.

### 14a. Humanoid [V-full arXiv]
- **Correction:** Humanoid is **not** by Pan et al. It is Y. Li, Z. Yang, Y. Guo, X. Chen (Peking University).
- **Citation:** *ASE 2019*, pp. 1070–1073, a short paper. arXiv 1901.02633 is the extended technical report. https://arxiv.org/abs/1901.02633
- **(a) Mechanism:** A deep network trained on human interaction traces prioritizes which UI element to interact with and how. Built on DroidBot.
- **(b) Evaluation:**
  - Interaction-prediction accuracy: top-1 51.2%, top-10 85.2%.
  - Higher coverage than six state-of-the-art generators (68 AndroTest apps plus market apps).
  - **Key caveat stated by the authors:** the learned model was *not* the main reason for the coverage gain. It had limited effect on the width and depth of GUI state search.

### 14b. Q-testing [V-abs]
- **Citation:** M. Pan, A. Huang, G. Wang, T. Zhang, X. Li. "Reinforcement Learning Based Curiosity-Driven Testing of Android Applications." *ISSTA 2020*, pp. 153–164. DOI 10.1145/3395363.3397354. ACM SIGSOFT Distinguished Paper.
- **(a) Mechanism:** Q-learning with a curiosity reward based on a memory of visited states. A neural network compares states at the level of functional scenarios.
- **(b) Evaluation:**
  - 50 open-source apps; outperformed state-of-the-art and state-of-practice tools in coverage and fault detection.
  - 22 reported faults confirmed, 7 fixed.
  - Per-tool numbers: **UNVERIFIED** (full text not retrieved).

### 14c. Themis [V-full]
- **Citation:** T. Su, J. Wang, Z. Su. "Benchmarking Automated GUI Testing for Android against Real-World Bugs." *ESEC/FSE 2021*, pp. 119–130. DOI 10.1145/3468264.3468620. https://github.com/the-themis-benchmarks/home
- **Setup:**
  - 52 real, reproducible "critical" crash bugs.
  - Six tools: Monkey, Ape, Humanoid, ComboDroid, TimeMachine, Q-testing.
  - More than 10,920 CPU hours; 6-hour runs repeated 5 times.
- **Findings:**
  - 18 of the 52 bugs were found by **no** tool.
  - Each tool on its own missed 53.8–71.2% of the bugs.
  - Tools show obvious randomness in triggering bugs, and **no tool consistently outperforms the others**.
  - Results are largely driven by exploration strategy, **state-abstraction criteria**, and small heuristics.
  - Five common challenges:
    1. deep use-case scenarios
    2. specific text inputs
    3. changing system or app settings
    4. specific user-interaction patterns
    5. external app interaction

### 15. TimeMachine [V-abs; numbers V-sec]
- **Citation:** Z. Dong, M. Böhme, L. Cojocaru, A. Roychoudhury. "Time-travel Testing of Android Apps." *ICSE 2020*, pp. 481–492. DOI 10.1145/3377811.3380402. ACM SIGSOFT Distinguished Paper. https://github.com/DroidTest/TimeMachine
- **(a) Mechanism:**
  - Snapshots the whole system (app plus environment, in a VM) at "interesting" states and keeps a state corpus.
  - When progress stalls, it restores the most progressive saved state and explores from there.
  - Built on Monkey.
- **(b) Evaluation:**
  - Outperforms Sapienz and Stoat in coverage and crashes on open- and closed-source apps.
  - "1.15× statement coverage and 1.73× unique crashes over the baseline (Monkey) on AndroTest" comes from a secondary summary and is **UNVERIFIED** against the PDF (the author site returned 403).

### 16a. DroidAgent [V-full arXiv]
- **Correction:** the published ICST title is **"Intent-Driven Mobile GUI Testing with Autonomous Large Language Model Agents."**
- **Citation:** J. Yoon, R. Feldt, S. Yoo. *ICST 2024*, pp. 129–139. DOI 10.1109/ICST60714.2024.00020. arXiv 2311.08649. https://arxiv.org/abs/2311.08649
- **Mechanism:** An LLM agent that sets its own task goals with long- and short-term memory.
- **Evaluation:**
  - 15 Themis apps.
  - Activity coverage 60.7% (about 61%), versus the best baseline Humanoid at 51.4%. Other baselines: Monkey, DroidBot, and a reimplementation of GPTDroid.
  - Tasks judged realistic: arXiv v1 says 317/374, but the Chalmers record says 317/547. **This discrepancy is unresolved.**

### 16b. Exploration-first trajectory synthesis [V-abs]
- **NNetNav:** S. Murty, H. Zhu, D. Bahdanau, C. D. Manning. arXiv 2410.02907 (ICLR 2025 listing).
  - Explores websites without supervision, then uses an LM to relabel rollouts with instructions retroactively, pruning by hierarchical sub-task decomposition.
  - WebArena success for Llama-3.1-8B rose from 1% to 7.2%.
- **OS-Genesis:** Q. Sun et al. *ACL 2025* long paper, pp. 5555–5579. arXiv 2412.19723.
  - Explores GUIs step by step first, then synthesizes tasks in reverse, filtered by a trajectory reward model.

---

## Automata learning / model-based testing

### 17. L*, TTT, LearnLib [V-abs]
- **L\*:** D. Angluin. "Learning regular sets from queries and counterexamples." *Information and Computation* 75(2):87–106, 1987. DOI 10.1016/0890-5401(87)90052-6.
  - Learns a minimal DFA using membership and equivalence queries in time polynomial in the number of states and the length of the longest counterexample. This is the standard result and was not re-read from the PDF.
- **TTT:** M. Isberner, F. Howar, B. Steffen. *RV 2014*, LNCS, pp. 307–322. DOI 10.1007/978-3-319-11164-3_26.
  - Stores observations without redundancy (spanning tree, discrimination tree, and discriminator finalization). Space complexity is linear.
  - Robust to very long counterexamples, as in monitoring and runtime verification.
  - Isberner's 2015 thesis claims TTT is space-optimal [V-sec].
- **LearnLib:** M. Isberner, F. Howar, B. Steffen. "The Open-Source LearnLib — A Framework for Active Automata Learning." *CAV 2015*, LNCS 9206, pp. 487–495. DOI 10.1007/978-3-319-21690-4_32.
  - The venue is inferred from the DOI volume.

### 18. Abstraction/mappers; register automata [V-abs]
- **Aarts, Jonsson, Uijen, Vaandrager.** "Generating models of infinite-state communication protocols using regular inference with abstraction." *Formal Methods in System Design* 46(1):1–41, 2015 (online November 2014). DOI 10.1007/s10703-014-0216-x.
  - A conference version (Aarts, Jonsson, Uijen) appeared in 2010 in LNCS, pp. 188–204 (ICTSS 2010; venue not separately verified).
  - **Mechanism:** a **mapper** placed between learner and system abstracts concrete parameter values into a small abstract alphabet, in the spirit of predicate abstraction, so that L* can be applied.
  - **Subjects:** the SIP and TCP implementations in the ns-2 simulator, learned using LearnLib [V-sec].
- **Tomte:** F. Aarts, P. Fiterău-Broştean, H. Kuppens, F. Vaandrager. "Learning Register Automata with Fresh Value Generation." *ICTAC 2015*, LNCS, pp. 165–183. Also Aarts, Howar, Kuppens, Vaandrager. "Algorithms for Inferring Register Automata." *ISoLA 2014*, pp. 202–219.
  - Builds the mapper automatically through counterexample-guided abstraction refinement [V-sec].
- **RALib line:** S. Cassel, F. Howar, B. Jonsson, B. Steffen. "Active learning for extended finite state machines." *Formal Aspects of Computing* 28(2):233–263, 2016.
  - Black-box learning of register automata with guards, using **tree queries** and parameterized by a data theory.
  - Case studies: TCP connection establishment and a Java priority queue.

### 19. Vaandrager, "Model Learning" [V-abs for citation; applications V-sec]
- **Citation:** *CACM* 60(2):86–95, 2017. DOI 10.1145/2967606.
- **Abstract:** model learning "emerges as an effective method for black-box state machine models of hardware and software components."
- **Applications associated with the Nijmegen line of work [V-sec]:**
  - EMV bank cards (Aarts et al. 2013)
  - TCP stacks; Windows and Linux were found to violate the TCP spec (Fiterău-Broştean et al.)
  - SSH and TLS implementations (de Ruiter and Poll)
  - The Océ printer Engine Status Manager (Smeenk et al. 2015)
  - Philips legacy component refactoring (Schuts, Hooman, Vaandrager, IFM 2016)
- **UNVERIFIED** which of these the CACM article itself names. The full text was not accessible.

### 20. Walkinshaw et al. [V-abs]
- **Citation:** N. Walkinshaw, R. Taylor, J. Derrick. "Inferring extended finite state machine models from software executions." *Empirical Software Engineering* 21(3):811–853. DOI 10.1007/s10664-015-9367-7. Online 2015; issue 2016, so citing "EMSE 2016" is acceptable.
  - Earlier version: WCRE 2013.
- **(a) Mechanism:** Passive (trace-based) EFSM inference that combines state-merging with off-the-shelf ML classifiers to infer data guards on transitions. It addresses the inflexibility and non-determinism of earlier EFSM inferencers. Tool: **MINT**.
- **(b) Evaluation:** Adapts an ML-style evaluation method; applied to three software systems. Specific accuracy numbers are **UNVERIFIED**.

### 21. Daikon [V-full abstract]
- **Citation:** M. D. Ernst, J. H. Perkins, P. J. Guo, S. McCamant, C. Pacheco, M. S. Tschantz, C. Xiao. "The Daikon system for dynamic detection of likely invariants." *Science of Computer Programming* 69(1–3):35–45, 2007. https://homes.cs.washington.edu/~mernst/pubs/daikon-tool-scp2007.pdf
- **Mechanism:** Runs the program, observes the values it computes, and reports properties from a template grammar that held over all observed executions.
  - Template examples: constants, non-zero, ranges, linear relationships, ordering, containment, sortedness.
  - Supports C, C++, Java, Perl, and record-structured data.
- **Limitation:** The results are *likely* invariants, valid only for the observed executions.

### 22. Utting, Pretschner, Legeard [V-abs]
- **Citation:** "A taxonomy of model-based testing approaches." *STVR* 22(5):297–312, 2012 (online 2011). DOI 10.1002/stvr.456.
- **Content:** Describes the MBT process and a taxonomy for classifying MBT tools, illustrated with three tools.
- **Dimension names and count:** **UNVERIFIED.** The 2006 Waikato working paper says "seven dimensions", and a secondary source mentions six for the journal preprint.

---

## API/UI evidence fusion and REST

### 23. RESTler [V-full]
- **Citation:** V. Atlidakis, P. Godefroid, M. Polishchuk. "RESTler: Stateful REST API Fuzzing." *ICSE 2019*, pp. 748–758. DOI 10.1109/ICSE.2019.00083. https://patricegodefroid.github.io/public_psfiles/icse2019.pdf
- **(a) Mechanism:**
  - Reads an OpenAPI/Swagger spec.
  - Infers producer–consumer dependencies: request B consumes a resource ID that request A produces.
  - Uses dynamic feedback to prune sequences the service rejects.
  - Search strategies: BFS, BFS-Fast, RandomWalk.
- **(b) Evaluation:** Found 28 bugs in GitLab plus bugs in Azure and Office365 services, all confirmed and fixed.
- **(c) Limitations:**
  - The oracle is only HTTP 500 (unexpected status codes).
  - No support for server-side redirects.
  - Requires a spec.

### 24. Morest [V-full abstract]
- **Citation:** Y. Liu, Y. Li, G. Deng, Y. Liu, R. Wan, R. Wu, D. Ji, S. Xu, M. Bao. "Morest: Model-based RESTful API Testing with Execution Feedback." *ICSE 2022*, pp. 1406–1417. DOI 10.1145/3510003.3510133. arXiv 2204.12148.
- **(a) Mechanism:** Builds a dynamically updated RESTful-service Property Graph (RPG) from the OpenAPI spec and refines it with execution feedback to guide call-sequence generation.
- **(b) Evaluation:**
  - Baselines: EvoMaster in black-box mode, RESTTestGen, and RESTler.
  - 6 services: 4 from the EvoMaster benchmark plus industrial ones.
  - Against those baselines:
    - 152.66–232.45% more API operations successfully requested
    - 26.16–103.24% more lines covered
    - 40.64–215.94% more bugs
  - 44 bugs in total, 13 not detectable by the others, including 2 confirmed in Bitbucket.

### 25. EvoMaster [V-abs]
- **Citation:** A. Arcuri. "RESTful API Automated Test Case Generation with EvoMaster." *ACM TOSEM* 28(1), 2019. DOI 10.1145/3293455. Earlier version at QRS 2017.
- **Summary:** Search-based (evolutionary) system-level test generation for REST APIs. It is white-box with bytecode-instrumentation heuristics and also has a black-box mode.

---

## Exploration / RL / planning

### 26. Options framework and MAXQ [V-abs]
- **Options:** R. S. Sutton, D. Precup, S. Singh. "Between MDPs and semi-MDPs: A framework for temporal abstraction in reinforcement learning." *Artificial Intelligence* 112(1–2):181–211, 1999.
- **MAXQ:** T. G. Dietterich. "Hierarchical Reinforcement Learning with the MAXQ Value Function Decomposition." *JAIR* 13:227–303, 2000.

### 27. Go-Explore [V-full preprint v6]
- **Citation:** A. Ecoffet, J. Huizinga, J. Lehman, K. O. Stanley, J. Clune. "First return, then explore." *Nature* 590:580–586, 2021. DOI 10.1038/s41586-020-03157-9. arXiv 2004.12919.
- **(a) Mechanism:**
  - Diagnoses two failure modes: "detachment" and "derailment".
  - Keeps an **archive of cells**: low-dimensional state representations such as downscaled frames, or domain features like room, level, and keys.
  - Selects a promising cell, **returns** to it (by restoring simulator state or with a goal-conditioned policy), then explores from it.
  - An optional robustification phase uses the backward algorithm to make the policy robust to stochasticity.
- **(b) Results:**
  - Solves all previously unsolved Atari games under sticky-action evaluation and beats the state of the art on all hard-exploration games.
  - Montezuma's Revenge: robustified 43,791 versus prior state of the art 11,618 and human 4,753.
  - Pitfall: 6,954 versus a prior state of the art of 0.
  - With domain-knowledge cells, Montezuma reaches 1,731,645.
  - Also solves a sparse-reward robotics pick-and-place task.
  - Numbers are from preprint v6, which matches the Nature version. Spot-check against the Nature tables if you quote them.
- **(c) Assumption:** The "return" step via state restore needs a resettable or restorable simulator. The policy-based return relaxes this.

### 28. Count-based exploration, curiosity, RND [V-full abstracts]
- **Count-based:** M. G. Bellemare, S. Srinivasan, G. Ostrovski, T. Schaul, D. Saxton, R. Munos. "Unifying Count-Based Exploration and Intrinsic Motivation." *NeurIPS (NIPS) 2016*. arXiv 1606.01868.
  - Derives pseudo-counts from a density model and turns them into exploration bonuses.
  - Significantly improved exploration on hard Atari games, including Montezuma's Revenge.
- **Curiosity (ICM):** D. Pathak, P. Agrawal, A. A. Efros, T. Darrell. "Curiosity-driven Exploration by Self-supervised Prediction." *ICML 2017*. arXiv 1705.05363.
  - Intrinsic reward is the forward-model prediction error in a feature space learned by an inverse-dynamics model, which ignores factors the agent cannot affect.
  - Evaluated on VizDoom and Super Mario Bros.
- **RND:** Y. Burda, H. Edwards, A. Storkey, O. Klimov. "Exploration by Random Network Distillation." *ICLR 2019*. arXiv 1810.12894.
  - The bonus is the error of a network predicting the outputs of a fixed, randomly initialized network.
  - State of the art on Montezuma's Revenge at the time, and the first to exceed average human performance without demonstrations or access to game state.

### 29. BALD and expected information gain [V-full / V-abs]
- **BALD:** N. Houlsby, F. Huszár, Z. Ghahramani, M. Lengyel. "Bayesian Active Learning for Classification and Preference Learning." arXiv 1112.5745, 2011.
  - Expresses information gain as a difference of predictive entropies, applied to GP classification.
  - The name "Bayesian Active Learning by Disagreement (BALD)" comes from this paper.
- **Expected information gain (canonical):**
  - D. V. Lindley. "On a Measure of the Information Provided by an Experiment." *Annals of Mathematical Statistics* 27(4):986–1005, 1956.
  - Review: K. Chaloner, I. Verdinelli. "Bayesian Experimental Design: A Review." *Statistical Science* 10(3):273–304, 1995.

### 30. SHOP2 [V-abs]
- **Citation:** D. Nau, T.-C. Au, O. Ilghami, U. Kuter, J. W. Murdock, D. Wu, F. Yaman. "SHOP2: An HTN Planning System." *JAIR* 20:379–404, 2003. DOI 10.1613/jair.1141. arXiv 1106.4869.
- **Summary:** An HTN planner that decomposes tasks in the order they will be executed. It won a distinguished-performance award at IPC 2002 and handles temporal and numeric constraints.

---

## Oracles / state restoration

### 31. Oracle survey and metamorphic testing survey
- **Barr et al. [V-full]:** E. T. Barr, M. Harman, P. McMinn, M. Shahbaz, S. Yoo. "The Oracle Problem in Software Testing: A Survey." *IEEE TSE* 41(5):507–525, 2015. DOI 10.1109/TSE.2014.2372785. https://discovery.ucl.ac.uk/1471263/
  - Four categories, with the number of papers surveyed in each:

    | Category | Papers |
    |---|---|
    | Specified oracles | 317 |
    | Derived oracles | 245 |
    | Implicit oracles | 76 |
    | Handling the lack of an oracle (incl. human oracle cost) | 56 |

- **Metamorphic testing [V-abs]:** T. Y. Chen, F.-C. Kuo, H. Liu, P.-L. Poon, D. Towey, T. H. Tse, Z. Q. Zhou. "Metamorphic Testing: A Review of Challenges and Opportunities." *ACM CSUR* 51(1), Art. 4, 2018. DOI 10.1145/3143561.

### 32. Nyx and AFLNet
- **Nyx [V-full abstract]:** S. Schumilo, C. Aschermann, A. Abbasi, S. Wörner, T. Holz. "Nyx: Greybox Hypervisor Fuzzing using Fast Snapshots and Affine Types." *USENIX Security 2021*, pp. 2597–2614.
  - Fast VM snapshot restore reloads the system under test thousands of times per second.
  - Uses a bytecode/DAG input representation with affine types.
  - Found 44 new bugs, with 22 CVEs requested.
  - Lower raw throughput than blind fuzzers, but it wins on complex devices.
- **AFLNet [V-abs]:** V.-T. Pham, M. Böhme, A. Roychoudhury. "AFLNet: A Greybox Fuzzer for Network Protocols." *ICST 2020* (short tool paper), pp. 460–465. DOI 10.1109/ICST46399.2020.00062.
  - Seeded with recorded client–server message exchanges; no spec or grammar is needed.
  - Uses server **response codes** as state identifiers, builds an implemented-protocol state machine, and steers toward "progressive" states.
  - Two case studies (FTP and RTSP); 2 critical CVEs.
  - Head-to-head numbers from the original paper: **UNVERIFIED**.
  - **Retrospective [V-full]:** Meng, Pham, Böhme, Roychoudhury. "AFLNet Five Years Later." arXiv 2412.20324.
    - State feedback alone works when the number of states is reasonable.
    - Adding state feedback covered 35.67× more states.
    - It did **not** significantly improve code coverage (significant on only 1 of 12 subjects, and significantly negative on 2).
    - The authors attribute this partly to response codes being a poor state definition.

### 33. Test isolation, state pollution, and database reset
- **PolDet [V-full abstract]:** A. Gyori, A. Shi, F. Hariri, D. Marinov. "Reliable Testing: Detecting State-Polluting Tests to Prevent Test Dependency." *ISSTA 2015*, pp. 223–233. DOI 10.1145/2771783.2771793.
  - Detects heap and file-system pollution. It does not cover databases.
  - 26 projects with 6,105 tests: 324 reported as polluting, of which 194 were relevant.
- **VMVM [V-abs]:** J. Bell, G. Kaiser. "Unit Test Virtualization with VMVM." *ICSE 2014*, pp. 550–561. DOI 10.1145/2568225.2568248.
  - A lightweight in-JVM isolation container.
  - On 20 Java apps, test-suite time dropped by up to 97% (62% on average) compared with process-per-test isolation.
  - Four times the reduction achieved by a test-suite minimization technique, with no loss of fault-finding ability.
- **Luo et al. [V-full]:** Q. Luo, F. Hariri, L. Eloussi, D. Marinov. "An Empirical Analysis of Flaky Tests." *FSE 2014*.
  - 161 flaky-fix commits studied in depth.
  - Test Order Dependency accounted for 19/161 (12%) of commits, versus Async Wait at 45%.
  - 47% of order-dependency cases were caused by dependence on external resources.
  - 74% were fixed by cleaning shared state.
- **TEDD — web end-to-end specific [V-full abstract]:** M. Biagiola, A. Stocco, A. Mesbah, F. Ricca, P. Tonella. "Web Test Dependency Detection." *ESEC/FSE 2019*. DOI 10.1145/3338906.3338948. arXiv 1905.00357.
  - Argues that multi-tier web apps make isolated per-test state hard to achieve.
  - Uses string analysis plus NLP to find and validate dependencies in Selenium suites.
  - Six apps (196 tests); up to 72% faster than a validate-all baseline; parallel speed-up of up to 7×.
- **Snapshot/reset used in papers above (all [V-full]):**
  - ATUSA: SQL script resets the DB before each run.
  - Deemon: VM snapshot and restore.
  - Atropos: Nyx full-VM snapshot including the DB, restored after every input.
  - TimeMachine: VM snapshots used as exploration checkpoints.
- **Not found:** a dedicated empirical study measuring **database** snapshot/reset strategies (transaction rollback, truncate, reseed, or VM snapshot) for web E2E test isolation.

---

## Extra: 2023–2026 work on black-box feature mapping and SPA state abstraction
1. **FragGen** [V-abs]: R. Yandrapally, A. Mesbah. "Fragment-Based Test Generation for Web Apps." *IEEE TSE* 49(3):1086–1101, 2023. arXiv 2110.14043.
   - Threshold-free state equivalence based on page fragments.
   - On 86,165 state pairs it detected 123% more near-duplicates than whole-page techniques.
   - Crawl models had +62% precision and +70% recall.
2. **VISCA** [V-abs]: P. Alian, M. Tang, A. Mesbah. arXiv 2506.04161, 2025.
   - Segments pages into a hierarchy of semantic UI-component abstractions, classified by a multimodal LLM, to feed E2E test generation.
   - 92% average feature coverage on E2EBench, 16% above the prior LLM-based state of the art (AutoE2E's 79%).
3. **Liu, Yang, Zhang, Xie** [V-abs]: "Understanding Automated Web GUI Testing: An Empirical Study Across Exploration Strategies and State Abstractions." arXiv 2606.16650, June 2026.
   - Compares model-based, RL-based, and LLM-based strategies under six state abstractions.
   - No single strategy wins on every dimension.
   - Fine-grained abstractions favour model-based exploration; compact abstractions favour RL.
   - Code coverage correlates only weakly with failure discovery.
4. **YuraScanner** [V-abs]: Stafeev et al. *NDSS 2025* (author list not fully verified). https://ndss-symposium.org/ndss-paper/yurascanner-leveraging-llms-for-task-driven-web-app-scanning
   - An LLM extracts user tasks/workflows and drives the crawl, with Black Widow's attack module reused for comparison.
   - Evaluated on 20 apps; found 12 new XSS versus 3 for Black Widow.
5. **Hoyen** [V-sec]: "Unlocking User-oriented Pages: Intention-driven Black-box Scanner for Real-world Web Applications." arXiv 2504.20801, 2025.
   - An LLM predicts user intentions to expand scanner scope.

**Note:** every 2024–2026 "feature-level" mapping system found relies on LLMs at runtime: AutoE2E, VISCA, YuraScanner, Hoyen, DroidAgent, NNetNav, and OS-Genesis. FragGen is the most recent model-free work on state abstraction.
