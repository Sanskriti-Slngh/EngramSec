"""Framework-aware canvas introspection and safe driving (read-mostly).

A DOM-snapshot crawler cannot see the functionality of a `<canvas>` node-graph app (e.g. ComfyUI): its
nodes and operations live in a JS model, not the DOM, so Agent 1 maps 0 workflows there. Blind
coordinate-based clicking on a canvas is unreliable AND unsafe (it can trigger arbitrary, possibly
destructive actions), so it is deliberately NOT done here.

Two capabilities, both reading the app's own model through JS:

1. **Introspection** (`introspect_canvas_graph`) — detect the graph framework and extract its model.
   Supports LiteGraph (ComfyUI), Cytoscape.js, vis.js Network, React Flow (DOM nodes), plus a generic
   sweep of `window` for graph-shaped objects (`._nodes` / `.nodes` / `.getNodes()` /
   `.model.nodeDataArray`). Reports which frameworks are present even when a model is not reachable.

2. **Driving** (`drive_node_schemas`, `demonstrate_drive`) — for a LiteGraph app, instantiate each
   registered node type and read its live I/O schema (typed input/output ports + widgets with defaults),
   and prove the graph is drivable by adding then removing a node. This is client-side only: it never
   executes the graph (no `queuePrompt`) and never reaches the server, and it restores the graph to its
   prior state. It turns "543 node types exist" into "543 node types with their full I/O contracts".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ----------------------------------------------------------------------------- introspection

_INTROSPECT_JS = r"""
() => {
  const W = window, D = document;
  const SIG = {
    litegraph: () => !!W.LiteGraph,
    cytoscape: () => !!(W.cytoscape || (W.cy && typeof W.cy.nodes === 'function')),
    gojs: () => !!(W.go && W.go.Diagram),
    jointjs: () => !!(W.joint && W.joint.dia),
    visjs: () => !!((W.vis && (W.vis.Network || W.vis.DataSet)) || (W.network && W.network.body)),
    rete: () => !!(W.Rete || W.rete),
    reactflow: () => !!D.querySelector('.react-flow, .react-flow__renderer, [data-testid="rf__wrapper"]'),
    mxgraph: () => !!(W.mxGraph || W.mxClient),
    konva: () => !!W.Konva,
    fabric: () => !!W.fabric,
  };
  const detected = [];
  for (const [k, f] of Object.entries(SIG)) { try { if (f()) detected.push(k); } catch (e) {} }

  const cap = a => (a || []).slice(0, 2000);
  const norm = (framework, nodes, edges, catalog) => ({
    framework, node_count: nodes.length, nodes: cap(nodes), edges: cap(edges || []),
    registered_node_types: catalog || [], node_type_count: (catalog || []).length,
  });

  // --- LiteGraph (ComfyUI and others) ---
  try {
    if (W.LiteGraph && W.LiteGraph.registered_node_types) {
      const LG = W.LiteGraph;
      const graph = (W.app && W.app.graph) || W.graph ||
        (W.LGraphCanvas && W.LGraphCanvas.active_canvas && W.LGraphCanvas.active_canvas.graph) || null;
      const nodes = (graph && Array.isArray(graph._nodes)) ? graph._nodes.map(n => ({
        id: n.id, type: n.type || null, label: n.title || null,
        pos: Array.isArray(n.pos) ? n.pos : null,
        widgets: (n.widgets || []).slice(0, 20).map(w => ({ name: w && w.name, value: w && w.value })),
      })) : [];
      const edges = (graph && Array.isArray(graph.links) ? Object.values(graph.links) :
        (graph && graph.links ? Object.values(graph.links) : [])).filter(Boolean).map(l => ({
        from: l.origin_id, to: l.target_id })).slice(0, 2000);
      return { frameworks_detected: detected,
        ...norm('litegraph', nodes, edges, Object.keys(LG.registered_node_types)) };
    }
  } catch (e) {}

  // --- Cytoscape.js ---
  try {
    const cy = (W.cy && typeof W.cy.nodes === 'function') ? W.cy : null;
    if (cy) {
      const nodes = cy.nodes().map(n => ({ id: n.id(),
        label: n.data('label') || n.data('name') || n.id(), type: n.data('type') || null }));
      const edges = cy.edges().map(e => ({ from: e.data('source'), to: e.data('target') }));
      return { frameworks_detected: detected, ...norm('cytoscape', nodes, edges, null) };
    }
  } catch (e) {}

  // --- vis.js Network ---
  try {
    const net = (W.network && W.network.body) ? W.network : null;
    if (net && net.body && net.body.data && net.body.data.nodes) {
      const nodes = net.body.data.nodes.get().map(n => ({ id: n.id, label: n.label || null, type: n.group || null }));
      const edges = (net.body.data.edges ? net.body.data.edges.get() : []).map(e => ({ from: e.from, to: e.to }));
      return { frameworks_detected: detected, ...norm('visjs', nodes, edges, null) };
    }
  } catch (e) {}

  // --- React Flow (nodes are real DOM elements, not canvas) ---
  try {
    const els = D.querySelectorAll('.react-flow__node');
    if (els.length) {
      const nodes = Array.from(els).map(el => ({ id: el.getAttribute('data-id'),
        label: (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 80),
        type: el.getAttribute('data-nodetype') || (el.className.match(/react-flow__node-(\w+)/) || [])[1] || null }));
      const edges = Array.from(D.querySelectorAll('.react-flow__edge')).map(e => ({
        from: e.getAttribute('data-source') || null, to: e.getAttribute('data-target') || null }));
      return { frameworks_detected: detected, ...norm('reactflow', nodes, edges, null) };
    }
  } catch (e) {}

  // --- Generic sweep: an editor/graph instance stored on a global ---
  const nodesFrom = (o) => {
    try {
      if (!o || typeof o !== 'object') return null;
      if (Array.isArray(o._nodes)) return o._nodes;
      if (Array.isArray(o.nodes)) return o.nodes;
      if (typeof o.getNodes === 'function') { const r = o.getNodes(); if (Array.isArray(r)) return r; }
      if (o.model && Array.isArray(o.model.nodeDataArray)) return o.model.nodeDataArray;
      if (o.graph && Array.isArray(o.graph._nodes)) return o.graph._nodes;
    } catch (e) {}
    return null;
  };
  try {
    for (const key of Object.keys(W)) {
      let v; try { v = W[key]; } catch (e) { continue; }
      const ns = nodesFrom(v);
      if (ns && ns.length) {
        const nodes = ns.slice(0, 2000).map((n, i) => ({ id: n.id != null ? n.id : i,
          label: n.title || n.label || n.name || (n.data && (n.data.label || n.data.name)) || null,
          type: n.type || (n.data && n.data.type) || n.category || null }));
        return { frameworks_detected: detected, ...norm('generic:' + key, nodes, [], null) };
      }
    }
  } catch (e) {}

  if (detected.length || D.querySelectorAll('canvas').length) {
    return { frameworks_detected: detected, framework: null, node_count: 0, nodes: [], edges: [],
      registered_node_types: [], node_type_count: 0, model_reachable: false };
  }
  return null;
}
"""


@dataclass
class CanvasInventory:
    framework: str | None
    frameworks_detected: list[str] = field(default_factory=list)
    node_count: int = 0
    node_type_count: int = 0
    registered_node_types: list[str] = field(default_factory=list)
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    model_reachable: bool = True

    @property
    def is_introspectable(self) -> bool:
        return self.framework is not None or bool(self.nodes) or self.node_type_count > 0


def introspect_canvas_graph(page: Any) -> CanvasInventory | None:
    """Introspect a canvas node-graph app's model from an already-loaded Playwright `page`.

    Returns a CanvasInventory (framework, operation catalog, placed nodes + edges) or None if the page
    has no canvas and no detectable graph framework. Read-only; does not interact with the canvas.
    """
    raw = page.evaluate(_INTROSPECT_JS)
    if not raw:
        return None
    return CanvasInventory(
        framework=raw.get("framework"),
        frameworks_detected=list(raw.get("frameworks_detected", [])),
        node_count=int(raw.get("node_count", 0)),
        node_type_count=int(raw.get("node_type_count", 0)),
        registered_node_types=list(raw.get("registered_node_types", [])),
        nodes=list(raw.get("nodes", [])),
        edges=list(raw.get("edges", [])),
        model_reachable=bool(raw.get("model_reachable", True)),
    )


# ----------------------------------------------------------------------------- driving (LiteGraph)

_DRIVE_SCHEMAS_JS = r"""
(args) => {
  const LG = window.LiteGraph;
  if (!LG || !LG.registered_node_types) return { error: 'no litegraph' };
  const all = Object.keys(LG.registered_node_types);
  const types = (args.types && args.types.length) ? args.types : all.slice(0, args.limit);
  const schemas = [];
  for (const t of types) {
    try {
      const n = LG.createNode(t);               // instantiate only; never added to the executing graph
      if (!n) { schemas.push({ type: t, created: false }); continue; }
      schemas.push({ type: t, created: true, title: n.title || t,
        inputs: (n.inputs || []).map(i => ({ name: i.name, type: i.type })),
        outputs: (n.outputs || []).map(o => ({ name: o.name, type: o.type })),
        widgets: (n.widgets || []).map(w => ({ name: w.name, type: w.type, value: w.value })) });
    } catch (e) { schemas.push({ type: t, error: String(e).slice(0, 160) }); }
  }
  return { schemas, catalog_size: all.length };
}
"""

_DRIVE_DEMO_JS = r"""
(nodeType) => {
  const LG = window.LiteGraph;
  const graph = (window.app && window.app.graph) || window.graph;
  if (!LG || !graph || !Array.isArray(graph._nodes)) return { error: 'no graph' };
  const before = graph._nodes.length;
  const node = LG.createNode(nodeType);
  if (!node) return { error: 'could not create ' + nodeType };
  node.pos = [100, 100];
  graph.add(node);
  const after_add = graph._nodes.length;
  const live = { title: node.title,
    widgets: (node.widgets || []).map(w => ({ name: w.name, value: w.value })) };
  graph.remove(node);                           // restore the graph to its prior state
  const after_remove = graph._nodes.length;
  return { node_type: nodeType, before, after_add, after_remove,
    added_ok: after_add === before + 1, removed_ok: after_remove === before, live };
}
"""


@dataclass
class NodeSchema:
    type: str
    created: bool
    title: str | None = None
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    widgets: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def drive_node_schemas(page: Any, *, types: list[str] | None = None, limit: int = 50) -> list[NodeSchema]:
    """Instantiate LiteGraph node types and read each one's live I/O schema (typed input/output ports and
    widgets with defaults). Client-side only: nodes are created in memory, never executed, never sent to
    the server. Deepens the catalog into full per-node I/O contracts."""
    raw = page.evaluate(_DRIVE_SCHEMAS_JS, {"types": types or [], "limit": limit})
    if not raw or raw.get("error"):
        return []
    return [NodeSchema(
        type=s.get("type"), created=bool(s.get("created")), title=s.get("title"),
        inputs=list(s.get("inputs", [])), outputs=list(s.get("outputs", [])),
        widgets=list(s.get("widgets", [])), error=s.get("error"),
    ) for s in raw.get("schemas", [])]


def demonstrate_drive(page: Any, node_type: str = "Note") -> dict[str, Any] | None:
    """Prove the graph is drivable: add a node of `node_type`, read its live state, then remove it
    (restoring the graph). Client-side only; never executes the graph. Returns the add/remove evidence."""
    raw = page.evaluate(_DRIVE_DEMO_JS, node_type)
    if not raw or raw.get("error"):
        return None
    return raw


# ----------------------------------------------------------------------------- convenience

def probe_url(url: str, *, wait_ms: int = 16000, ignore_https_errors: bool = False) -> CanvasInventory | None:
    """Launch a browser, load `url`, wait for the app to build, and introspect its canvas. Returns a
    CanvasInventory or None if no canvas app. For driving, use `on_page` to also read node schemas."""
    return _with_page(url, wait_ms, ignore_https_errors, lambda page: introspect_canvas_graph(page))


def on_page(url: str, fn: Any, *, wait_ms: int = 16000, ignore_https_errors: bool = False) -> Any:
    """Launch a browser, load `url`, wait, and run `fn(page)` — for combining introspection with
    `drive_node_schemas` / `demonstrate_drive` against the same loaded page."""
    return _with_page(url, wait_ms, ignore_https_errors, fn)


def _with_page(url: str, wait_ms: int, ignore_https_errors: bool, fn: Any) -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(ignore_https_errors=ignore_https_errors)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            return fn(page)
        finally:
            browser.close()
