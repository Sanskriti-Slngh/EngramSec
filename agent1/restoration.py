"""Experimental state-tolerant restoration: the action starting-state contract.

Opt-in (``RunConfig.restoration_policy = "contract"``). The default ``"strict"``
policy is unchanged: a restored page must reproduce the saved state group.

When the strict group check fails, the contract asks a narrower question: can the
pending action's *starting conditions* be established in the page actually
restored? It never asserts that the two application states are equivalent.

The contract accepts only if every check below holds:

1. Same exact URL (origin, route, path instance and query values), so URL-borne
   record identity is preserved, and the same session context and markers.
2. Same form schemas (method, exact action URL, field names/types/required).
3. Exactly one current, safe, enabled target control, identical to the recorded
   one in kind, role, interaction, label, exact target, method, fields,
   component, frame, DOM position, inline handler, listener handler locations
   and behavior revision; no new same-label or same-signature ambiguity.
4. The same set of affordances (all controls, safe or not). A control missing
   from the restored snapshot counts as present only when a direct DOM probe
   finds it at its recorded position with the same label and target (snapshot
   occlusion artefact); a control that appears or disappears only while the
   page is passively re-observed counts as volatile display.
5. Unchanged text in the target's functional container (form, row, list item,
   article, section, ...), in page-identity regions (title, h1-h3, breadcrumb,
   aria-current, hidden input values) and in status regions (alert, status,
   aria-live, outcome classes).
6. For *contextual* actions (buttons, script handlers, listener-derived or
   form controls) every other text difference must be passively volatile: it
   changes on its own across repeated passive observations of the restored
   page. For *declarative* actions (a same-origin GET link with no inline or
   observed handler, whose request is fully specified by its exact target)
   stable differences outside the scopes in 5 are tolerated and recorded as
   ``outside_scope``.

Anything that cannot be localized (shadow DOM, frames) or that lacks prior
evidence is refused. Return-path write safety is enforced before the contract is
reached and is not relaxed by it.
"""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .state import (VOLATILE_CONTROL, allowed_origin, compact_text, digest, normalize_instance_text, route_pattern,
                    sanitize_url)


class RestorationRefused(RuntimeError):
    """The restored page did not establish the pending action's starting contract."""


CONTAINER_SELECTOR = (
    "form,fieldset,tr,li,article,section,aside,dialog,details,[role=dialog],[role=region],[role=group],"
    "[role=row],[role=listitem],[role=tabpanel],[role=article],[data-component]"
)

