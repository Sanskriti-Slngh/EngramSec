from __future__ import annotations

from typing import Any


CASES: dict[str, dict[str, Any]] = {
    "search": {
        "path": "/search",
        "functional_outcomes": {"Result Alpha", "Result Beta"},
        "cosmetic_only": False,
    },
    "form": {
        "path": "/form",
        "success_text": "Registration created",
        "failure_text": "Invite code is invalid",
        "cosmetic_only": False,
    },
    "multi": {
        "path": "/multi",
        "success_text": "Workspace setup complete",
        "required_event_sequence": ("setup", "completion"),
        "cosmetic_only": False,
    },
    "records": {
        "path": "/records",
        "distinct_instances": {"1", "2"},
        "cosmetic_only": False,
    },
    "cosmetic": {
        "path": "/cosmetic",
        "cosmetic_only": True,
    },
    "outcomes": {
        "path": "/outcomes",
        "cosmetic_only": False,
        "diagram_case": True,
    },
}


def event_values(events: list[dict[str, Any]], kind: str, field: str) -> list[Any]:
    return [event.get(field) for event in events if event.get("kind") == kind]
