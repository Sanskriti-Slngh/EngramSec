"""Adversarial contract tests for the experimental restoration contract (agent1/restoration.py).

Synthetic pages are built from a small page model so that each case isolates one
difference between the saved page (E) and the page a restoration returned to (R).
``find_current`` is the explorer's real control matcher. Browser-level tests at the
end exercise the region script on the volatile-state fixture.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent1.explorer import BrowserSession, Explorer, UnsafeRestoration
from agent1.restoration import condense, declarative, evaluate
from agent1.schema import ActionDescriptor, Control, FormField, FormObservation, Observation, RunConfig
from agent1.state import content_fingerprint, control_signature, digest, route_pattern, signatures

BASE = "http://127.0.0.1:9/"


def ctl(label, css, kind="button", target=None, container="", handler="", listener=None, revision=None,
        provenance="snapshot", method=None, fields=()):
    return dict(label=label, css=css, kind=kind, target=target, container=container, handler=handler,
                listener=listener, revision=revision, provenance=provenance, method=method, fields=list(fields))


def page(path="board", controls=(), regions=None, title="Board", markers=None, context="anon", hidden=(),
         disabled=(), hit=None, frames=1, forms=(), shadow=0):
    """(Observation, raw region capture) for one synthetic page."""
    url = BASE + path
    regions = dict(regions or {})
    built = []
    for c in controls:
        role = "link" if c["kind"] == "link" else "button"
        sig = control_signature(c["kind"], role, c["label"], c["target"], c["method"], "click", "main")
        cid = "ctl_" + digest([url, c["css"], sig], 18)
        if c["css"] in hidden or c["css"] in disabled:
            continue
        built.append(Control(id=cid, kind=c["kind"], label=c["label"], css_path=c["css"], role=role, target=c["target"],
                             method=c["method"], signature=sig, component="main", provenance=c["provenance"],
                             behavior_revision=c["revision"], fields=c["fields"],
                             listener_evidence={"handler_locations": c["listener"]} if c["listener"] else None))
    forms = [FormObservation(index=i, method=m, action=BASE + a, fields=[FormField(name=n, input_type="text")])
             for i, (m, a, n) in enumerate(forms)]
    text = " ".join(v[0] for v in regions.values())
    raw_sig, group, pattern = signatures(url=url, title=title, controls=built, forms=forms, session_context=context,
                                         session_markers=markers or {}, meaningful_text=text)
    obs = Observation(id="obs_" + digest([url, raw_sig, text, path], 10), sequence=1, url=url, title=title,
                      text_excerpt=text, meaningful_text=text, content_fingerprint=content_fingerprint(text),
                      controls=built, forms=forms, state_signature=raw_sig, group_signature=group,
                      session_context=context, session_markers=markers or {}, route_pattern=pattern,
                      instance_facts={"frame_count": frames})
    raw = {"title": title, "shadow_roots": shadow,
           "regions": {k: {"text": v[0], "container": v[1] if len(v) > 1 else "",
                           "identity": len(v) > 2 and v[2] == "identity", "status": len(v) > 2 and v[2] == "status"}
                       for k, v in regions.items()},
           "controls": [[c["label"], c["target"] or ""] for c in controls if c["css"] not in disabled],
           "probe": {c["css"]: {"shown": True, "hit": (hit or {}).get(c["css"], "self"), "labels": [c["label"]],
                                "href": c["target"] or "", "handler": c["handler"], "container": c["container"],
                                "disabled": c["css"] in disabled} for c in controls}}
    return obs, raw


def decide(e, r, label, samples=None, start=BASE):
    """Evaluate the contract for the E control labelled ``label``; samples default to R's capture once."""
    (eo, eraw), (ro, rraw) = e, r
    control = next(c for c in eo.controls if c.label == label)
    action = BrowserSession.descriptor(control)
    current = BrowserSession.find_current(None, ro, action)
    caps = [condense(x) for x in (samples or [rraw])]
    return evaluate(eo, ro, action, current, condense(eraw), caps, start)


def resample(raw, **changes):
    """Copy of a raw capture with some region texts changed (a later passive sample)."""
    out = {**raw, "regions": {k: dict(v) for k, v in raw["regions"].items()}, "controls": list(raw["controls"])}
    for key, text in changes.items():
        if text is None:
            out["regions"].pop(key, None)
        else:
            out["regions"].setdefault(key, {"text": "", "container": "", "identity": False, "status": False})
            out["regions"][key]["text"] = text
    return out


# ------------------------------------------------------------------ fixtures of the page model
ROW = "body:1/main:1/table:1/tbody:1/tr:{}"


