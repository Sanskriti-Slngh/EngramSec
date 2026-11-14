"""Security-oriented capability evidence view (derived from acg/1; never assesses vulnerabilities)."""
from __future__ import annotations

from agent1.security_evidence import POLICY_BLOCK, capability_evidence


def _export(op_method, op_route, params, label, aff_kind="form_submit"):
    return {
        "operations": [{"id": "op1", "channel": "http", "method": op_method, "route": op_route, "params": params}],
        "affordances": [{"id": "a1", "family": {"kind": aff_kind, "interaction": "click"},
                         "labels": [{"text": label, "evidence_id": "e"}]}],
        "capabilities": [{"id": "c1", "status": "observed", "role": "anonymous", "operation_ids": ["op1"],
                          "effects": [{"kind": "component_state_changed", "target": "form"}],
                          "bindings": [{"affordance_id": "a1", "action_ids": ["t1"]}], "action_ids": ["t1"],
                          "evidence_ids": ["ev:transitions:t1"]}],
    }


def _run(method, url, status=None, failure=None):
    return {"transitions": [{"id": "t1", "action": {"kind": "form_submit", "label": "x"},
                             "network": [{"method": method, "url": url, "status": status, "failure": failure},
                                         {"method": "GET", "url": "http://h/static/font.woff", "status": 200}]}]}


def test_successful_write_is_possible_state_change_with_relevance_and_no_verdict():
    rec = capability_evidence(_export("POST", "/api/register", ["username", "password", "email"], "Register"),
                              _run("POST", "http://h/api/register", 200))[0]
    assert rec["state_change"] == "possible_confirm_separately"
    assert rec["response"] == {"POST /api/register": [200]}            # page subresources excluded
    assert {"account_lifecycle", "authentication"} <= set(rec["security_relevance"])
    assert rec["vulnerability_status"] == "not_assessed"
    assert rec["trigger"][0]["label"] == "Register" and rec["network_effect"][0]["params"] == ["username", "password", "email"]


def test_policy_blocked_write_is_recorded_as_blocked_not_as_absent():
    rec = capability_evidence(_export("POST", "/api/register", ["username"], "Register"),
                              _run("POST", "http://h/api/register", failure=POLICY_BLOCK))[0]
    assert rec["state_change"] == "blocked_by_policy" and rec["blocked_requests"] == ["POST /api/register"]


def test_read_only_operation_reports_no_observed_state_change():
    rec = capability_evidence(_export("GET", "/search", ["q"], "Search", "form_submit"),
                              _run("GET", "http://h/search?q=a", 200))[0]
    assert rec["state_change"] == "none_observed" and "search_query" in rec["security_relevance"]
    assert rec["vulnerability_status"] == "not_assessed"
