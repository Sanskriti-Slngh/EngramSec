from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from agent1.explorer import BrowserSession, Explorer
from agent1.schema import ActionDescriptor, FormField, RunConfig
from agent1.state import allowed_origin
from development_apps.js_heavy_lab import start_js_heavy_lab


def test_origin_aliases_are_explicit_loopback_only(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="loopback origins"):
        RunConfig(
            start_url="http://127.0.0.1:8000/",
            output_dir=tmp_path,
            origin_aliases=["https://example.com"],
        )
    config = RunConfig(
        start_url="http://127.0.0.1:8000/",
        output_dir=tmp_path,
        origin_aliases=["http://localhost:8000"],
    )
    assert allowed_origin(config.start_url, "http://localhost:8000/area", config.origin_aliases)
    assert not allowed_origin(config.start_url, "http://localhost:9000/area", config.origin_aliases)
    assert not allowed_origin(config.start_url, "https://example.com/", config.origin_aliases)


def test_action_budget_reserves_complete_form_action(tmp_path: Path) -> None:
    explorer = Explorer(
        RunConfig(
            start_url="http://127.0.0.1:8000/",
            output_dir=tmp_path,
            max_browser_actions=10,
        ),
        Path(__file__).resolve().parents[1],
    )
    descriptor = ActionDescriptor(
        control_id="submit",
        kind="form_submit",
        label="Submit",
        role="button",
        css_path="button",
        fields=[
            FormField(name="first", input_type="text"),
            FormField(name="second", input_type="select"),
        ],
        signature="form",
    )
    explorer.artifact.metrics.browser_actions = 8
    assert explorer._descriptor_action_cost(descriptor) == 3
    assert not explorer._fits_action_budget(explorer._descriptor_action_cost(descriptor))


def test_readiness_observes_hydrated_controls_and_initial_network(tmp_path: Path) -> None:
    server, thread, start_url = start_js_heavy_lab()
    try:
        config = RunConfig(
            start_url=start_url,
            output_dir=tmp_path,
            robust_readiness=True,
            readiness_timeout_ms=2_000,
            readiness_poll_ms=100,
            origin_aliases=[f"http://localhost:{server.server_port}"],
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                with BrowserSession(browser, config) as session:
                    session.goto_start()
                    observation = session.observe(1)
                    labels = {item.label: item for item in observation.controls}
                    assert observation.readiness.status == "usable"
                    assert "Open workflow" in labels
                    assert "Load late reports" in labels
                    assert labels["Public alias area"].safe
                    assert not labels["External documentation"].safe
                    assert any(
                        "/api/bootstrap" in event.url
                        for event in session.last_navigation_network
                    )
                    changed_context = observation.model_copy(
                        update={
                            "session_markers": {
                                "cookie_names": ["member_session"],
                                "local_storage_keys": [],
                                "session_storage_keys": [],
                            }
                        }
                    )
                    assert not Explorer._usable_return_screen(observation, changed_context)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_persistent_discovery_keeps_fresh_replay_and_provenance(tmp_path: Path) -> None:
    server, thread, start_url = start_js_heavy_lab()
    try:
        config = RunConfig(
            start_url=start_url,
            output_dir=tmp_path / "persistent",
            policy="coverage",
            max_seconds=30,
            max_transitions=10,
            max_browser_actions=80,
            replay_reserve_fraction=0.35,
            allow_post_forms=True,
            robust_readiness=True,
            readiness_timeout_ms=2_000,
            origin_aliases=[f"http://localhost:{server.server_port}"],
            exploration_mode="persistent",
        )
        artifact = Explorer(config, Path(__file__).resolve().parents[1]).run()
        assert artifact.metrics.live_state_reuses > 0
        assert artifact.metrics.restoration_actions == 0
        assert artifact.replays
        assert artifact.metrics.replay_navigation_successes == artifact.metrics.replay_attempts
        assert any(item.reason == "replay" for item in artifact.navigation_evidence)
        assert any(
            "/api/bootstrap" in event.url
            for item in artifact.navigation_evidence
            for event in item.network
        )
        assert "member-secret-9f31" not in artifact.model_dump_json()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
