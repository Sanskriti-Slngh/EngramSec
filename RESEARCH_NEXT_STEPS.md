# Research next steps for Agent 1

Date: 2026-10-29

## Evidence boundary

These priorities use only the frozen JS-heavy lab, public Crawlground marker results, prior independent Coverage Lab/Northstar evidence, and published research. They do not use WebExploitBench outputs, protected metadata, vulnerability locations, or traces.

P2 solved the controlled deep-path problem: 11/11 areas replayed at depth 5 in all three repeats. It did not solve general crawling: only 5/59 public Crawlground markers were reached, 10/27 transfer replays failed, and 27 state groups were produced. The next objective is therefore higher independently replayable marker/surface coverage, not a larger graph.

## Ranked candidate 1: bounded semantic interaction plugins

**Measured weakness.** Crawlground misses directly expose absent hover, scroll/intersection, focus/keyboard, iframe, and shadow-DOM interaction/observation. BrowserGym's action space makes the gap explicit; Crawljax supports an event/state-flow view.

**Hypothesis.** Add one safe, browser-observable action class at a time: viewport/container scroll, hover disclosure, focus/Enter, same-origin iframe traversal, then open shadow-root traversal. Each candidate must be registered from an observed affordance and recorded as an ordinary Graph A action; no broad endpoint guessing.

**Complexity/tradeoff.** Medium per plugin, high in aggregate. Scroll and hover can cause candidate explosion; coordinate actions replay poorly; closed shadow roots and canvas may remain outside a DOM-first model.

**Independent experiment.** Freeze a gesture fixture and use Crawlground categories. Compare click-only against one plugin at a time under equal 140-action budgets, three repeats. Primary endpoint: new independent markers with a fresh replay. Track ineffective-action rate and regressions in existing replay reliability.

**Falsifier.** Reject a plugin if it adds no marker/replayed area on two independent testbeds, mostly produces ineffective transitions, causes a critical false merge, or lowers replay reliability below 95%.

Sources: [Crawljax](https://github.com/crawljax/crawljax), [BrowserGym action space](https://browsergym.readthedocs.io/latest/core/action_space.html).

## Ranked candidate 2: diversity- and cost-aware replay scheduling

**Measured weakness.** Persistent discovery produced 30 transitions quickly. On the final Crawlground run, the verifier attempted 27, failed 10, and left three untested; on controlled P1 the shallow-first scheduler replayed only 7–9 of 11 areas. P2 succeeded locally because paths were cheap and deterministic, not because scheduling is solved.

**Hypothesis.** Reserve validation budget across unique target groups, request shapes, contexts, and prerequisite-prefix classes. Rank by marginal evidence novelty divided by measured replay cost, while retaining failed and untested paths. This adapts Go-Explore's archive/return separation without snapshots or RL.

**Complexity/tradeoff.** Medium; current archives already contain most inputs. Cost prediction can starve important deep paths, and diversity proxies can be gamed by cosmetic states.

**Independent experiment.** Hold discovery output fixed, then replay the same frozen transition set with shallow-first, random, and diversity/cost scheduling under identical action limits. Score distinct independently labeled area/request classes replayed, reliability, and variance.

**Falsifier.** Reject if the median number of distinct replayed classes does not improve, gains vanish after charging setup actions, or reliability falls.

Source: [Go-Explore](https://arxiv.org/abs/2004.12919); the randomized baseline is required by the [State of the Krawlers SoK](https://www.usenix.org/conference/usenixsecurity24/presentation/stafeev).

## Ranked candidate 3: component-aware identity and novelty

**Measured weakness.** P2 produced 27 groups on Crawlground and repeatedly encountered shared shallow chrome. Current novelty is dominated by global control shape; it neither localizes a control to a component nor separates stable content from a changing fragment.

**Hypothesis.** Extract reversible accessible/DOM fragments around landmarks, forms, lists, dialogs, and control ancestors. Use component-local control novelty and independently audited fragment correspondence. Preserve raw observations, record/session markers, and unknown comparisons.

**Complexity/tradeoff.** Medium-high. Virtualized DOM, overlays, and moving boundaries can create false splits; aggressive fragment equivalence risks critical record/session merges.

**Independent experiment.** Freeze labeled fragment pairs (cosmetic rotation, different records, reordered lists, session controls, modal overlays) before implementation. First require zero critical false merges; then ablate whole-state versus component novelty under equal budgets.

**Falsifier.** Reject on any record/session false merge or if fewer groups do not yield more independent markers/replayed surfaces.

Source: [FragGen](https://arxiv.org/abs/2110.14043).

## Deferred method: multidimensional curiosity/RL

WebExplor suggests request/form/state novelty and automaton guidance, but deterministic plugins and scheduling have cheaper, directly measured failure targets. Full RL is unjustified until these ablations plateau. Source: [WebExplor](https://arxiv.org/abs/2103.06018).

## Agent boundary

Agent 1 owns safe website observation, origin/readiness enforcement, action discovery, sanitized request attribution, state/context identity, archived prerequisites, fresh replay, and unresolved/blocked reporting. Future planning/security-testing agents own vulnerability hypotheses, security-test selection, authorized credential acquisition, destructive-action approval, exploit construction, and impact confirmation. Agent 1 should expose a reachable surface and evidence path, never infer vulnerability from reachability.

## Next experiment

Implement only safe scroll plus hover-disclosure plugins first, each behind an explicit config flag, then run click-only/scroll-only/hover-only/combined ablations on the frozen gesture fixture and Crawlground. Do not combine with a new scheduler until the action plugins' independent contribution is measured.
