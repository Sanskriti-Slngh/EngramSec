"""Named RunConfig profiles: the 'general' preset is the validated, read-only, works-on-any-website set;
'default' is the frozen baseline; 'pentest' adds authorized write-chaining and must refuse to build without
a disposable attestation."""
import pytest

from agent1.profiles import PROFILES, build_config, profile_names

_COMMON = dict(start_url="http://example.test/", output_dir="/tmp/agent1-profile-test")


def test_default_profile_is_frozen_baseline() -> None:
    c = build_config("default", **_COMMON)
    assert c.exploration_mode == "fresh"
    assert c.readiness_any_enabled is False
    assert c.session_loss_guard is False
    assert c.follow_client_navigation is False
    assert c.effective_write_policy == "read_only"


def test_general_profile_is_read_only_and_spa_ready() -> None:
    c = build_config("general", **_COMMON)
    # validated general-web traversal set
    assert c.exploration_mode == "persistent"
    assert c.runtime_listener_observation == "revisit"
    assert c.robust_readiness and c.readiness_any_enabled and c.readiness_strategy == "adaptive"
    assert c.loopback_origin_equivalence and c.neutralize_blocked_writes
    assert c.eager_child_expansion and c.exhaustive_local_controls
    assert c.follow_client_navigation and c.await_spa_route_change and c.session_loss_guard
    # SAFE on an arbitrary site: no writes, no form POSTs
    assert c.effective_write_policy == "read_only"
    assert c.allow_post_forms is False


def test_pentest_profile_requires_disposable_attestation() -> None:
    # The write-chaining profile mutates the target, so RunConfig's validators must reject it without a
    # 'disposable:' attestation.
    with pytest.raises(Exception):
        build_config("pentest", **_COMMON)
    c = build_config("pentest", environment_attestation="disposable: throwaway CI target", **_COMMON)
    assert c.effective_write_policy == "disposable"
    assert c.allow_post_forms is True
    assert c.write_execution_policy == "focused_adaptive"
    assert c.execute_js_driven_writes is True


def test_run_kwargs_override_profile_and_drop_none() -> None:
    c = build_config("general", context_label="admin", max_seconds=300, storage_state_path=None, **_COMMON)
    assert c.context_label == "admin"
    assert c.max_seconds == 300
    assert c.storage_state_path is None            # None dropped -> schema default stands
    assert c.exploration_mode == "persistent"      # profile value untouched


def test_unknown_profile_rejected() -> None:
    with pytest.raises(ValueError):
        build_config("nope", **_COMMON)
    assert set(profile_names()) == set(PROFILES) == {"default", "general", "pentest"}
