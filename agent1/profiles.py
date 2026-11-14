"""Named RunConfig profiles — point Agent 1 at *any* website without hand-setting a dozen flags.

Each profile is a dict of RunConfig field overrides, validated across the dev fixtures and the external
crawler benchmarks (see AGENT1_ROADBLOCK_FIXES.md). A profile only sets exploration/readiness/safety
behaviour; run-shaping fields the caller always provides (start_url, output_dir, budgets, auth, attestation)
are layered on top by `build_config`.

Profiles
--------
- "default"  : the frozen baseline — every opt-in capability OFF. Byte-identical to the historical config.
- "general"  : the validated general-web traversal set, READ-ONLY and safe to run on an arbitrary
               (possibly production) site — no writes, no form POSTs. Handles SPAs (persistent exploration,
               runtime listeners, hydration-aware readiness, client-side route changes), loopback origin
               aliases, per-leaf control exercise, and (when a session is supplied) the logout session-loss
               guard. This is the "works on any website" profile.
- "pentest"  : "general" PLUS the authorized write-chaining layer (form POSTs + disposable write policy +
               focused adaptive write execution + JS-driven writes). This MUTATES the target, so it is only
               valid against a disposable / explicitly-authorized environment and requires an
               `environment_attestation` beginning with "disposable:". The agent still never types live
               credentials — authenticated surface comes from an operator-provided `storage_state_path`.
"""
from __future__ import annotations

from typing import Any

from .schema import RunConfig

# The validated general-web flag set (read-only safe). Rationale per flag is in AGENT1_ROADBLOCK_FIXES.md
# and the agent1-general-traversal-roadblocks memory.
_GENERAL: dict[str, Any] = {
    "policy": "coverage",
    "exploration_mode": "persistent",       # explore from the live mutated state (SPAs, stateful lists)
    "state_aware_exploration": True,
    "record_aware_graph": True,
    "runtime_listener_observation": "revisit",  # DevTools listeners: see addEventListener controls + refires
    "robust_readiness": True,               # wait out hydration instead of snapshotting a half-built page
    "readiness_any_enabled": True,          # ...but key "ready" off ANY enabled control, not just <main>
    "readiness_strategy": "adaptive",
    "loopback_origin_equivalence": True,    # localhost == 127.0.0.1 for scope
    "neutralize_blocked_writes": True,      # SAFE: a blocked write is fulfilled with a synthetic local 200;
                                            # the server never receives it. Keeps write-on-init SPAs alive.
    "eager_child_expansion": True,
    "eager_expansion_max": 12,
    "exhaustive_local_controls": True,      # exercise each reached state's own novel controls first
    "follow_client_navigation": True,       # chase meta-refresh / setTimeout / pushState navigations
    "await_spa_route_change": True,         # wait for a client-side route change before snapshotting
    "session_loss_guard": True,             # inert without storage_state_path; else recover from logout bounce
    # Read-only and safe for an arbitrary site: no writes, no form submissions.
    "write_policy": "read_only",
    "allow_post_forms": False,
}

# Authorized pentest profile: general + the write-chaining layer. Disposable/authorized targets ONLY.
_PENTEST: dict[str, Any] = {
    **_GENERAL,
    "allow_post_forms": True,
    "write_policy": "disposable",
    "write_execution_policy": "focused_adaptive",
    "execute_js_driven_writes": True,
}

PROFILES: dict[str, dict[str, Any]] = {
    "default": {},
    "general": _GENERAL,
    "pentest": _PENTEST,
}


def profile_names() -> list[str]:
    return list(PROFILES)


def build_config(profile: str, **run_kwargs: Any) -> RunConfig:
    """Construct a RunConfig from a named profile plus caller-supplied run-shaping fields.

    `run_kwargs` (start_url, output_dir, budgets, context_label, storage_state_path, environment_attestation,
    model_provider, ...) always win over the profile. `None` values in run_kwargs are dropped so the profile
    (or the schema default) stands. The `pentest` profile's disposable write policy is enforced by RunConfig's
    own validators (needs allow_post_forms=True — set by the profile — and an environment_attestation
    beginning with "disposable:", which the caller must supply)."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; choose one of {profile_names()}")
    merged: dict[str, Any] = {**PROFILES[profile]}
    for key, value in run_kwargs.items():
        if value is not None:
            merged[key] = value
    return RunConfig(**merged)