# Collected once per observation (contract policy only) and per passive sample.
REGION_SCRIPT = r"""
(args) => {
  const CONTAINER = %s;
  const IDENTITY = 'h1,h2,h3,[aria-current]:not([aria-current=false]),.breadcrumb,[aria-label*="breadcrumb" i]';
  const STATUS = '[data-outcome],[role=alert],[role=status],[aria-live]:not([aria-live=off]),.alert,.notice,.message,.error,.success';
  const CONTROL = 'a[href],button,input[type=submit],input[type=button],input[type=image],[role=button],[role=link],[role=tab],[role=menuitem],summary';
  const pathOf = (el) => {
    const parts = [];
    for (let n = el; n && n.nodeType === 1 && n !== document.documentElement; n = n.parentElement) {
      let i = 1;
      for (let s = n.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === n.tagName) i++;
      parts.push(n.tagName.toLowerCase() + ':' + i);
    }
    return parts.reverse().join('/');
  };
  const shown = (el) => {
    const s = window.getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0' && r.width > 0 && r.height > 0;
  };
  const clean = (v) => String(v || '').replace(/\s+/g, ' ').trim().slice(0, 160);
  const labels = (el) => [el.getAttribute('aria-label'), el.labels ? Array.from(el.labels).map(x => x.innerText).join(' ') : '',
                          el.innerText, el.value, el.getAttribute('title'), el.getAttribute('placeholder'),
                          el.id ? el.id.replace(/[-_]+/g, ' ') : ''].map(clean).filter(Boolean);
  const containerOf = (el) => { const c = el.closest(CONTAINER); return c ? pathOf(c) : ''; };
  const regions = {};
  const add = (key, el, text, identity) => {
    let r = regions[key];
    if (!r) r = regions[key] = {text: '', container: containerOf(el), identity: identity || !!el.closest(IDENTITY),
                                status: !!el.closest(STATUS)};
    r.text = r.text ? r.text + ' ' + text : text;
  };
  const root = document.body || document.documentElement;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const el = node.parentElement;
    if (!el || el.closest('script,style,noscript,template')) continue;
    const text = (node.nodeValue || '').replace(/\s+/g, ' ').trim();
    if (!text || !shown(el)) continue;
    add(pathOf(el), el, text, false);
  }
  for (const el of document.querySelectorAll('input,select,textarea')) {
    const type = (el.getAttribute('type') || el.tagName).toLowerCase();
    if (type === 'password' || type === 'file') continue;
    if (type !== 'hidden' && !shown(el)) continue;
    add(pathOf(el) + '#value', el, clean(el.value) || '(empty)', type === 'hidden');
  }
  const controls = [];
  for (const el of document.querySelectorAll(CONTROL)) {
    if (!shown(el)) continue;
    controls.push([labels(el)[0] || '', el.href ? String(el.href.baseVal || el.href) : '']);
  }
  // What is on top at the element's first line box: itself, an ancestor (e.g. the cell around a
  // wrapped link, which the snapshot's occlusion test misreads), or an unrelated element (an overlay).
  const hitOf = (el) => {
    const box = el.getClientRects()[0] || el.getBoundingClientRect();
    const x = box.left + Math.min(box.width / 2, 4), y = box.top + box.height / 2;
    if (x < 0 || y < 0 || x >= window.innerWidth || y >= window.innerHeight) return 'offscreen';
    const top = document.elementFromPoint(x, y);
    if (!top || top === el || el.contains(top)) return 'self';
    return top.contains(el) ? 'ancestor' : 'other';
  };
  const probe = {};
  for (const sel of (args && args.probe) || []) {
    let el = null;
    try { el = document.querySelector(sel); } catch (e) { el = null; }
    probe[sel] = el ? {shown: shown(el), hit: hitOf(el), labels: labels(el), href: el.href ? String(el.href.baseVal || el.href) : '',
                       handler: el.getAttribute('onclick') || '', container: containerOf(el),
                       disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true'} : null;
  }
  return {title: clean(document.title), regions, controls, probe,
          shadow_roots: Array.from(document.querySelectorAll('*')).filter(el => el.shadowRoot).length};
}
""" % repr(CONTAINER_SELECTOR)


