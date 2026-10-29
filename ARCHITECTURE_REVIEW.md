# Agent 1 architecture review

Date: 2026-10-29

## Evidence boundary

This review uses the Agent 1 implementation, its independent local fixtures, the public Crawlground obstacle course, and published sources. No WebExploitBench evaluation artifact, vulnerability metadata, protected location, trace, or prior benchmark observation was used to choose or tune the changes.

## Prior architecture and measured liabilities

Agent 1 already had a sound evidence core: raw browser observations, reversible groups, sanitized document/Fetch/XHR structures, per-action transitions, protected form-plan references, archived return paths, fresh-context replay, connection-evidence audits, and checkpoint defaults. Graph A preserved individual observations and session marker *names* rather than cookie/storage values.

The exploration lifecycle was the limiting design. Every frontier edge created a new browser context, loaded the root, waited a fixed interval, and replayed its complete prerequisite path. Initial-navigation traffic was drained rather than represented. Restoration normally required a whole grouped signature match. Scope treated any hostname change as cross-origin, even when an operator had explicitly configured two local aliases. These choices are safe but systematically expensive and can observe a JavaScript application before hydration.

The current action alphabet is ordinary link/button/form click and fill/select/check. It does not yet cover hover, scroll, focus/keyboard sequences, iframe traversal, shadow DOM, drag/drop, canvas coordinates, or reliable new-tab handling.

## Transferable findings from prior work

- ZAP's July 2026 Client Spider rationale reports that repeatedly reopening the root wastes initialization work and can destroy session state. Its maintained Client Map tracks discovered and pending states while the extension streams DOM events. Agent 1 adopts the live-state/archive principle, not ZAP's extension implementation: [ZAP Client Spider design rationale](https://www.zaproxy.org/blog/2026-07-06-client-spider-now-recommended/).
- The 2024 USENIX SoK found no universally best crawler configuration and found randomized algorithms competitive or better in parts of its evaluation. This rules out treating policy sophistication as evidence; P0/P1/P2 therefore use matched budgets and independent scoring: [Stafeev and Pellegrino, USENIX Security 2024](https://www.usenix.org/conference/usenixsecurity24/presentation/stafeev).
- Crawljax's event/state-flow model supports representing browser events and resulting UI states. FragGen shows why thresholded whole-page equivalence is inadequate for near-duplicate dynamic pages and motivates a later fragment-aware experiment, not a merge heuristic added without evaluation: [Crawljax](https://github.com/crawljax/crawljax), [FragGen](https://arxiv.org/abs/2110.14043).
- Go-Explore separates remembering, returning, and branching. Agent 1 already had return paths; the new persistent policy uses the current verified live state when safe and falls back to an archived path: [Go-Explore](https://arxiv.org/abs/2004.12919).
- WebExplor combines an online automaton with curiosity-guided action selection. Its reported results do not justify introducing RL here; deterministic novelty remains inspectable and cheaper: [WebExplor](https://arxiv.org/abs/2103.06018).
- Playwright explicitly states there is no universal page-loaded predicate for modern applications. Locator actions auto-wait for visibility, stability, event reception, and enabled state; hydration can still present controls before listeners are ready. Agent 1 therefore records a bounded readiness trace rather than using `networkidle` or claiming total load: [navigation/hydration guidance](https://playwright.dev/docs/navigations), [actionability checks](https://playwright.dev/docs/actionability).
- BrowserGym's action representation includes hover, focus, keyboard, scroll, drag, coordinate, tab, and navigation primitives. This is a useful completeness checklist for Agent 1's future deterministic action plugins: [BrowserGym action space](https://browsergym.readthedocs.io/latest/core/action_space.html).

## Implemented design

### P1: readiness and origin foundation

`robust_readiness` polls browser-observable document state, explicit `aria-busy`, enabled/disabled actionable controls, and a compact control-shape fingerprint. It requires a short stable window, records every sample, and classifies `usable`, `blocked`, or `timeout`. It is bounded and does not claim the entire application is loaded. Initial document/Fetch/XHR events are exported as `navigation_evidence`, separate from action-triggered networks.

`origin_aliases` accepts only explicit HTTP(S) loopback origins without credentials or paths. Unlisted ports/hosts and all external destinations remain rejected. Restoration affordance comparison now includes cookie/storage marker names, preventing an authenticated-looking state from being accepted as an anonymous return screen.

### P2: persistent discovery, independent verification

The persistent policy keeps one discovery context, continues from the current observation when the queued action belongs to that exact state/context, and records the actual live prerequisite path. It archives shorter paths, detects stale execution, resets the browser context when queued and live session markers differ, and otherwise performs controlled root/path restoration. Replay is unchanged in principle: every validation still starts in a fresh context and executes the complete recorded sequence.

An early P2 experiment exposed missing live-path provenance and a later one exposed session-marker omission in restoration equivalence. Both failed artifacts are preserved. They were fixed before the three reported P2 repeats.

## Graph A compatibility and evidence audit

- Existing transition, replay, feature, functional-workflow, connection-evidence, state-group, and return-path fields remain intact.
- New config and artifact fields have defaults, so older checkpoints continue to validate.
- State nodes add `readiness_statuses`; Graph A adds top-level `navigation_evidence` with sanitized network structures and readiness samples.
- Live discovery never promotes an edge to replay-validated. Only the separate fresh-context verifier can do that.
- Raw observations remain preserved; grouping stays reversible.
- Cookie/storage values and form values are not exported. The independent leak check found zero occurrences of the fixture secret in every reported run.

## Known limits

Readiness is an interaction heuristic, not application quiescence. A control that changes after the bounded stable window can still be missed. Persistent discovery can generate more valid transitions than the verifier can schedule, and Crawlground exposed replay failures and unsupported interaction classes. The current viewport-only extraction and ordinary-click alphabet are the largest demonstrated external limitations.
