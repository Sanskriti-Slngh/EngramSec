from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from .providers import DecisionProvider, ModelProviderError, build_provider
from .revision import code_revision
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
    FormObservation,
    FrontierItem,
    InputReference,
    NetworkEvent,
    Observation,
    OutcomeSignal,
    ReplayResult,
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
    same_origin,
    sanitize_url,
    signatures,
)


DANGEROUS_ACTION = re.compile(
    r"\b(delete|remove|destroy|drop|reset|shutdown|disable|unsubscribe|purge|clear|empty|logout|sign\s*out)\b",
    re.I,
)
AMBIGUOUS_LABEL = re.compile(r"^(|click|submit|go|ok|more|next|button|link)$", re.I)


EXTRACT_SCRIPT = r"""
() => {
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (style.visibility === 'hidden' || style.display === 'none' || style.opacity === '0' || rect.width <= 0 || rect.height <= 0) return false;
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    if (cx >= 0 && cy >= 0 && cx < window.innerWidth && cy < window.innerHeight) {
      const top = document.elementFromPoint(cx, cy);
      if (top && top !== el && !el.contains(top)) return false;
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
  const forms = Array.from(document.forms).map((form, index) => ({
    index,
    method: (form.method || 'GET').toUpperCase(),
    action: form.action || location.href,
    fields: Array.from(form.querySelectorAll('input,select,textarea')).filter(el => el.name || el.id).map(fieldFor),
    submit_labels: Array.from(form.querySelectorAll('button,input[type=submit],input[type=button]')).map(labelFor).filter(Boolean)
  }));
  const selector = 'a[href],button,input[type=submit],input[type=button],[role=button],' +
    '[onclick],[aria-controls],[data-toggle],[data-target],[id^="toggle-"]';
  const controls = Array.from(document.querySelectorAll(selector)).filter(visible).map((el) => {
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || (tag === 'a' ? 'link' : 'button');
    const formIndex = el.form ? Array.from(document.forms).indexOf(el.form) : null;
    const form = formIndex === null || formIndex < 0 ? null : forms[formIndex];
    const kind = tag === 'a' ? 'link' : (form ? 'form_submit' : 'button');
    return {
      kind,
      label: labelFor(el),
      css_path: cssPath(el),
      role,
      target: tag === 'a' ? el.href : (form ? form.action : null),
      method: form ? form.method : null,
      form_index: formIndex === null || formIndex < 0 ? null : formIndex,
      fields: form ? form.fields : []
    };
  });
  const main = document.querySelector('main,[role=main]') || document.body;
  const meaningful = main ? main.cloneNode(true) : null;
  if (meaningful) meaningful.querySelectorAll(
    'script,style,noscript,template,nav,header,footer,[data-volatile],.timestamp,' +
    '#think_page_trace,#think_page_trace_open,#sfWebDebug,#debug-toolbar,[data-debug-toolbar]'
  ).forEach(el => el.remove());
  if (meaningful) meaningful.querySelectorAll(
    'i[class*="eye"],i[class*="view"],[aria-label*="view count" i],[title*="view count" i]'
  ).forEach(icon => (icon.closest('span,small') || icon).remove());
  const signalElements = Array.from(document.querySelectorAll(
    '[data-outcome],[role=alert],[role=status],[aria-live]:not([aria-live=off]),.success,.error,.alert,.notice,.message'
  ));
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
    meaningful_text: meaningful ? meaningful.innerText : '',
    outcomes
  };
}
"""


class NetworkRecorder:
    def __init__(self, page: Page):
        self.events: list[NetworkEvent] = []
        page.on("response", self._response)
        page.on("requestfailed", self._failed)

    def _response(self, response: Any) -> None:
        request = response.request
        if request.resource_type not in {"document", "xhr", "fetch"}:
            return
        self.events.append(
            NetworkEvent(
                method=request.method,
                url=sanitize_url(request.url),
                status=response.status,
                resource_type=request.resource_type,
            )
        )

    def _failed(self, request: Any) -> None:
        if request.resource_type not in {"document", "xhr", "fetch"}:
            return
        self.events.append(
            NetworkEvent(
                method=request.method,
                url=sanitize_url(request.url),
                resource_type=request.resource_type,
                failure=compact_text(str(request.failure or "request failed"), 200),
            )
        )

    def drain(self) -> list[NetworkEvent]:
        current = self.events
        self.events = []
        return current


