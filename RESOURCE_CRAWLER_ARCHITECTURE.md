# Resource-aware Agent 1 architecture

## Pipeline

Agent 1 now combines browser-observed interactions with a bounded typed resource spider. Browser control/action transitions remain the authority for observed UI behavior. The spider extracts references from actual same-scope response bodies and headers and contributes resource candidates/evidence to the same Graph A; a reference is not promoted to a browser transition or functional workflow.

The `agent1.resource_spider` module parses observed HTML attributes and elements, `<base>`, `srcset`, inline styles, CSS `url()`/`@import`, bounded literal script/module references, and HTTP `Location`, `Link`, and `Refresh`. It resolves against the response URL and effective base, rejects unsafe schemes/userinfo, strips fragments, canonicalizes and deduplicates, and classifies navigation, asset, and API candidates. It retains source element/header, source response, response status, and redacted reference provenance. The spider fetches only safe same-scope GET candidates; API candidates are recorded but not submitted. Redirect following is disabled to prevent scope escape. Unknown/oversized bodies are not buffered by the spider.

Target scope is explicit. Same-origin is the default, and a configured loopback alias is accepted only when present in the target's existing allowlist. Out-of-scope destinations remain visible as rejected references but are never fetched. A shared request/depth/byte budget separates typed HTTP fetches from browser actions.

## Readiness

Navigation readiness now has a short passive-resource phase and a bounded interactive observation phase. It records initialization/actionability samples, script presence, and delayed refresh hints. It does not require `networkidle` or equality of the entire page. This cuts passive waiting on fast resource-heavy Crawl Maze pages while allowing scripted pages a bounded period to expose controls. Per-action browser automation still relies on Playwright's built-in actionability checks and a bounded post-action observation window. Timeouts and delayed changes remain evidence, rather than silent permission to act.

## Restoration and replay

Path restoration returns the prerequisite action sequence and each step's observed network evidence. Those events are attached to prerequisite connections, so restoring a path no longer creates unexplained request events. Replay attempts are accounted separately from observed transitions and remain path-level. The default scheduler is shallow replay. The optional route/action/request/context diversity score was tested and did not help the observed workload; the Crawl Maze combined-diverse run had 29/30 replay success compared with 32/32 under shallow.

## Graph A compatibility and privacy

The existing Graph A observation/state/action/transition identities remain. New resource source-response and reference nodes link via evidence-bearing `references` edges. Prerequisite step evidence records action identity and request events. Older Graph A consumers can ignore the added node/edge types. The final audit had 2,198 complete evidence connections and no missing evidence connection. Credential-like query values are redacted before exported resource evidence; raw application response bodies and checkpoints remain in ignored local caches and should not be committed.

## Known limits

The spider uses bounded parsing of observed literal references; it is not a JavaScript interpreter or arbitrary endpoint crawler. It will miss computed URLs, service-worker behavior not represented in captured content, dynamically generated requests not triggered in the browser, and oversized/unknown-length content. Direct fetches are GET-only, same-scope, and not equivalent to UI navigation. Crawl Maze results show this limit: 100 spider fetches, but only 8 expected marker URLs fetched by the spider; the browser fetched 11 and the union was 16. Reaching more HTML/JS long-tail resources and reducing repeated root/restoration work are the next general problems.
