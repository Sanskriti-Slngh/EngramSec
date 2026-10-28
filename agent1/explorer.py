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
from .schema import (
    ActionDescriptor,
    Advertisement,
    Checkpoint,
    Control,
    EvidenceStatus,
    Feature,
    FormField,
    FormObservation,
    FrontierItem,
    InputReference,
    NetworkEvent,
    Observation,
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
      el.getAttribute('title') || el.getAttribute('placeholder') || '').replace(/\s+/g, ' ').trim();
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
  const fieldFor = (el) => ({
    name: el.getAttribute('name') || el.id || '',
    input_type: (el.getAttribute('type') || el.tagName || 'text').toLowerCase(),
    label: labelFor(el),
    required: !!el.required
  });
  const forms = Array.from(document.forms).map((form, index) => ({
    index,
    method: (form.method || 'GET').toUpperCase(),
    action: form.action || location.href,
    fields: Array.from(form.querySelectorAll('input,select,textarea')).filter(el => el.name || el.id).map(fieldFor),
    submit_labels: Array.from(form.querySelectorAll('button,input[type=submit],input[type=button]')).map(labelFor).filter(Boolean)
  }));
  const selector = 'a[href],button,input[type=submit],input[type=button],[role=button]';
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
  return { controls, forms, body_text: document.body ? document.body.innerText : '' };
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
            forms.append(FormObservation.model_validate(item))
        controls: list[Control] = []
        for raw in extracted["controls"]:
            target = sanitize_url(raw["target"], self.page.url) if raw.get("target") else None
            label = compact_text(raw.get("label", ""), 160)
            method = (raw.get("method") or "").upper() or None
            fields = [FormField.model_validate(field) for field in raw.get("fields", [])]
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
        raw_sig, group_sig, pattern = signatures(
            url=current_url,
            title=title,
            controls=controls,
            forms=forms,
            session_context=self.config.context_label,
        )
        observation_id = "obs_" + digest([sequence, current_url, raw_sig, time.time_ns()], 20)
        body_text = compact_text(extracted.get("body_text", ""), 2_000)
        return Observation(
            id=observation_id,
            sequence=sequence,
            url=current_url,
            title=title,
            text_excerpt=body_text,
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

    def execute(self, control: Control) -> tuple[list[InputReference], list[NetworkEvent], list[dict[str, str]], int]:
        assert self.page and self.network
        self.network.drain()
        self.dialogs = []
        input_refs: list[InputReference] = []
        action_count = 0
        if control.kind == "form_submit" and control.form_index is not None:
            refs, fills = self._fill_form(control.form_index)
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

    def _fill_form(self, form_index: int) -> tuple[list[InputReference], int]:
        assert self.page
        form = self.page.locator("form").nth(form_index)
        fields = form.locator("input,select,textarea")
        refs: list[InputReference] = []
        actions = 0
        for index in range(fields.count()):
            field = fields.nth(index)
            name = field.get_attribute("name") or field.get_attribute("id") or f"field_{index}"
            tag = field.evaluate("el => el.tagName.toLowerCase()")
            kind = (field.get_attribute("type") or tag or "text").lower()
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
                value, value_ref = self._generated_value(kind, name)
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
    def _generated_value(kind: str, name: str) -> tuple[str, str]:
        lowered = name.lower()
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
        self.frontier.sort(key=lambda item: (len(item.path), -item.priority, item.action.signature))

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
                if actual != expected:
                    raise RuntimeError(
                        f"saved return path restored {actual}, expected {expected}"
                    )
                current_control = session.find_current(source, item.action)
                if current_control is None:
                    raise RuntimeError("registered control was not present in the current observation")
                input_refs, network, dialogs, action_count = session.execute(current_control)
                self.artifact.metrics.browser_actions += action_count
                result = session.observe(self._next_sequence())
                workflow_path = list(item.path) + [BrowserSession.descriptor(current_control)]
                self._record_observation(result, workflow_path)
                transition = Transition(
                    id="tr_" + digest([self.run_id, source.id, current_control.id, result.id], 20),
                    source_observation_id=source.id,
                    source_state_signature=source.state_signature,
                    source_group_signature=source.group_signature,
                    action=BrowserSession.descriptor(current_control),
                    workflow_path=workflow_path,
                    input_references=input_refs,
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

    def _restore(self, session: BrowserSession, path: list[ActionDescriptor]) -> Observation:
        observation = session.observe(self._next_sequence())
        for descriptor in path:
            control = session.find_current(observation, descriptor)
            if control is None:
                raise RuntimeError(f"return-path control missing: {descriptor.signature}")
            _, _, _, count = session.execute(control)
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
            replay = self._replay_transition(browser, transition)
            self.artifact.replays.append(replay)
            self.artifact.metrics.replay_success_denominator += 1
            if replay.status == EvidenceStatus.REPLAY_VALIDATED:
                self.artifact.metrics.replay_success_numerator += 1
                transition.status = EvidenceStatus.REPLAY_VALIDATED
            self._record_progress()
            self.save_checkpoint()

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
                    _, _, _, count = session.execute(control)
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
                }
                status = (
                    EvidenceStatus.REPLAY_VALIDATED if all(checks.values()) else EvidenceStatus.FAILED
                )
                error = None if status == EvidenceStatus.REPLAY_VALIDATED else "outcome checks did not match"
                actual_group = observation.group_signature
        except Exception as exc:
            checks = {}
            status = EvidenceStatus.FAILED
            error = f"{type(exc).__name__}: {compact_text(str(exc), 300)}"
            actual_group = None
        self.artifact.metrics.browser_actions += browser_actions
        return ReplayResult(
            id=replay_id,
            transition_id=transition.id,
            path_length=len(transition.workflow_path),
            status=status,
            expected_group_signature=transition.result_group_signature or "",
            actual_group_signature=actual_group,
            outcome_checks=checks,
            browser_actions=browser_actions,
            error=error,
            started_at=started_at,
            ended_at=utc_now(),
        )

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
            validated = any(
                replay.status == EvidenceStatus.REPLAY_VALIDATED
                for transition in transitions
                for replay in replays_by_transition.get(transition.id, [])
            )
            status = EvidenceStatus.REPLAY_VALIDATED if validated else EvidenceStatus.OBSERVED
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
                )
            )
        return features

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
        self.artifact.metrics.advertised_unexecuted = sum(
            (advertisement.source_observation_id, advertisement.control.id) not in executed
            for advertisement in self.artifact.advertisements
        )
        self.artifact.metrics.unsupported_connections = sum(
            replay.status == EvidenceStatus.FAILED for replay in self.artifact.replays
        )
        self.artifact.metrics.network_events_recorded = sum(
            len(transition.network) for transition in self.artifact.transitions
        )
        self._record_progress(validated_override=len(validated))

    def _record_progress(self, validated_override: int | None = None) -> None:
        validated = validated_override
        if validated is None:
            replayed = {
                replay.transition_id
                for replay in self.artifact.replays
                if replay.status == EvidenceStatus.REPLAY_VALIDATED
            }
            validated = len(
                {
                    self._feature_key_for_transition(transition)
                    for transition in self.artifact.transitions
                    if transition.id in replayed
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
