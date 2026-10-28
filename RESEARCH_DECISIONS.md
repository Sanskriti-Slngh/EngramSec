# Coverage-method decisions

The existing comparative review remains in `RESEARCH_REVIEW.md`; this milestone maps established mechanisms to measured baseline weaknesses rather than restarting that review.

| Candidate | Measured weakness addressed | Expected effect | Cost and failure mode | Decision/experiment |
|---|---|---|---|---|
| Crawljax-style event/state-flow crawling | Invisible JS/disclosure controls and event branches | More reachable areas and controls | More clicks; unsafe or ineffective events can waste budget | Adopt a bounded semantic-control subset; compare equal-budget recall |
| FragGen-style fragment awareness | Whole-page identity and shared chrome | Component novelty without merging record content | Incorrect fragments can cause false merges/splits | Defer full fragmentation; retain raw observations and use control/request novelty first |
| Go-Explore archive/return/branch | Repeated shallow starts and deep prerequisites | Better deep-path branching | Restoration itself costs actions; mutable state may invalidate paths | Keep saved paths and add restoration-cost/novelty scoring; do not reuse mutable browser contexts yet |
| WebExplor-style coverage/curiosity guidance | Type-only frontier repeatedly explores common links | More new controls/forms/requests per action | Proxy novelty can favor cosmetic churn | Add deterministic coverage policy and ablate it against grouped policy |
| Active automata learning | Need systematic action/output abstraction | Better behavioral model under reliable resets | Reset assumptions fail on stateful apps; membership queries are expensive | Do not implement now; fresh-context replay remains the bounded conformance check |
| Request-aware action evidence | 60% request recall; POST parameters absent | More security-relevant endpoint/input structure with provenance | Request bodies may contain secrets | Record names/shape only, never values; add leak regression |
| Browser-observed context markers | Static label falsely implies session identity | Preserve anonymous/member separation | Cookie values are sensitive and volatile | Record only hashed marker-name sets, not values |
| Model assistance | No measured semantic interpretation bottleneck yet | May disambiguate novel controls/forms | Latency, nondeterminism, cost, and self-grading risk | Not selected; deterministic ablations first, no external calls |

The three bounded iterations are: (1) semantic-control readiness, (2) coverage-guided frontier scoring, and (3) request/context structure. A change is retained only with positive/negative regressions and matched evaluation. No RL training, visual model, benchmark-specific selector, expected route, or vulnerability metadata is introduced.

Established mechanisms are described in the primary Crawljax, FragGen, Go-Explore, WebExplor, and automata-learning sources already cited in `RESEARCH_REVIEW.md`. The implementation here is an engineering adaptation, not a novelty claim.