def condense(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep text digests, not text: region evidence is compared, never exported."""
    regions = {key: (digest(value["text"], 12), value["container"], bool(value["identity"]), bool(value["status"]))
               for key, value in (raw.get("regions") or {}).items()}
    regions["__title__"] = (digest(raw.get("title", ""), 12), "", True, False)
    probe = {}
    for sel, value in (raw.get("probe") or {}).items():
        if value is None:
            probe[sel] = None
            continue
        probe[sel] = dict(value, href=sanitize_url(value["href"]) if value.get("href", "").startswith("http") else "",
                          handler=digest(value.get("handler") or "", 12) if value.get("handler") else "")
    controls = Counter((compact_text(label, 160), sanitize_url(href) if href.startswith("http") else "")
                       for label, href in raw.get("controls") or [])
    return {"regions": regions, "controls": controls, "probe": probe,
            "shadow_roots": int(raw.get("shadow_roots") or 0)}


@dataclass
class Decision:
    accepted: bool
    tier: str
    reasons: list[str] = field(default_factory=list)
    tolerated: dict[str, int] = field(default_factory=dict)
    needs_samples: bool = False
    samples: int = 0

    def record(self) -> dict[str, Any]:
        return {"accepted": self.accepted, "tier": self.tier, "reasons": sorted(set(self.reasons)),
                "tolerated": dict(self.tolerated), "samples": self.samples}


# Reasons that repeated passive observation may still explain.
_VOLATILITY_ELIGIBLE = {"content_changed", "page_identity_changed", "status_changed", "affordance_added",
                        "affordance_removed"}


def _akey(control: Any) -> tuple:
    """Functional identity of one control, with its exact target (not its route shape)."""
    return (control.kind, control.role, control.interaction, normalize_instance_text(control.label),
            control.target or "", (control.method or "").upper(),
            tuple((f.name, f.input_type, f.required) for f in control.fields),
            control.component, control.frame_index, control.safe, control.provenance,
            control.behavior_revision)


def _ckey(control: Any) -> tuple[str, str]:
    return (compact_text(control.label, 160), control.target or "")


def _forms(observation: Any) -> list[tuple]:
    return [(form.method, form.action, [(f.name, f.input_type, f.required) for f in form.fields])
            for form in observation.forms]


def _label_matches(control: Any, probe: dict[str, Any] | None) -> bool:
    if not probe or not probe.get("shown") or probe.get("disabled") or probe.get("hit") == "other":
        return False
    if compact_text(control.label, 160) not in probe.get("labels", []) and not control.label.startswith("unnamed "):
        return False
    if control.kind != "link":
        return not probe.get("href")
    return (control.target or "") == (probe.get("href") or "")


def _in_scope(key: str, container: str) -> bool:
    return bool(container) and (key == container or key.startswith(container + "/")
                                or key.startswith(container + "#"))


def declarative(control: Any, start_url: str, aliases: list[str], probe: dict[str, Any] | None) -> bool:
    """A same-origin GET link whose request is fully specified by its exact target."""
    return (control.kind == "link" and bool(control.target) and control.target.startswith(("http://", "https://"))
            and allowed_origin(start_url, control.target, aliases) and control.provenance == "snapshot"
            and not control.behavior_revision and control.interaction in {"click", "navigate"}
            and not (control.listener_evidence or {}).get("handler_locations")
            and not (probe or {}).get("handler"))


def evaluate(expected: Any, actual: Any, action: Any, current: Any, prior: dict[str, Any] | None,
             samples: list[dict[str, Any]], start_url: str, aliases: list[str] | None = None) -> Decision:
    """Decide whether ``actual`` establishes the starting contract of ``action`` recorded in ``expected``.

    ``prior`` is the condensed region capture of ``expected``; ``samples`` are condensed passive captures of
    the restored page (the first taken immediately, later ones after a short wait), each probing the recorded
    control positions.
    """
    aliases = aliases or []
    reasons: list[str] = []
    tolerated: Counter = Counter()
    recorded = next((c for c in expected.controls if c.id == action.control_id), None) or next(
        (c for c in expected.controls if c.css_path == action.css_path and c.signature == action.signature), None)
    first = samples[0] if samples else None
    target_probe = (first or {}).get("probe", {}).get(action.css_path) if first else None
    prior_probe = (prior or {}).get("probe", {}).get(action.css_path) if prior else None
    tier = "declarative" if (current is not None and declarative(current, start_url, aliases, target_probe)
                             and declarative(recorded or current, start_url, aliases, prior_probe)) else "contextual"

    def done(accepted: bool, needs: bool = False) -> Decision:
        return Decision(accepted, tier, sorted(set(reasons)), dict(tolerated), needs, len(samples))

    # 1-2: location, record, session, forms
    if expected.url != actual.url:
        reasons.append("route_changed" if route_pattern(expected.url) != route_pattern(actual.url)
                       else "record_identity_changed")
    if expected.session_context != actual.session_context or expected.session_markers != actual.session_markers:
        reasons.append("session_changed")
    if _forms(expected) != _forms(actual):
        reasons.append("form_schema_changed")
    frames = (expected.instance_facts.get("frame_count", 1), actual.instance_facts.get("frame_count", 1))
    if max(frames) > 1:
        reasons.append("multi_frame_state_unsupported")
    if prior is None or not samples:
        reasons.append("no_region_evidence")
    if reasons:
        return done(False)

    # 3: target control
    if current is None:
        reasons.append("target_disabled" if (target_probe or {}).get("disabled") else "target_absent")
    elif recorded is None:
        reasons.append("target_not_in_recorded_state")
    else:
        if _akey(current) != _akey(recorded):
            reasons.append("target_changed")
        if current.css_path != recorded.css_path:
            reasons.append("target_moved")
        if current.frame_index:
            reasons.append("frame_target_unsupported")
        handlers = lambda c: sorted(map(str, (c.listener_evidence or {}).get("handler_locations") or []))
        if handlers(current) != handlers(recorded) or (target_probe or {}).get("handler", "") != (prior_probe or {}).get(
                "handler", ""):
            reasons.append("handler_changed")
        # Controls the matcher could confuse with the target: same signature, or same role and label.
        confusable = lambda obs: Counter(_akey(c) for c in obs.controls if c.safe
                                         and c.interaction == current.interaction
                                         and (c.signature == current.signature
                                              or (c.role == current.role and normalize_instance_text(c.label)
                                                  == normalize_instance_text(current.label))))
        exp_conf, act_conf = confusable(expected), confusable(actual)
        if (act_conf - exp_conf) or act_conf[_akey(current)] != exp_conf[_akey(recorded)]:
            reasons.append("target_ambiguous")
    if reasons:
        return done(False)

    # passive volatility across restored samples
    def keys(sample: dict[str, Any]) -> dict[str, tuple]:
        return sample["regions"]

    volatile_regions: set[str] = set()
    for key in set().union(*(keys(s) for s in samples)):
        values = {keys(s).get(key, (None,))[0] for s in samples}
        if len(values) > 1:
            volatile_regions.add(key)
    volatile_controls: set[tuple[str, str]] = set()
    for ck in set().union(*(s["controls"] for s in samples)):
        if len({s["controls"].get(ck, 0) for s in samples}) > 1:
            volatile_controls.add(ck)
    # Functional containers whose own text changes on its own (a carousel, a live feed).
    volatile_containers = {meta[1] for s in samples for key, meta in keys(s).items()
                           if key in volatile_regions and meta[1]}

    def volatile_control(control: Any, probe: dict[str, Any] | None) -> bool:
        return _ckey(control) in volatile_controls or ((probe or {}).get("container") or "") in volatile_containers

    # 4: affordances (every control, safe or not; listener-derived included)
    exp_aff = Counter(_akey(c) for c in expected.controls if not VOLATILE_CONTROL.match(c.label))
    act_aff = Counter(_akey(c) for c in actual.controls if not VOLATILE_CONTROL.match(c.label))
    for key, count in (exp_aff - act_aff).items():
        missing = [c for c in expected.controls if _akey(c) == key]
        present = sum(1 for c in missing if c.provenance == "snapshot"
                      and _label_matches(c, (first or {}).get("probe", {}).get(c.css_path)))
        unexplained = count - min(count, present)
        if present:
            tolerated["affordance_present_in_dom"] += min(count, present)
        for c in missing[:unexplained]:
            if volatile_control(c, prior["probe"].get(c.css_path)):
                tolerated["affordance_volatile"] += 1
            else:
                reasons.append("affordance_removed")
    for key, count in (act_aff - exp_aff).items():
        added = [c for c in actual.controls if _akey(c) == key][:count]
        for c in added:
            if c.provenance == "snapshot" and prior["controls"].get(_ckey(c), 0) > Counter(
                    _ckey(x) for x in expected.controls).get(_ckey(c), 0):
                tolerated["affordance_present_in_prior_dom"] += 1
            elif volatile_control(c, (first or {}).get("probe", {}).get(c.css_path)):
                tolerated["affordance_volatile"] += 1
            else:
                reasons.append("affordance_added")

    # 5-6: text regions
    container = (target_probe or {}).get("container", "")
    if container != (prior_probe or {}).get("container", ""):
        reasons.append("target_context_changed")
    if container and container in volatile_containers:
        reasons.append("target_context_volatile")
    exp_regions = prior["regions"]
    changed: set[str] = set()
    for key in set(exp_regions) | set().union(*(keys(s) for s in samples)):
        # A difference counts only if it persists in every restored sample.
        if all(keys(s).get(key, (None,))[0] != exp_regions.get(key, (None,))[0] for s in samples):
            changed.add(key)
    meta = lambda key: exp_regions.get(key) or next((keys(s)[key] for s in samples if key in keys(s)))
    for key in changed:
        _, _, identity, status = meta(key)
        scoped = _in_scope(key, container)
        if key in volatile_regions:
            if scoped:
                reasons.append("target_context_volatile")
            else:
                tolerated["volatile_region"] += 1
        elif scoped:
            reasons.append("target_context_changed")
        elif identity:
            reasons.append("page_identity_changed")
        elif status:
            reasons.append("status_changed")
        elif tier == "declarative":
            tolerated["outside_scope"] += 1
        else:
            reasons.append("content_changed")
    if expected.content_fingerprint != actual.content_fingerprint and not changed:
        # The snapshot saw a difference the region evidence cannot localize (e.g. shadow DOM).
        reasons.append("unlocalized_content_change")
    if (prior.get("shadow_roots") or any(s.get("shadow_roots") for s in samples)) and tier == "contextual" and changed:
        reasons.append("unlocalized_content_change")

    if reasons and len(samples) < 3 and set(reasons) <= _VOLATILITY_ELIGIBLE:
        return done(False, needs=True)
    return done(not reasons)


def collect(page: Any, probe: list[str]) -> dict[str, Any]:
    return condense(page.main_frame.evaluate(REGION_SCRIPT, {"probe": probe}))


def sample_restored(page: Any, probe: list[str], interval_ms: int, count: int) -> tuple[list[dict[str, Any]], float]:
    started = time.monotonic()
    out = []
    for index in range(count):
        if index:
            page.wait_for_timeout(interval_ms)
        out.append(collect(page, probe))
    return out, (time.monotonic() - started) * 1_000
