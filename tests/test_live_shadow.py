"""Phase 2: live ACG and shadow tour scheduler against the deterministic Phase 2 fixture (real browser)."""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import pytest

from agent1.explorer import Explorer
from agent1.model.evidence import read_log
from agent1.model.importer import import_run_artifact
from agent1.model.materialize import materialize
from agent1.model.schema import Status
from agent1.schema import RunConfig
from development_apps.phase2_lab import ITEMS, start_phase2_lab

ROOT = Path(__file__).resolve().parents[1]
BUDGETED = dict(policy="multidimensional", exploration_mode="persistent", max_seconds=150, max_transitions=60,
                max_browser_actions=150, settle_ms=80, action_timeout_ms=1500, allow_post_forms=False,
                replay_policy="structure", state_aware_exploration=True, max_total_http_requests=600)
HOST = re.compile(r"127\.0\.0\.1:\d+")


def _run(shadow: bool, out: Path, start: str = "", **overrides):
    server, url, log, state = start_phase2_lab()
    try:
        explorer = Explorer(RunConfig(start_url=url + start, output_dir=out, shadow_tours=shadow,
                                      **{**BUDGETED, **overrides}), ROOT)
        artifact = explorer.run()
        return explorer, artifact, list(log)
    finally:
        server.shutdown()


@pytest.fixture(scope="module")
def runs():
    base = Path(tempfile.mkdtemp())
    return {"off": _run(False, base / "off"), "on": _run(True, base / "on"), "dir": base / "on"}


def _exploration(artifact):
    norm = lambda s: HOST.sub("H", s or "")
    return [(t.action.kind, t.action.css_path, norm(t.action.target),
             [(e.method, norm(e.url)) for e in t.network]) for t in artifact.transitions]


def test_legacy_exploration_and_writes_are_unchanged_by_shadow_mode(runs) -> None:
    (_, off, log_off), (_, on, log_on) = runs["off"], runs["on"]
    assert _exploration(off) == _exploration(on)
    writes = lambda log: sorted(x for x in log if x[0] == "POST")
    assert writes(log_off) == writes(log_on)
    assert len(off.replays) == len(on.replays)
    assert "shadow_tours" not in off.config and "acg_evidence" not in off.config


def test_acg_is_reconstructible_and_live_projection_matches_offline_import(runs) -> None:
    explorer, artifact, _ = runs["on"]
    rebuilt = materialize(read_log(runs["dir"] / "acg_evidence.jsonl")).model_dump(mode="json")
    assert rebuilt == json.loads((runs["dir"] / "live_acg.json").read_text())
    from agent1.live.acg import LiveACG
    plain = LiveACG("live", sink=None)
    plain.sync(artifact)
    assert [r.model_dump() for r in plain.records()] == \
        [r.model_dump() for r in import_run_artifact(artifact.model_dump(mode="json"), "live", "live")]


def test_persisted_evidence_holds_no_raw_identifiers_or_values(runs) -> None:
    for name in ("acg_evidence.jsonl", "live_acg.json", "shadow_decisions.jsonl", "shadow_summary.json"):
        text = (runs["dir"] / name).read_text()
        for raw in list(ITEMS) + ["90000", "engramsec-test", "\"news\"", "compact"]:
            assert raw not in text, (name, raw)


def test_live_acg_captures_required_concepts(runs) -> None:
    acg = json.loads((runs["dir"] / "live_acg.json").read_text())
    records = read_log(runs["dir"] / "acg_evidence.jsonl")
    affs = [a for r in records if r.kind == "observation" for a in r.affordances or []]
    assert any(a.disabled for a in affs) and any(a.disabled is False for a in affs)
    preds = {c["predicate"] for c in acg["claims"]}
    assert "observed_disabled" in preds and "establishes" in preds         # Accept enables Continue
    item_instances = [i for i in acg["entity_instances"]
                      if any(re.search(r"/items/\d+$", p) for p in i["observed_paths"])]
    assert len({i["token"] for i in item_instances}) >= 2 and len(item_instances) == len({i["id"] for i in item_instances})
    posts = [o for o in acg["operations"] if o["method"] == "POST"]
    assert any(o["route"].endswith("/notes") for o in posts)               # method-less form that POSTs
    reqs = [q for r in records if r.kind == "action" for q in r.requests or []]
    assert any(q.response_shape for q in reqs) and any(q.id_tokens for q in reqs)
    by_id = {r.id: r for r in records}
    for cap in acg["capabilities"]:
        if cap["status"] == Status.VERIFIED:
            kinds = {by_id[e].verification_kind for e in cap["behavioral_class"]["evidence_ids"] if by_id[e].kind == "replay"}
            assert kinds & {"paired_search", "cross_view"}