class BrowserSession:
    def __init__(self, browser: Browser, config: RunConfig):
        self.browser = browser
        self.config = config
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.network: NetworkRecorder | None = None
        self.dialogs: list[dict[str, str]] = []

    def __enter__(self) -> "BrowserSession":
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.network = NetworkRecorder(self.page)
        self.page.on("dialog", self._dialog)
        return self

    def __exit__(self, *_: Any) -> None:
        if self.context:
            self.context.close()

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
        response = self.page.goto(
            self.config.start_url,
            wait_until="domcontentloaded",
            timeout=self.config.action_timeout_ms * 2,
        )
        if not same_origin(self.config.start_url, self.page.url):
            raise RuntimeError("start navigation left the configured origin")
        if response and response.status >= 500:
            raise RuntimeError(f"start navigation returned HTTP {response.status}")
        if self.config.settle_ms:
            self.page.wait_for_timeout(self.config.settle_ms)
        if self.network:
            self.network.drain()
        return 1

    def observe(self, sequence: int) -> Observation:
        assert self.page
        extracted = self.page.evaluate(EXTRACT_SCRIPT)
        current_url = sanitize_url(self.page.url)
        forms = []
        for item in extracted["forms"]:
            item = dict(item)
            item["action"] = sanitize_url(item.get("action") or self.page.url, self.page.url)
            fields = []
            for field_index, raw_field in enumerate(item.get("fields", [])):
                raw_field = dict(raw_field)
                raw_field["id"] = "fld_" + digest(
                    [current_url, item["index"], raw_field.get("css_path"), raw_field.get("name"), field_index],
                    18,
                )
                fields.append(raw_field)
            item["fields"] = fields
            forms.append(FormObservation.model_validate(item))
        controls: list[Control] = []
        for raw in extracted["controls"]:
            target = sanitize_url(raw["target"], self.page.url) if raw.get("target") else None
            label = compact_text(raw.get("label", ""), 160)
            method = (raw.get("method") or "").upper() or None
            form_index = raw.get("form_index")
            fields = forms[form_index].fields if form_index is not None and form_index < len(forms) else []
            if not label and raw["kind"] == "form_submit" and any(
                field.input_type == "search"
                or SEARCH_SEMANTICS.search(
                    " ".join((field.name, field.label, field.placeholder, field.description))
                )
                for field in fields
            ):
                label = "Search"
            unsafe_reason = self._unsafe_reason(label, target, method, fields)
            signature = control_signature(raw["kind"], raw["role"], label, target, method)
            control_id = "ctl_" + digest([current_url, raw["css_path"], signature], 18)
            controls.append(
                Control(
                    id=control_id,
                    kind=raw["kind"],
                    label=label or f"unnamed {raw['role']}",
                    css_path=raw["css_path"],
                    role=raw["role"],
                    target=target,
                    method=method,
                    form_index=raw.get("form_index"),
                    fields=fields,
                    safe=unsafe_reason is None,
                    skip_reason=unsafe_reason,
                    signature=signature,
                )
            )
        title = compact_text(self.page.title(), 200)
        meaningful_text = compact_text(extracted.get("meaningful_text", ""), 8_000)
        outcome_signals = [
            OutcomeSignal(
                kind=item["kind"],
                text_excerpt=compact_text(item.get("text", ""), 240),
                fingerprint=digest([item["kind"], compact_text(item.get("text", "").lower(), 1_000)]),
                source=compact_text(item.get("source", "unknown"), 80),
            )
            for item in extracted.get("outcomes", [])
        ]
        raw_sig, group_sig, pattern = signatures(
            url=current_url,
            title=title,
            controls=controls,
            forms=forms,
            session_context=self.config.context_label,
            meaningful_text=meaningful_text,
        )
        observation_id = "obs_" + digest([sequence, current_url, raw_sig, time.time_ns()], 20)
        body_text = compact_text(extracted.get("body_text", ""), 2_000)
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
            route_pattern=pattern,
            instance_facts={
                "form_count": len(forms),
                "safe_control_count": sum(control.safe for control in controls),
                "all_control_count": len(controls),
            },
        )

    def _unsafe_reason(
        self,
        label: str,
        target: str | None,
        method: str | None,
        fields: list[FormField],
    ) -> str | None:
        if target and not same_origin(self.config.start_url, target):
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
        )

    def find_current(self, observation: Observation, descriptor: ActionDescriptor) -> Control | None:
        for control in observation.controls:
            if control.id == descriptor.control_id and control.safe:
                return control
        candidates = [
            control
            for control in observation.controls
            if control.signature == descriptor.signature and control.safe
        ]
        return candidates[0] if len(candidates) == 1 else None

    def execute(
        self,
        control: Control,
        input_values: dict[str, str] | None = None,
        input_plan_ref: str | None = None,
    ) -> tuple[list[InputReference], list[NetworkEvent], list[dict[str, str]], int]:
        assert self.page and self.network
        self.network.drain()
        self.dialogs = []
        input_refs: list[InputReference] = []
        action_count = 0
        if control.kind == "form_submit" and control.form_index is not None:
            refs, fills = self._fill_form(
                control.form_index,
                control.fields,
                input_values=input_values or {},
                input_plan_ref=input_plan_ref,
            )
            input_refs.extend(refs)
            action_count += fills
        locator = self.page.locator(control.css_path).first
        if locator.count() == 0:
            locator = self.page.get_by_role(control.role, name=control.label, exact=True).first
        locator.click(timeout=self.config.action_timeout_ms)
        action_count += 1
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=self.config.action_timeout_ms)
        except PlaywrightTimeoutError:
            pass
        if self.config.settle_ms:
            self.page.wait_for_timeout(self.config.settle_ms)
        if not same_origin(self.config.start_url, self.page.url):
            raise RuntimeError("action left the configured origin")
        return input_refs, self.network.drain(), list(self.dialogs), action_count

    def _fill_form(
        self,
        form_index: int,
        observed_fields: list[FormField],
        input_values: dict[str, str],
        input_plan_ref: str | None,
    ) -> tuple[list[InputReference], int]:
        assert self.page
        form = self.page.locator("form").nth(form_index)
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


