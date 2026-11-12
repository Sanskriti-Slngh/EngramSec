"""Framework-aware canvas introspection (read-only).

A DOM-snapshot crawler cannot see the functionality of a `<canvas>` node-graph app (e.g. ComfyUI): its
nodes and operations live in a JS model, not the DOM, so Agent 1 maps 0 workflows there. Blind
coordinate-based clicking on the canvas is unreliable AND unsafe (it can trigger arbitrary, possibly
destructive, actions), so it is deliberately NOT done here.

The tractable, safe path is to read the app's **own graph model** through its JS globals. Many node-graph
apps are built on LiteGraph (ComfyUI, many others), which exposes:
  * `window.LiteGraph.registered_node_types` — the full catalog of operations the app offers (its
    capability set); for ComfyUI this is ~543 node types (KSampler, CLIPTextEncode, VAEDecode, …);
  * `app.graph._nodes` / `window.graph._nodes` — the nodes currently placed, with their widgets/values.

This yields a real functionality inventory for a canvas app with no interaction and no risk. It is
framework-specific by nature (currently LiteGraph); for a canvas with no introspectable model it returns
None, which is reported honestly rather than guessed at. Driving the graph (adding/wiring nodes) remains a
separate, larger capability; enumerating it is the high-value, safe first step.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Read-only: reads JS globals, never mutates the graph or clicks the canvas.
_INTROSPECT_JS = r"""
() => {
  const canvases = document.querySelectorAll('canvas');
  if (!canvases.length) return null;
  const out = {canvas_count: canvases.length, framework: null,
               node_type_count: 0, registered_node_types: [], current_nodes: []};
  const LG = window.LiteGraph;
  if (LG && LG.registered_node_types) {
    out.framework = 'litegraph';
    const keys = Object.keys(LG.registered_node_types);
    out.node_type_count = keys.length;
    out.registered_node_types = keys;
  }
  const app = window.app;
  const graph = (app && app.graph) || window.graph ||
    (window.LGraphCanvas && window.LGraphCanvas.active_canvas && window.LGraphCanvas.active_canvas.graph) || null;
  if (graph && Array.isArray(graph._nodes)) {
    out.current_nodes = graph._nodes.slice(0, 500).map(n => ({
      type: n.type || null, title: n.title || null,
      pos: Array.isArray(n.pos) ? n.pos : null,
      widgets: (n.widgets || []).slice(0, 20).map(w => ({name: w && w.name, value: w && w.value}))
    }));
  }
  return (out.framework || out.current_nodes.length) ? out : null;
}
"""


@dataclass
class CanvasInventory:
    framework: str | None
    canvas_count: int
    node_type_count: int
    registered_node_types: list[str] = field(default_factory=list)
    current_nodes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_introspectable(self) -> bool:
        return self.framework is not None or bool(self.current_nodes)


def introspect_canvas_graph(page: Any) -> CanvasInventory | None:
    """Introspect a canvas node-graph app's model from an already-loaded Playwright `page`.

    Returns a CanvasInventory (the operation catalog + any placed nodes) or None if the page has no
    canvas with an introspectable graph model. Read-only; does not interact with the canvas.
    """
    raw = page.evaluate(_INTROSPECT_JS)
    if not raw:
        return None
    return CanvasInventory(
        framework=raw.get("framework"),
        canvas_count=int(raw.get("canvas_count", 0)),
        node_type_count=int(raw.get("node_type_count", 0)),
        registered_node_types=list(raw.get("registered_node_types", [])),
        current_nodes=list(raw.get("current_nodes", [])),
    )


def probe_url(url: str, *, wait_ms: int = 16000, ignore_https_errors: bool = False) -> CanvasInventory | None:
    """Convenience: launch a browser, load `url`, wait for the app to build, and introspect its canvas."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(ignore_https_errors=ignore_https_errors)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            return introspect_canvas_graph(page)
        finally:
            browser.close()