def board(done=0, marked=(), target_row_text=None, extra_link=False):
    """Three task rows; ``extra_link`` adds a record link the way stateful_lab's GET /counter does."""
    rows = {}
    controls = []
    for k in (1, 2, 3):
        rows[ROW.format(k) + "/td:1/a:1"] = (f"Task {k}", ROW.format(k))
        mark = "✓ visit" if k in marked else "—"
        rows[ROW.format(k) + "/td:2"] = (target_row_text if (k == 2 and target_row_text) else mark, ROW.format(k))
        controls.append(ctl(f"Task {k}", f"tr:nth-of-type({k}) a", kind="link", target=BASE + f"board/task/{k}",
                            container=ROW.format(k)))
    if extra_link:
        controls.append(ctl("GET mutation", "a:nth-of-type(9)", kind="link", target=BASE + "board/task/9"))
    regions = {"body:1/main:1/h1:1": ("Task board", "", "identity"),
               "body:1/main:1/p:1": (f"Completed: {done} / 3", ""), **rows}
    return controls, regions


def clock_page(time_text, out_text="", extra=None):
    controls = [ctl("Check in", "#in"), ctl("Check out", "#out-btn"), ctl("Clock home", "nav a", kind="link",
                                                                           target=BASE)]
    regions = {"body:1/main:1/h1:1": ("Clock desk", "", "identity"), "body:1/main:1/p:1/span:1": (time_text, ""),
               **({"body:1/main:1/div:2": (out_text, "")} if out_text else {}), **(extra or {})}
    return controls, regions


# ------------------------------------------------------------------ 1. volatile clock
def test_volatile_clock_with_unchanged_controls_is_accepted_after_passive_observation():
    e = page("clock", *clock_page("Local time 10:00:00.100"), title="Clock desk")
    r = page("clock", *clock_page("Local time 10:00:05.300"), title="Clock desk")
    first = decide(e, r, "Check in")
    assert not first.accepted and first.needs_samples and first.reasons == ["content_changed"]
    later = [r[1], resample(r[1], **{"body:1/main:1/p:1/span:1": "Local time 10:00:05.600"}),
             resample(r[1], **{"body:1/main:1/p:1/span:1": "Local time 10:00:05.900"})]
    d = decide(e, r, "Check in", later)
    assert d.accepted and d.tier == "contextual" and d.tolerated == {"volatile_region": 1}


def test_clock_that_stops_changing_is_not_volatile():
    e = page("clock", *clock_page("Local time 10:00:00.100"), title="Clock desk")
    r = page("clock", *clock_page("Local time 10:00:05.300"), title="Clock desk")
    d = decide(e, r, "Check in", [r[1], r[1], r[1]])
    assert not d.accepted and d.reasons == ["content_changed"]


# ------------------------------------------------------------------ 2. changing score counter
def test_score_counter_outside_the_target_row_is_tolerated_for_a_declarative_link():
    e = page("board", *board(done=0))
    r = page("board", *board(done=1, marked=(1,)))
    d = decide(e, r, "Task 2", [r[1], r[1], r[1]])
    assert d.accepted and d.tier == "declarative" and d.tolerated == {"outside_scope": 2}


def test_score_counter_refuses_a_contextual_action_and_a_changed_target_row():
    controls, regions = board(done=0)
    controls.append(ctl("Refresh board", "#refresh"))
    e = page("board", controls, regions)
    controls2, regions2 = board(done=1, marked=(1,))
    controls2.append(ctl("Refresh board", "#refresh"))
    r = page("board", controls2, regions2)
    assert decide(e, r, "Refresh board", [r[1]] * 3).reasons == ["content_changed"]
    e2, r2 = page("board", *board(done=0)), page("board", *board(done=1, marked=(2,)))
    assert decide(e2, r2, "Task 2", [r2[1]] * 3).reasons == ["target_context_changed"]


# ------------------------------------------------------------------ 3. dynamic carousel
def carousel(slide):
    controls = [ctl(f"Learn about slide {slide}", ".carousel a", kind="link", target=BASE + f"slide/{slide}",
                    container="body:1/main:1/section:1"), ctl("Add to wishlist", "#wish")]
    regions = {"body:1/main:1/h1:1": ("Showcase", "", "identity"),
               "body:1/main:1/section:1/p:1": (f"Slide {slide}", "body:1/main:1/section:1")}
    return controls, regions


