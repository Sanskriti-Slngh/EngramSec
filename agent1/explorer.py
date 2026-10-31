from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections import defaultdict
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.parse import parse_qsl

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Frame,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)
from playwright.sync_api import sync_playwright

from .providers import DecisionProvider, ModelProviderError, build_provider
from .cookies import context_cookie_bridge
from .listeners import ListenerObserver, ListenerSnapshot
from .resource_spider import ResourceBudget, TypedResourceSpider
from .revision import code_revision
from .hierarchical import AreaTourPlanner
from .zap_adapter import load_zap_evidence
from .search import (
    SEARCH_SEMANTICS,
    introduced_links,
    is_get_search_action,
    observable_links,
    search_field,
)
from .schema import (
    ActionDescriptor,
    Advertisement,
    Checkpoint,
    Control,
    EvidenceStatus,
    Feature,
    FormAttempt,
    FunctionalStatus,
    FunctionalWorkflow,
    ConnectionEvidence,
    FormField,
    ListenerEvidence,
    FormObservation,
    FrontierItem,
    InputReference,
    NetworkEvent,
    NavigationEvidence,
    Observation,
    OutcomeSignal,
    PrerequisiteStepEvidence,
    ReadinessEvidence,
    ReadinessSample,
    ReplayResult,
    ResourceEvidence,
    RunArtifact,
    RunConfig,
    Transition,
    utc_now,
)
from .state import (
    VOLATILE_CONTROL,
    compact_text,
    control_signature,
    digest,
    feature_action_signature,
    feature_key,
    group_control_signature,
    normalize_instance_text,
    content_fingerprint,
    outcome_signature,
    allowed_origin,
    behavior_signature,
    route_pattern,
    sanitize_url,
    signatures,
)


DANGEROUS_ACTION = re.compile(
    r"\b(delete|remove|destroy|drop|reset|shutdown|disable|unsubscribe|purge|clear|empty|logout|sign\s*out)\b",
    re.I,
)
AMBIGUOUS_LABEL = re.compile(r"^(|click|submit|go|ok|more|next|button|link)$", re.I)
LOW_VALUE_REPORT = re.compile(
    r"^(?:view\s+)?(?:results?|score(?:board)?|reports?|status|exports?)(?:\s|$)", re.I
)


EXTRACT_SCRIPT = r"""
() => {
  const roots = [document];
  for (let index = 0; index < roots.length; index++) {
    for (const el of roots[index].querySelectorAll('*')) {
      if (el.shadowRoot && !roots.includes(el.shadowRoot)) roots.push(el.shadowRoot);
    }
  }
  const all = (selector) => roots.flatMap(root => Array.from(root.querySelectorAll(selector)));
  const rendered = (el) => {
    if (el.tagName?.toLowerCase() === 'area') return !!el.href;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (style.visibility === 'hidden' || style.display === 'none' || style.opacity === '0' || rect.width <= 0 || rect.height <= 0) return false;
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    if (cx >= 0 && cy >= 0 && cx < window.innerWidth && cy < window.innerHeight) {
      const top = document.elementFromPoint(cx, cy);
      const host = el.getRootNode()?.host;
      if (top && top !== el && !el.contains(top) && top !== host && !top.contains?.(host)) return false;
    }
    return true;
  };
  const labelFor = (el) => {
    const labels = el.labels ? Array.from(el.labels).map(x => x.innerText).join(' ') : '';
    return (el.getAttribute('aria-label') || labels || el.innerText || el.value ||
      el.getAttribute('title') || el.getAttribute('placeholder') ||
      (el.id ? el.id.replace(/[-_]+/g, ' ') : '') || '').replace(/\s+/g, ' ').trim();
  };
  const cssPath = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    let current = el;
    while (current && current.nodeType === Node.ELEMENT_NODE && current !== document.documentElement) {
      let part = current.tagName.toLowerCase();
      const siblings = current.parentElement ? Array.from(current.parentElement.children).filter(x => x.tagName === current.tagName) : [];
      if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(current) + 1})`;
      parts.unshift(part);
      current = current.parentElement;
    }
    return parts.join(' > ');
  };
  const componentFor = (el) => {
    const landmark = el.closest?.('nav,header,footer,aside,main,form,dialog,[role=menu],[role=navigation],[role=main],[role=dialog]');
    const node = landmark || el.getRootNode()?.host || document.body;
    const tag = (node?.tagName || 'document').toLowerCase();
    const role = node?.getAttribute?.('role') || '';
    const id = node?.id || '';
    const classes = String(node?.className || '').split(/\s+/).filter(Boolean).slice(0, 2).join('.');
    return [tag, role, id, classes].filter(Boolean).join(':').slice(0, 160) || 'document';
  };
  const fieldFor = (el) => {
    const describedIds = (el.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
    const description = describedIds.map(id => document.getElementById(id)?.innerText || '').join(' ');
    return {
      name: el.getAttribute('name') || el.id || '',
      input_type: (el.getAttribute('type') || el.tagName || 'text').toLowerCase(),
      label: labelFor(el),
      required: !!el.required,
      css_path: cssPath(el),
      placeholder: el.getAttribute('placeholder') || '',
      pattern: el.getAttribute('pattern') || '',
      min_length: typeof el.minLength === 'number' && el.minLength >= 0 ? el.minLength : null,
      max_length: typeof el.maxLength === 'number' && el.maxLength >= 0 ? el.maxLength : null,
      min_value: el.getAttribute('min'),
      max_value: el.getAttribute('max'),
      step: el.getAttribute('step'),
      description: description.replace(/\s+/g, ' ').trim(),
      options: el.tagName.toLowerCase() === 'select' ? Array.from(el.options).map(option => ({
        value: option.value || '', label: (option.innerText || '').replace(/\s+/g, ' ').trim()
      })) : []
    };
  };
  const formElements = all('form');
  const forms = formElements.map((form, index) => ({
    index,
    method: (form.method || 'GET').toUpperCase(),
    action: form.action || location.href,
    fields: Array.from(form.querySelectorAll('input,select,textarea')).filter(el => el.name || el.id).map(fieldFor),
    submit_labels: Array.from(form.querySelectorAll('button,input[type=submit],input[type=button],input[type=image]')).map(labelFor).filter(Boolean)
  }));
  const eventTypesFor = (el) => {
    const region = el.closest?.('.control-area,section,article,[data-component]');
    let context = (el.innerText || '') + ' ' + (region?.innerText || '');
    let sibling = region?.previousElementSibling;
    for (let count = 0; sibling && count < 2; count++, sibling = sibling.previousElementSibling) {
      if (sibling.matches?.('p,.desc,.description,h1,h2,h3')) context += ' ' + (sibling.innerText || '');
    }
    context = context.toLowerCase();
    const events = [];
    if (/\b(?:right[- ]?click|contextmenu|context menu)\b/.test(context)) events.push('context_menu');
    if (/\b(?:double[- ]?click|dblclick)\b/.test(context)) events.push('double_click');
    if (/\b(?:mouse ?over|hover)\b/.test(context)) events.push('hover');
    if (/\b(?:focus|focusin)\b/.test(context)) events.push('focus');
    if (/\b(?:key(?:down|up|press)|press (?:enter|return))\b/.test(context)) events.push('key_enter');
    if (/\b(?:long[- ]?press|press and hold|mousedown)\b/.test(context)) events.push('press_hold');
    return events;
  };
  const pageHasEventSemantics = /\b(?:right[- ]?click|contextmenu|double[- ]?click|dblclick|mouse ?over|hover|focus|focusin|key(?:down|up|press)|long[- ]?press|press and hold|mousedown)\b/i.test(document.body?.innerText || '');
  const selector = 'a[href],area[href],button,input[type=submit],input[type=button],input[type=image],input[type=checkbox],input[type=radio],select,[role=button],' +
    '[role=tab],[role=menuitem],[role=link],summary,[data-action],[tabindex]:not([tabindex="-1"]),' +
    '[onclick],[ondblclick],[oncontextmenu],[onmouseover],[onmouseenter],[onfocus],[onkeydown],' +
    '[onpointerup],[onmousedown],[aria-controls],[aria-haspopup],[data-toggle],[data-target],[popovertarget],[id^="toggle-"]';
  const semanticElements = pageHasEventSemantics ? all('main div,main span,main img,main canvas,main svg,main [tabindex],main [draggable=true]').filter(el => {
    const rect = el.getBoundingClientRect();
    const identity = el.id || String(el.className || '') || el.getAttribute('role') || el.getAttribute('style');
    const excluded = el.matches('nav,header,footer,.desc,.description,.breadcrumb') || el.closest('.desc,.description,.breadcrumb');
    const hasUsefulGeometry = rect.width >= 16 && rect.height >= 16 && rect.width < window.innerWidth * 0.95;
    const leafLike = el.children.length <= 3 || !!el.id || !!el.getAttribute('role');
    return identity && !excluded && hasUsefulGeometry && leafLike && eventTypesFor(el).length;
  }) : [];
  const candidateElements = Array.from(new Set([...all(selector), ...semanticElements])).filter(el => {
    const tag = el.tagName.toLowerCase();
    const inputType = (el.getAttribute('type') || '').toLowerCase();
    const passiveField = tag === 'textarea' || tag === 'select' ||
      (tag === 'input' && !['submit', 'button', 'image'].includes(inputType));
    const selectable = tag === 'select' || (tag === 'input' && ['checkbox','radio'].includes(inputType));
    const hasFieldEvent = passiveField && (selectable || el.hasAttribute('onfocus') || el.hasAttribute('onkeydown'));
    return rendered(el) && (!passiveField || hasFieldEvent) && !el.disabled &&
      el.getAttribute('aria-disabled') !== 'true';
  });
  const controls = candidateElements.flatMap((el) => {
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || (['a','area'].includes(tag) ? 'link' : 'button');
    const formIndex = el.form ? formElements.indexOf(el.form) : null;
    const form = formIndex === null || formIndex < 0 ? null : forms[formIndex];
    const inputType = (el.getAttribute('type') || '').toLowerCase();
    const submitsForm = !!form && (tag === 'button' || ['submit','button','image'].includes(inputType));
    const kind = ['a','area'].includes(tag) ? 'link' : (submitsForm ? 'form_submit' : 'button');
    const rawHref = ['a','area'].includes(tag) ? (el.getAttribute('href') || '') : '';
    const interactions = [];
    if (kind === 'link' && rawHref && !el.hasAttribute('onclick') &&
        !rawHref.startsWith('#') && !rawHref.toLowerCase().startsWith('javascript:') &&
        (el.getAttribute('target') || '').toLowerCase() !== '_blank') interactions.push('navigate');
    else if (kind !== 'button' || el.matches('button,[role=button],[role=tab],[role=menuitem],summary,[onclick],[data-action],[aria-controls],[popovertarget]')) interactions.push('click');
    if (el.hasAttribute('ondblclick')) interactions.push('double_click');
    if (el.hasAttribute('oncontextmenu')) interactions.push('context_menu');
    if (el.hasAttribute('onmouseover') || el.hasAttribute('onmouseenter') ||
        el.getAttribute('aria-haspopup') || /(?:hover|dropdown|menu)/i.test(String(el.className || ''))) interactions.push('hover');
    if (el.hasAttribute('onfocus')) interactions.push('focus');
    if (el.hasAttribute('onkeydown')) interactions.push('key_enter');
    if (el.hasAttribute('onmousedown')) interactions.push('press_hold');
    if (tag === 'select') interactions.push('select_option');
    if (tag === 'input' && ['checkbox','radio'].includes(inputType)) interactions.push('toggle');
    const localEvents = eventTypesFor(el);
    if (semanticElements.includes(el)) interactions.push(...localEvents);
    if (localEvents.includes('hover') && el.matches('button,a:not([href]),[role=button],[role=menuitem]')) interactions.push('hover');
    if (localEvents.includes('focus') && el.matches('button,a:not([href]),input,select,textarea,[tabindex]')) interactions.push('focus');
    if (localEvents.includes('key_enter') && el.matches('button,a:not([href]),input,[role=button],[tabindex]')) interactions.push('key_enter');
    if (!interactions.length) interactions.push('click');
    const base = {
      kind,
      label: labelFor(el),
      css_path: cssPath(el),
      role,
      target: ['a','area'].includes(tag) ? (el.href?.baseVal || el.href || rawHref) : (form ? form.action : null),
      method: form ? form.method : null,
      form_index: formIndex === null || formIndex < 0 ? null : formIndex,
      fields: form ? form.fields : [],
      component: componentFor(el)
    };
    return Array.from(new Set(interactions)).map(interaction => ({...base, interaction}));
  });
  if (document.documentElement.scrollHeight > window.innerHeight + 64) {
    controls.push({kind:'button',label:'Scroll viewport',css_path:'__viewport__',role:'document',
      target:null,method:null,form_index:null,fields:[],component:'document',interaction:'scroll_viewport'});
  }
  for (const el of all('*').filter(el => {
    const style = window.getComputedStyle(el);
    return rendered(el) && el.scrollHeight > el.clientHeight + 64 &&
      ['auto','scroll'].includes(style.overflowY);
  }).slice(0, 5)) {
    controls.push({kind:'button',label:`Scroll ${labelFor(el) || 'container'}`,css_path:cssPath(el),role:'region',
      target:null,method:null,form_index:null,fields:[],component:componentFor(el),interaction:'scroll_container'});
  }
  const main = document.querySelector('main,[role=main]') || document.body;
  const meaningful = main ? main.cloneNode(true) : null;
  if (meaningful) meaningful.querySelectorAll(
    'script,style,noscript,template,nav,header,footer,[data-volatile],.timestamp,' +
    '#think_page_trace,#think_page_trace_open,#sfWebDebug,#debug-toolbar,[data-debug-toolbar]'
  ).forEach(el => el.remove());
  if (meaningful) meaningful.querySelectorAll(
    'i[class*="eye"],i[class*="view"],[aria-label*="view count" i],[title*="view count" i]'
  ).forEach(icon => (icon.closest('span,small') || icon).remove());
  const signalElements = all(
    '[data-outcome],[role=alert],[role=status],[aria-live]:not([aria-live=off]),.success,.error,.alert,.notice,.message'
  );
  const outcomes = [];
  const seen = new Set();
  for (const el of signalElements) {
    const text = (el.innerText || '').replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const declared = (el.getAttribute('data-outcome') || '').toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    const classes = String(el.className || '').toLowerCase();
    let kind = declared;
    if (!['success','validation_error','result','status','setup'].includes(kind)) {
      if (role === 'alert' || /(?:^|\s)(?:error|danger|invalid)(?:\s|$)/.test(classes)) kind = 'validation_error';
      else if (/(?:^|\s)success(?:\s|$)/.test(classes)) kind = 'success';
      else if (role === 'status') kind = 'status';
      else kind = 'unknown';
    }
    const key = `${kind}:${text}`;
    if (seen.has(key)) continue;
    seen.add(key);
    outcomes.push({kind, text, source: declared ? 'data-outcome' : (role ? `role:${role}` : 'class-or-live')});
  }
  return {
    controls,
    forms,
    body_text: document.body ? document.body.innerText : '',
    meaningful_text: [meaningful ? meaningful.innerText : '', ...roots.slice(1).map(root => root.textContent || '')].join(' '),
    outcomes
  };
}
"""


# The snapshot's interactive-element selector, shared with the listener
# observer so that listener nodes already represented by a snapshot control
# are recognized as such.
SNAPSHOT_SELECTOR = "".join(re.findall(r"'([^']*)'", re.search(
    r"const selector = (.*?);\n", EXTRACT_SCRIPT, re.S).group(1)))


def action_request_structures(network: list[NetworkEvent]) -> set[tuple[str, str, tuple[str, ...]]]:
    """Application request structures an action triggered: script-initiated
    requests (fetch/XHR) and any non-GET request, by method, route shape and
    parameter names (never values)."""
    return {
        (event.method.upper(), route_pattern(event.url), tuple(event.parameter_names))
        for event in network
        if event.resource_type in {"xhr", "fetch"} or event.method.upper() not in {"GET", "HEAD"}
    }


def transition_has_effect(transition: Any) -> bool:
    """Observable functional effect of one action: a different visible state,
    a dialog, a document navigation, or an application request."""
    return (transition.source_group_signature != transition.result_group_signature or bool(transition.dialogs)
            or bool(action_request_structures(transition.network))
            or any(event.resource_type == "document" for event in transition.network))


READINESS_SCRIPT = r"""
() => {
  if (!window.__engramReadiness) {
    window.__engramReadiness = {mutations: 0};
    new MutationObserver(records => { window.__engramReadiness.mutations += records.length; })
      .observe(document.documentElement, {subtree:true,childList:true,attributes:true,characterData:true});
  }
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== 'hidden' && style.display !== 'none' &&
      style.opacity !== '0' && rect.width > 0 && rect.height > 0;
  };
  const selector = 'a[href],area[href],button,input[type=submit],input[type=button],input[type=image],[role=button],' +
    '[role=tab],[role=menuitem],[role=link],summary,[data-action],[tabindex]:not([tabindex="-1"]),' +
    '[onclick],[ondblclick],[oncontextmenu],[onmouseover],[onmouseenter],[onfocus],[onkeydown],' +
    '[aria-controls],[aria-haspopup],[data-toggle],[data-target],[popovertarget],[id^="toggle-"]';
  const controls = Array.from(document.querySelectorAll(selector)).filter(visible);
  const enabled = controls.filter(el => !el.disabled && el.getAttribute('aria-disabled') !== 'true');
  const shape = enabled.map(el => [
    el.tagName.toLowerCase(), el.getAttribute('role') || '', el.getAttribute('href') || '',
    el.getAttribute('name') || '', (el.innerText || el.value || el.getAttribute('aria-label') || '')
      .replace(/\s+/g, ' ').trim().slice(0, 120)
  ].join('|')).sort().join('\n');
  return {
    document_state: document.readyState,
    aria_busy_count: document.querySelectorAll('[aria-busy="true"]').length,
    enabled_control_count: enabled.length,
    disabled_control_count: controls.length - enabled.length,
    main_enabled_control_count: enabled.filter(el => !!el.closest('main,[role=main]')).length,
    control_shape: shape,
    body_length: (document.body?.innerText || '').trim().length,
    mutation_count: window.__engramReadiness.mutations
    ,script_count: document.scripts.length
    ,meta_refresh_delay_ms: (() => {
      const meta = document.querySelector('meta[http-equiv="refresh" i]');
      if (!meta) return null;
      const match = (meta.content || '').match(/^\s*(\d+(?:\.\d+)?)/);
      return match ? Math.ceil(Number(match[1]) * 1000) : null;
    })()
  };
}
"""


