"""Opt-in, bounded Chromium DevTools observer for runtime event listeners.

The DOM snapshot recognizes interactive elements by semantics: links, buttons,
ARIA roles, inline handler attributes. It cannot see a plain element that
received a listener through `addEventListener`, or a control whose handler was
replaced while its DOM stayed the same. Chromium's DevTools protocol can:
`DOMDebugger.getEventListeners` on the document with `depth: -1, pierce: true`
reports the listeners of every node in the document, including same-process
frames and shadow roots, each with the node's `backendNodeId` and the handler's
source location.

Rules this observer follows:
* Only *direct* click-family listeners make an element a candidate. A listener
  on the document, window, body/html, or a container that holds other controls,
  is reported as a possible delegation host and never attributed to a
  descendant.
* A listener is never authorization to act. Candidates become ordinary controls
  that pass the same safety filter, scope routing and action budget as every
  other control.
* Handler identity is the listener's (type, script, line, column) within one
  document lifetime, compared only between observations of the same document.
  Function bodies are never read or hashed.
* Work is bounded: at most `max_nodes` listener-bearing nodes are inspected
  (resolved and described over DevTools) per observation, at most
  `family_limit` candidates per handler location and `max_candidates` per
  observation. Everything skipped is counted by reason. Inspection is
  incremental within one document: a node whose handler identities did not
  change and that was already described is reused without another DevTools
  call, and nodes new or changed since the previous observation are inspected
  first, so the budget is spent where an action changed something.
* Change classification, within one document, against the previous
  observation: `created_after_action` (the element did not exist before),
  `listener_attached_after_action` (the element existed without a click-family
  listener), `listener_appeared_after_action` (history unknown: the element is
  inside a shadow root or a frame), `handler_changed` (the click-family
  listener set of the node changed: a handler revision), and `unchanged`.
  Before the first observation of a document everything is
  `present_at_first_observation`. Element history uses a weak set of the main
  document's elements held by the DevTools session itself (not a page global);
  it is never read by page code.

Chromium only. Firefox and WebKit do not expose this DevTools domain through
Playwright, so the observer reports itself as unsupported there.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .state import digest

CLICK_FAMILY = {
    "click": "click", "mousedown": "click", "mouseup": "click", "pointerdown": "click",
    "pointerup": "click", "dblclick": "double_click", "contextmenu": "context_menu",
}
DELEGATION_TAGS = {"#document", "html", "body", "main"}
OBJECT_GROUP = "engramsec-listeners"
ELEMENT_GROUP = "engramsec-elements"
# A weak set of the main document's current elements; held only by the
# DevTools object group, so page scripts cannot reach it.
ELEMENTS_EXPRESSION = "new WeakSet(document.querySelectorAll('*'))"
HAS_FN = "function(seen) { return seen.has(this); }"

DESCRIBE_FN = r"""
function(selector) {
  const el = this;
  if (!el || !el.tagName) return {tag: '#' + String((el && el.nodeName) || 'node').toLowerCase().replace(/^#/, '')};
  const win = el.ownerDocument.defaultView;
  const tag = el.tagName.toLowerCase();
  const style = win.getComputedStyle(el);
  const rect = el.getBoundingClientRect();
  let rendered = !(style.visibility === 'hidden' || style.display === 'none' || style.opacity === '0' ||
                   rect.width <= 0 || rect.height <= 0);
  const root = el.getRootNode();
  if (rendered) {
    const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
    if (cx >= 0 && cy >= 0 && cx < win.innerWidth && cy < win.innerHeight) {
      const top = (root.elementFromPoint ? root : el.ownerDocument).elementFromPoint(cx, cy);
      if (top && top !== el && !el.contains(top) && top !== root.host) rendered = false;
    }
  }
  const cssPath = (node) => {
    if (node.id) return '#' + CSS.escape(node.id);
    const parts = [];
    let current = node;
    while (current && current.nodeType === 1 && current !== current.ownerDocument.documentElement) {
      let part = current.tagName.toLowerCase();
      const parent = current.parentElement;
      const siblings = parent ? Array.from(parent.children).filter(x => x.tagName === current.tagName) : [];
      if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
      parts.unshift(part);
      current = parent;
    }
    return parts.join(' > ');
  };
  let node = el, shadow = 'none';
  const chain = [];
  while (true) {
    chain.unshift(cssPath(node));
    const r = node.getRootNode();
    if (r instanceof win.ShadowRoot) {
      if (r.mode === 'closed') shadow = 'closed'; else if (shadow === 'none') shadow = 'open';
      node = r.host;
    } else break;
  }
  const landmark = el.closest('nav,header,footer,aside,main,form,dialog,[role=menu],[role=navigation],[role=main],[role=dialog]');
  const host = landmark || (root.host || el.ownerDocument.body);
  const component = [(host?.tagName || 'document').toLowerCase(), host?.getAttribute?.('role') || '', host?.id || '']
    .filter(Boolean).join(':').slice(0, 160) || 'document';
  const label = (el.getAttribute('aria-label') || el.innerText || el.getAttribute('title') || el.textContent || '')
    .replace(/\s+/g, ' ').trim().slice(0, 160);
  return {
    tag, rendered, label, shadow, component,
    css_path: chain.join(' >> '),
    role: el.getAttribute('role') || '',
    snapshot_control: el.matches(selector),
    descendant_controls: el.querySelectorAll(selector).length,
    descendant_elements: el.querySelectorAll('*').length,
    area_fraction: (rect.width * rect.height) / Math.max(1, win.innerWidth * win.innerHeight),
    disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
    frame_href: win.location.href,
    class_hint: String(el.className || '').split(/\s+/).filter(Boolean).slice(0, 2).join('.'),
  };
}
"""


@dataclass
class ListenerSnapshot:
    supported: bool = True
    document_token: str = ""
    candidates: list[dict[str, Any]] = field(default_factory=list)
    represented: list[dict[str, Any]] = field(default_factory=list)  # listener nodes that are snapshot controls
    revisions: list[dict[str, Any]] = field(default_factory=list)
    current_revisions: dict[int, str] = field(default_factory=dict)  # backendNodeId -> latest revision token
    skipped: dict[str, int] = field(default_factory=dict)
    skipped_examples: list[dict[str, Any]] = field(default_factory=list)
    listener_nodes: int = 0
    described_nodes: int = 0
    reused_nodes: int = 0  # unchanged nodes whose cached description was reused
    changes: dict[str, int] = field(default_factory=dict)  # provenance -> listener-bearing nodes
    truncated: bool = False  # the per-observation inspection limit was reached
    delegation_hosts: int = 0
    window_click_listeners: int = 0
    elapsed_ms: float = 0.0
    cdp_calls: int = 0
    error: str | None = None


def _location(item: dict[str, Any], portable: bool) -> str:
    base = f"{item['type']}@{item.get('lineNumber')}:{item.get('columnNumber')}"
    return base if portable else f"{base}#{item.get('scriptId')}"


class ListenerObserver:
    """Per-browser-session observer; remembers the previous snapshot of each document."""

    def __init__(self, snapshot_selector: str, *, max_nodes: int = 300, max_candidates: int = 12,
                 family_limit: int = 2):
        self.selector = snapshot_selector
        self.max_nodes = max_nodes
        self.max_candidates = max_candidates
        self.family_limit = family_limit
        self._sessions: dict[int, Any] = {}
        self._document: str = ""
        self._previous: dict[int, tuple[str, ...]] = {}  # backendNodeId -> handler identities
        self._revisions: dict[int, str] = {}
        self._described: dict[int, dict[str, Any]] = {}
        self._elements: str | None = None  # objectId of the previous observation's element weak set
        self._element_generation = 0

    def _cdp(self, page: Any) -> Any:
        key = id(page)
        if key not in self._sessions:
            self._sessions[key] = page.context.new_cdp_session(page)
        return self._sessions[key]

    def observe(self, page: Any, caused_by: str | None) -> ListenerSnapshot:
        snapshot = ListenerSnapshot()
        browser = page.context.browser
        if browser is not None and browser.browser_type.name != "chromium":
            snapshot.supported = False
            snapshot.error = f"unsupported_engine:{browser.browser_type.name}"
            return snapshot
        started = time.monotonic()
        try:
            self._observe(page, caused_by, snapshot)
        except Exception as exc:  # DevTools errors never break exploration
            snapshot.error = f"{type(exc).__name__}: {str(exc)[:200]}"
            snapshot.candidates = []
        finally:
            snapshot.elapsed_ms = round((time.monotonic() - started) * 1000, 2)
        return snapshot

    def _send(self, cdp: Any, snapshot: ListenerSnapshot, method: str, params: dict[str, Any]) -> dict[str, Any]:
        snapshot.cdp_calls += 1
        return cdp.send(method, params)

    def _observe(self, page: Any, caused_by: str | None, snapshot: ListenerSnapshot) -> None:
        cdp = self._cdp(page)
        send = lambda method, params: self._send(cdp, snapshot, method, params)  # noqa: E731
        origin = send("Runtime.evaluate", {"expression": "performance.timeOrigin + '|' + location.href",
                                           "returnByValue": True})["result"].get("value", "")
        token = digest([id(page), origin], 16)
        same_document = token == self._document
        if not same_document:
            self._document, self._previous, self._revisions, self._described = token, {}, {}, {}
            self._elements = None
        snapshot.document_token = token
        send("DOM.getDocument", {"depth": 0})
        document = send("Runtime.evaluate", {"expression": "document", "objectGroup": OBJECT_GROUP})["result"]
        window = send("Runtime.evaluate", {"expression": "window", "objectGroup": OBJECT_GROUP})["result"]
        try:
            listeners = send("DOMDebugger.getEventListeners",
                             {"objectId": document["objectId"], "depth": -1, "pierce": True})["listeners"]
            snapshot.window_click_listeners = sum(
                item["type"] in CLICK_FAMILY for item in
                send("DOMDebugger.getEventListeners", {"objectId": window["objectId"]})["listeners"])
            by_node: dict[int, list[dict[str, Any]]] = {}
            other_nodes: set[int] = set()
            for item in listeners:
                node = item.get("backendNodeId")
                if node is None:
                    continue
                if item["type"] in CLICK_FAMILY:
                    by_node.setdefault(node, []).append(item)
                else:
                    other_nodes.add(node)
            snapshot.listener_nodes = len(by_node)
            if other_nodes - set(by_node):
                snapshot.skipped["non_click_listener_nodes"] = len(other_nodes - set(by_node))
            identities = {node: tuple(sorted(_location(item, False) for item in items)) for node, items in by_node.items()}

            def priority(node: int) -> int:
                if same_document and (node not in self._previous or self._previous[node] != identities[node]):
                    return 0  # new or changed since the previous observation
                if node in self._described:
                    return 1  # unchanged and already described: reused without DevTools calls
                return 2      # never inspected in this document
            order = sorted(by_node, key=priority)  # stable: document order within a priority
            families: dict[str, int] = {}
            for node in order:
                items = by_node[node]
                changed = same_document and node in self._previous and self._previous[node] != identities[node]
                new = same_document and node not in self._previous
                info = self._described.get(node)
                if info is None or changed or new or not info.get("rendered"):
                    if snapshot.described_nodes >= self.max_nodes:
                        snapshot.truncated = True
                        self._skip(snapshot, "node_budget", None)
                        continue
                    resolved = send("DOM.resolveNode", {"backendNodeId": node, "objectGroup": OBJECT_GROUP})["object"]
                    info = send("Runtime.callFunctionOn", {
                        "objectId": resolved["objectId"], "functionDeclaration": DESCRIBE_FN,
                        "arguments": [{"value": self.selector}], "returnByValue": True,
                    })["result"].get("value") or {"tag": "#unknown"}
                    if new:
                        info["existed_before"] = self._existed_before(send, resolved["objectId"], info, page)
                    self._described[node] = info
                    snapshot.described_nodes += 1
                else:
                    snapshot.reused_nodes += 1
                portable = sorted({_location(item, True) for item in items})
                interactions = sorted({CLICK_FAMILY[item["type"]] for item in items})
                if not same_document:
                    provenance = "present_at_first_observation"
                elif new:
                    provenance = {True: "listener_attached_after_action", False: "created_after_action"}.get(
                        info.get("existed_before"), "listener_appeared_after_action")
                else:
                    provenance = "handler_changed" if changed else "unchanged"
                snapshot.changes[provenance] = snapshot.changes.get(provenance, 0) + 1
                entry = {"backend_node_id": node, "tag": info.get("tag"), "label": info.get("label", ""),
                         "css_path": info.get("css_path", ""), "frame_href": info.get("frame_href", ""),
                         "role": info.get("role", ""), "component": info.get("component", "document"),
                         "interactions": interactions, "handler_locations": portable,
                         "listener_count": len(items),
                         "provenance": provenance}
                if changed:
                    revision = digest([info.get("css_path"), caused_by, portable], 16)
                    self._revisions[node] = revision
                    snapshot.revisions.append(entry | {
                        "revision": revision, "caused_by_action": caused_by,
                        "before": sorted({x.rsplit("#", 1)[0] for x in self._previous[node]}), "after": portable,
                        "snapshot_control": bool(info.get("snapshot_control")),
                    })
                if node in self._revisions:
                    entry["behavior_revision"] = self._revisions[node]
                    snapshot.current_revisions[node] = self._revisions[node]
                tag = info.get("tag", "")
                if tag in DELEGATION_TAGS or tag.startswith("#"):
                    snapshot.delegation_hosts += 1
                    self._skip(snapshot, "delegation_host", entry)
                elif info.get("snapshot_control"):
                    snapshot.represented.append(entry)
                    self._skip(snapshot, "represented_by_snapshot", None)
                elif info.get("descendant_controls", 0) > 0 or info.get("descendant_elements", 0) > 12 \
                        or info.get("area_fraction", 0) > 0.5:
                    snapshot.delegation_hosts += 1
                    self._skip(snapshot, "possible_delegation_host", entry)
                elif info.get("shadow") == "closed":
                    self._skip(snapshot, "closed_shadow_root", entry)
                elif not info.get("rendered"):
                    self._skip(snapshot, "not_rendered", entry)
                elif info.get("disabled"):
                    self._skip(snapshot, "disabled", entry)
                else:
                    family = digest([portable, tag, info.get("class_hint", "")], 12)
                    entry["family"] = family
                    families[family] = families.get(family, 0) + 1
                    if families[family] > self.family_limit:
                        self._skip(snapshot, "family_limit", None)
                    elif len(snapshot.candidates) >= self.max_candidates:
                        self._skip(snapshot, "candidate_limit", None)
                    else:
                        snapshot.candidates.append(entry)
            self._previous = identities
            self._remember_elements(send, page)
        finally:
            send("Runtime.releaseObjectGroup", {"objectGroup": OBJECT_GROUP})

    def _existed_before(self, send: Any, object_id: str, info: dict[str, Any], page: Any) -> bool | None:
        """Whether a node that just gained a click listener was already in the
        main document at the previous observation; None when that cannot be
        known (shadow tree, frame, or no previous element set)."""
        if self._elements is None or info.get("shadow") != "none" or info.get("frame_href") != page.url:
            return None
        try:
            return bool(send("Runtime.callFunctionOn", {
                "objectId": object_id, "functionDeclaration": HAS_FN,
                "arguments": [{"objectId": self._elements}], "returnByValue": True,
            })["result"].get("value"))
        except Exception:  # different execution context or a released set
            return None

    def _remember_elements(self, send: Any, page: Any) -> None:
        """Hold a weak set of the main document's elements for the next
        observation's created-vs-attached classification. One native call."""
        previous_group = f"{ELEMENT_GROUP}-{self._element_generation}"
        self._element_generation += 1
        try:
            result = send("Runtime.evaluate", {"expression": ELEMENTS_EXPRESSION,
                                               "objectGroup": f"{ELEMENT_GROUP}-{self._element_generation}"})["result"]
            self._elements = result.get("objectId")
        except Exception:
            self._elements = None
        try:
            send("Runtime.releaseObjectGroup", {"objectGroup": previous_group})
        except Exception:
            pass

    @staticmethod
    def _skip(snapshot: ListenerSnapshot, reason: str, entry: dict[str, Any] | None) -> None:
        snapshot.skipped[reason] = snapshot.skipped.get(reason, 0) + 1
        if entry is not None and len(snapshot.skipped_examples) < 8:
            snapshot.skipped_examples.append({"reason": reason, "tag": entry.get("tag"),
                                              "label": entry.get("label", "")[:80], "css_path": entry.get("css_path", "")[:200]})
