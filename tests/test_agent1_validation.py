from __future__ import annotations

from pathlib import Path

import pytest

from agent1.explorer import Explorer
from agent1.explorer import EXTRACT_SCRIPT
from agent1.schema import EvidenceStatus, FunctionalStatus, RunConfig
from agent1.state import content_fingerprint
from playwright.sync_api import sync_playwright
from tests.fixtures.content_filter_cases import CONTENT_FILTER_CASES
from tests.fixtures.interactive_app import start_server


@pytest.fixture(scope="module")
def interactive_server():
    server, thread = start_server()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run_case(server, tmp_path: Path, case: str, *, transitions: int = 1):
    server.state.reset()
    artifact = Explorer(
        RunConfig(
            start_url=f"{server.base_url}/{case}",
            output_dir=tmp_path / case,
            policy="grouped",
            max_seconds=10,
            max_transitions=transitions,
            max_browser_actions=100,
            allow_post_forms=True,
            replay_reserve_fraction=0.45,
            context_label=f"fixture:{case}",
        ),
        Path(__file__).resolve().parents[1],
    ).run()
    return artifact, server.state.snapshot()


def test_same_url_result_change_fails_content_sensitive_replay(interactive_server, tmp_path: Path) -> None:
    artifact, events = run_case(interactive_server, tmp_path, "search")
    assert {item["result"] for item in events if item.get("kind") == "search_result"} == {
        "Result Alpha",
        "Result Beta",
    }
    assert len({item.group_signature for item in artifact.observations}) == 2
    assert artifact.metrics.replay_failures == 1
    assert artifact.metrics.functional_workflows_verified == 0


def test_observed_constraints_enable_verified_form_success(interactive_server, tmp_path: Path) -> None:
    artifact, events = run_case(interactive_server, tmp_path, "form")
    submissions = [item["success"] for item in events if item.get("kind") == "form_submission"]
    assert submissions and all(submissions)
    assert artifact.metrics.functional_workflows_verified == 1
    assert artifact.functional_workflows[0].status == FunctionalStatus.VERIFIED


def test_multistep_replay_reproduces_prerequisite(interactive_server, tmp_path: Path) -> None:
    artifact, events = run_case(interactive_server, tmp_path, "multi", transitions=8)
    completions = [item for item in events if item.get("kind") == "completion"]
    assert completions
    assert all(item["success"] and item["prerequisite"] for item in completions)
    assert artifact.metrics.functional_workflows_verified >= 1
    assert any(item.path_length >= 2 for item in artifact.functional_workflows)


def test_wrong_record_instance_is_not_accepted(interactive_server, tmp_path: Path) -> None:
    artifact, events = run_case(interactive_server, tmp_path, "records")
    visits = [item["record"] for item in events if item.get("kind") == "record_visit"]
    assert visits == ["2", "1"]
    assert artifact.replays[0].status == EvidenceStatus.FAILED
    assert artifact.replays[0].outcome_checks["content_fingerprint"] is False


def test_cosmetic_time_does_not_split_and_connections_are_complete(
    interactive_server, tmp_path: Path
) -> None:
    artifact, _ = run_case(interactive_server, tmp_path, "cosmetic")
    observations = [item for item in artifact.observations if item.route_pattern == "/cosmetic"]
    assert len({item.group_signature for item in observations}) == 1
    assert len({item.state_signature for item in observations}) == 1
    assert artifact.metrics.graph_connections_missing_evidence == 0


@pytest.mark.parametrize(
    ("case_name", "before_html", "after_html", "equivalent"),
    CONTENT_FILTER_CASES,
    ids=[item[0] for item in CONTENT_FILTER_CASES],
)
def test_content_filter_preserves_workflow_meaning(
    case_name: str,
    before_html: str,
    after_html: str,
    equivalent: bool,
) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(before_html)
        before = page.evaluate(EXTRACT_SCRIPT)["meaningful_text"]
        page.set_content(after_html)
        after = page.evaluate(EXTRACT_SCRIPT)["meaningful_text"]
        browser.close()

    assert (content_fingerprint(before) == content_fingerprint(after)) is equivalent, case_name
    if case_name == "carousel_content":
        assert "Campaign Alpha" in before
        assert "Campaign Beta" in after


def test_implicit_id_marked_toggle_is_observed() -> None:
    html = (
        '<main><i id="toggle-search" style="display:block;width:20px;height:20px"></i>'
        '<form><input type="search" name="query"><button>Search</button></form></main>'
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html)
        controls = page.evaluate(EXTRACT_SCRIPT)["controls"]
        browser.close()

    toggle = next(item for item in controls if item["label"] == "toggle search")
    assert toggle["kind"] == "button"
    assert toggle["role"] == "button"


def test_semantic_controls_are_observed_but_disabled_and_hidden_are_not() -> None:
    html = """<main>
      <div role="tab" tabindex="0">Analytics</div>
      <details><summary>Advanced settings</summary><p>Hidden body</p></details>
      <span tabindex="0" data-action="navigate">Help center</span>
      <span tabindex="-1">Programmatic focus only</span>
      <input tabindex="0" name="ordinary-field" value="Not an action">
      <button disabled>Disabled action</button>
      <button style="display:none">Hidden action</button>
    </main>"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html)
        controls = page.evaluate(EXTRACT_SCRIPT)["controls"]
        browser.close()

    labels = {item["label"] for item in controls}
    assert {"Analytics", "Advanced settings", "Help center"}.issubset(labels)
    assert labels.isdisjoint({
        "Programmatic focus only", "Not an action", "Disabled action", "Hidden action"
    })