def passive_http_reserve(config: RunConfig) -> int:
    """Shared-HTTP requests that passive channels (passive documents and
    speculative candidates) may never use; they remain for browser, redirect,
    replay and typed-resource traffic."""
    if config.passive_document_http_reserve is not None:
        return config.passive_document_http_reserve
    return (config.max_total_http_requests or 0) // 2


def build_resource_spider(config: RunConfig, budget: ResourceBudget) -> TypedResourceSpider:
    return TypedResourceSpider(
        config.start_url,
        config.origin_aliases,
        budget,
        config.max_resource_depth,
        config.max_resource_body_bytes,
        config.resource_frontier_policy,
        config.resource_random_seed,
        {
            "document": config.max_resource_document_fetches,
            "script": config.max_resource_script_fetches,
            "stylesheet": config.max_resource_stylesheet_fetches,
            "other_asset": config.max_resource_asset_fetches,
        },
        config.javascript_reference_parser,
        extraction=config.html_extraction,
        allocation=config.resource_allocation,
        passive_document_limit=config.max_passive_document_fetches,
        passive_http_reserve=passive_http_reserve(config),
        max_speculative_fetches=config.max_speculative_fetches,
        dangerous_pattern=DANGEROUS_ACTION,
        body_reader=config.response_body_reader,
        frontier_model=config.resource_frontier_model,
        passive_document_max_depth=config.passive_document_max_depth,
        budget_aware_deepening=config.budget_aware_deepening,
        hard_max_depth=config.hard_max_resource_depth,
    )


def effective_resource_budgets(config: RunConfig) -> dict[str, int | float | str | None]:
    shared = config.resource_allocation == "shared_http"
    return {
        "resource_allocation": config.resource_allocation,
        "html_extraction": config.html_extraction,
        "typed_resource_total": config.max_resource_fetches,
        "document_class_cap": None if shared else config.max_resource_document_fetches,
        "document_class_cap_configured": config.max_resource_document_fetches,
        "script_class_cap": config.max_resource_script_fetches,
        "stylesheet_class_cap": config.max_resource_stylesheet_fetches,
        "asset_class_cap": config.max_resource_asset_fetches,
        "passive_document_cap": config.max_passive_document_fetches if shared else 0,
        "passive_http_reserve": passive_http_reserve(config) if shared or config.max_speculative_fetches else None,
        "passive_channels_http_share": ((config.max_total_http_requests or 0) - passive_http_reserve(config))
        if shared or config.max_speculative_fetches else 0,
        "speculative_fetch_cap": config.max_speculative_fetches,
        "total_http_requests": config.max_total_http_requests,
        "max_resource_depth": config.max_resource_depth,
        "browser_actions": config.max_browser_actions,
        "seconds": config.max_seconds,
        "response_body_reader": config.response_body_reader,
        "resource_frontier_model": config.resource_frontier_model,
        "passive_document_max_depth": config.passive_document_max_depth,
        "budget_aware_deepening": config.budget_aware_deepening,
        "hard_max_resource_depth": config.hard_max_resource_depth if config.budget_aware_deepening else None,
    }


class NetworkRecorder:
    TRACKED_TYPES = {
        "document", "xhr", "fetch", "stylesheet", "script", "image", "media", "font", "manifest"
    }

    def __init__(
        self,
        source: Page | BrowserContext,
        config: RunConfig,
        resource_budget: ResourceBudget,
        resource_spider: TypedResourceSpider | None = None,
        run_started_monotonic: float | None = None,
        body_status: defaultdict[str, int] | None = None,
    ):
        self.source = source
        self.events: list[NetworkEvent] = []
        self.config = config
        self.run_started_monotonic = run_started_monotonic or time.monotonic()
        self.spider = resource_spider or build_resource_spider(config, resource_budget)
        self.request_count = 0
        self.body_status: defaultdict[str, int] = body_status if body_status is not None else defaultdict(int)
        source.on("response", self._response)
        source.on("requestfailed", self._failed)

    def _response(self, response: Any) -> None:
        request = response.request
        self.request_count += 1
        if request.resource_type not in self.TRACKED_TYPES:
            return
        if not allowed_origin(self.config.start_url, request.url, self.config.origin_aliases):
            return
        parameter_names, body_encoding = request_structure(
            request.method, request.url, request.headers, request.post_data
        )
        self.events.append(
            NetworkEvent(
                method=request.method,
                url=sanitize_url(request.url),
                status=response.status,
                resource_type=request.resource_type,
                parameter_names=parameter_names,
                body_encoding=body_encoding,
                elapsed_ms=int((time.monotonic() - self.run_started_monotonic) * 1_000),
            )
        )
        content_type = response.headers.get("content-type", "")
        if self.config.typed_resource_spider and (
            request.resource_type in {"document", "stylesheet", "script", "manifest"}
            or request.resource_type == "image" and "image/svg+xml" in content_type.lower()
        ):
            media = content_type.lower()
            is_robots = "text/plain" in media and "robots.txt" in urlsplit(response.url).path.lower()
            if is_robots or any(kind in media for kind in ("html", "css", "javascript", "ecmascript", "manifest+json", "image/svg+xml", "application/xml")):
                try:
                    body, body_status = self._browser_body(response)
                    self.body_status[body_status] += 1
                    charset = re.search(r"charset\s*=\s*['\"]?([^;\s'\"]+)", content_type, re.I)
                    try:
                        text = body.decode(charset.group(1) if charset else "utf-8", errors="replace")
                    except LookupError:
                        text = body.decode("utf-8", errors="replace")
                    self.spider.observe_response(
                        text,
                        response.url,
                        content_type,
                        {str(k).lower(): str(v) for k, v in response.headers.items()},
                    )
                except (PlaywrightError, UnicodeError, ValueError, LookupError):
                    pass

    def _browser_body(self, response: Any) -> tuple[bytes, str]:
        """Copy a browser-received body into Python only when its size is known
        to be within bounds before copying. Chromium already holds the body;
        the bound is on what Agent 1 copies, not on what the browser received."""
        limit = self.config.max_resource_body_bytes
        raw = response.headers.get("content-length")
        try:
            declared = int(raw) if raw not in (None, "") else None
        except ValueError:
            if self.config.response_body_reader != "bounded_stream":
                raise  # legacy behavior: the whole response is skipped
            declared = None
        if self.config.response_body_reader == "bounded_stream" and declared is None:
            try:
                declared = int(response.request.sizes().get("responseBodySize", -1))
            except (PlaywrightError, ValueError, TypeError):
                declared = None
            if declared is not None and declared < 0:
                declared = None
            if declared is not None and response.headers.get("content-encoding", "").lower() not in {"", "identity"}:
                # The reported size is the encoded transfer size; allow a bounded
                # expansion before copying the decoded body.
                declared *= 8
        if declared is None:
            return b"", "skipped_unknown_length"
        if declared == 0:
            return b"", "empty"
        if declared > limit:
            return b"", "skipped_oversized"
        return response.body(), "complete"

    def _failed(self, request: Any) -> None:
        self.request_count += 1
        if request.resource_type not in self.TRACKED_TYPES:
            return
        if not allowed_origin(self.config.start_url, request.url, self.config.origin_aliases):
            return
        parameter_names, body_encoding = request_structure(
            request.method, request.url, request.headers, request.post_data
        )
        self.events.append(
            NetworkEvent(
                method=request.method,
                url=sanitize_url(request.url),
                resource_type=request.resource_type,
                failure=compact_text(str(request.failure or "request failed"), 200),
                parameter_names=parameter_names,
                body_encoding=body_encoding,
                elapsed_ms=int((time.monotonic() - self.run_started_monotonic) * 1_000),
            )
        )

    def drain(self) -> list[NetworkEvent]:
        current = self.events
        self.events = []
        return current

    def drain_resources(self, request_context: Any) -> list[ResourceEvidence]:
        # The bounded reader acts as this browser context's user agent: it sends
        # the context's cookies and applies Set-Cookie back (RFC 6265), so a
        # server-side session rotation on a passive fetch cannot desynchronize
        # the browser's authorized session.
        if hasattr(self.source, "cookies"):
            self.spider.cookie_source, self.spider.cookie_sink = context_cookie_bridge(self.source)
            if not self.config.passive_cookie_sync:
                self.spider.cookie_sink = None  # b4a9a40 semantics, kept for the ablation
        else:
            self.spider.cookie_source = self.spider.cookie_sink = None
        records = self.spider.fetch_pending(
            request_context, self.config.max_resource_fetches_per_observation
        )
        return [
            ResourceEvidence.model_validate(
                item
                | {
                    "evidence_id": "resource_evidence_"
                    + digest(
                        [
                            item.get("url"), item.get("kind"), item.get("source_type"),
                            item.get("source_url"), item.get("source"), item.get("relation"),
                            item.get("depth"), item.get("status"), item.get("http_status"),
                        ],
                        20,
                    )
                }
            )
            for item in records
        ]


def request_structure(
    method: str, url: str, headers: dict[str, str] | None, post_data: str | None
) -> tuple[list[str], str | None]:
    """Return input names and encoding without retaining request values."""

    names = {key for key, _ in parse_qsl(urlsplit(url).query, keep_blank_values=True)}
    content_type = (headers or {}).get("content-type", "").lower()
    body_encoding = None
    if post_data and method.upper() not in {"GET", "HEAD"}:
        if "application/x-www-form-urlencoded" in content_type:
            names.update(key for key, _ in parse_qsl(post_data, keep_blank_values=True))
            body_encoding = "form"
        elif "application/json" in content_type:
            try:
                payload = json.loads(post_data)
                if isinstance(payload, dict):
                    names.update(str(key) for key in payload)
                body_encoding = "json"
            except (TypeError, ValueError):
                body_encoding = "json-invalid"
        elif "multipart/form-data" in content_type:
            names.update(re.findall(r'name="([^"\r\n]+)"', post_data))
            body_encoding = "multipart"
        else:
            body_encoding = "opaque"
    return sorted(compact_text(name, 120) for name in names if name), body_encoding


