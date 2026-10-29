# Agent 1 high-coverage crawler architecture

## Evidence contract

All discovery mechanisms feed the existing Graph A. A static reference is an advertised candidate; it becomes an observed transition only after Chromium follows it. Fresh-context replay remains separate from persistent-session discovery. Each action records its observed control, interaction type, component, frame, protected input references, source/result observations, request structures, prerequisite path, and replay status. State grouping remains reversible because raw observations and signatures are retained.

The final implementation changes no origin or dangerous-action boundary. Cross-origin destinations remain blocked unless an explicit loopback alias is configured. POST remains opt-in. Browser context values, request values, cookies, and storage values are not exported.

## Hybrid discovery

`hybrid_link_discovery` turns browser-observed same-scope `a`/`area` hrefs into lightweight `navigate` candidates. It does not guess endpoints. The browser still supplies the DOM, resolves URLs, enforces origin policy, and records the resulting document/Fetch/XHR evidence. JavaScript controls and state changes use browser interactions. Both mechanisms deduplicate into the same frontier and Graph A.

Open shadow roots and same-scope frames are observed recursively. Controls retain `frame_index` and a sanitized `frame_url`; replays reidentify the frame before locating the control. Context-level network recording captures main pages and popups. A same-scope popup becomes the active page in the same isolated context, while an external popup is closed.

The current hybrid layer deliberately does not parse every HTML resource attribute. The independent Crawl Maze transfer result shows that `img`, CSS `url()`, meta refresh, header Link, and similar non-anchor references remain a major gap.

## Modular interaction engine

The extended profile supports:

- click and observed-href navigation;
- hover, focus, Enter, double-click, context menu, and bounded press-hold;
- checkbox/radio toggles and non-empty select options;
- viewport and scrollable-container scrolling;
- ordinary forms under the existing GET/explicit-POST policy;
- open shadow DOM, same-origin frames, popups/new tabs, and browser history/hash results.

Candidates require browser-visible evidence. Inline attributes, ARIA roles, standard form semantics, element geometry, and local component text are used. For listeners registered only through JavaScript, alternate gestures are proposed only when the local component describes that gesture and contains a plausible bounded target. The failed Iteration B demonstrated why whole-page keyword inference is unsafe: a results listing induced 235+ useless hover/focus actions. The retained rule scopes semantics to the nearest component and excludes ordinary navigable anchors from alternate gestures.

## Adaptive readiness

Readiness samples document state, busy/disabled controls, main-content actionability, control shape, and MutationObserver counts. A state is usable after bounded control/mutation stability; a passive page receives a configurable idle observation window. HTTP authentication/rate-limit responses are recorded as blocked. Navigation replacement during sampling is tolerated and recorded rather than treated as a stable page.

This is intentionally not `networkidle`, a fixed sleep, or whole-page hash equality. The transfer run nevertheless shows a cost problem on passive documents: 38 transitions used 181.5 seconds while consuming only 103 browser actions. Resource-type-aware readiness is the highest-value next foundation change.

## Persistent exploration and archive

Persistent discovery reuses a live state when the queued action is still present. Otherwise it restores the shortest archived prerequisite path from the configured root, resetting the context when session markers disagree. A per-state burst cap prevents a page with hundreds of locally plausible actions from monopolizing the run. Scroll actions are scheduled once per route/component, and repeated global navigation chrome is scheduled once per target/role/label shape.

Discovery reuse is never replay proof. Replay opens an independent browser context, performs the complete recorded path, and accounts for all navigation, input, and action costs.

## Coverage scheduler

The `multidimensional` policy scores new evidence in independent dimensions:

- observed target/route;
- control within a meaningful component;
- form field/method/action structure;
- interaction class;
- globally new control shape;
- prerequisite depth/restoration cost;
- known ineffective-action penalties;
- repeated global chrome and low-value report navigation penalties.

The policy is deterministic. It contains no expected Crawlground paths, marker identifiers, or application selectors. `breadth` remains an explicit shallow baseline, and the historical `coverage` policy remains available.

## Replay at scale

Replay scheduling deduplicates identical destination/group/interaction instances and prefers shorter paths. Control restoration first uses the recorded ID/signature, then a bounded role/label/component/target fallback against the current observation. Navigation replay requires the exact sanitized destination URL, route, normalized title, and usable interaction shape. Same-URL dynamic transitions still require content/outcome equivalence. This preserves wrong-record protection while tolerating cosmetic content changes on an exact navigated record.

The serious Crawlground replay rate improved from 15/33 to 25/38. Thirteen failures remain, and 211 observed paths were untested because the action budget was exhausted. Replay scheduling—not merely locator quality—is therefore still a dominant bottleneck.

## Compatibility audit

New configuration and schema fields have defaults, so old checkpoints validate. Existing action IDs and raw observations remain present. Graph A now exposes state URLs plus top-level interaction/component/frame fields while retaining full action descriptors inside `workflow_path`. The full test suite verifies old functional-search, content identity, origin, checkpoint, and budget behavior alongside the new frame/shadow/popup regression.