def test_carousel_rotation_does_not_redefine_the_state_for_an_action_outside_it():
    e = page("showcase", *carousel(1), title="Showcase")
    r = page("showcase", *carousel(2), title="Showcase")
    samples = [r[1], page("showcase", *carousel(3), title="Showcase")[1], r[1]]
    d = decide(e, r, "Add to wishlist", samples)
    assert d.accepted and d.tolerated == {"volatile_region": 1, "affordance_volatile": 2}


def test_a_carousel_slide_link_is_never_restored_from_another_slide():
    e = page("showcase", *carousel(1), title="Showcase")
    r = page("showcase", *carousel(2), title="Showcase")
    d = decide(e, r, "Learn about slide 1", [r[1], page("showcase", *carousel(3), title="Showcase")[1], r[1]])
    # The explorer's matcher normalizes digits, so it offers "slide 2" for "slide 1"; the contract refuses it.
    assert d.tier == "declarative" and BrowserSession.find_current(None, r[0], BrowserSession.descriptor(
        e[0].controls[0])).label == "Learn about slide 2"
    assert not d.accepted and "target_changed" in d.reasons


# ------------------------------------------------------------------ 4. two records with the same controls
def record(name, path="records?id=1", hidden_value=None, in_card=False):
    card = "body:1/main:1/article:1"
    controls = [ctl("Open history", "#history", container=card if in_card else ""),
                ctl("Help", "a.help", kind="link", target=BASE + "help")]
    regions = {"body:1/main:1/h1:1": ("Record", "", "identity")}
    if in_card:
        regions[card + "/p:1"] = (name, card)
    else:
        regions["body:1/main:1/h2:1"] = (name, "", "identity")
    if hidden_value is not None:
        regions["body:1/main:1/input:1#value"] = (hidden_value, "", "identity")
    return page(path, controls, regions, title="Record")


def test_two_records_with_identical_controls_are_never_confused():
    one, two = record("Harbor survey"), record("Quarry ledger", path="records?id=2")
    assert decide(one, two, "Open history").reasons == ["record_identity_changed"]
    same_url = record("Quarry ledger")
    for label in ("Open history", "Help"):                  # contextual and declarative alike
        assert decide(record("Harbor survey"), same_url, label, [same_url[1]] * 3).reasons == ["page_identity_changed"]
    hidden_a, hidden_b = record("Desk", hidden_value="1"), record("Desk", hidden_value="2")
    assert decide(hidden_a, hidden_b, "Help", [hidden_b[1]] * 3).reasons == ["page_identity_changed"]
    card_a, card_b = record("Harbor survey", in_card=True), record("Quarry ledger", in_card=True)
    assert decide(card_a, card_b, "Open history", [card_b[1]] * 3).reasons == ["target_context_changed"]


def test_existing_shape_tolerance_would_accept_the_query_borne_wrong_record():
    """Audit finding: `_usable_return_screen` ignores query values and content, and `record_instance`
    is None for query-identified records, so the existing tolerance (enabled by robust_readiness or
    search) accepts record ?id=2 for ?id=1. The contract refuses it (previous test)."""
    from agent1.action_behavior import record_instance
    one, two = record("Harbor survey")[0], record("Quarry ledger", path="records?id=2")[0]
    assert Explorer._usable_return_screen(one, two)
    assert record_instance(one) == record_instance(two) is None


# ------------------------------------------------------------------ 5. two sessions, identical visible pages
def test_two_sessions_with_identical_visible_pages_are_refused():
    controls, regions = clock_page("Local time 10:00:00.100")
    anon = page("clock", controls, regions)
    for kwargs in ({"markers": {"cookie_names": ["member_session"]}}, {"context": "member"}):
        other = page("clock", controls, regions, **kwargs)
        assert decide(anon, other, "Check in").reasons == ["session_changed"]


# ------------------------------------------------------------------ 6. changed handler or meaning
def test_a_control_whose_target_handler_or_revision_changed_is_refused():
    base = [ctl("Open", "#open", kind="link", target=BASE + "items/1"), ctl("Run", "#run", handler="go(1)")]
    e = page("p", base, {"body:1/main:1/h1:1": ("P", "", "identity")})
    retarget = lambda target: page("p", [ctl("Open", "#open", kind="link", target=BASE + target), base[1]],
                                   {"body:1/main:1/h1:1": ("P", "", "identity")})
    assert "target_changed" in decide(e, retarget("items/2"), "Open").reasons   # matcher accepts the same route shape
    assert decide(e, retarget("other"), "Open").reasons == ["target_absent"]
    rehandled = page("p", [base[0], ctl("Run", "#run", handler="go(2)")], {"body:1/main:1/h1:1": ("P", "", "identity")})
    assert decide(e, rehandled, "Run").reasons == ["handler_changed"]
    lis = lambda loc: [ctl("Save", "div.save", provenance="observed_listener", listener=[loc])]
    le = page("p", lis("app.js:10:2"), {"body:1/main:1/h1:1": ("P", "", "identity")})
    lr = page("p", lis("app.js:44:9"), {"body:1/main:1/h1:1": ("P", "", "identity")})
    assert decide(le, lr, "Save").reasons == ["handler_changed"]
    re_ = page("p", [ctl("Save", "div.save", provenance="observed_listener", revision="rev1")],
               {"body:1/main:1/h1:1": ("P", "", "identity")})
    rr = page("p", [ctl("Save", "div.save", provenance="observed_listener")], {"body:1/main:1/h1:1": ("P", "", "identity")})
    assert decide(re_, rr, "Save").reasons == ["target_absent"]