class BrowserSession:
    def __init__(
        self,
        browser: Browser,
        config: RunConfig,
        resource_budget: ResourceBudget | None = None,
        resource_spider: TypedResourceSpider | None = None,
        run_started_monotonic: float | None = None,
        http_budget: Any | None = None,
        body_status: defaultdict[str, int] | None = None,
    ):
        self.body_status = body_status
        self.browser = browser
        self.config = config
        self.resource_budget = resource_budget or ResourceBudget(
            config.max_resource_fetches,
            {
                "document": config.max_resource_document_fetches,
                "script": config.max_resource_script_fetches,
                "stylesheet": config.max_resource_stylesheet_fetches,
                "other_asset": config.max_resource_asset_fetches,
            }, http_budget,
        )
        self.resource_spider = resource_spider
        self.run_started_monotonic = run_started_monotonic or time.monotonic()
        self.http_budget = http_budget
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.network: NetworkRecorder | None = None
        self.dialogs: list[dict[str, str]] = []
        self._attached_pages: set[int] = set()
        self.last_readiness = ReadinessEvidence()
        self.last_navigation_network: list[NetworkEvent] = []
        self.last_navigation_resources: list[ResourceEvidence] = []
        self.last_action_resources: list[ResourceEvidence] = []
        self.last_popup_opened = False
        self._last_action: str | None = None
        self.listener_observer: ListenerObserver | None = None

    def _new_listener_observer(self) -> ListenerObserver | None:
        if self.config.runtime_listener_observation == "off":
            return None
        return ListenerObserver(SNAPSHOT_SELECTOR, max_nodes=self.config.max_listener_nodes,
                                max_candidates=self.config.max_listener_candidates,
                                family_limit=self.config.listener_family_limit)

    def __enter__(self) -> "BrowserSession":
        self.listener_observer = self._new_listener_observer()
        self._last_action = None
        self.context = self.browser.new_context()
        # The scope router is installed whenever an HTTP budget is configured.
        # Listener candidates have no statically known target, so the
        # cross-origin check on link targets cannot apply to them; with listener
        # observation on, the router is installed even without a budget and
        # then enforces scope only.
        if self.http_budget is not None or self.config.runtime_listener_observation != "off":
            budget = self.http_budget if self.http_budget is not None else HttpBudget(10**9)
            config = self.config

            def bounded_route(route: Any, request: Any) -> None:
                # Playwright routes only the first request of a redirect chain.
                if not allowed_origin(config.start_url, request.url, config.origin_aliases):
                    budget.blocked += 1
                    route.abort("blockedbyclient")
                    return
                if not budget.consume("browser"):
                    route.abort("blockedbyclient")
                    return
                try:
                    response = route.fetch(max_redirects=0, timeout=config.action_timeout_ms * 2)
                except PlaywrightError:
                    route.abort("failed")
                    return
                location = response.headers.get("location")
                if 300 <= response.status < 400 and location:
                    # The browser follows this hop outside the router, so scope
                    # and budget are enforced here; the hop is charged when its
                    # request event fires, never at this point (no double charge).
                    if not allowed_origin(config.start_url, urljoin(request.url, location), config.origin_aliases):
                        budget.blocked += 1
                        route.abort("blockedbyclient")
                        return
                    if not budget.remaining():
                        budget.blocked += 1
                        route.abort("blockedbyclient")
                        return
                route.fulfill(response=response)

            def charge_redirect_hop(request: Any) -> None:
                if request.redirected_from is None:
                    return
                budget.charge_observed("browser_redirect")
                if not allowed_origin(config.start_url, request.url, config.origin_aliases):
                    # A second or later hop cannot be intercepted by Playwright.
                    budget.redirect_scope_violations += 1

            self.context.route("**/*", bounded_route)
            self.context.on("request", charge_redirect_hop)
        self.network = NetworkRecorder(
            self.context,
            self.config,
            self.resource_budget,
            self.resource_spider,
            self.run_started_monotonic,
            self.body_status,
        )
        self.context.on("page", self._attach_page)
        self.page = self.context.new_page()
        self._attach_page(self.page)
        return self

    def _attach_page(self, page: Page) -> None:
        if id(page) in self._attached_pages:
            return
        self._attached_pages.add(id(page))
        page.on("dialog", self._dialog)

    def __exit__(self, *_: Any) -> None:
        if self.context:
            self.context.close()

    def reset_context(self) -> None:
        if self.context:
            self.context.close()
        self.context = None
        self.page = None
        self.network = None
        self.dialogs = []
        self._attached_pages = set()
        self.last_readiness = ReadinessEvidence()
        self.last_navigation_network = []
        self.last_navigation_resources = []
        self.last_navigation_resources = []
        self.last_popup_opened = False
        self.__enter__()

    def _dialog(self, dialog: Any) -> None:
        self.dialogs.append(
            {"type": str(dialog.type), "message": compact_text(str(dialog.message), 240)}
        )
        if dialog.type == "alert":
            dialog.accept()
        else:
            dialog.dismiss()

    def goto_start(self) -> int:
        assert self.page
        self._last_action = "navigation:start"
        response = self.page.goto(
            self.config.start_url,
            wait_until="domcontentloaded",
            timeout=self.config.action_timeout_ms * 2,
        )
        if not allowed_origin(
            self.config.start_url, self.page.url, self.config.origin_aliases
        ):
            raise RuntimeError("start navigation left the configured origin")
        if response and response.status >= 500:
            raise RuntimeError(f"start navigation returned HTTP {response.status}")
        if self.config.robust_readiness:
            self.last_readiness = self._wait_for_readiness(
                response.status if response else None
            )
        elif self.config.settle_ms:
            self.page.wait_for_timeout(self.config.settle_ms)
            self.last_readiness = ReadinessEvidence()
        else:
            self.last_readiness = ReadinessEvidence()
        if self.network:
            if self.config.typed_resource_spider:
                self.last_navigation_resources = self.network.drain_resources(self.context.request)
            self.last_navigation_network = self.network.drain()
        return 1

    def go_back(self) -> bool:
        """One browser-history step in the live context; the caller verifies the result."""
        assert self.page
        self._last_action = "navigation:history"
        try:
            response = self.page.go_back(wait_until="domcontentloaded", timeout=self.config.action_timeout_ms * 2)
        except PlaywrightError:
            return False
        if not allowed_origin(self.config.start_url, self.page.url, self.config.origin_aliases):
            raise RuntimeError("history return left the configured origin")
        if self.config.robust_readiness:
            self.last_readiness = self._wait_for_readiness(response.status if response else None)
        elif self.config.settle_ms:
            self.page.wait_for_timeout(self.config.settle_ms)
            self.last_readiness = ReadinessEvidence()
        else:
            self.last_readiness = ReadinessEvidence()
        if self.network:
            if self.config.typed_resource_spider:
                self.last_navigation_resources = self.network.drain_resources(self.context.request)
            self.last_navigation_network = self.network.drain()
        return True

    def _wait_for_readiness(self, http_status: int | None = None) -> ReadinessEvidence:
        """Record a bounded, browser-observable readiness trace.

        This is deliberately not a claim that the whole application has loaded.
        It waits for explicit busy/disabled initialization signals to clear and
        for the visible action shape to stabilize briefly.
        """

        assert self.page
        started = time.monotonic()
        samples: list[ReadinessSample] = []
        prior_fingerprint = ""
        stable_samples = 0
        prior_mutations = -1
        final_status = "initializing"
        while True:
            try:
                raw = self.page.evaluate(READINESS_SCRIPT)
            except PlaywrightError:
                if int((time.monotonic() - started) * 1_000) >= self.config.readiness_timeout_ms:
                    final_status = "timeout"
                    break
                self.page.wait_for_timeout(self.config.readiness_poll_ms)
                continue
            elapsed_ms = int((time.monotonic() - started) * 1_000)
            fingerprint = digest(raw.get("control_shape", ""), 16)
            sample = ReadinessSample(
                elapsed_ms=elapsed_ms,
                document_state=str(raw.get("document_state", "unknown")),
                aria_busy_count=int(raw.get("aria_busy_count", 0)),
                enabled_control_count=int(raw.get("enabled_control_count", 0)),
                disabled_control_count=int(raw.get("disabled_control_count", 0)),
                control_fingerprint=fingerprint,
                main_enabled_control_count=int(raw.get("main_enabled_control_count", 0)),
                mutation_count=int(raw.get("mutation_count", 0)),
                script_count=int(raw.get("script_count", 0)),
                meta_refresh_delay_ms=raw.get("meta_refresh_delay_ms"),
            )
            samples.append(sample)
            initializing = (
                sample.document_state == "loading"
                or sample.aria_busy_count > 0
                or (
                    sample.enabled_control_count == 0
                    and sample.disabled_control_count > 0
                )
            )
            if http_status in {401, 403, 407, 429}:
                final_status = "blocked"
                break
            # Cosmetic timers may mutate forever.  Mutation counts remain
            # evidence, while readiness is based on stable actionable shape;
            # newly hydrated controls still change the fingerprint and reset
            # the bounded stability window.
            stable = fingerprint == prior_fingerprint
            if not initializing:
                stable_samples = stable_samples + 1 if stable else 1
                refresh_wait = (sample.meta_refresh_delay_ms or 0) + 250
                if sample.main_enabled_control_count == 0:
                    if self.config.readiness_strategy == "adaptive" and sample.script_count:
                        mutation_active = (
                            prior_mutations >= 0
                            and sample.mutation_count > prior_mutations
                        )
                        hydration_window = 1_000 if mutation_active else 800
                        minimum_wait = max(
                            min(self.config.idle_page_wait_ms, hydration_window),
                            refresh_wait,
                        )
                    else:
                        minimum_wait = max(
                            self.config.idle_page_wait_ms
                            if sample.script_count
                            else self.config.passive_page_wait_ms,
                            refresh_wait,
                        )
                else:
                    minimum_wait = max(self.config.readiness_poll_ms * 3, refresh_wait)
                if stable_samples >= 3 and elapsed_ms >= minimum_wait:
                    final_status = "usable"
                    break
            else:
                stable_samples = 0
            prior_fingerprint = fingerprint
            prior_mutations = sample.mutation_count
            if elapsed_ms >= self.config.readiness_timeout_ms:
                final_status = "timeout"
                break
            self.page.wait_for_timeout(self.config.readiness_poll_ms)
        return ReadinessEvidence(
            status=final_status,
            duration_ms=int((time.monotonic() - started) * 1_000),
            http_status=http_status,
            samples=samples,
        )

    def observe(self, sequence: int) -> Observation:
        assert self.page
        frame_payloads: list[tuple[int, str, dict[str, Any]]] = []
        for frame_index, frame in enumerate(self.page.frames):
            frame_url_raw = frame.url or self.page.url
            if frame is not self.page.main_frame and not (
                frame_url_raw.startswith("about:")
                or allowed_origin(
                    self.config.start_url, frame_url_raw, self.config.origin_aliases
                )
            ):
                continue
            try:
                frame_payloads.append((frame_index, frame_url_raw, frame.evaluate(EXTRACT_SCRIPT)))
            except PlaywrightError:
                continue
        if not frame_payloads:
            raise RuntimeError("no observable same-scope browser frame")
        current_url = sanitize_url(self.page.url)
        forms: list[FormObservation] = []
        forms_by_frame: dict[tuple[int, int], FormObservation] = {}
        for frame_index, frame_url_raw, extracted in frame_payloads:
            safe_frame_url = (
                sanitize_url(frame_url_raw)
                if urlsplit(frame_url_raw).scheme in {"http", "https"}
                else compact_text(frame_url_raw, 240)
            )
            for item in extracted["forms"]:
                item = dict(item)
                local_index = item["index"]
                item["action"] = sanitize_url(
                    item.get("action") or frame_url_raw, frame_url_raw
                )
                fields = []
                for field_index, raw_field in enumerate(item.get("fields", [])):
                    raw_field = dict(raw_field)
                    raw_field["id"] = "fld_" + digest(
                        [
                            current_url,
                            safe_frame_url,
                            local_index,
                            raw_field.get("css_path"),
                            raw_field.get("name"),
                            field_index,
                        ],
                        18,
                    )
                    fields.append(raw_field)
                item["fields"] = fields
                item["frame_index"] = frame_index
                item["frame_url"] = safe_frame_url
                observed_form = FormObservation.model_validate(item)
                forms.append(observed_form)
                forms_by_frame[(frame_index, local_index)] = observed_form
        controls: list[Control] = []
        for frame_index, frame_url_raw, extracted in frame_payloads:
            safe_frame_url = (
                sanitize_url(frame_url_raw)
                if urlsplit(frame_url_raw).scheme in {"http", "https"}
                else compact_text(frame_url_raw, 240)
            )
            for raw in extracted["controls"]:
                interaction = raw.get("interaction") or "click"
                if self.config.interaction_profile == "basic" and interaction not in {
                    "click",
                    "navigate",
                }:
                    continue
                if interaction == "navigate" and not self.config.hybrid_link_discovery:
                    interaction = "click"
                raw_target = raw.get("target")
                resolved_target = urljoin(frame_url_raw, raw_target) if raw_target else None
                target = (
                    sanitize_url(resolved_target)
                    if resolved_target and urlsplit(resolved_target).scheme in {"http", "https"}
                    else None
                )
                label = compact_text(raw.get("label", ""), 160)
                method = (raw.get("method") or "").upper() or None
                form_index = raw.get("form_index")
                observed_form = (
                    forms_by_frame.get((frame_index, form_index))
                    if form_index is not None
                    else None
                )
                fields = observed_form.fields if observed_form else []
                if not label and raw["kind"] == "form_submit" and any(
                    field.input_type == "search"
                    or SEARCH_SEMANTICS.search(
                        " ".join((field.name, field.label, field.placeholder, field.description))
                    )
                    for field in fields
                ):
                    label = "Search"
                component = compact_text(raw.get("component", "document"), 160)
                unsafe_reason = self._unsafe_reason(label, target, method, fields)
                signature = control_signature(
                    raw["kind"],
                    raw["role"],
                    label,
                    target,
                    method,
                    interaction,
                    component,
                )
                control_id = "ctl_" + digest(
                    [current_url, safe_frame_url, raw["css_path"], signature], 18
                )
                controls.append(
                    Control(
                        id=control_id,
                        kind=raw["kind"],
                        label=label or f"unnamed {raw['role']}",
                        css_path=raw["css_path"],
                        role=raw["role"],
                        target=target,
                        method=method,
                        form_index=form_index,
                        fields=fields,
                        safe=unsafe_reason is None,
                        skip_reason=unsafe_reason,
                        signature=signature,
                        interaction=interaction,
                        component=component,
                        frame_index=frame_index,
                        frame_url=safe_frame_url,
                    )
                )
        listener_evidence: ListenerEvidence | None = None
        active_revisions: list[str] = []
        if self.listener_observer is not None:
            snapshot = self.listener_observer.observe(self.page, self._last_action)
            listener_evidence, active_revisions = self._apply_listener_snapshot(snapshot, controls, current_url)
        title = compact_text(self.page.title(), 200)
        session_markers = self._session_markers()
        meaningful_text = compact_text(
            " ".join(payload.get("meaningful_text", "") for _, _, payload in frame_payloads),
            8_000,
        )
        outcome_signals = [
            OutcomeSignal(
                kind=item["kind"],
                text_excerpt=compact_text(item.get("text", ""), 240),
                fingerprint=digest([item["kind"], compact_text(item.get("text", "").lower(), 1_000)]),
                source=compact_text(item.get("source", "unknown"), 80),
            )
            for _, _, payload in frame_payloads
            for item in payload.get("outcomes", [])
        ]
        raw_sig, group_sig, pattern = signatures(
            url=current_url,
            title=title,
            controls=controls,
            forms=forms,
            session_context=self.config.context_label,
            session_markers=session_markers,
            meaningful_text=meaningful_text,
        )
        observation_id = "obs_" + digest([sequence, current_url, raw_sig, time.time_ns()], 20)
        body_text = compact_text(
            " ".join(payload.get("body_text", "") for _, _, payload in frame_payloads),
            2_000,
        )
        return Observation(
            id=observation_id,
            sequence=sequence,
            url=current_url,
            title=title,
            text_excerpt=body_text,
            meaningful_text=meaningful_text,
            content_fingerprint=content_fingerprint(meaningful_text),
            outcome_signals=outcome_signals,
            controls=controls,
            forms=forms,
            state_signature=raw_sig,
            group_signature=group_sig,
            session_context=self.config.context_label,
            session_markers=session_markers,
            route_pattern=pattern,
            instance_facts={
                "form_count": len(forms),
                "safe_control_count": sum(control.safe for control in controls),
                "all_control_count": len(controls),
                "frame_count": len(frame_payloads),
            },
            readiness=self.last_readiness,
            listener_evidence=listener_evidence,
            behavior_signature=behavior_signature(group_sig, active_revisions, sorted(
                control.signature for control in controls if control.provenance == "observed_listener" and control.safe)),
        )

    def _frame_for_href(self, href: str) -> tuple[int, str] | None:
        assert self.page
        for index, frame in enumerate(self.page.frames):
            if frame.url == href or (
                urlsplit(href).scheme in {"http", "https"} and frame.url.startswith(("http://", "https://"))
                and sanitize_url(frame.url) == sanitize_url(href)
            ):
                safe = sanitize_url(frame.url) if urlsplit(frame.url).scheme in {"http", "https"} else compact_text(frame.url, 240)
                if index > 0 and not (frame.url.startswith("about:") or allowed_origin(
                        self.config.start_url, frame.url, self.config.origin_aliases)):
                    return None
                return index, safe
        return None

    def _apply_listener_snapshot(
        self, snapshot: ListenerSnapshot, controls: list[Control], current_url: str
    ) -> tuple[ListenerEvidence, list[str]]:
        """Turn bounded DevTools listener evidence into candidate controls.

        A candidate becomes an ordinary control: it passes the same safety
        filter and is executed only within the action budget. Revisions are
        attached to controls only in revisit mode; in observe mode they are
        evidence only.
        """
        revisit = self.config.runtime_listener_observation == "revisit"
        evidence = ListenerEvidence(
            supported=snapshot.supported, document_token=snapshot.document_token,
            caused_by_action=self._last_action, listener_nodes=snapshot.listener_nodes,
            described_nodes=snapshot.described_nodes, reused_nodes=snapshot.reused_nodes,
            changes=dict(snapshot.changes), truncated=snapshot.truncated, skipped=dict(snapshot.skipped),
            skipped_examples=snapshot.skipped_examples, delegation_hosts=snapshot.delegation_hosts,
            window_click_listeners=snapshot.window_click_listeners, elapsed_ms=snapshot.elapsed_ms,
            cdp_calls=snapshot.cdp_calls, error=snapshot.error,
        )
        evidence.revisions = [{k: v for k, v in item.items() if k != "backend_node_id"} for item in snapshot.revisions]

        def same_element(control: Control, entry: dict[str, Any], frame_index: int) -> bool:
            path = entry.get("css_path", "")
            return control.frame_index == frame_index and (
                control.css_path == path or control.css_path == path.split(" >> ")[-1])

        active: list[str] = []
        for entry in snapshot.represented:
            revision = entry.get("behavior_revision")
            frame = self._frame_for_href(entry.get("frame_href", ""))
            if not revision or frame is None:
                continue
            active.append(revision)
            evidence.active_revisions.append({"css_path": entry.get("css_path", ""), "revision": revision})
            if not revisit:
                continue
            for control in controls:
                if control.provenance == "snapshot" and same_element(control, entry, frame[0]):
                    control.behavior_revision = revision
                    control.id = "ctl_" + digest([control.id, revision], 18)
        allowed = None if self.config.interaction_profile != "basic" else {"click"}
        for entry in snapshot.candidates:
            frame = self._frame_for_href(entry.get("frame_href", ""))
            record = {k: v for k, v in entry.items() if k != "backend_node_id"} | {"control_ids": []}
            if frame is None:
                record["skip_reason"] = "frame_not_observable"
                evidence.skipped["frame_not_observable"] = evidence.skipped.get("frame_not_observable", 0) + 1
                evidence.candidates.append(record)
                continue
            frame_index, frame_url = frame
            if any(control.provenance == "snapshot" and same_element(control, entry, frame_index) for control in controls):
                continue
            revision = entry.get("behavior_revision")
            if revision:
                active.append(revision)
                evidence.active_revisions.append({"css_path": entry.get("css_path", ""), "revision": revision})
            label = compact_text(entry.get("label", ""), 160) or f"unnamed {entry.get('tag', 'element')}"
            component = compact_text(entry.get("component", "document"), 160)
            unsafe_reason = self._unsafe_reason(label, None, None, [])
            for interaction in entry.get("interactions", ["click"]):
                if allowed is not None and interaction not in allowed:
                    continue
                signature = control_signature("button", "generic", label, None, None, interaction, component)
                control_revision = revision if revisit else None
                control = Control(
                    id="ctl_" + digest([current_url, frame_url, entry["css_path"], signature, "listener", control_revision], 18),
                    kind="button", label=label, css_path=entry["css_path"], role="generic",
                    safe=unsafe_reason is None, skip_reason=unsafe_reason, signature=signature,
                    interaction=interaction, component=component, frame_index=frame_index, frame_url=frame_url,
                    provenance="observed_listener", behavior_revision=control_revision,
                    listener_evidence={"provenance": entry.get("provenance"), "family": entry.get("family"),
                                       "handler_locations": entry.get("handler_locations", []),
                                       "caused_by_action": self._last_action},
                )
                controls.append(control)
                record["control_ids"].append(control.id)
                record["safe"] = unsafe_reason is None
                record["skip_reason"] = unsafe_reason
            evidence.candidates.append(record)
        return evidence, active

    def _session_markers(self) -> dict[str, list[str]]:
        assert self.page and self.context
        cookies = self.context.cookies([self.page.url])
        storage = self.page.evaluate(
            "() => ({local: Object.keys(localStorage), session: Object.keys(sessionStorage)})"
        )
        return {
            "cookie_names": sorted(
                {compact_text(item.get("name", ""), 120) for item in cookies if item.get("name")}
            ),
            "local_storage_keys": sorted(
                {compact_text(item, 120) for item in storage.get("local", []) if item}
            ),
            "session_storage_keys": sorted(
                {compact_text(item, 120) for item in storage.get("session", []) if item}
            ),
        }

    def _unsafe_reason(
        self,
        label: str,
        target: str | None,
        method: str | None,
        fields: list[FormField],
    ) -> str | None:
        if target and not allowed_origin(
            self.config.start_url, target, self.config.origin_aliases
        ):
            return "cross_origin"
        candidate = f"{label} {urlsplit(target).path if target else ''}"
        if DANGEROUS_ACTION.search(candidate):
            return "dangerous_label_or_target"
        if any(field.input_type in {"password", "file"} for field in fields):
            return "requires_protected_or_file_input"
        if method == "POST" and not self.config.allow_post_forms:
            return "post_forms_disabled"
        return None

    @staticmethod
    def descriptor(control: Control) -> ActionDescriptor:
        return ActionDescriptor(
            control_id=control.id,
            kind=control.kind,
            label=control.label,
            role=control.role,
            css_path=control.css_path,
            target=control.target,
            method=control.method,
            form_index=control.form_index,
            fields=control.fields,
            signature=control.signature,
            interaction=control.interaction,
            component=control.component,
            frame_index=control.frame_index,
            frame_url=control.frame_url,
            provenance=control.provenance,
            behavior_revision=control.behavior_revision,
        )

    def find_current(self, observation: Observation, descriptor: ActionDescriptor) -> Control | None:
        # A recorded action names the handler revision it exercised (None for
        # the original behavior); only a control in that behavior matches.
        revision = getattr(descriptor, "behavior_revision", None)
        observation = observation.model_copy(update={"controls": [
            control for control in observation.controls if control.behavior_revision == revision]})
        for control in observation.controls:
            if control.id == descriptor.control_id and control.safe:
                return control
        candidates = [
            control
            for control in observation.controls
            if control.signature == descriptor.signature
            and control.interaction == descriptor.interaction
            and control.safe
        ]
        if len(candidates) == 1:
            return candidates[0]
        # DOM positions and generated IDs can move after hydration.  A bounded
        # semantic fallback remains scoped to the observed role/component and
        # never invents a control that was not in the current observation.
        candidates = [
            control
            for control in observation.controls
            if control.safe
            and control.role == descriptor.role
            and control.label == descriptor.label
            and control.interaction == descriptor.interaction
            and (
                descriptor.component == "document"
                or control.component == descriptor.component
            )
            and (not descriptor.target or control.target == descriptor.target)
        ]
        return candidates[0] if len(candidates) == 1 else None

    def _frame_for(self, frame_index: int, frame_url: str) -> Frame:
        assert self.page
        frames = self.page.frames
        if 0 <= frame_index < len(frames):
            candidate = frames[frame_index]
            if frame_index == 0 or not frame_url or sanitize_url(candidate.url) == frame_url:
                return candidate
        matches = [
            frame for frame in frames
            if frame_url and frame.url.startswith(("http://", "https://"))
            and sanitize_url(frame.url) == frame_url
        ]
        if len(matches) == 1:
            return matches[0]
        if frame_index == 0:
            return self.page.main_frame
        raise RuntimeError("observed frame is no longer available")

    def _locator_for(self, control: Control) -> Any:
        frame = self._frame_for(control.frame_index, control.frame_url)
        locator = frame.locator(control.css_path).first
        if locator.count() == 0 and control.role not in {"document", "generic"}:
            locator = frame.get_by_role(control.role, name=control.label, exact=True).first
        if locator.count() == 0:
            raise RuntimeError("observed control locator is no longer present")
        return locator

    def execute(
        self,
        control: Control,
        input_values: dict[str, str] | None = None,
        input_plan_ref: str | None = None,
    ) -> tuple[list[InputReference], list[NetworkEvent], list[dict[str, str]], int]:
        assert self.page and self.network
        self.network.drain()
        self.dialogs = []
        self.last_popup_opened = False
        self.last_action_resources = []
        self._last_action = control.signature + (f"@{control.behavior_revision}" if control.behavior_revision else "")
        input_refs: list[InputReference] = []
        action_count = 0
        if control.kind == "form_submit" and control.form_index is not None:
            refs, fills = self._fill_form(
                control.form_index,
                control.fields,
                control.frame_index,
                control.frame_url,
                input_values=input_values or {},
                input_plan_ref=input_plan_ref,
            )
            input_refs.extend(refs)
            action_count += fills
        prior_pages = set(self.context.pages) if self.context else {self.page}
        if control.interaction == "navigate":
            if not control.target:
                raise RuntimeError("navigation candidate has no observed target")
            self.page.goto(
                control.target,
                wait_until="domcontentloaded",
                timeout=self.config.action_timeout_ms * 2,
            )
        elif control.interaction == "scroll_viewport":
            self.page.evaluate("() => window.scrollBy(0, Math.max(innerHeight * 0.85, 320))")
        else:
            locator = self._locator_for(control)
            if control.interaction == "hover":
                locator.hover(timeout=self.config.action_timeout_ms)
            elif control.interaction == "focus":
                locator.focus(timeout=self.config.action_timeout_ms)
            elif control.interaction == "key_enter":
                locator.focus(timeout=self.config.action_timeout_ms)
                locator.press("Enter", timeout=self.config.action_timeout_ms)
            elif control.interaction == "double_click":
                locator.dblclick(timeout=self.config.action_timeout_ms)
            elif control.interaction == "context_menu":
                locator.click(button="right", timeout=self.config.action_timeout_ms)
            elif control.interaction == "press_hold":
                locator.hover(timeout=self.config.action_timeout_ms)
                locator.dispatch_event("mousedown")
                self.page.wait_for_timeout(700)
                locator.dispatch_event("mouseup")
            elif control.interaction == "scroll_container":
                locator.evaluate("el => el.scrollBy(0, Math.max(el.clientHeight * 0.85, 160))")
            elif control.interaction == "toggle":
                locator.check(timeout=self.config.action_timeout_ms)
            elif control.interaction == "select_option":
                values = locator.locator("option").evaluate_all(
                    "options => options.map(option => option.value).filter(Boolean)"
                )
                if not values:
                    raise RuntimeError("observed select has no non-empty option")
                locator.select_option(values[-1], timeout=self.config.action_timeout_ms)
            else:
                locator.click(timeout=self.config.action_timeout_ms)
        action_count += 1
        if self.context:
            if len(self.context.pages) == len(prior_pages):
                self.page.wait_for_timeout(100)
            new_pages = [page for page in self.context.pages if page not in prior_pages]
            if new_pages:
                popup = new_pages[-1]
                try:
                    popup.wait_for_load_state("domcontentloaded", timeout=self.config.action_timeout_ms)
                except PlaywrightTimeoutError:
                    pass
                if allowed_origin(self.config.start_url, popup.url, self.config.origin_aliases):
                    self.page = popup
                    self._attach_page(popup)
                    self.last_popup_opened = True
                else:
                    popup.close()
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=self.config.action_timeout_ms)
        except PlaywrightTimeoutError:
            pass
        if self.config.robust_readiness:
            self.last_readiness = self._wait_for_readiness()
        elif self.config.settle_ms:
            self.page.wait_for_timeout(self.config.settle_ms)
            self.last_readiness = ReadinessEvidence()
        else:
            self.last_readiness = ReadinessEvidence()
        if self.config.typed_resource_spider and self.network and self.context:
            self.last_action_resources = self.network.drain_resources(self.context.request)
        if not allowed_origin(
            self.config.start_url, self.page.url, self.config.origin_aliases
        ):
            raise RuntimeError("action left the configured origin")
        return input_refs, self.network.drain(), list(self.dialogs), action_count

    def _fill_form(
        self,
        form_index: int,
        observed_fields: list[FormField],
        frame_index: int,
        frame_url: str,
        input_values: dict[str, str],
        input_plan_ref: str | None,
    ) -> tuple[list[InputReference], int]:
        assert self.page
        frame = self._frame_for(frame_index, frame_url)
        form = frame.locator("form").nth(form_index)
        fields = form.locator("input,select,textarea")
        refs: list[InputReference] = []
        actions = 0
        specs_by_name = {item.name: item for item in observed_fields}
        for index in range(fields.count()):
            field = fields.nth(index)
            name = field.get_attribute("name") or field.get_attribute("id") or f"field_{index}"
            tag = field.evaluate("el => el.tagName.toLowerCase()")
            kind = (field.get_attribute("type") or tag or "text").lower()
            spec = specs_by_name.get(name)
            if kind in {"hidden", "submit", "button", "reset", "password", "file", "image"}:
                continue
            if kind in {"checkbox", "radio"}:
                field.check(timeout=self.config.action_timeout_ms)
                value_ref = f"generated:{kind}:checked"
            elif tag == "select":
                options = field.locator("option")
                selected = None
                for option_index in range(options.count()):
                    value = options.nth(option_index).get_attribute("value")
                    if value:
                        selected = value
                        break
                if selected is None:
                    continue
                field.select_option(selected, timeout=self.config.action_timeout_ms)
                value_ref = "generated:select:first_nonempty"
            else:
                if spec and spec.id in input_values:
                    value = input_values[spec.id]
                    value_ref = f"input-plan:{input_plan_ref or 'memory'}:{spec.id}"
                else:
                    value, value_ref = self._generated_value(kind, name, spec)
                field.fill(value, timeout=self.config.action_timeout_ms)
            refs.append(
                InputReference(
                    field_name=name[:100],
                    input_type=kind,
                    value_ref=value_ref,
                    protected=True,
                )
            )
            actions += 1
        return refs, actions

    @staticmethod
    def _generated_value(
        kind: str, name: str, spec: FormField | None = None
    ) -> tuple[str, str]:
        lowered = name.lower()
        if spec and spec.placeholder:
            placeholder = spec.placeholder.strip()
            if placeholder and (
                not spec.pattern or re.fullmatch(spec.pattern, placeholder) is not None
            ):
                return placeholder[: max(1, spec.max_length or 200)], "generated:observed_placeholder"
        if kind == "email" or "email" in lowered:
            return "agent1@example.test", "generated:email"
        if kind in {"number", "range"}:
            return "1", "generated:number:1"
        if kind == "tel" or "phone" in lowered:
            return "5550100", "generated:phone"
        if kind == "url":
            return "https://example.test/", "generated:url"
        if "search" in lowered or kind == "search":
            return "engramsec-test", "generated:search"
        return "EngramSec test", "generated:text"


