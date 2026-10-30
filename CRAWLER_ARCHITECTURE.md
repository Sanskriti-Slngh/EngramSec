# Agent 1 high-coverage crawler architecture

## Evidence contract

All discovery mechanisms feed the existing Graph A. A static reference is an advertised candidate; it becomes an observed transition only after Chromium follows it. Fresh-context replay remains separate from persistent-session discovery. Each action records its observed control, interaction type, component, frame, protected input references, source/result observations, request structures, prerequisite path, and replay status. State grouping remains reversible because raw observations and signatures are retained.

The final implementation changes no origin or dangerous-action boundary. Cross-origin destinations remain blocked unless an explicit loopback alias is configured. POST remains opt-in. Browser context values, request values, cookies, and storage values are not exported.

## Hybrid discovery

`hybrid_link_discovery` turns browser-observed same-scope `a`/`area` hrefs into lightweight `navigate` candidates. It does not guess endpoints. The browser still supplies the DOM, resolves URLs, enforces origin policy, and records the resulting document/Fetch/XHR evidence. JavaScript controls and state changes use browser interactions. Both mechanisms deduplicate into the same frontier and Graph A.

Open shadow roots and same-scope frames are observed recursively. Controls retain `frame_index` and a sanitized `frame_url`; replays reidentify the frame before locating the control. Context-level network recording captures main pages and popups. A same-scope popup becomes the active page in the same isolated context, while an external popup is closed.

Since the typed-spider integration, observed HTTP response bodies and headers are parsed independently of browser interaction. It covers ordinary HTML URL attributes and metadata, base resolution, `srcset`, inline/external CSS references, manifests/XML/robots sitemap references, header `Location`/`Link`/`Refresh`, and same-scope resources. Fetched responses recursively feed the same typed frontier. References remain advertised/fetched-resource evidence; they do not create a UI transition.

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

Readiness samples document state, busy/disabled controls, main-content actionability, control shape, script presence, and MutationObserver counts. Adaptive mode gives scripted screens without actionable controls an 800–1000 ms bounded hydration window, while retaining normal three-sample actionability checks and delayed-refresh floors. HTTP authentication/rate-limit responses are recorded as blocked. Navigation replacement during sampling is tolerated and recorded rather than treated as a stable page. Adaptive mode is opt-in pending a same-budget Crawlground recheck; it is tested on Crawl Maze and the independent JS lab.

This is intentionally not `networkidle`, a fixed sleep, or whole-page hash equality. The transfer run nevertheless shows a cost problem on passive documents: 38 transitions used 181.5 seconds while consuming only 103 browser actions. Resource-type-aware readiness is the highest-value next foundation change.

## Persistent exploration and archive

Persistent discovery reuses a live state when the queued action is still present. Otherwise it restores the shortest archived prerequisite path from the configured root, resetting the context when session markers disagree. A per-state burst cap prevents a page with hundreds of locally plausible actions from monopolizing the run. Scroll actions are scheduled once per route/component, and repeated global navigation chrome is scheduled once per target/role/label shape. A run-scoped typed-resource queue can be shared across fresh browser sessions so a context change does not discard pending response-derived candidates; an ablation found substantially more repeated class-budget records without sharing, but its one-run marker difference was inconclusive.

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

The policy is deterministic. It contains no expected Crawlground/Crawl Maze paths, marker identifiers, or application selectors. Resource frontier policies `fifo`, route diversity, empirical marginal reference yield, and seeded random selection are available. In a matched 180-second Crawl Maze comparison all four reached the same 21/91 marker set; FIFO remains the default. `breadth` remains an explicit shallow baseline, and the historical `coverage` policy remains available.

## Replay at scale

Replay scheduling deduplicates identical destination/group/interaction instances and prefers shorter paths. Control restoration first uses the recorded ID/signature, then a bounded role/label/component/target fallback against the current observation. Navigation replay requires the exact sanitized destination URL, route, normalized title, and usable interaction shape. Same-URL dynamic transitions still require content/outcome equivalence. This preserves wrong-record protection while tolerating cosmetic content changes on an exact navigated record.

The historical serious Crawlground replay rate improved from 15/33 to 25/38, with 211 observed paths untested; this milestone did not rerun its marker scorer. In Crawl Maze, the adaptive-readiness 180-second runs validated all 24 attempted paths but left 79–80 transitions untested. A diverse replay ablation covered more marker destinations in successful replays (5–6 versus 1–2), but one repeat had a replay failure and did not reduce the untested count. Replay scheduling remains a bottleneck, and replay status stays attached to path instances.

## Compatibility audit

New configuration and schema fields have defaults, so old checkpoints validate. Existing action IDs and raw observations remain present. Graph A now exposes state URLs plus top-level interaction/component/frame fields while retaining full action descriptors inside `workflow_path`. The full test suite verifies old functional-search, content identity, origin, checkpoint, and budget behavior alongside the new frame/shadow/popup regression.

## Measured update — 2026-10-30

The typed parser now uses Tree-sitter's JavaScript grammar on scripts actually delivered by same-scope responses. It folds only bounded immutable string literals and concatenations, extracts static imports, fetch/Request/XHR/navigation/resource-loading references, and records computed expressions as unresolved evidence without executing or inventing a URL. The parser-only Crawl Maze ablation tied the legacy extractor at 21/91; its value is structural robustness, not a measured score gain on this corpus. A depth-6 run increased reference records but fell to 17/91, so depth 3 remains the tested default.

At matched 180-second budgets, adaptive readiness reached 25/91 versus a 20–21/91 fixed-readiness range over three fixed runs. It cut interactive readiness waiting from about 62 seconds to 32–34 seconds, while producing more transitions and leaving more untested paths. A 300-second adaptive run reached 37/91; see `COVERAGE_ABLATIONS.md` for the complete funnel, uncertainty, and budgets.

Relevant design references: [ZAP Traditional Spider](https://www.zaproxy.org/docs/desktop/addons/spider/), [ZAP Spider quick start](https://www.zaproxy.org/docs/desktop/addons/quick-start/), [Tree-sitter documentation](https://tree-sitter.github.io/tree-sitter/), and the [JavaScript grammar](https://github.com/tree-sitter/tree-sitter-javascript).