def test_shadow_proposals_are_grounded_feasible_or_explained(runs) -> None:
    records = {r.id for r in read_log(runs["dir"] / "acg_evidence.jsonl")}
    proposals = [json.loads(line) for line in (runs["dir"] / "shadow_decisions.jsonl").read_text().splitlines()]
    assert proposals and not any("error" in p for p in proposals)
    for p in proposals:
        assert p["feasibility"] in {"executable_now", "executable_with_restoration", "no_feasible_question",
                                    "live_state_not_recorded", "control_missing_in_live_state",
                                    "restoration_unresolved", "unsupported_by_executor"}
        prop = p.get("proposal")
        if prop:
            assert "snapshot" not in prop["plan_ops"]
            if prop["kind"] != "find_entry_point":
                assert prop["evidence"] and set(prop["evidence"]) <= records
        assert p["capture_gaps"] is not None
    summary = json.loads((runs["dir"] / "shadow_summary.json").read_text())
    assert summary["scheduler_errors"] == 0 and summary["compared"] > 0


def test_websocket_frames_are_scoped_structural_and_attributed() -> None:
    # Without the HTTP budget router: under it, Chromium blocks local WebSockets on fulfilled pages
    # (a pre-existing legacy limitation, reported).
    out = Path(tempfile.mkdtemp())
    explorer, artifact, log = _run(True, out, start="live", max_total_http_requests=None, max_transitions=3,
                                   max_browser_actions=8, max_seconds=40, settle_ms=150)
    counters = explorer.evidence_sink.summary()["counters"]
    assert counters.get("ws_out_of_scope_refused", 0) >= 1
    assert counters.get("ws_frames_sent", 0) >= 1 and counters.get("ws_frames_received", 0) >= 1
    records = read_log(out / "acg_evidence.jsonl")
    sends = [q for r in records if r.kind == "action" for q in r.requests or [] if q.channel == "websocket_send"]
    assert sends and all(q.message_skeleton for q in sends)
    text = (out / "acg_evidence.jsonl").read_text()
    assert '"subscribe"' not in text and '"news"' not in text and "48213" not in text   # payload values


def test_pseudonymization_preserves_acg_semantics(runs) -> None:
    from agent1.live.acg import LiveACG
    from agent1.live.capture import EvidenceSink
    _, artifact, _ = runs["on"]
    raw = materialize(import_run_artifact(artifact.model_dump(mode="json"), "live", "live"))
    pseudo = LiveACG("live", sink=EvidenceSink())          # pseudonyms only: no extra capture attached
    pseudo.sync(artifact)
    live = pseudo.export()
    assert raw.summary == live.summary
    assert sorted(t.route for t in raw.templates) == sorted(t.route for t in live.templates)
    assert sorted(str(c.status) for c in raw.capabilities) == sorted(str(c.status) for c in live.capabilities)
    assert sorted(len(c.action_ids) for c in raw.capabilities) == sorted(len(c.action_ids) for c in live.capabilities)



def test_websockets_work_under_the_http_router_with_scope_enforced() -> None:
    out = Path(tempfile.mkdtemp())
    explorer, artifact, log = _run(True, out, start="live", max_transitions=3, max_browser_actions=8, max_seconds=40,
                                   settle_ms=150, websocket_local_access=True)   # BUDGETED keeps the HTTP router on
    counters = explorer.evidence_sink.summary()["counters"]
    assert counters.get("lna_granted_origins", 0) >= 1
    assert counters.get("ws_out_of_scope_refused", 0) >= 1               # out-of-scope socket never connected
    assert counters.get("ws_frames_sent", 0) >= 1 and counters.get("ws_frames_received", 0) >= 1
    assert any(p == "/ws" for _, p in log) and explorer.http_budget.redirect_scope_violations == 0