class HttpBudget:
    """Run-wide HTTP request ledger shared by browser, replay, spider and ZAP traffic.

    Pre-flight requests (browser route, spider GET) are charged with
    ``consume`` and refused once the limit is reached. Playwright does not route
    redirect hops, so each hop is charged once from the context ``request`` event
    via ``charge_observed``; hops that could not be refused are counted as
    ``redirect_overrun`` when they exceed the limit.
    """

    # Sources allowed to spend the verification reserve once replay begins.
    VERIFICATION_SOURCES = {"browser", "browser_redirect"}

    def __init__(self, limit: int, verification_reserve: int = 0):
        self.limit, self.used, self.blocked = limit, 0, 0
        self.redirect_overrun = 0
        self.redirect_scope_violations = 0
        self.by_source: defaultdict[str, int] = defaultdict(int)
        # Requests held back for independent replay, mirroring the time and
        # action replay reserve: discovery (browser exploration and every
        # passive source) stops at limit - reserve; only browser replay
        # traffic may spend the reserve.
        self.verification_reserve = verification_reserve
        self.phase = "discovery"

    def _cap(self, source: str) -> int:
        if self.phase == "verification" and source in self.VERIFICATION_SOURCES:
            return self.limit
        return self.limit - self.verification_reserve

    def remaining(self, source: str = "browser") -> bool:
        return self.used < self._cap(source)

    def _label(self, source: str) -> str:
        return f"{source}_verification" if self.phase == "verification" and source in self.VERIFICATION_SOURCES else source

    def consume(self, source: str = "browser") -> bool:
        if not self.remaining(source):
            self.blocked += 1
            return False
        self.used += 1
        self.by_source[self._label(source)] += 1
        return True

    def charge_observed(self, source: str) -> None:
        self.used += 1
        self.by_source[self._label(source)] += 1
        if self.used > self.limit:
            self.redirect_overrun += 1

    def charge_external(self, requests: int, source: str) -> None:
        if requests > self.limit - self.used:
            raise ValueError(f"{source} request count exceeds the remaining HTTP budget")
        self.used += requests
        self.by_source[source] += requests

    def export(self, metrics: Any) -> None:
        metrics.total_http_budget_used = self.used
        metrics.total_http_budget_blocked = self.blocked
        metrics.http_redirect_budget_overrun = self.redirect_overrun
        metrics.http_redirect_scope_violations = self.redirect_scope_violations
        metrics.http_budget_by_source = dict(self.by_source)

    def restore(self, metrics: Any) -> None:
        self.used = metrics.total_http_budget_used
        self.blocked = metrics.total_http_budget_blocked
        self.redirect_overrun = metrics.http_redirect_budget_overrun
        self.redirect_scope_violations = metrics.http_redirect_scope_violations
        self.by_source = defaultdict(int, metrics.http_budget_by_source)