# ------------------------------------------------------------------ 7. disabled after a prerequisite
def test_an_action_disabled_after_a_prerequisite_is_refused():
    controls = [ctl("Continue", "#continue"), ctl("Back", "#back")]
    regions = {"body:1/main:1/h1:1": ("Wizard", "", "identity")}
    e = page("wizard", controls, regions)
    r = page("wizard", controls, regions, disabled=("#continue",))
    assert "target_disabled" in decide(e, r, "Continue").reasons


# ------------------------------------------------------------------ 8. GET that mutates server state
def test_an_unflagged_get_mutation_that_adds_an_affordance_is_refused():
    """stateful_lab: /counter inserts a record; the restored list has one more record link."""
    e = page("board", *board(done=0))
    r = page("board", *board(done=0, extra_link=True))
    d = decide(e, r, "Task 1", [r[1]] * 3)
    assert not d.accepted and d.reasons == ["affordance_added"]


class _FakeSession:
    def __init__(self, observation):
        self.observation, self.executed = observation, []

    def observe(self, _):
        return self.observation

    def find_current(self, observation, descriptor):
        return BrowserSession.find_current(None, observation, descriptor)

    def execute(self, control, *_):
        self.executed.append(control.label)
        return [], [], [], 1


@pytest.mark.parametrize("behavior", [{"possible_state_change": True}, {"write_capable_request_observed": True}])
def test_return_paths_through_a_mutating_get_or_an_observed_write_are_refused_before_the_contract(tmp_path, behavior):
    from agent1.action_behavior import action_identity
    from agent1.schema import EvidenceStatus, Transition
    explorer = Explorer(RunConfig(start_url=BASE, output_dir=tmp_path, restoration_policy="contract"), tmp_path)
    obs, _ = page("board", *board())
    step = BrowserSession.descriptor(obs.controls[0])
    explorer.artifact.transitions.append(Transition(
        id="t1", source_observation_id=obs.id, source_state_signature=obs.state_signature,
        source_group_signature=obs.group_signature, action=step, workflow_path=[step], status=EvidenceStatus.OBSERVED,
        result_observation_id=obs.id, result_state_signature=obs.state_signature,
        result_group_signature=obs.group_signature,
        behavior={"action_identity": action_identity(obs, step), **behavior}, started_at="x", ended_at="x",
        run_id="r"))
    session = _FakeSession(obs)
    with pytest.raises(UnsafeRestoration):
        explorer._restore(session, [step], [])
    assert session.executed == []


# ------------------------------------------------------------------ 9. same-label controls with different targets
def test_same_label_controls_with_different_targets_are_refused():
    one = [ctl("Open", "li:nth-of-type(1) a", kind="link", target=BASE + "items/1")]
    two = one + [ctl("Open", "li:nth-of-type(2) a", kind="link", target=BASE + "items/2")]
    head = {"body:1/main:1/h1:1": ("Items", "", "identity")}
    e, r = page("items", one, head), page("items", two, head)
    d = decide(e, r, "Open", [r[1]] * 3)
    assert not d.accepted and "target_ambiguous" in d.reasons
    swapped = [ctl("Open", "li:nth-of-type(1) a", kind="link", target=BASE + "items/2"),
               ctl("Open", "li:nth-of-type(2) a", kind="link", target=BASE + "items/1")]
    e2, r2 = page("items", two, head), page("items", swapped, head)
    assert "target_changed" in decide(e2, r2, "Open").reasons