class Explorer:
    def __init__(self, config: RunConfig, repository_root: Path):
        self.config = config
        self.repository_root = repository_root
        self.output_dir = config.output_dir
        self.run_id = config.run_id or time.strftime("agent1-%Y%m%dT%H%M%SZ", time.gmtime())
        self.started_monotonic = time.monotonic()
        self.prior_elapsed = 0.0
        self.sequence = 0
        self.frontier: list[FrontierItem] = []
        self.tried: set[str] = set()
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

    def _revision(self) -> str:
        return code_revision(self.repository_root)

    def _elapsed(self) -> float:
        return time.monotonic() - self.started_monotonic

    def _next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

    def _validate_target(self) -> None:
        parsed = urlsplit(self.config.start_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("target must use HTTP or HTTPS")
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Agent 1 defaults to explicitly configured loopback targets only")

    def run(self) -> RunArtifact:
        self._validate_target()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.config.headless)
            try:
                if self.config.resume_from:
                    self._load_checkpoint(self.config.resume_from)
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
        with BrowserSession(browser, self.config) as session:
            self.artifact.metrics.browser_actions += session.goto_start()
            self.artifact.metrics.navigation_requests += 1
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
            if tried_key in self.tried:
                continue
            self.tried.add(tried_key)
            kind_score = {"form_submit": 3.0, "button": 2.0, "link": 1.0}[control.kind]
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
        self.frontier.sort(
            key=lambda item: (
                item.priority < 10.0,
                len(item.path),
                -item.priority,
                item.action.signature,
            )
        )

    def _explore(self, browser: Browser) -> None:
        exploration_deadline = self.config.max_seconds * (1.0 - self.config.replay_reserve_fraction)
        while self.frontier:
            if self._elapsed() >= exploration_deadline:
                break
            if len(self.artifact.transitions) >= self.config.max_transitions:
                break
            if self.artifact.metrics.browser_actions >= self.config.max_browser_actions:
                break
            item = self.frontier.pop(0)
            self._attempt_frontier(browser, item)
            self.save_checkpoint()

    def _attempt_frontier(self, browser: Browser, item: FrontierItem) -> None:
        started_at = utc_now()
        self.artifact.metrics.transitions_attempted += 1
        with BrowserSession(browser, self.config) as session:
            try:
                self.artifact.metrics.browser_actions += session.goto_start()
                self.artifact.metrics.navigation_requests += 1
                source = self._restore(session, item.path)
                expected = (
                    item.expected_source_signature
                    if self.config.policy == "exact"
                    else item.expected_source_group
                )
                actual = source.state_signature if self.config.policy == "exact" else source.group_signature
                self._record_observation(source, item.path)
                expected_observation = self._observation_by_id(item.source_observation_id)
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
                if actual != expected and not (
                    search_related
                    and expected_observation
                    and self._usable_return_screen(expected_observation, source)
                ):
                    raise RuntimeError(
                        f"saved return path restored {actual}, expected {expected}"
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
                self.artifact.metrics.browser_actions += action_count
                result = session.observe(self._next_sequence())
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
                    self.artifact.metrics.browser_actions += retry_actions
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
                workflow_path = list(item.path) + descriptors
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
                    network=network,
                    dialogs=dialogs,
                    started_at=started_at,
                    ended_at=utc_now(),
                    run_id=self.run_id,
                )
                self.artifact.transitions.append(transition)
                self.artifact.metrics.transitions_observed += 1
                self._enqueue(result, workflow_path)
                self._record_progress()
            except Exception as exc:
                transition = Transition(
                    id="tr_" + digest([self.run_id, item.source_observation_id, item.action.signature, started_at], 20),
                    source_observation_id=item.source_observation_id,
                    source_state_signature=item.expected_source_signature,
                    source_group_signature=item.expected_source_group,
                    action=item.action,
                    workflow_path=list(item.path) + [item.action],
                    status=EvidenceStatus.FAILED,
                    error=f"{type(exc).__name__}: {compact_text(str(exc), 300)}",
                    started_at=started_at,
                    ended_at=utc_now(),
                    run_id=self.run_id,
                )
                self.artifact.transitions.append(transition)
                self.artifact.metrics.transitions_failed += 1
                self._record_progress()

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

    def _restore(self, session: BrowserSession, path: list[ActionDescriptor]) -> Observation:
        observation = session.observe(self._next_sequence())
        for descriptor in path:
            control = session.find_current(observation, descriptor)
            if control is None:
                raise RuntimeError(f"return-path control missing: {descriptor.signature}")
            plan = self._resolve_form_plan(descriptor)
            _, _, _, count = session.execute(control, plan, descriptor.input_plan_ref)
            self.artifact.metrics.browser_actions += count
            observation = session.observe(self._next_sequence())
        return observation

    def _replay(self, browser: Browser) -> None:
        candidates = [
            transition for transition in self.artifact.transitions if transition.status == EvidenceStatus.OBSERVED
        ]
        candidates.sort(key=lambda transition: (len(transition.workflow_path), transition.id))
        for transition in candidates:
            if self._elapsed() >= self.config.max_seconds:
                break
            if self.artifact.metrics.browser_actions >= self.config.max_browser_actions:
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
                replay = (
                    self._replay_search_transition(browser, transition, pair_index)
                    if paired_search
                    else self._replay_transition(browser, transition)
                )
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

    def _execute_replay_path(
        self,
        session: BrowserSession,
        path: list[ActionDescriptor],
    ) -> tuple[Observation, int, list[Observation]]:
        observation = session.observe(self._next_sequence())
        observations = [observation]
        browser_actions = 0
        for descriptor in path:
            control = session.find_current(observation, descriptor)
            if control is None:
                raise RuntimeError(f"replay control missing: {descriptor.signature}")
            plan = self._resolve_form_plan(descriptor)
            _, _, _, count = session.execute(control, plan, descriptor.input_plan_ref)
            browser_actions += count
            observation = session.observe(self._next_sequence())
            observations.append(observation)
        return observation, browser_actions, observations

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
            with BrowserSession(browser, self.config) as session:
                browser_actions += session.goto_start()
                self.artifact.metrics.navigation_requests += 1
                primary_result, count, primary_path_observations = self._execute_replay_path(
                    session, transition.workflow_path
                )
                browser_actions += count
                browser_actions += session.goto_start()
                self.artifact.metrics.navigation_requests += 1
                contrast_result, count, contrast_path_observations = self._execute_replay_path(
                    session, contrast_path
                )
                browser_actions += count
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
            functional_status=functional_status,
            browser_actions=browser_actions,
            error=error,
            started_at=started_at,
            ended_at=utc_now(),
        )

    def _replay_transition(self, browser: Browser, transition: Transition) -> ReplayResult:
        replay_id = "replay_" + digest([transition.id, len(self.artifact.replays)], 20)
        started_at = utc_now()
        browser_actions = 0
        try:
            with BrowserSession(browser, self.config) as session:
                browser_actions += session.goto_start()
                self.artifact.metrics.navigation_requests += 1
                observation = session.observe(self._next_sequence())
                for descriptor in transition.workflow_path:
                    control = session.find_current(observation, descriptor)
                    if control is None:
                        raise RuntimeError(f"replay control missing: {descriptor.signature}")
                    plan = self._resolve_form_plan(descriptor)
                    _, _, _, count = session.execute(control, plan, descriptor.input_plan_ref)
                    browser_actions += count
                    observation = session.observe(self._next_sequence())
                expected_observation = self._observation_by_id(transition.result_observation_id)
                checks = {
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
                }
                status = (
                    EvidenceStatus.REPLAY_VALIDATED if all(checks.values()) else EvidenceStatus.FAILED
                )
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

    def _finalize(self) -> None:
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
        checkpoint = Checkpoint(
            artifact=self.artifact,
            frontier=self.frontier,
            tried=sorted(self.tried),
        )
        self._atomic_json(self.output_dir / "checkpoint.json", checkpoint.model_dump(mode="json"))

    def _load_checkpoint(self, path: Path) -> None:
        checkpoint = Checkpoint.model_validate_json(path.read_text(encoding="utf-8"))
        self.artifact = checkpoint.artifact
        self.run_id = self.artifact.run_id
        self.frontier = checkpoint.frontier
        self.tried = set(checkpoint.tried)
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
            self.frontier.sort(key=lambda item: (len(item.path), -item.priority, item.action.signature))
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
