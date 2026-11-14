from __future__ import annotations

from experiments.evaluate_coverage import evaluate


def test_evaluator_uses_explicit_denominators_and_observed_structure() -> None:
    graph = {
        "nodes": {
            "states": [{
                "id": "state_home", "route_pattern": "/", "session_markers": {
                    "cookie_names": ["member"], "local_storage_keys": [], "session_storage_keys": []
                }
            }],
            "actions_evidence": [{
                "id": "action_open", "label": "Open", "kind": "link",
                "status": "replay_validated", "workflow_path": [{"target": "http://local/item/1"}],
                "network": [{
                    "method": "POST", "url": "http://local/submit", "parameter_names": ["name"],
                    "resource_type": "document"
                }],
            }],
        },
        "advertised_unexecuted": [],
        "edges": [{"type": "results_in", "source": "action_open", "target": "state_home"}],
        "metrics": {
            "replay_attempts": 1, "replay_navigation_successes": 1, "browser_actions": 2,
            "elapsed_seconds": 1, "grouped_states": 1, "raw_states": 1,
            "incorrect_state_merges": 0, "graph_connections_missing_evidence": 0,
        },
    }
    truth = {
        "application": "unit",
        "areas": [
            {"id": "home", "route": "/", "scope": "applicable"},
            {"id": "backend", "route": "/backend", "scope": "blocked"},
            {"id": "external", "route": "https://outside", "scope": "outside"},
        ],
        "controls": [{"id": "open", "label": "Open", "kind": "link", "scope": "applicable"}],
        "requests": [{
            "id": "submit", "method": "POST", "path": "/submit", "params": ["name"],
            "scope": "applicable",
        }],
        "instances": [{"id": "one", "target_suffix": "/item/1", "scope": "applicable"}],
        "contexts": [
            {"id": "anonymous", "cookie_name": None, "scope": "applicable"},
            {"id": "member", "cookie_name": "member", "scope": "applicable"},
        ],
    }

    result = evaluate(graph, truth)
    assert result["denominators"]["areas"] == 1
    assert result["metrics"]["state_interface_recall"] == 1
    assert result["metrics"]["request_surface_recall"] == 1
    assert result["metrics"]["context_recall"] == 1
    assert result["areas"][1]["status"] == "missed"  # Not silently credited as covered.