# ------------------------------------------------------------------ snapshot artefacts and evidence limits
def test_a_control_dropped_only_by_the_snapshot_occlusion_test_counts_as_present():
    """Crawlground /results: a wrapped link whose box centre falls on its own cell."""
    controls, regions = board(done=0)
    e = page("board", controls, regions)
    r = page("board", controls, regions, hidden=("tr:nth-of-type(3) a",), hit={"tr:nth-of-type(3) a": "self"})
    d = decide(e, r, "Task 1")
    assert d.accepted and d.tolerated == {"affordance_present_in_dom": 1}
    covered = page("board", controls, regions, hidden=("tr:nth-of-type(3) a",), hit={"tr:nth-of-type(3) a": "other"})
    assert decide(e, covered, "Task 1", [covered[1]] * 3).reasons == ["affordance_removed"]


def test_missing_evidence_frames_and_unlocalized_changes_are_refused():
    e = page("clock", *clock_page("Local time 1"))
    r = page("clock", *clock_page("Local time 2"))
    (eo, eraw), (ro, rraw) = e, r
    action = BrowserSession.descriptor(eo.controls[0])
    current = BrowserSession.find_current(None, ro, action)
    assert evaluate(eo, ro, action, current, None, [condense(rraw)], BASE).reasons == ["no_region_evidence"]
    framed = page("clock", *clock_page("Local time 2"), frames=2)
    assert "multi_frame_state_unsupported" in decide(e, framed, "Check in").reasons
    # The snapshot text differs but no region does (e.g. shadow DOM): refused, not tolerated.
    controls, regions = clock_page("Local time 1")
    shadowed = page("clock", controls, regions)
    shadowed = (shadowed[0].model_copy(update={"content_fingerprint": "different"}), shadowed[1])
    assert decide(e, shadowed, "Check in").reasons == ["unlocalized_content_change"]


def test_an_unchanged_page_is_accepted_without_sampling_and_form_schema_changes_are_refused():
    e = page("clock", *clock_page("Local time 1"))
    d = decide(e, e, "Check in")
    assert d.accepted and d.samples == 1 and not d.tolerated
    fe = page("clock", *clock_page("Local time 1"), forms=[("GET", "search", "q")])
    fr = page("clock", *clock_page("Local time 1"), forms=[("GET", "search", "query")])
    assert decide(fe, fr, "Check in").reasons == ["form_schema_changed"]


def test_declarative_tier_requires_a_same_origin_handler_free_snapshot_link():
    link = Control(id="c", kind="link", label="x", css_path="a", role="link", target=BASE + "a", signature="s")
    assert declarative(link, BASE, [], {"handler": ""})
    assert not declarative(link, BASE, [], {"handler": "abc"})
    assert not declarative(link.model_copy(update={"target": "http://elsewhere.test/"}), BASE, [], None)
    assert not declarative(link.model_copy(update={"provenance": "observed_listener"}), BASE, [], None)
    assert not declarative(link.model_copy(update={"kind": "button"}), BASE, [], None)


def test_default_policy_is_strict_and_captures_no_region_evidence(tmp_path):
    config = RunConfig(start_url=BASE, output_dir=tmp_path)
    assert config.restoration_policy == "strict"
    assert Explorer(config, tmp_path)._region_maps is None


# ------------------------------------------------------------------ browser: region evidence on the fixture
@pytest.fixture(scope="module")
def lab():
    from development_apps.volatile_lab import start_volatile_lab
    server, url, state = start_volatile_lab()
    yield url, state
    server.shutdown()


def _capture(page_, probe=()):
    from agent1.restoration import collect
    return collect(page_, list(probe))


def test_browser_region_evidence_detects_clock_and_carousel_volatility_and_the_wrapped_link(lab):
    from playwright.sync_api import sync_playwright

    from agent1.explorer import EXTRACT_SCRIPT
    url, _ = lab
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        for path, expect in (("clock", 1), ("showcase", 2)):
            pg.goto(url + path)
            pg.wait_for_timeout(250)
            caps = [_capture(pg)]
            for _ in range(2):
                pg.wait_for_timeout(330)
                caps.append(_capture(pg))
            keys = set().union(*(c["regions"] for c in caps))
            volatile = {k for k in keys if len({c["regions"].get(k, (None,))[0] for c in caps}) > 1}
            assert len(volatile) >= expect, path
        pg.goto(url + "wrap")
        pg.wait_for_timeout(250)
        labels = [c["label"] for c in pg.evaluate(EXTRACT_SCRIPT)["controls"]]
        assert "Link appears on scroll (IntersectionObserver)" not in labels      # snapshot occlusion artefact
        sel = "body > main > table > tbody > tr:nth-of-type(1) > td:nth-of-type(2) > a"
        probe = _capture(pg, [sel])["probe"][sel]
        assert probe["shown"] and probe["hit"] == "self"
        assert probe["labels"][0] == "Link appears on scroll (IntersectionObserver)"
        browser.close()