class Explorer:
    def __init__(self, config: RunConfig, repository_root: Path):
        self.config = config
        self.repository_root = repository_root
        self.output_dir = config.output_dir
        self.run_id = config.run_id or time.strftime("agent1-%Y%m%dT%H%M%SZ", time.gmtime())
        self.started_monotonic = time.monotonic()
        self.prior_elapsed = 0.0
        self.sequence = 0
        self.http_budget = HttpBudget(
            config.max_total_http_requests,
            int(config.max_total_http_requests * config.http_verification_reserve_fraction),
        ) if config.max_total_http_requests else None
        self.browser_body_status: defaultdict[str, int] = defaultdict(int)
        self.resource_budget = ResourceBudget(
            config.max_resource_fetches,
            {
                "document": config.max_resource_document_fetches,
                "script": config.max_resource_script_fetches,
                "stylesheet": config.max_resource_stylesheet_fetches,
                "other_asset": config.max_resource_asset_fetches,
            }, self.http_budget,
        )
        self.resource_spider = (
            build_resource_spider(config, self.resource_budget)
            if config.typed_resource_spider and config.share_resource_frontier
            else None
        )
        self.frontier: list[FrontierItem] = []
        self.tried: set[str] = set()
        self._seen_control_shapes: set[str] = set()
        self._seen_targets: set[str] = set()
        self._seen_components: set[str] = set()
        self._seen_form_shapes: set[str] = set()
        self._scheduled_global_actions: set[str] = set()
        self._ineffective_actions: defaultdict[str, int] = defaultdict(int)
        self.provider: DecisionProvider = build_provider(
            config.model_provider,
            config.model_name,
            repository_root / "agent1" / ".cache" / "model_decisions.json",
        )
        self.model_labels: dict[str, str] = {}
        self.artifact = RunArtifact(
            run_id=self.run_id,
            code_revision=self._revision(),
            config=self._safe_config(),
            started_at=utc_now(),
            notes=[
                "Website-only browser evidence; target source and verifier internals were not inspected.",
                "A browser-observed edge is not counted as a validated feature until its complete path replays.",
                "Query values with sensitive-looking keys are redacted from stored network evidence.",
            ],
        )
        self._observation_ids: set[str] = set()

    def _safe_config(self) -> dict[str, Any]:
        data = self.config.model_dump(mode="json")
        data["output_dir"] = str(self.output_dir)
        if data.get("resume_from"):
            data["resume_from"] = str(data["resume_from"])
        return data

    def _browser_session(self, browser: Browser) -> BrowserSession:
        return BrowserSession(
            browser,
            self.config,
            self.resource_budget,
            self.resource_spider,
            self.started_monotonic,
            self.http_budget,
            self.browser_body_status,
        )

    def _revision(self) -> str:
        return code_revision(self.repository_root)

    def _elapsed(self) -> float:
        return time.monotonic() - self.started_monotonic

    @staticmethod
    def _descriptor_action_cost(descriptor: ActionDescriptor) -> int:
        fills = 0
        if descriptor.kind == "form_submit":
            fills = sum(
                field.input_type
                not in {"hidden", "submit", "button", "reset", "password", "file", "image"}
                for field in descriptor.fields
            )
        return 1 + fills

    @classmethod
    def _path_action_cost(cls, path: list[ActionDescriptor]) -> int:
        return sum(cls._descriptor_action_cost(item) for item in path)

    def _fits_action_budget(self, additional_actions: int) -> bool:
        return (
            self.artifact.metrics.browser_actions + additional_actions
            <= self.config.max_browser_actions
        )

    def _replay_candidates(self) -> list[Transition]:
        candidates: list[Transition] = []
        seen_destinations: set[str] = set()
        for transition in self.artifact.transitions:
            if transition.status == EvidenceStatus.REPLAY_VALIDATED:
                continue
            result = self._observation_by_id(transition.result_observation_id or "")
            if result is None:
                continue
            destination = self._replay_destination(transition, result)
            if destination in seen_destinations:
                continue
            seen_destinations.add(destination)
            candidates.append(transition)
        return candidates

    def _current_replay_reserve(self) -> tuple[float, int]:
        if self.config.budget_allocation_strategy == "fixed":
            return self.config.replay_reserve_fraction, 0
        candidates = self._replay_candidates()
        if not candidates:
            return 0.0, 0
        reserve_fraction = min(
            self.config.replay_reserve_fraction,
            max(0.05, 0.025 * len(candidates)),
        )
        action_cap = int(self.config.max_browser_actions * self.config.replay_reserve_fraction)
        estimated_actions = 0
        for transition in sorted(
            candidates,
            key=lambda item: (1 + self._path_action_cost(item.workflow_path), item.id),
        ):
            cost = 1 + self._path_action_cost(transition.workflow_path)
            if estimated_actions + cost > action_cap:
                break
            estimated_actions += cost
        return reserve_fraction, estimated_actions

    def _exploration_deadline(self) -> float:
        reserve_fraction, _ = self._current_replay_reserve()
        return self.config.max_seconds * (1.0 - reserve_fraction)

    def _discovery_http_exhausted(self) -> bool:
        """Exploration ends cleanly once discovery may not send another browser
        request; the remaining requests (if any) belong to verification."""
        if self.http_budget is None or self.http_budget.remaining("browser"):
            return False
        if "HTTP discovery budget exhausted; exploration stopped before replay." not in self.artifact.notes:
            self.artifact.notes.append("HTTP discovery budget exhausted; exploration stopped before replay.")
        return True

    def _fits_exploration_action_budget(self, additional_actions: int) -> bool:
        if self.config.budget_allocation_strategy == "fixed":
            return self._fits_action_budget(additional_actions)
        _, reserve = self._current_replay_reserve()
        return (
            self.artifact.metrics.browser_actions + additional_actions + reserve
            <= self.config.max_browser_actions
        )

    def _next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

    def _navigate_start(
        self,
        session: BrowserSession,
        reason: str,
    ) -> None:
        self.artifact.metrics.browser_actions += session.goto_start()
        self.artifact.metrics.navigation_requests += 1
        self.artifact.metrics.root_reloads += 1
        self._record_navigation_evidence(session, reason)

    def _collect_resource_evidence(self, records: list[ResourceEvidence]) -> None:
        if not records:
            return
        self.artifact.resource_evidence.extend(records)
        self.artifact.metrics.resource_references_discovered = len(
            {item.url for item in self.artifact.resource_evidence if item.url}
        )
        attempts = sum(item.status in {"fetched", "failed"} for item in records)
        self.artifact.metrics.resource_fetches_attempted += attempts
        self.artifact.metrics.resource_fetches_succeeded += sum(item.status == "fetched" for item in records)
        self.artifact.metrics.resource_fetch_failures += sum(item.status == "failed" for item in records)
        self.artifact.metrics.resource_fetch_budget_exhausted += sum(
            item.status == "budget_limited" for item in records
        )
        self.artifact.metrics.resource_fetch_class_budget_exhausted += sum(
            item.status == "class_budget_limited" for item in records
        )
        self.artifact.metrics.resource_new_references += sum(
            item.new_references or 0 for item in records
        )
        self.artifact.metrics.resource_responses_with_body += sum(
            item.new_references is not None for item in records
        )
        self.artifact.metrics.resource_references_extracted += sum(
            item.response_reference_count or 0 for item in records
        )
        self.artifact.metrics.resource_references_queued += sum(
            item.queued_references or 0 for item in records
        )
        self.artifact.metrics.resource_references_excluded += sum(
            item.excluded_references or 0 for item in records
        )
        self.artifact.metrics.resource_unresolved_candidates += sum(
            item.status == "unresolved_candidate" for item in records
        )
        self.artifact.metrics.passive_document_fetches += sum(
            item.status in {"fetched", "failed"} and item.channel == "passive_document" for item in records
        )
        self.artifact.metrics.speculative_fetches += sum(
            item.status in {"fetched", "failed"} and item.channel == "speculative" for item in records
        )
        self.artifact.metrics.observed_only_request_surfaces += sum(
            item.queue_decision.startswith("observed_only_") for item in records
        )

    def _account_readiness(self, readiness: ReadinessEvidence) -> None:
        if not readiness.samples:
            return
        latest = readiness.samples[-1]
        if latest.main_enabled_control_count or latest.script_count:
            self.artifact.metrics.interactive_readiness_wait_ms += readiness.duration_ms
        else:
            self.artifact.metrics.passive_readiness_wait_ms += readiness.duration_ms

    def _record_navigation_evidence(
        self,
        session: BrowserSession,
        reason: str,
    ) -> None:
        if reason == "replay":
            self.artifact.metrics.verification_root_reloads += 1
        elif reason == "history_return":
            self.artifact.metrics.history_returns += 1
        else:
            self.artifact.metrics.discovery_root_reloads += 1
        readiness = session.last_readiness
        if readiness.status in {"blocked", "timeout"}:
            self.artifact.metrics.startup_readiness_failures += 1
        network = list(session.last_navigation_network)
        self.artifact.metrics.navigation_network_events_recorded += len(network)
        self.artifact.metrics.observed_http_requests += len(network)
        self._account_readiness(readiness)
        self._collect_resource_evidence(session.last_navigation_resources)
        self.artifact.navigation_evidence.append(
            NavigationEvidence(
                id="nav_"
                + digest(
                    [self.run_id, reason, len(self.artifact.navigation_evidence), session.page.url],
                    20,
                ),
                reason=reason,
                url=sanitize_url(session.page.url),
                readiness=readiness,
                network=network,
            )
        )

    def _validate_target(self) -> None:
        parsed = urlsplit(self.config.start_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("target must use HTTP or HTTPS")
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Agent 1 defaults to explicitly configured loopback targets only")

    def run(self) -> RunArtifact:
        self._validate_target()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.config.zap_evidence_path and not self.config.resume_from:
            records, rejected, requests, elapsed = load_zap_evidence(
                self.config.zap_evidence_path, self.config.zap_source_origin or "", self.config.start_url
            )
            if self.http_budget is not None:
                self.http_budget.charge_external(requests, "zap_traditional_spider")
            self.artifact.external_discoveries = records
            self.artifact.metrics.external_discovery_records = len(records)
            self.artifact.metrics.external_discovery_rejected = rejected
            self.artifact.metrics.external_request_upper_bound = requests
            self.artifact.metrics.external_elapsed_seconds = elapsed
            self.artifact.notes.append("ZAP evidence is externally reported and does not prove a UI transition or replay.")
            for item in records:
                if (item.method == "GET" and item.http_status is not None and 200 <= item.http_status < 300
                        and not item.parameter_names and not DANGEROUS_ACTION.search(urlsplit(item.mapped_url).path)):
                    self.resource_spider.seed_external(item.mapped_url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.config.headless)
            self.artifact.browser_version = f"chromium {browser.version}"
            try:
                if self.config.resume_from:
                    self._load_checkpoint(self.config.resume_from)
                    if self.resource_spider:
                        self.resource_spider.restore_from_evidence(
                            [item.model_dump(mode="json") for item in self.artifact.resource_evidence]
                        )
                else:
                    self._initialize(browser)
                self._explore(browser)
                self._replay(browser)
            finally:
                browser.close()
        self._finalize()
        self.save_checkpoint()
        return self.artifact

    def _initialize(self, browser: Browser) -> None:
        with self._browser_session(browser) as session:
            self._navigate_start(session, "initial")
            observation = session.observe(self._next_sequence())
        self._record_observation(observation, [])
        self._enqueue(observation, [])
        self.save_checkpoint()

    def _record_observation(self, observation: Observation, path: list[ActionDescriptor]) -> None:
        if observation.id not in self._observation_ids:
            self.artifact.observations.append(observation)
            self._observation_ids.add(observation.id)
        members = self.artifact.state_groups.setdefault(observation.group_signature, [])
        if observation.id not in members:
            members.append(observation.id)
        current = self.artifact.return_paths.get(observation.group_signature)
        if current is None or len(path) < len(current):
            self.artifact.return_paths[observation.group_signature] = list(path)
        behavior = observation.behavior_signature
        if behavior and behavior != observation.group_signature:
            # Same visible DOM, evidenced different handler behavior: the way
            # back must re-create that behavior, so it is kept separately.
            current = self.artifact.return_paths.get(behavior)
            if current is None or len(path) < len(current):
                self.artifact.return_paths[behavior] = list(path)
        existing_ads = {
            (item.source_observation_id, item.control.id) for item in self.artifact.advertisements
        }
        for control in observation.controls:
            key = (observation.id, control.id)
            if key not in existing_ads:
                self.artifact.advertisements.append(
                    Advertisement(
                        source_observation_id=observation.id,
                        source_group_signature=observation.group_signature,
                        control=control,
                    )
                )

    def _decision_order(self, observation: Observation) -> list[str]:
        safe = [control for control in observation.controls if control.safe]
        deterministic = sorted(
            safe,
            key=lambda control: (
                {"form_submit": 3, "button": 2, "link": 1}[control.kind],
                not AMBIGUOUS_LABEL.match(control.label),
                control.label.lower(),
            ),
            reverse=True,
        )
        should_ask = self.config.policy == "model_all" or (
            self.config.policy == "selective_model"
            and any(AMBIGUOUS_LABEL.match(control.label) or control.kind == "form_submit" for control in safe)
        )
        if not should_ask:
            return [control.id for control in deterministic]
        try:
            decision = self.provider.decide(observation)
            if not decision.cached:
                self.artifact.metrics.model_calls += 1
                self.artifact.metrics.model_input_tokens += decision.input_tokens
                self.artifact.metrics.model_output_tokens += decision.output_tokens
                self.artifact.metrics.monetary_cost_usd += decision.cost_usd
            self.model_labels.update(decision.labels)
            model_order = decision.ordered_control_ids
            return model_order + [control.id for control in deterministic if control.id not in model_order]
        except Exception as exc:  # Keep the deterministic mapper available when models fail.
            self.artifact.metrics.model_calls += 1
            self.artifact.metrics.model_failures += 1
            if isinstance(exc, ModelProviderError):
                self.artifact.metrics.model_input_tokens += exc.input_tokens
                self.artifact.metrics.model_output_tokens += exc.output_tokens
            self.artifact.notes.append(
                f"Model decision failed for {observation.id}: {type(exc).__name__}; deterministic order used."
            )
            return [control.id for control in deterministic]

    def _enqueue(self, observation: Observation, path: list[ActionDescriptor]) -> None:
        controls = {control.id: control for control in observation.controls}
        order = self._decision_order(observation)
        for rank, control_id in enumerate(order):
            control = controls.get(control_id)
            if not control or not control.safe:
                continue
            identity = (
                observation.state_signature if self.config.policy == "exact" else observation.group_signature
            )
            tried_key = f"{identity}:{control.signature}"
            if control.behavior_revision:
                # Evidence that this control's handler changed: the old action
                # is not a reason to suppress the new behavior.
                tried_key += f"@{control.behavior_revision}"
            if tried_key in self.tried:
                continue
            global_component = bool(
                re.match(r"^(nav|header|footer|aside)(?::|$)", control.component, re.I)
                or ":navigation" in control.component.lower()
            )
            global_key = digest(
                [control.interaction, control.target or "", control.role, control.label], 20
            )
            repeated_view_action = control.interaction in {
                "scroll_viewport", "scroll_container"
            }
            if repeated_view_action:
                global_key = digest(
                    [observation.route_pattern, control.interaction, control.component], 20
                )
            if (
                self.config.policy in {"multidimensional", "hierarchical"}
                and (global_component or repeated_view_action)
                and global_key in self._scheduled_global_actions
            ):
                self.artifact.metrics.duplicate_controls_suppressed += 1
                self.tried.add(tried_key)
                continue
            self.tried.add(tried_key)
            if global_component or repeated_view_action:
                self._scheduled_global_actions.add(global_key)
            kind_score = {"form_submit": 3.0, "button": 2.0, "link": 1.0}[control.kind]
            shape_key = control.signature + (f"@{control.behavior_revision}" if control.behavior_revision else "")
            globally_novel = shape_key not in self._seen_control_shapes
            self._seen_control_shapes.add(shape_key)
            if self.config.policy == "coverage":
                # Event-flow novelty: branch on a newly observed control before
                # repeating shared chrome. A small depth cost accounts for the
                # browser actions required to restore an archived path.
                kind_score += 12.0 if globally_novel else 0.0
                kind_score -= 0.20 * len(path)
            if self.config.policy in {"multidimensional", "hierarchical"}:
                target_key = control.target or ""
                target_novel = bool(target_key and target_key not in self._seen_targets)
                component_key = f"{control.component}:{control.role}:{control.label}" + (
                    f"@{control.behavior_revision}" if control.behavior_revision else "")
                component_novel = component_key not in self._seen_components
                form_shape = digest(
                    [
                        control.method or "",
                        control.target or "",
                        [(field.input_type, field.name, field.required) for field in control.fields],
                    ],
                    20,
                )
                form_novel = bool(control.fields and form_shape not in self._seen_form_shapes)
                dynamic = control.interaction not in {"click", "navigate"}
                kind_score += 15.0 if target_novel else 0.0
                kind_score += 8.0 if component_novel else 0.0
                kind_score += 12.0 if form_novel else 0.0
                kind_score += 10.0 if dynamic else 0.0
                kind_score += 5.0 if globally_novel else 0.0
                kind_score -= 0.6 * len(path)
                kind_score -= 8.0 * self._ineffective_actions[control.signature]
                if global_component and not target_novel:
                    kind_score -= 10.0
                if global_component:
                    kind_score -= 18.0
                if control.kind == "link" and LOW_VALUE_REPORT.match(control.label):
                    kind_score -= 28.0
                if target_key:
                    self._seen_targets.add(target_key)
                self._seen_components.add(component_key)
                if control.fields:
                    self._seen_form_shapes.add(form_shape)
            if self.config.search_probe_primary and (
                is_get_search_action(control)
                or SEARCH_SEMANTICS.search(f"{control.label} {control.target or ''}")
            ):
                kind_score += 20.0
            if self.config.focus_query:
                haystack = f"{control.label} {control.target or ''}".lower()
                if self.config.focus_query.lower() in haystack:
                    kind_score += 10.0
            self.frontier.append(
                FrontierItem(
                    source_observation_id=observation.id,
                    expected_source_signature=observation.state_signature,
                    expected_source_group=observation.group_signature,
                    path=list(path),
                    action=BrowserSession.descriptor(control),
                    priority=kind_score - rank / max(1, len(order)),
                )
            )
        self._sort_frontier()

    def _sort_frontier(self) -> None:
        if self.config.policy in {"coverage", "multidimensional", "hierarchical"}:
            self.frontier.sort(
                key=lambda item: (-item.priority, len(item.path), item.action.signature)
            )
            return
        if self.config.policy == "breadth":
            self.frontier.sort(key=lambda item: (len(item.path), item.action.signature))
            return
        self.frontier.sort(
            key=lambda item: (
                item.priority < 10.0,
                len(item.path),
                -item.priority,
                item.action.signature,
            )
        )

    def _explore(self, browser: Browser) -> None:
        if self.config.exploration_mode == "persistent":
            self._explore_persistent(browser)
            return
        while self.frontier:
            if self._elapsed() >= self._exploration_deadline():
                break
            if len(self.artifact.transitions) >= self.config.max_transitions:
                break
            if self._discovery_http_exhausted():
                break
            if self.artifact.metrics.browser_actions >= self.config.max_browser_actions:
                break
            item = self.frontier.pop(0)
            if not self._fits_exploration_action_budget(
                1 + self._path_action_cost(item.path) + self._descriptor_action_cost(item.action)
            ):
                self.frontier.insert(0, item)
                break
            self._attempt_frontier(browser, item)
            self.save_checkpoint()

    def _explore_persistent(self, browser: Browser) -> None:
        planner = (AreaTourPlanner(prefix_reuse=self.config.state_reuse == "prefix")
                   if self.config.policy == "hierarchical" else None)
        with self._browser_session(browser) as session:
            self._navigate_start(session, "persistent_restore")
            live = session.observe(self._next_sequence())
            live_path: list[ActionDescriptor] = []
            burst_group = live.group_signature
            local_burst = 0
            self._record_observation(live, [])
            self._enqueue(live, [])
            while self.frontier:
                if self._elapsed() >= self._exploration_deadline():
                    break
                if len(self.artifact.transitions) >= self.config.max_transitions:
                    break
                if self._discovery_http_exhausted():
                    break
                if self.artifact.metrics.browser_actions >= self.config.max_browser_actions:
                    break
                if live.group_signature != burst_group:
                    burst_group = live.group_signature
                    local_burst = 0
                local_index = None
                selected_index = None
                if planner:
                    selected_index = planner.choose(
                        self.frontier,
                        {item.id: item for item in self.artifact.observations},
                        live, live_path,
                    )
                    candidate = self.frontier[selected_index]
                    if (candidate.expected_source_group == live.group_signature
                            and session.find_current(live, candidate.action) is not None):
                        local_index = selected_index
                elif local_burst < 8:
                    local_index = next(
                        (
                            index
                            for index, candidate in enumerate(self.frontier)
                            if candidate.expected_source_group == live.group_signature
                            and session.find_current(live, candidate.action) is not None
                        ),
                        None,
                    )
                chosen_index = selected_index if selected_index is not None else (local_index if local_index is not None else 0)
                item = self.frontier.pop(chosen_index)
                local = local_index is not None
                local_burst = local_burst + 1 if local else 0
                required_actions = self._descriptor_action_cost(item.action)
                if not local:
                    required_actions += 1 + self._path_action_cost(item.path)
                if not self._fits_exploration_action_budget(required_actions):
                    self.frontier.insert(chosen_index, item)
                    break
                updated = self._attempt_frontier(
                    browser,
                    item,
                    persistent_session=session,
                    live_source=live,
                    live_path=live_path,
                )
                if updated is None:
                    self.artifact.metrics.live_state_stale += 1
                    if self._discovery_http_exhausted():
                        break
                    self._navigate_start(session, "persistent_restore")
                    live = session.observe(self._next_sequence())
                    live_path = []
                else:
                    live, observed_path = updated
                    live_path = list(
                        self.artifact.return_paths.get(live.behavior_signature or live.group_signature, observed_path)
                    )
                self.save_checkpoint()

    def _attempt_frontier(
        self,
        browser: Browser,
        item: FrontierItem,
        *,
        persistent_session: BrowserSession | None = None,
        live_source: Observation | None = None,
        live_path: list[ActionDescriptor] | None = None,
    ) -> tuple[Observation, list[ActionDescriptor]] | None:
        started_at = utc_now()
        self.artifact.metrics.transitions_attempted += 1
        manager = (
            nullcontext(persistent_session)
            if persistent_session is not None
            else self._browser_session(browser)
        )
        with manager as session:
            prerequisite_network: list[PrerequisiteStepEvidence] = []
            restoration_attempted = False
            reused_prefix_steps = 0
            action_network: list[NetworkEvent] = []
            try:
                expected_observation = self._observation_by_id(item.source_observation_id)
                expected = (
                    item.expected_source_signature
                    if self.config.policy == "exact"
                    else item.expected_source_group
                )
                live_actual = None
                if live_source is not None:
                    live_actual = (
                        live_source.state_signature
                        if self.config.policy == "exact"
                        else live_source.group_signature
                    )
                current_live_control = (
                    session.find_current(live_source, item.action)
                    if live_source is not None
                    else None
                )
                if live_source is not None and live_actual == expected and current_live_control:
                    source = live_source
                    source_path = list(live_path if live_path is not None else item.path)
                    self.artifact.metrics.live_state_reuses += 1
                elif (prefix := self._reusable_live_prefix(item, live_source, live_path, expected_observation,
                                                          persistent_session is not None)) is not None:
                    # TimeMachine-style reuse: the live page is the verified end of a
                    # prefix of this item's return path, so only the suffix is executed.
                    # The final source signature is still verified below.
                    restoration_attempted = True
                    reused_prefix_steps = prefix
                    self.artifact.metrics.prefix_state_reuses += 1
                    self.artifact.metrics.root_reloads_avoided += 1
                    source = self._restore(session, item.path[prefix:], prerequisite_network, start_index=prefix)
                    source_path = list(item.path)
                elif (parent := self._history_return(session, item, live_source, live_path,
                                                     expected_observation, persistent_session is not None)) is not None:
                    # Verified one-step history return to the live parent, then the suffix.
                    restoration_attempted = True
                    reused_prefix_steps = len(parent[1])
                    self.artifact.metrics.root_reloads_avoided += 1
                    source = self._restore(session, item.path[len(parent[1]):], prerequisite_network,
                                           start_index=len(parent[1]), initial=parent[0])
                    source_path = list(item.path)
                else:
                    reason = "persistent_restore" if persistent_session is not None else "frontier_restore"
                    if (
                        persistent_session is not None
                        and live_source is not None
                        and expected_observation is not None
                        and live_source.session_markers
                        != expected_observation.session_markers
                    ):
                        session.reset_context()
                    self._navigate_start(session, reason)
                    restoration_attempted = True
                    source = self._restore(session, item.path, prerequisite_network)
                    source_path = list(item.path)
                actual = source.state_signature if self.config.policy == "exact" else source.group_signature
                self._record_observation(source, source_path)
                search_related = bool(self.config.search_probe_primary) and (
                    is_get_search_action(item.action)
                    or SEARCH_SEMANTICS.search(f"{item.action.label} {item.action.target or ''}")
                    or any(
                        is_get_search_action(descriptor)
                        or SEARCH_SEMANTICS.search(
                            f"{descriptor.label} {descriptor.target or ''}"
                        )
                        for descriptor in item.path
                    )
                )
                if actual != expected:
                    usable = bool(expected_observation) and self._usable_return_screen(
                        expected_observation, source
                    )
                    if not ((search_related or self.config.robust_readiness) and usable):
                        raise RuntimeError(
                            f"saved return path restored {actual}, expected {expected}"
                        )
                    self.artifact.notes.append(
                        "Restoration content signature differed, but the independently compared "
                        f"interaction shape remained usable for {item.action.signature}."
                    )
                current_control = session.find_current(source, item.action)
                if current_control is None:
                    raise RuntimeError("registered control was not present in the current observation")
                descriptors: list[ActionDescriptor] = []
                form_attempts: list[FormAttempt] = []
                descriptor = BrowserSession.descriptor(current_control)
                plan_values, plan_ref = self._propose_form_plan(source, descriptor, [])
                descriptor.input_plan_ref = plan_ref
                descriptors.append(descriptor)
                input_refs, network, dialogs, action_count = session.execute(
                    current_control, plan_values, plan_ref
                )
                action_network.extend(network)
                self.artifact.metrics.browser_actions += action_count
                self.artifact.metrics.observed_http_requests += len(network)
                self._account_readiness(session.last_readiness)
                self._collect_resource_evidence(session.last_action_resources)
                if current_control.interaction == "navigate":
                    self.artifact.metrics.static_navigation_actions += 1
                elif current_control.interaction not in {"click"}:
                    self.artifact.metrics.dynamic_interaction_actions += 1
                if current_control.frame_index > 0:
                    self.artifact.metrics.frame_observations += 1
                if session.last_popup_opened:
                    self.artifact.metrics.popup_navigations += 1
                result = session.observe(self._next_sequence())
                source_controls = sorted(
                    (control.signature, control.interaction)
                    for control in source.controls if control.safe
                )
                result_controls = sorted(
                    (control.signature, control.interaction)
                    for control in result.controls if control.safe
                )
                ineffective = (
                    source.url == result.url
                    and source.content_fingerprint == result.content_fingerprint
                    and source_controls == result_controls
                    and not network
                    and not dialogs
                )
                if ineffective:
                    self.artifact.metrics.ineffective_transitions += 1
                    self._ineffective_actions[current_control.signature] += 1
                if current_control.kind == "form_submit":
                    form_attempts.append(
                        FormAttempt(
                            attempt_index=0,
                            input_references=input_refs,
                            outcome_signals=result.outcome_signals,
                            status=self._classify_result(current_control.kind, result),
                            input_plan_ref=plan_ref,
                        )
                    )
                retry_count = 0
                while (
                    current_control.kind == "form_submit"
                    and self.config.model_form_assistance
                    and retry_count < self.config.max_form_retries
                    and any(item.kind == "validation_error" for item in result.outcome_signals)
                ):
                    retry_control = session.find_current(result, descriptor)
                    if retry_control is None:
                        break
                    retry_descriptor = BrowserSession.descriptor(retry_control)
                    retry_values, retry_ref = self._propose_form_plan(
                        result, retry_descriptor, result.outcome_signals
                    )
                    if not retry_values or retry_ref == plan_ref:
                        break
                    retry_descriptor.input_plan_ref = retry_ref
                    descriptors.append(retry_descriptor)
                    retry_refs, retry_network, retry_dialogs, retry_actions = session.execute(
                        retry_control, retry_values, retry_ref
                    )
                    action_network.extend(retry_network)
                    self.artifact.metrics.browser_actions += retry_actions
                    self.artifact.metrics.observed_http_requests += len(retry_network)
                    self._account_readiness(session.last_readiness)
                    self._collect_resource_evidence(session.last_action_resources)
                    input_refs.extend(retry_refs)
                    network.extend(retry_network)
                    dialogs.extend(retry_dialogs)
                    result = session.observe(self._next_sequence())
                    retry_count += 1
                    form_attempts.append(
                        FormAttempt(
                            attempt_index=retry_count,
                            input_references=retry_refs,
                            outcome_signals=result.outcome_signals,
                            status=self._classify_result(retry_control.kind, result),
                            input_plan_ref=retry_ref,
                        )
                    )
                workflow_path = source_path + descriptors
                self._record_observation(result, workflow_path)
                transition = Transition(
                    id="tr_" + digest([self.run_id, source.id, current_control.id, result.id], 20),
                    source_observation_id=source.id,
                    source_state_signature=source.state_signature,
                    source_group_signature=source.group_signature,
                    action=descriptors[0],
                    workflow_path=workflow_path,
                    input_references=input_refs,
                    form_attempts=form_attempts,
                    result_observation_id=result.id,
                    result_state_signature=result.state_signature,
                    result_group_signature=result.group_signature,
                    status=EvidenceStatus.OBSERVED,
                    network=action_network,
                    restoration_attempted=restoration_attempted,
                    reused_prefix_steps=reused_prefix_steps,
                    prerequisite_network=prerequisite_network,
                    dialogs=dialogs,
                    started_at=started_at,
                    ended_at=utc_now(),
                    run_id=self.run_id,
                )
                self.artifact.transitions.append(transition)
                self.artifact.metrics.transitions_observed += 1
                self._enqueue(result, workflow_path)
                self._record_progress()
                return result, workflow_path
            except Exception as exc:
                transition = Transition(
                    id="tr_" + digest([self.run_id, item.source_observation_id, item.action.signature, started_at], 20),
                    source_observation_id=item.source_observation_id,
                    source_state_signature=item.expected_source_signature,
                    source_group_signature=item.expected_source_group,
                    action=item.action,
                    workflow_path=list(item.path) + [item.action],
                    status=EvidenceStatus.FAILED,
                    network=action_network,
                    restoration_attempted=restoration_attempted,
                    reused_prefix_steps=reused_prefix_steps,
                    prerequisite_network=prerequisite_network,
                    error=f"{type(exc).__name__}: {compact_text(str(exc), 300)}",
                    started_at=started_at,
                    ended_at=utc_now(),
                    run_id=self.run_id,
                )
                self.artifact.transitions.append(transition)
                self.artifact.metrics.transitions_failed += 1
                self._record_progress()
                return None

    def _propose_form_plan(
        self,
        observation: Observation,
        descriptor: ActionDescriptor,
        feedback: list[OutcomeSignal],
    ) -> tuple[dict[str, str], str | None]:
        field = search_field(descriptor)
        if field and self.config.search_probe_primary:
            values = {field.id: self.config.search_probe_primary}
            plan_ref = self.provider.store_form_plan(values, "search-primary-v1")
            return values, plan_ref
        if not self.config.model_form_assistance or descriptor.kind != "form_submit":
            return {}, None
        try:
            proposal = self.provider.propose_form(observation, descriptor, feedback)
            if not proposal.cached:
                self.artifact.metrics.model_calls += 1
                self.artifact.metrics.model_input_tokens += proposal.input_tokens
                self.artifact.metrics.model_output_tokens += proposal.output_tokens
                self.artifact.metrics.monetary_cost_usd += proposal.cost_usd
            if not proposal.values:
                self.artifact.notes.append(
                    f"Model form proposal for {descriptor.control_id} supplied no valid current field IDs; "
                    f"rejected IDs: {len(proposal.rejected_field_ids)}."
                )
            return proposal.values, proposal.plan_ref or None
        except Exception as exc:
            self.artifact.metrics.model_calls += 1
            self.artifact.metrics.model_failures += 1
            if isinstance(exc, ModelProviderError):
                self.artifact.metrics.model_input_tokens += exc.input_tokens
                self.artifact.metrics.model_output_tokens += exc.output_tokens
            self.artifact.notes.append(
                f"Model form proposal failed for {descriptor.control_id}: {type(exc).__name__}; "
                "deterministic values used."
            )
            return {}, None

    def _resolve_form_plan(self, descriptor: ActionDescriptor) -> dict[str, str]:
        plan = self.provider.resolve_form_plan(descriptor.input_plan_ref)
        field = search_field(descriptor)
        if descriptor.input_plan_ref and not plan:
            raise RuntimeError("referenced input plan is missing from the protected cache")
        if field and self.config.search_probe_primary:
            if not descriptor.input_plan_ref or field.id not in plan:
                raise RuntimeError("configured search replay requires its exact protected input plan")
        return plan

    @staticmethod
    def _usable_return_screen(expected: Observation, actual: Observation) -> bool:
        """Match interaction affordances for restoration without validating action outcomes."""

        def shape(observation: Observation) -> dict[str, Any]:
            return {
                "route": observation.route_pattern,
                "session": observation.session_context,
                "session_markers": observation.session_markers,
                "forms": [
                    {
                        "method": form.method,
                        "action": form.action,
                        "fields": [
                            (field.name, field.input_type, field.required) for field in form.fields
                        ],
                    }
                    for form in observation.forms
                ],
                "controls": sorted(
                    group_control_signature(control)
                    for control in observation.controls
                    if control.safe and not VOLATILE_CONTROL.match(control.label)
                ),
            }

        return shape(expected) == shape(actual)

    def _reusable_live_prefix(
        self,
        item: FrontierItem,
        live_source: Observation | None,
        live_path: list[ActionDescriptor] | None,
        expected_observation: Observation | None,
        persistent: bool,
    ) -> int | None:
        """Length of the live return path when it is a strict prefix of ``item.path``.

        Reuse requires the same session markers as the item's source, so record
        and session identities are never crossed; cookies or storage are not
        assumed to restore server state because the prefix is still live.
        """
        if (self.config.state_reuse != "prefix" or not persistent or live_source is None
                or live_path is None or expected_observation is None
                or live_source.session_markers != expected_observation.session_markers
                or len(live_path) >= len(item.path)):
            return None
        if [step.signature for step in item.path[:len(live_path)]] != [step.signature for step in live_path]:
            return None
        return len(live_path)

    def _history_return(
        self,
        session: BrowserSession,
        item: FrontierItem,
        live_source: Observation | None,
        live_path: list[ActionDescriptor] | None,
        expected_observation: Observation | None,
        persistent: bool,
    ) -> tuple[Observation, list[ActionDescriptor]] | None:
        """Return to the live state's parent with one history step when it is a prefix of ``item.path``.

        Only an undo of a plain, input-free navigate/click is attempted, inside
        the same context and session markers. The parent is accepted only if the
        next required control (or the item's own control) is present; otherwise
        the caller falls back to a root reload. Server state is never assumed:
        the page is re-observed and the final source signature is still checked.
        """
        if (self.config.state_reuse != "prefix" or not persistent or live_source is None
                or not live_path or expected_observation is None
                or live_source.session_markers != expected_observation.session_markers):
            return None
        parent_path = live_path[:-1]
        undone = live_path[-1]
        if (undone.interaction not in {"navigate", "click"} or undone.input_plan_ref or undone.fields
                or len(parent_path) > len(item.path)
                or [s.signature for s in item.path[:len(parent_path)]] != [s.signature for s in parent_path]):
            return None
        self.artifact.metrics.history_return_attempts += 1
        if not session.go_back():
            return None
        self.artifact.metrics.browser_actions += 1
        self.artifact.metrics.restoration_actions += 1
        self._record_navigation_evidence(session, "history_return")
        observation = session.observe(self._next_sequence())
        needed = item.path[len(parent_path)] if len(item.path) > len(parent_path) else item.action
        if session.find_current(observation, needed) is None:
            self.artifact.metrics.history_return_rejected += 1
            return None
        return observation, parent_path

    def _restore(
        self,
        session: BrowserSession,
        path: list[ActionDescriptor],
        network_evidence: list[PrerequisiteStepEvidence],
        start_index: int = 0,
        initial: Observation | None = None,
    ) -> Observation:
        observation = initial or session.observe(self._next_sequence())
        for step_index, descriptor in enumerate(path, start=start_index):
            control = session.find_current(observation, descriptor)
            if control is None:
                raise RuntimeError(f"return-path control missing: {descriptor.signature}")
            plan = self._resolve_form_plan(descriptor)
            _, network, _, count = session.execute(control, plan, descriptor.input_plan_ref)
            network_evidence.append(
                PrerequisiteStepEvidence(
                    step_index=step_index,
                    action_signature=descriptor.signature,
                    action_label=descriptor.label,
                    network=network,
                )
            )
            self.artifact.metrics.browser_actions += count
            self.artifact.metrics.restoration_actions += count
            self.artifact.metrics.observed_http_requests += len(network)
            self._account_readiness(session.last_readiness)
            self._collect_resource_evidence(session.last_action_resources)
            observation = session.observe(self._next_sequence())
        return observation

    def _replay(self, browser: Browser) -> None:
        if self.http_budget is not None:
            self.http_budget.phase = "verification"
        raw_candidates = [
            transition for transition in self.artifact.transitions if transition.status == EvidenceStatus.OBSERVED
        ]
        raw_candidates.sort(key=lambda transition: (len(transition.workflow_path), transition.id))
        candidates: list[Transition] = []
        scheduled_destinations: set[str] = set()
        for transition in raw_candidates:
            result = self._observation_by_id(transition.result_observation_id)
            if not result:
                continue
            key = self._replay_destination(transition, result)
            if key in scheduled_destinations:
                continue
            scheduled_destinations.add(key)
            candidates.append(transition)
        if self.config.replay_policy == "diverse":
            candidates = self._diverse_replay_order(candidates)
        else:
            candidates.sort(key=lambda transition: (len(transition.workflow_path), transition.id))
        for transition in candidates:
            if self._elapsed() >= self.config.max_seconds:
                break
            if self.artifact.metrics.browser_actions >= self.config.max_browser_actions:
                break
            if self.http_budget is not None and not self.http_budget.remaining("browser"):
                # A replay that cannot be sent is untested, not failed.
                self.artifact.notes.append("HTTP verification budget exhausted; remaining transitions left untested.")
                break
            paired_search = bool(self.config.search_probe_primary) and is_get_search_action(
                transition.action
            )
            required_replays = 2 if paired_search else 1
            completed: list[ReplayResult] = []
            for pair_index in range(required_replays):
                if self._elapsed() >= self.config.max_seconds:
                    break
                if self.artifact.metrics.browser_actions >= self.config.max_browser_actions:
                    break
                path_cost = 1 + self._path_action_cost(transition.workflow_path)
                if paired_search:
                    path_cost *= 2
                if not self._fits_action_budget(path_cost):
                    break
                replay = (
                    self._replay_search_transition(browser, transition, pair_index)
                    if paired_search
                    else self._replay_transition(browser, transition)
                )
                if replay.status == EvidenceStatus.NOT_TESTED:
                    self.artifact.metrics.replays_untested_http_budget += 1
                    break
                completed.append(replay)
                self.artifact.replays.append(replay)
                self.artifact.metrics.replay_success_denominator += 1
                if replay.status == EvidenceStatus.REPLAY_VALIDATED:
                    self.artifact.metrics.replay_success_numerator += 1
            if len(completed) == required_replays and all(
                replay.status == EvidenceStatus.REPLAY_VALIDATED for replay in completed
            ):
                transition.status = EvidenceStatus.REPLAY_VALIDATED
            self._record_progress()
            self.save_checkpoint()

    @staticmethod
    def _replay_destination(transition: Transition, result: Observation) -> str:
        """Replay de-duplication key. A transition whose only effect is a
        request (same visible DOM), or that exercised a revised handler, is a
        different workflow from another action ending on the same screen."""
        parts: list[Any] = [result.url, result.group_signature, transition.action.interaction]
        if transition.action.behavior_revision:
            parts.append(transition.action.behavior_revision)
        structures = action_request_structures(transition.network)
        if structures and transition.source_group_signature == transition.result_group_signature:
            parts.append(sorted(structures))
        return digest(parts, 24)

    def _diverse_replay_order(self, candidates: list[Transition]) -> list[Transition]:
        """Greedily cover distinct routes/actions/requests/contexts per replay cost."""
        remaining = list(candidates)
        selected: list[Transition] = []
        seen_routes: set[str] = set()
        seen_actions: set[str] = set()
        seen_requests: set[str] = set()
        seen_contexts: set[str] = set()
        seen_groups: set[str] = set()
        observations = {item.id: item for item in self.artifact.observations}
        while remaining:
            ranked: list[tuple[float, int, str, Transition, tuple[str, str, str, str, str]]] = []
            for transition in remaining:
                result = observations.get(transition.result_observation_id or "")
                route = result.route_pattern if result else ""
                action = f"{transition.action.kind}:{transition.action.interaction}"
                request_shape = digest(
                    sorted(
                        (event.method, event.resource_type or "", event.parameter_names)
                        for event in transition.network
                    ),
                    16,
                ) if transition.network else "none"
                context = digest(
                    [result.session_context, sorted(result.session_markers)] if result else "unknown",
                    16,
                )
                group = transition.result_group_signature or ""
                novel = (
                    (2.0 if route and route not in seen_routes else 0.0)
                    + (1.5 if action not in seen_actions else 0.0)
                    + (1.5 if request_shape != "none" and request_shape not in seen_requests else 0.0)
                    + (1.0 if context not in seen_contexts else 0.0)
                    + (0.75 if group and group not in seen_groups else 0.0)
                )
                cost = 1 + self._path_action_cost(transition.workflow_path)
                # A small floor prevents known deep paths from being starved
                # after all shallow novelty has been exhausted.
                score = novel / cost + (0.15 if len(transition.workflow_path) >= 3 else 0.0)
                ranked.append((score, -cost, transition.id, transition, (route, action, request_shape, context, group)))
            _, _, _, chosen, features = max(ranked, key=lambda item: (item[0], item[1], item[2]))
            selected.append(chosen)
            remaining.remove(chosen)
            route, action, request_shape, context, group = features
            if route:
                seen_routes.add(route)
            seen_actions.add(action)
            if request_shape != "none":
                seen_requests.add(request_shape)
            seen_contexts.add(context)
            if group:
                seen_groups.add(group)
        return selected

    def _execute_replay_path(
        self,
        session: BrowserSession,
        path: list[ActionDescriptor],
    ) -> tuple[Observation, int, list[Observation], list[NetworkEvent]]:
        observation = session.observe(self._next_sequence())
        observations = [observation]
        browser_actions = 0
        network_events: list[NetworkEvent] = []
        for descriptor in path:
            control = session.find_current(observation, descriptor)
            if control is None:
                raise RuntimeError(f"replay control missing: {descriptor.signature}")
            plan = self._resolve_form_plan(descriptor)
            _, network, _, count = session.execute(control, plan, descriptor.input_plan_ref)
            browser_actions += count
            network_events.extend(network)
            self.artifact.metrics.observed_http_requests += len(network)
            self._account_readiness(session.last_readiness)
            self._collect_resource_evidence(session.last_action_resources)
            observation = session.observe(self._next_sequence())
            observations.append(observation)
        return observation, browser_actions, observations, network_events

    def _replay_search_transition(
        self,
        browser: Browser,
        transition: Transition,
        pair_index: int,
    ) -> ReplayResult:
        replay_id = "replay_" + digest([transition.id, "paired_search", pair_index], 20)
        started_at = utc_now()
        browser_actions = 0
        checks: dict[str, bool] = {}
        functional_checks: dict[str, bool] = {}
        verification_evidence: dict[str, Any] = {}
        verification_ids: list[str] = []
        input_plan_refs: list[str] = []
        replay_network: list[NetworkEvent] = []
        try:
            primary = self.config.search_probe_primary
            contrast = self.config.search_probe_contrast
            if not primary or not contrast:
                raise RuntimeError("paired search probes are not configured")
            final = transition.workflow_path[-1]
            field = search_field(final)
            if field is None:
                raise RuntimeError("search transition no longer has one eligible observed field")
            primary_plan = self._resolve_form_plan(final)
            if primary_plan.get(field.id) != primary:
                raise RuntimeError("primary protected input plan does not match the configured probe")
            contrast_ref = self.provider.store_form_plan(
                {field.id: contrast}, "search-contrast-v1"
            )
            contrast_final = final.model_copy(update={"input_plan_ref": contrast_ref})
            contrast_path = list(transition.workflow_path[:-1]) + [contrast_final]
            input_plan_refs = [final.input_plan_ref or "", contrast_ref]
            with self._browser_session(browser) as session:
                browser_actions += session.goto_start()
                self.artifact.metrics.navigation_requests += 1
                self.artifact.metrics.root_reloads += 1
                self._record_navigation_evidence(session, "replay")
                primary_result, count, primary_path_observations, primary_network = self._execute_replay_path(
                    session, transition.workflow_path
                )
                browser_actions += count
                browser_actions += session.goto_start()
                self.artifact.metrics.navigation_requests += 1
                self.artifact.metrics.root_reloads += 1
                self._record_navigation_evidence(session, "replay")
                contrast_result, count, contrast_path_observations, contrast_network = self._execute_replay_path(
                    session, contrast_path
                )
                browser_actions += count
                replay_network = primary_network + contrast_network
            expected = self._observation_by_id(transition.result_observation_id)
            checks = {
                "group_signature": bool(expected)
                and primary_result.group_signature == transition.result_group_signature,
                "route_pattern": bool(expected)
                and primary_result.route_pattern == expected.route_pattern,
                "title": bool(expected)
                and normalize_instance_text(primary_result.title)
                == normalize_instance_text(expected.title),
                "content_fingerprint": bool(expected)
                and primary_result.content_fingerprint == expected.content_fingerprint,
                "outcome_signals": bool(expected)
                and outcome_signature(primary_result.outcome_signals)
                == outcome_signature(expected.outcome_signals),
            }
            primary_before = primary_path_observations[-2]
            contrast_before = contrast_path_observations[-2]
            primary_links = introduced_links(primary_before, primary_result)
            contrast_links = introduced_links(contrast_before, contrast_result)
            primary_targets = sorted({item["target"] for item in primary_links})
            contrast_targets = sorted({item["target"] for item in contrast_links})
            primary_only_targets = sorted(set(primary_targets) - set(contrast_targets))
            contrast_only_targets = sorted(set(contrast_targets) - set(primary_targets))
            primary_baseline_targets = sorted(
                {item["target"] for item in observable_links(primary_before)}
            )
            contrast_baseline_targets = sorted(
                {item["target"] for item in observable_links(contrast_before)}
            )
            functional_checks = {
                "baseline_link_targets_match": (
                    primary_baseline_targets == contrast_baseline_targets
                ),
                "primary_introduces_links": bool(primary_links),
                "contrast_introduces_links": bool(contrast_links),
                "primary_has_distinct_introduced_targets": bool(primary_only_targets),
                "contrast_has_distinct_introduced_targets": bool(contrast_only_targets),
                "meaningful_content_differs": (
                    primary_result.content_fingerprint
                    != contrast_result.content_fingerprint
                ),
            }
            required_functional = (
                functional_checks["baseline_link_targets_match"]
                and functional_checks["primary_introduces_links"]
                and functional_checks["contrast_introduces_links"]
                and functional_checks["primary_has_distinct_introduced_targets"]
                and functional_checks["contrast_has_distinct_introduced_targets"]
            )
            kinds = {
                item.kind
                for observation in (primary_result, contrast_result)
                for item in observation.outcome_signals
            }
            if "validation_error" in kinds:
                functional_status = FunctionalStatus.VALIDATION_FAILURE
            elif required_functional:
                functional_status = FunctionalStatus.VERIFIED
            else:
                functional_status = FunctionalStatus.UNRESOLVED
            status = (
                EvidenceStatus.REPLAY_VALIDATED
                if all(checks.values())
                else EvidenceStatus.FAILED
            )
            error = None if status == EvidenceStatus.REPLAY_VALIDATED else "navigation checks did not match"
            self.artifact.replay_observations.extend(
                [primary_before, primary_result, contrast_before, contrast_result]
            )
            verification_ids = [
                primary_before.id,
                primary_result.id,
                contrast_before.id,
                contrast_result.id,
            ]
            verification_evidence = {
                "evidence_rule": "introduced-link-target-delta-v2",
                "primary_baseline_targets": primary_baseline_targets,
                "contrast_baseline_targets": contrast_baseline_targets,
                "primary_introduced_links": primary_links,
                "contrast_introduced_links": contrast_links,
                "primary_only_targets": primary_only_targets,
                "contrast_only_targets": contrast_only_targets,
                "primary_content_fingerprint": primary_result.content_fingerprint,
                "contrast_content_fingerprint": contrast_result.content_fingerprint,
            }
            actual_group = primary_result.group_signature
            actual_observation_id = primary_result.id
        except Exception as exc:
            status = EvidenceStatus.FAILED
            error = f"{type(exc).__name__}: {compact_text(str(exc), 300)}"
            actual_group = None
            actual_observation_id = None
            functional_status = FunctionalStatus.FAILED
        self.artifact.metrics.browser_actions += browser_actions
        return ReplayResult(
            id=replay_id,
            transition_id=transition.id,
            path_length=len(transition.workflow_path),
            status=status,
            expected_group_signature=transition.result_group_signature or "",
            actual_group_signature=actual_group,
            actual_observation_id=actual_observation_id,
            outcome_checks=checks,
            functional_checks=functional_checks,
            verification_kind="paired_search",
            verification_observation_ids=verification_ids,
            verification_evidence=verification_evidence,
            input_plan_refs=input_plan_refs,
            network=replay_network,
            functional_status=functional_status,
            browser_actions=browser_actions,
            error=error,
            started_at=started_at,
            ended_at=utc_now(),
        )

    def _replay_transition(self, browser: Browser, transition: Transition) -> ReplayResult:
        verification: dict[str, Any] = {}
        replay_id = "replay_" + digest([transition.id, len(self.artifact.replays)], 20)
        started_at = utc_now()
        browser_actions = 0
        replay_network: list[NetworkEvent] = []
        try:
            with self._browser_session(browser) as session:
                browser_actions += session.goto_start()
                self.artifact.metrics.navigation_requests += 1
                self.artifact.metrics.root_reloads += 1
                self._record_navigation_evidence(session, "replay")
                observation = session.observe(self._next_sequence())
                last_step_network: list[NetworkEvent] = []
                for descriptor in transition.workflow_path:
                    control = session.find_current(observation, descriptor)
                    if control is None:
                        raise RuntimeError(f"replay control missing: {descriptor.signature}")
                    plan = self._resolve_form_plan(descriptor)
                    _, network, _, count = session.execute(control, plan, descriptor.input_plan_ref)
                    browser_actions += count
                    replay_network.extend(network)
                    last_step_network = network
                    self.artifact.metrics.observed_http_requests += len(network)
                    self._account_readiness(session.last_readiness)
                    self._collect_resource_evidence(session.last_action_resources)
                    observation = session.observe(self._next_sequence())
                expected_observation = self._observation_by_id(transition.result_observation_id)
                source_observation = self._observation_by_id(transition.source_observation_id)
                checks = {
                    "exact_url": bool(expected_observation)
                    and observation.url == expected_observation.url,
                    "group_signature": observation.group_signature == transition.result_group_signature,
                    "route_pattern": bool(expected_observation)
                    and observation.route_pattern == expected_observation.route_pattern,
                    "title": bool(expected_observation)
                    and normalize_instance_text(observation.title)
                    == normalize_instance_text(expected_observation.title),
                    "content_fingerprint": bool(expected_observation)
                    and observation.content_fingerprint == expected_observation.content_fingerprint,
                    "outcome_signals": bool(expected_observation)
                    and outcome_signature(observation.outcome_signals)
                    == outcome_signature(expected_observation.outcome_signals),
                    "usable_interaction_shape": bool(expected_observation)
                    and self._usable_return_screen(expected_observation, observation),
                }
                if self.config.replay_policy == "diverse":
                    checks["content_identity"] = bool(expected_observation) and self._content_identity_match(
                        expected_observation, observation
                    )
                changed_url = bool(source_observation and expected_observation) and (
                    source_observation.url != expected_observation.url
                )
                navigation_valid = (
                    changed_url
                    and checks["exact_url"]
                    and checks["route_pattern"]
                    and checks["title"]
                    and checks["usable_interaction_shape"]
                    and (
                        self.config.replay_policy != "diverse"
                        or checks.get("content_identity", False)
                    )
                )
                # An action whose only observable effect is a script-initiated or
                # non-GET request (same visible DOM, no dialog) is reproduced only
                # if the replay's final step issues the same request structures.
                expected_structures = action_request_structures(transition.network)
                network_only_effect = bool(expected_structures) and (
                    transition.source_group_signature == transition.result_group_signature
                    and not transition.dialogs
                )
                structures_reproduced = expected_structures <= action_request_structures(last_step_network)
                if expected_structures:
                    verification["request_structures_expected"] = len(expected_structures)
                    verification["request_structures_reproduced"] = structures_reproduced
                if network_only_effect:
                    checks["request_structures"] = structures_reproduced
                dynamic_valid = all(
                    checks[name]
                    for name in (
                        "exact_url", "group_signature", "route_pattern", "title",
                        "content_fingerprint", "outcome_signals",
                    )
                ) and (not network_only_effect or structures_reproduced)
                status = EvidenceStatus.REPLAY_VALIDATED if (
                    navigation_valid or dynamic_valid
                ) else EvidenceStatus.FAILED
                error = None if status == EvidenceStatus.REPLAY_VALIDATED else "outcome checks did not match"
                actual_group = observation.group_signature
                self.artifact.replay_observations.append(observation)
                actual_observation_id = observation.id
                functional_status = (
                    self._classify_functional_outcome(transition)
                    if status == EvidenceStatus.REPLAY_VALIDATED
                    else FunctionalStatus.FAILED
                )
        except Exception as exc:
            checks = {}
            status = EvidenceStatus.FAILED
            error = f"{type(exc).__name__}: {compact_text(str(exc), 300)}"
            if "ERR_BLOCKED_BY_CLIENT" in error and self.http_budget is not None \
                    and not self.http_budget.remaining("browser"):
                status = EvidenceStatus.NOT_TESTED  # budget, not behavior
                error = "verification HTTP budget exhausted during replay"
            actual_group = None
            actual_observation_id = None
            functional_status = FunctionalStatus.FAILED
        self.artifact.metrics.browser_actions += browser_actions
        return ReplayResult(
            id=replay_id,
            transition_id=transition.id,
            path_length=len(transition.workflow_path),
            status=status,
            expected_group_signature=transition.result_group_signature or "",
            actual_group_signature=actual_group,
            actual_observation_id=actual_observation_id,
            outcome_checks=checks,
            functional_status=functional_status,
            browser_actions=browser_actions,
            network=replay_network,
            verification_evidence=verification,
            error=error,
            started_at=started_at,
            ended_at=utc_now(),
        )

    def _classify_functional_outcome(self, transition: Transition) -> FunctionalStatus:
        result = self._observation_by_id(transition.result_observation_id)
        if not result:
            return FunctionalStatus.UNRESOLVED
        return self._classify_result(transition.action.kind, result)

    @staticmethod
    def _classify_result(action_kind: str, result: Observation) -> FunctionalStatus:
        kinds = {item.kind for item in result.outcome_signals}
        if "validation_error" in kinds:
            return FunctionalStatus.VALIDATION_FAILURE
        if kinds & {"success", "result"}:
            return FunctionalStatus.VERIFIED
        if action_kind == "link":
            return FunctionalStatus.NAVIGATION_ONLY
        return FunctionalStatus.UNRESOLVED

    @staticmethod
    def _content_identity_match(expected: Observation, actual: Observation) -> bool:
        """Require shared meaningful body evidence for navigational replay."""
        def tokens(value: str) -> set[str]:
            ignored = {"this", "that", "with", "from", "your", "have", "been", "will"}
            return {
                item for item in re.findall(r"[a-z0-9]{4,}", value.lower())
                if item not in ignored
            }

        expected_tokens = tokens(expected.meaningful_text or expected.text_excerpt)
        actual_tokens = tokens(actual.meaningful_text or actual.text_excerpt)
        if not expected_tokens:
            return expected.content_fingerprint == actual.content_fingerprint
        shared = len(expected_tokens & actual_tokens)
        minimum = min(3, max(1, (len(expected_tokens) + 3) // 4))
        return shared >= minimum and shared / len(expected_tokens) >= 0.25

    def _observation_by_id(self, observation_id: str | None) -> Observation | None:
        if not observation_id:
            return None
        return next((item for item in self.artifact.observations if item.id == observation_id), None)

    @staticmethod
    def _is_meaningful_feature(transition: Transition) -> bool:
        if not transition.result_group_signature or VOLATILE_CONTROL.match(transition.action.label):
            return False
        return (
            transition.source_group_signature != transition.result_group_signature
            or bool(transition.dialogs)
            or any(event.method.upper() not in {"GET", "HEAD"} for event in transition.network)
        )

    def _feature_key_for_transition(self, transition: Transition) -> str:
        semantic_action = feature_action_signature(transition.action)
        if transition.action.behavior_revision:
            semantic_action = digest([semantic_action, transition.action.behavior_revision])
        outcome_signature = ""
        if transition.action.kind != "link":
            target = self._observation_by_id(transition.result_observation_id)
            outcome_signature = digest(
                {
                    "route": target.route_pattern if target else "",
                    "result_group": transition.result_group_signature,
                    "dialogs": sorted(item.get("type", "") for item in transition.dialogs),
                    "non_get_methods": sorted(
                        event.method.upper()
                        for event in transition.network
                        if event.method.upper() not in {"GET", "HEAD"}
                    ),
                }
            )
        return feature_key(semantic_action, outcome_signature)

    def _build_features(self) -> list[Feature]:
        by_key: dict[str, list[Transition]] = defaultdict(list)
        for transition in self.artifact.transitions:
            if not self._is_meaningful_feature(transition):
                continue
            key = self._feature_key_for_transition(transition)
            by_key[key].append(transition)
        replays_by_transition = defaultdict(list)
        for replay in self.artifact.replays:
            replays_by_transition[replay.transition_id].append(replay)
        features: list[Feature] = []
        for key, transitions in sorted(by_key.items()):
            first = transitions[0]
            target = self._observation_by_id(first.result_observation_id)
            target_description = target.title or target.route_pattern if target else first.result_group_signature
            target_groups = sorted(
                {
                    transition.result_group_signature
                    for transition in transitions
                    if transition.result_group_signature
                }
            )
            source_groups = sorted({transition.source_group_signature for transition in transitions})
            replay_ids = [
                replay.id
                for transition in transitions
                for replay in replays_by_transition.get(transition.id, [])
            ]
            validated_transition_ids = sorted(
                transition.id
                for transition in transitions
                if transition.status == EvidenceStatus.REPLAY_VALIDATED
            )
            failed_transition_ids = sorted(
                transition.id
                for transition in transitions
                if any(
                    replay.status == EvidenceStatus.FAILED
                    for replay in replays_by_transition.get(transition.id, [])
                )
            )
            tested = set(validated_transition_ids) | set(failed_transition_ids)
            untested_transition_ids = sorted(
                transition.id for transition in transitions if transition.id not in tested
            )
            if failed_transition_ids:
                status = EvidenceStatus.FAILED
            elif validated_transition_ids and len(validated_transition_ids) == len(transitions):
                status = EvidenceStatus.REPLAY_VALIDATED
            else:
                status = EvidenceStatus.OBSERVED
            label = first.action.label or first.action.kind
            description = f"{compact_text(label, 80)} leads to {compact_text(target_description, 100)}"
            if target and first.action.kind == "link":
                normalized_labels = {
                    normalize_instance_text(transition.action.label)
                    for transition in transitions
                    if transition.action.label
                }
                if len(normalized_labels) > 1 or "{instance}" in target.route_pattern:
                    description = f"Observed link workflow to {compact_text(target.route_pattern, 100)}"
                else:
                    description = (
                        f"{compact_text(label, 80)} opens {compact_text(target.route_pattern, 100)}"
                    )
            features.append(
                Feature(
                    id="feature_" + key,
                    description=description,
                    action_signature=feature_action_signature(first.action),
                    source_group_signature=first.source_group_signature,
                    source_group_signatures=source_groups,
                    target_group_signature=first.result_group_signature,
                    target_group_signatures=target_groups,
                    evidence_transition_ids=[transition.id for transition in transitions],
                    replay_ids=replay_ids,
                    status=status,
                    validated_transition_ids=validated_transition_ids,
                    failed_transition_ids=failed_transition_ids,
                    untested_transition_ids=untested_transition_ids,
                )
            )
        return features

    def _build_functional_workflows(self) -> list[FunctionalWorkflow]:
        replays_by_transition: dict[str, list[ReplayResult]] = defaultdict(list)
        for replay in self.artifact.replays:
            replays_by_transition[replay.transition_id].append(replay)
        workflows: list[FunctionalWorkflow] = []
        for transition in self.artifact.transitions:
            if not transition.result_observation_id:
                continue
            replays = replays_by_transition.get(transition.id, [])
            paired = [item for item in replays if item.verification_kind == "paired_search"]
            workflow_checks: dict[str, bool] = {}
            if paired:
                evidence_signatures = {
                    digest(
                        {
                            "primary_only_targets": item.verification_evidence.get(
                                "primary_only_targets", []
                            ),
                            "contrast_only_targets": item.verification_evidence.get(
                                "contrast_only_targets", []
                            ),
                        }
                    )
                    for item in paired
                }
                workflow_checks = {
                    "two_independent_replays": len(paired) >= 2,
                    "introduced_target_evidence_consistent": (
                        len(paired) >= 2 and len(evidence_signatures) == 1
                    ),
                }
                if any(item.status == EvidenceStatus.FAILED for item in paired):
                    functional_status = FunctionalStatus.FAILED
                elif any(
                    item.functional_status == FunctionalStatus.VALIDATION_FAILURE
                    for item in paired
                ):
                    functional_status = FunctionalStatus.VALIDATION_FAILURE
                elif len(paired) >= 2 and all(
                    item.status == EvidenceStatus.REPLAY_VALIDATED
                    and item.functional_status == FunctionalStatus.VERIFIED
                    for item in paired
                ) and all(workflow_checks.values()):
                    functional_status = FunctionalStatus.VERIFIED
                else:
                    functional_status = FunctionalStatus.UNRESOLVED
            elif replays:
                functional_status = replays[-1].functional_status
            else:
                functional_status = FunctionalStatus.NOT_TESTED
            result = self._observation_by_id(transition.result_observation_id)
            workflows.append(
                FunctionalWorkflow(
                    id="workflow_"
                    + digest([transition.id, [item.id for item in replays] or ["untested"]], 18),
                    transition_id=transition.id,
                    replay_id=replays[0].id if replays else None,
                    replay_ids=[item.id for item in replays],
                    verification_checks=workflow_checks,
                    path_length=len(transition.workflow_path),
                    action_label=transition.action.label,
                    status=functional_status,
                    outcome_signal_fingerprints=(
                        outcome_signature(result.outcome_signals) if result else []
                    ),
                    source_observation_id=transition.source_observation_id,
                    result_observation_id=transition.result_observation_id,
                )
            )
        return workflows

    def _audit_connection_evidence(self) -> list[ConnectionEvidence]:
        observations = {item.id: item for item in self.artifact.observations}
        transitions = {item.id: item for item in self.artifact.transitions}
        results: list[ConnectionEvidence] = []
        for advertisement in self.artifact.advertisements:
            source = observations.get(advertisement.source_observation_id)
            present = bool(source) and any(
                item.id == advertisement.control.id and item.signature == advertisement.control.signature
                for item in source.controls
            )
            results.append(
                ConnectionEvidence(
                    id="conn_" + digest(["advertised", advertisement.source_observation_id, advertisement.control.id]),
                    claim_type="advertised_control",
                    subject_id=advertisement.control.id,
                    complete=present,
                    evidence_ids=[advertisement.source_observation_id] if present else [],
                    missing=[] if present else ["source observation containing the advertised control"],
                )
            )
        for transition in self.artifact.transitions:
            source = observations.get(transition.source_observation_id)
            action_present = bool(source) and any(
                item.id == transition.action.control_id or item.signature == transition.action.signature
                for item in source.controls
            )
            results.append(
                ConnectionEvidence(
                    id="conn_" + digest(["source_action", transition.id]),
                    claim_type="source_action",
                    subject_id=transition.id,
                    complete=action_present,
                    evidence_ids=[transition.source_observation_id] if action_present else [],
                    missing=[] if action_present else ["registered action in source observation"],
                )
            )
            if transition.action.provenance == "observed_listener" or transition.action.behavior_revision:
                evidence = source.listener_evidence if source else None
                if transition.action.provenance == "observed_listener":
                    listed = bool(evidence) and any(
                        transition.action.control_id in item.get("control_ids", []) for item in evidence.candidates)
                    results.append(ConnectionEvidence(
                        id="conn_" + digest(["listener_candidate", transition.id]),
                        claim_type="listener_candidate", subject_id=transition.id, complete=listed,
                        evidence_ids=[transition.source_observation_id] if listed else [],
                        missing=[] if listed else ["DevTools listener evidence for the executed element"],
                    ))
                if transition.action.behavior_revision:
                    revised = bool(evidence) and any(
                        item.get("revision") == transition.action.behavior_revision for item in evidence.active_revisions)
                    results.append(ConnectionEvidence(
                        id="conn_" + digest(["handler_revision", transition.id]),
                        claim_type="handler_revision", subject_id=transition.id, complete=revised,
                        evidence_ids=[transition.source_observation_id] if revised else [],
                        missing=[] if revised else ["observed handler revision in the source observation"],
                    ))
            if transition.result_observation_id:
                result = observations.get(transition.result_observation_id)
                result_complete = bool(result) and result.state_signature == transition.result_state_signature
                results.append(
                    ConnectionEvidence(
                        id="conn_" + digest(["action_result", transition.id]),
                        claim_type="action_result",
                        subject_id=transition.id,
                        complete=result_complete,
                        evidence_ids=[transition.result_observation_id] if result_complete else [],
                        missing=[] if result_complete else ["matching result observation"],
                    )
                )
            if transition.restoration_attempted:
                expected_steps = max(0, len(transition.workflow_path) - 1)
                # Steps before reused_prefix_steps ran earlier in the same live
                # context and are evidenced by their own transitions.
                expected_range = list(range(transition.reused_prefix_steps, expected_steps))
                indexes = [item.step_index for item in transition.prerequisite_network]
                restore_complete = indexes == expected_range
                results.append(
                    ConnectionEvidence(
                        id="conn_" + digest(["prerequisite_network", transition.id]),
                        claim_type="prerequisite_network",
                        subject_id=transition.id,
                        complete=restore_complete,
                        evidence_ids=[
                            f"{transition.id}:prerequisite:{item.step_index}"
                            for item in transition.prerequisite_network
                        ],
                        missing=[] if restore_complete else [
                            f"prerequisite step evidence {index}"
                            for index in expected_range
                            if index not in indexes
                        ],
                    )
                )
        for replay in self.artifact.replays:
            transition = transitions.get(replay.transition_id)
            replay_observation = next(
                (item for item in self.artifact.replay_observations if item.id == replay.actual_observation_id),
                None,
            )
            verification_observations = [
                next(
                    (
                        item
                        for item in self.artifact.replay_observations
                        if item.id == observation_id
                    ),
                    None,
                )
                for observation_id in replay.verification_observation_ids
            ]
            required_verification_observations = (
                4
                if replay.verification_evidence.get("evidence_rule")
                == "introduced-link-target-delta-v2"
                else 2
            )
            complete = bool(transition and replay.outcome_checks and replay_observation) and (
                replay.verification_kind != "paired_search"
                or (
                    replay.functional_checks
                    and len(verification_observations)
                    == required_verification_observations
                    and all(verification_observations)
                )
            )
            missing = []
            if not transition:
                missing.append("referenced transition")
            if not replay.outcome_checks:
                missing.append("observable outcome checks")
            if not replay_observation:
                missing.append("raw replay observation")
            if replay.verification_kind == "paired_search" and not replay.functional_checks:
                missing.append("paired search functional checks")
            if replay.verification_kind == "paired_search" and (
                len(verification_observations) != required_verification_observations
                or not all(verification_observations)
            ):
                missing.append("paired search before/after observations")
            results.append(
                ConnectionEvidence(
                    id="conn_" + digest(["replay", replay.id]),
                    claim_type="replay",
                    subject_id=replay.id,
                    complete=complete,
                    evidence_ids=[
                        item
                        for item in [
                            replay.transition_id,
                            replay.actual_observation_id,
                            *replay.verification_observation_ids,
                        ]
                        if item
                    ],
                    missing=missing,
                )
            )
        for external in self.artifact.external_discoveries:
            complete = bool(external.id and external.engine and external.run_id and external.source_origin
                            and external.source_record_id and external.export_digest and external.mapped_url)
            results.append(ConnectionEvidence(
                id="conn_" + digest(["external_observation", external.id]),
                claim_type="external_observation", subject_id=external.id, complete=complete,
                evidence_ids=[external.id] if complete else [],
                missing=[] if complete else ["external record provenance"],
            ))
        for resource in self.artifact.resource_evidence:
            resource_evidence_id = resource.evidence_id or (
                "resource_evidence_" + digest(resource.model_dump(mode="json"), 20)
            )
            # An unresolved candidate has no URL by definition (its target is a
            # runtime value); its evidence is the expression fingerprint instead.
            unresolved = resource.status == "unresolved_candidate"
            target_evidence = resource.expression_fingerprint if unresolved else resource.url
            complete = bool(
                resource_evidence_id
                and target_evidence
                and resource.kind
                and resource.source_url
                and resource.source_type
                and resource.source
            )
            results.append(
                ConnectionEvidence(
                    id="conn_" + digest(["resource_reference", resource_evidence_id, resource.url]),
                    claim_type="resource_reference",
                    subject_id=resource_evidence_id or resource.url,
                    complete=complete,
                    evidence_ids=[resource_evidence_id] if resource_evidence_id else [],
                    missing=[] if complete else [
                        name for name, value in (
                            ("stable evidence id", resource_evidence_id),
                            ("expression fingerprint" if unresolved else "reference URL", target_evidence),
                            ("source response URL", resource.source_url),
                            ("source type", resource.source_type),
                            ("source element or header", resource.source),
                        ) if not value
                    ],
                )
            )
        return results

    def _audit_incorrect_merges(self) -> int:
        observations = {item.id: item for item in self.artifact.observations}
        incorrect = 0
        for members in self.artifact.state_groups.values():
            shapes = set()
            sessions = set()
            for member in members:
                observation = observations[member]
                shapes.add(
                    json.dumps(
                        {
                            "route": observation.route_pattern,
                            "controls": sorted(
                                group_control_signature(control)
                                for control in observation.controls
                                if control.safe and not VOLATILE_CONTROL.match(control.label)
                                and control.provenance == "snapshot"
                            ),
                            "forms": [form.model_dump(mode="json") for form in observation.forms],
                        },
                        sort_keys=True,
                    )
                )
                sessions.add(observation.session_context)
            if len(shapes) > 1 or len(sessions) > 1:
                incorrect += 1
        return incorrect

    def _finalize_listener_metrics(self) -> None:
        metrics = self.artifact.metrics
        metrics.listener_observations = metrics.listener_observation_errors = metrics.listener_cdp_calls = 0
        metrics.listener_nodes_inspected = metrics.listener_nodes_reused = metrics.listener_bearing_nodes_max = 0
        metrics.listener_scans_truncated = 0
        metrics.listener_observation_ms = 0.0
        skipped: defaultdict[str, int] = defaultdict(int)
        changes: defaultdict[str, int] = defaultdict(int)
        candidates: set[str] = set()
        revisions: set[str] = set()
        sightings = 0
        seen: dict[tuple[str, str], tuple[bool, str | None]] = {}  # (signature, revision) -> (safe, first provenance)
        new_classes = {"created_after_action", "listener_attached_after_action", "listener_appeared_after_action"}
        for observation in self.artifact.observations:
            evidence = observation.listener_evidence
            if evidence is None:
                continue
            metrics.listener_observations += 1
            metrics.listener_observation_errors += evidence.error is not None
            metrics.listener_observation_ms += evidence.elapsed_ms
            metrics.listener_cdp_calls += evidence.cdp_calls
            metrics.listener_nodes_inspected += evidence.described_nodes
            metrics.listener_nodes_reused += evidence.reused_nodes
            metrics.listener_bearing_nodes_max = max(metrics.listener_bearing_nodes_max, evidence.listener_nodes)
            metrics.listener_scans_truncated += evidence.truncated
            for reason, count in evidence.skipped.items():
                skipped[reason] += count
            for kind, count in evidence.changes.items():
                changes[kind] += count
            revisions.update(item["revision"] for item in evidence.revisions)
            for control in observation.controls:
                if control.provenance != "observed_listener":
                    continue
                sightings += 1
                key = (control.signature, control.behavior_revision or "")
                if key not in seen:
                    seen[key] = (control.safe, (control.listener_evidence or {}).get("provenance"))
            for record in evidence.candidates:
                if record.get("skip_reason") == "frame_not_observable":
                    seen.setdefault(("frame:" + str(record.get("css_path")), ""), (False, record.get("provenance")))
        for observation in self.artifact.observations:
            candidates.update(c.signature for c in observation.controls if c.provenance == "observed_listener" and c.safe)
        metrics.listener_observation_ms = round(metrics.listener_observation_ms, 1)
        metrics.listener_skipped = dict(skipped)
        metrics.listener_changes = dict(changes)
        metrics.listener_candidates_distinct = len(candidates)
        metrics.listener_candidates_new = sum(1 for _, first in seen.values() if first in new_classes)
        metrics.listener_candidates_deduplicated = max(0, sightings - sum(1 for k in seen if not k[0].startswith("frame:")))
        metrics.listener_candidates_safe = sum(1 for safe, _ in seen.values() if safe)
        metrics.listener_candidates_rejected = sum(1 for safe, _ in seen.values() if not safe)
        observed = [t for t in self.artifact.transitions if t.status != EvidenceStatus.FAILED]
        listener_actions = [t for t in observed if t.action.provenance == "observed_listener"]
        metrics.listener_candidates_executed = len({t.action.signature for t in listener_actions})
        metrics.listener_actions_executed = len(listener_actions)
        metrics.listener_transitions_with_effect = sum(1 for t in listener_actions if transition_has_effect(t))
        metrics.handler_revision_candidates = len({
            (c.signature, c.behavior_revision) for o in self.artifact.observations for c in o.controls if c.behavior_revision})
        metrics.handler_revisions_observed = len(revisions)
        metrics.handler_revisits_executed = sum(1 for t in observed if t.action.behavior_revision)
        by_id = {item.id: item for item in self.artifact.observations}
        metrics.behavior_divergent_groups = sum(
            1 for members in self.artifact.state_groups.values()
            if len({by_id[m].behavior_signature or by_id[m].group_signature for m in members if m in by_id}) > 1)

    def _finalize(self) -> None:
        self._finalize_listener_metrics()
        try:
            import resource as _resource
            peak = _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss
            self.artifact.metrics.python_peak_rss_mb = round(peak / (1024 * 1024 if os.uname().sysname == "Darwin" else 1024), 1)
        except (ImportError, AttributeError):
            pass
        cookie_updates: defaultdict[str, int] = defaultdict(int)
        self.artifact.metrics.passive_wire_bytes = sum(item.wire_bytes or 0 for item in self.artifact.resource_evidence)
        for item in self.artifact.resource_evidence:
            for key, value in (item.cookie_updates or {}).items():
                cookie_updates[key] += value
        self.artifact.metrics.passive_cookie_updates = dict(cookie_updates)
        self.artifact.metrics.effective_resource_budgets = effective_resource_budgets(self.config)
        self.artifact.metrics.browser_body_status = dict(self.browser_body_status)
        spider_status: defaultdict[str, int] = defaultdict(int)
        for item in self.artifact.resource_evidence:
            if item.status in {"fetched", "failed"}:
                spider_status[item.body_status or ("error" if item.error and not item.http_status else "unrecorded")] += 1
        self.artifact.metrics.spider_body_status = dict(spider_status)
        if self.http_budget is not None:
            self.http_budget.export(self.artifact.metrics)
        self.artifact.ended_at = utc_now()
        self.artifact.features = self._build_features()
        self.artifact.functional_workflows = self._build_functional_workflows()
        self.artifact.connection_evidence = self._audit_connection_evidence()
        distinct_raw = {item.state_signature for item in self.artifact.observations}
        distinct_groups = {item.group_signature for item in self.artifact.observations}
        validated = [
            feature for feature in self.artifact.features if feature.status == EvidenceStatus.REPLAY_VALIDATED
        ]
        executed = {
            (transition.source_observation_id, transition.action.control_id)
            for transition in self.artifact.transitions
        }
        self.artifact.metrics.elapsed_seconds = round(self.prior_elapsed + self._elapsed(), 3)
        self.artifact.metrics.raw_states = len(distinct_raw)
        self.artifact.metrics.grouped_states = len(distinct_groups)
        self.artifact.metrics.redundant_states = max(0, len(distinct_raw) - len(distinct_groups))
        self.artifact.metrics.incorrect_state_merges = self._audit_incorrect_merges()
        self.artifact.metrics.distinct_validated_feature_workflows = len(validated)
        self.artifact.metrics.navigation_categories_replay_validated = len(validated)
        self.artifact.metrics.advertised_unexecuted = sum(
            (advertisement.source_observation_id, advertisement.control.id) not in executed
            for advertisement in self.artifact.advertisements
        )
        self.artifact.metrics.unsupported_connections = sum(
            replay.status == EvidenceStatus.FAILED for replay in self.artifact.replays
        )
        self.artifact.metrics.replay_attempts = len(self.artifact.replays)
        self.artifact.metrics.replay_navigation_successes = sum(
            replay.status == EvidenceStatus.REPLAY_VALIDATED for replay in self.artifact.replays
        )
        self.artifact.metrics.replay_failures = sum(
            replay.status == EvidenceStatus.FAILED for replay in self.artifact.replays
        )
        replayed_transitions = {item.transition_id for item in self.artifact.replays}
        self.artifact.metrics.replay_untested_paths = sum(
            bool(item.result_observation_id) and item.id not in replayed_transitions
            for item in self.artifact.transitions
        )
        self.artifact.metrics.functional_workflows_verified = sum(
            item.status == FunctionalStatus.VERIFIED for item in self.artifact.functional_workflows
        )
        self.artifact.metrics.functional_validation_failures = sum(
            item.status == FunctionalStatus.VALIDATION_FAILURE
            for item in self.artifact.functional_workflows
        )
        self.artifact.metrics.functional_unresolved = sum(
            item.status in {FunctionalStatus.UNRESOLVED, FunctionalStatus.NOT_TESTED, FunctionalStatus.FAILED}
            for item in self.artifact.functional_workflows
        )
        self.artifact.metrics.graph_connections_total = len(self.artifact.connection_evidence)
        self.artifact.metrics.graph_connections_complete = sum(
            item.complete for item in self.artifact.connection_evidence
        )
        self.artifact.metrics.graph_connections_missing_evidence = sum(
            not item.complete for item in self.artifact.connection_evidence
        )
        self.artifact.metrics.network_events_recorded = sum(
            len(transition.network) for transition in self.artifact.transitions
        ) + sum(
            sum(len(step.network) for step in transition.prerequisite_network)
            for transition in self.artifact.transitions
        ) + sum(
            len(item.network) for item in self.artifact.navigation_evidence
        ) + sum(
            len(item.network) for item in self.artifact.replays
        )
        self.artifact.notes.append(
            "unsupported_connections is retained only as a backwards-compatible failed-replay alias; "
            "use replay_failures and graph_connections_missing_evidence for distinct claims."
        )
        self._record_progress(validated_override=len(validated))

    def _record_progress(self, validated_override: int | None = None) -> None:
        validated = validated_override
        if validated is None:
            validated = len(
                {
                    self._feature_key_for_transition(transition)
                    for transition in self.artifact.transitions
                    if transition.status == EvidenceStatus.REPLAY_VALIDATED
                    and self._is_meaningful_feature(transition)
                }
            )
        point = {
            "elapsed_seconds": round(self._elapsed(), 3),
            "validated_workflows": validated,
            "browser_actions": self.artifact.metrics.browser_actions,
            "transitions_observed": self.artifact.metrics.transitions_observed,
        }
        if not self.artifact.metrics.progress or self.artifact.metrics.progress[-1] != point:
            self.artifact.metrics.progress.append(point)

    def save_checkpoint(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.artifact.metrics.elapsed_seconds = round(self.prior_elapsed + self._elapsed(), 3)
        if self.http_budget is not None:
            self.http_budget.export(self.artifact.metrics)
        checkpoint = Checkpoint(
            artifact=self.artifact,
            frontier=self.frontier,
            tried=sorted(self.tried),
        )
        self._atomic_json(self.output_dir / "checkpoint.json", checkpoint.model_dump(mode="json"))

    def _load_checkpoint(self, path: Path) -> None:
        checkpoint = Checkpoint.model_validate_json(path.read_text(encoding="utf-8"))
        self.artifact = checkpoint.artifact
        if self.http_budget is not None:
            self.http_budget.restore(self.artifact.metrics)
        self.run_id = self.artifact.run_id
        self.frontier = checkpoint.frontier
        self.tried = set(checkpoint.tried)
        self._seen_control_shapes = {
            key.rsplit(":", 1)[-1] for key in self.tried if ":" in key
        }
        self._observation_ids = {observation.id for observation in self.artifact.observations}
        self.sequence = max((observation.sequence for observation in self.artifact.observations), default=0)
        self.prior_elapsed = self.artifact.metrics.elapsed_seconds
        self.started_monotonic = time.monotonic()
        self.artifact.notes.append(f"Resumed from checkpoint saved at {checkpoint.saved_at}.")
        if self.config.focus_query:
            query = self.config.focus_query.lower()
            for item in self.frontier:
                if query in f"{item.action.label} {item.action.target or ''}".lower():
                    item.priority += 10.0
            self._sort_frontier()
            self.artifact.notes.append(
                f"Frontier prioritized for the requested focus: {self.config.focus_query[:100]}."
            )

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        fd, temporary = tempfile.mkstemp(prefix=path.name, dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
