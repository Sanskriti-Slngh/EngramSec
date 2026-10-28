from __future__ import annotations

import re

from .schema import ActionDescriptor, Control, FormField, Observation


SEARCH_SEMANTICS = re.compile(r"(?:^|\b)(?:search|query|find|lookup)(?:\b|$)", re.I)


def search_field(action: ActionDescriptor | Control) -> FormField | None:
    """Return the single browser-observed field that makes a safe GET form a search form."""

    if action.kind != "form_submit" or (action.method or "").upper() != "GET":
        return None
    candidates: list[FormField] = []
    for field in action.fields:
        semantics = " ".join(
            (field.name, field.label, field.placeholder, field.description)
        )
        if field.input_type == "search" or SEARCH_SEMANTICS.search(semantics):
            candidates.append(field)
    if len(candidates) != 1:
        return None
    if any(
        field.required
        and field.id != candidates[0].id
        and field.input_type not in {"hidden", "submit", "button"}
        for field in action.fields
    ):
        return None
    return candidates[0]


def is_get_search_action(action: ActionDescriptor | Control) -> bool:
    return search_field(action) is not None


def matching_result_links(observation: Observation, query: str) -> list[dict[str, str]]:
    """Collect non-echo evidence from result-link labels, never from title/input text alone."""

    needle = query.casefold().strip()
    if not needle:
        return []
    return [
        {"control_id": control.id, "label": control.label, "target": control.target or ""}
        for control in observation.controls
        if control.kind == "link"
        and control.target
        and needle in control.label.casefold()
    ]
