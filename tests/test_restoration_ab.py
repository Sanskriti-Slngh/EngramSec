"""Contract tests for the restoration A/B harness and its contract-independent oracle (no browser)."""
from __future__ import annotations

import pytest

from evaluation import restoration_ab as H
from evaluation.comprehensive_config import FROZEN, INSTRUMENTATION


def test_arms_differ_only_in_restoration_policy_and_share_the_best_perception_configuration():
    a, b = H.arm_fields("A"), H.arm_fields("B")
    assert a == {**FROZEN, **INSTRUMENTATION, "runtime_listener_observation": "revisit"}
    assert {k for k in set(a) | set(b) if a.get(k) != b.get(k)} == {"restoration_policy"}
    assert b["restoration_policy"] == "contract" and a.get("restoration_policy", "strict") == "strict"
    assert not a.get("robust_readiness")          # readiness would also enable the old shape tolerance


def test_both_arms_build_configs_with_equal_budgets_and_safety(tmp_path):
    from agent1.schema import RunConfig
    configs = [RunConfig(start_url="http://127.0.0.1:1/", output_dir=tmp_path, context_label="t", **H.arm_fields(a))
               for a in H.ARMS]
    for field in ("policy", "max_seconds", "max_browser_actions", "max_transitions", "allow_post_forms",
                  "exploration_mode", "interaction_profile", "settle_ms", "robust_readiness", "model_provider",
                  "runtime_listener_observation", "state_aware_exploration", "replay_policy"):
        assert len({getattr(c, field) for c in configs}) == 1, field
    assert configs[0].max_seconds == 180 and configs[0].max_browser_actions == 500 and configs[0].max_transitions == 100
    assert configs[0].restoration_policy == "strict" and configs[1].restoration_policy == "contract"


def test_production_default_is_unchanged():
    from agent1.schema import RunConfig
    assert RunConfig.model_fields["restoration_policy"].default == "strict"
    assert "restoration_policy" not in FROZEN


def test_order_alternates_and_only_preregistered_development_environments_run(monkeypatch):
    assert [H.arm_order(t) for t in range(3)] == [["A", "B"], ["B", "A"], ["A", "B"]]
    monkeypatch.setattr(H, "tree_clean", lambda paths: True)
    monkeypatch.setattr(H, "EXPECTED_AGENT_TREE", None)
    for env in ("comfyui", "siyucms", "prestashop", "transfer_library", "coverage_lab"):
        with pytest.raises(SystemExit):
            H.run("diagnostic", 1, [env])


def _o(url, text, controls, markers=None, route=None):
    return {"url": url, "meaningful_text": text, "session_markers": markers or {}, "session_context": "c",
            "forms": [], "route_pattern": route or "/" + url.rsplit("/", 1)[-1].split("?")[0],
            "controls": [{"label": l, "target": t, "safe": True} for l, t in controls]}


def test_oracle_separates_safe_volatility_wrong_records_changed_rows_and_server_state():
    act = {"label": "Annotate current", "target": None}
    desk = lambda name: _o("http://h/desk", f"DeskCurrent record: {name}Annotate current", [("Annotate current", None)])
    assert H.oracle("volatile_lab", desk("Harbor survey"), desk("Quarry ledger"), act) == "unsafe:wrong_record"
    clock = lambda t: _o("http://h/clock", f"Clock deskLocal time {t}", [("Check in", None)])
    assert H.oracle("volatile_lab", clock("1"), clock("2"), {"label": "Check in"}) == "safe_volatile"
    board = lambda a, b: _o("http://h/board", f"Task boardCompleted: 1 / 6Archive logs{a}Rotate keys{b}",
                            [("Archive logs", "http://h/board/task/3"), ("Rotate keys", "http://h/board/task/2")])
    link = {"label": "Archive logs", "target": "http://h/board/task/3"}
    assert H.oracle("volatile_lab", board("—", "—"), board("—", "✓ visit #1"), link) == "safe_volatile"
    assert H.oracle("volatile_lab", board("—", "—"), board("✓ visit #1", "—"), link) == "unsafe:target_row_changed"
    res = lambda score, row: _o("http://h/results", f"Results Tool: default — {score} / 59 reached Plain link {row} next",
                                [("Plain link", "http://h/test/1")], route="/results")
    plain = {"label": "Plain link", "target": "http://h/test/1"}
    assert H.oracle("crawlground", res("0", "· — —"), res("1", "· — —"), plain) == "safe_volatile"
    assert H.oracle("crawlground", res("0", "· — —"), res("1", "✓ 2026-11-05T22:03:48.737Z 1"),
                    plain) == "unsafe:target_row_changed"
    root = lambda links: _o("http://h/", "Records " + " ".join(links), [(l, f"http://h/records/{i}")
                                                                       for i, l in enumerate(links)], route="/")
    beta = {"label": "Beta", "target": "http://h/records/1"}
    assert H.oracle("stateful_lab", root(["Alpha", "Beta"]), root(["Alpha", "Beta", "GET mutation"]),
                    beta) == "server_state_changed"
    other = _o("http://h/clock", "x", [("Check in", None)], markers={"cookie_names": ["sid"]})
    assert H.oracle("volatile_lab", clock("1"), other, {"label": "Check in"}) == "unsafe:different_context"
