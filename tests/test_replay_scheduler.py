"""Unit tests for the request-structure replay scheduler (no browser)."""
from __future__ import annotations

from types import SimpleNamespace as NS

from agent1.replay_scheduler import ReplayScheduler, request_structure_key, request_structures, structure_paths


def event(method="GET", url="http://h/api/x", rtype="fetch", params=(), status=200, enc=None, failure=None):
    return NS(method=method, url=url, resource_type=rtype, parameter_names=list(params), status=status,
              body_encoding=enc, failure=failure)


def transition(tid, depth, *structures_urls, request_only=True):
    return NS(id=tid, workflow_path=[None] * depth, network=[event(url=u) for u in structures_urls],
              request_only=request_only)


def scheduler(transitions, eligible=lambda t: True, attempts=2):
    pool = [(t, request_structures(t.network), 1 + len(t.workflow_path), eligible(t)) for t in transitions]
    shallow = sorted(((t, 1 + len(t.workflow_path)) for t in transitions), key=lambda x: (len(x[0].workflow_path), x[0].id))
    return ReplayScheduler(pool, shallow, max_attempts=attempts)


def of(t):
    return request_structures(t.network), t.request_only


def drain(s, outcome=lambda item: True):
    order = []
    while (item := s.next(of)) is not None:
        order.append((item.transition.id, item.lane, tuple(item.target_structures)))
        ok = outcome(item)
        s.record(item, ok, request_structures(item.transition.network) if ok else set(), item.cost,
                 None if ok else "control_missing")
    return order


def test_structure_key_is_normalized_and_value_free():
    a = request_structure_key(event(url="http://h/api/items/42/reviews?page=3&sort=new", params=("page", "sort")))
    b = request_structure_key(event(url="http://h/api/items/7/reviews?page=1&sort=old", params=("page", "sort")))
    assert a == b and "42" not in a and "new" not in a
    assert request_structure_key(event(rtype="stylesheet", url="http://h/s.css")) is None   # static subresource
    assert request_structure_key(event(rtype="document", url="http://h/page")) is None       # plain navigation
    assert request_structure_key(event(rtype="document", url="http://h/search?q=x", params=("q",))).startswith("document GET /search")
    assert request_structure_key(event(method="POST", rtype="document", url="http://h/login", params=("user",), enc="form")) \
        == "document POST /login [user] form"
    assert request_structure_key(event(status=None, failure="net::ERR_BLOCKED_BY_CLIENT")) is None
    # Record identity keeps the concrete path (never the query values) for the replay comparison.
    key = request_structure_key(event(url="http://h/api/items/42/reviews?page=3", params=("page",)))
    assert structure_paths([event(url="http://h/api/items/42/reviews?page=3", params=("page",))], {key}) == {
        key: {"/api/items/42/reviews"}}


def test_deep_unverified_structure_is_scheduled_before_shallow_redundancy():
    shallow = [transition(f"s{i}", 1, "http://h/api/ping") for i in range(6)]          # equivalent, shallow
    deep = transition("deep", 5, "http://h/api/secret")                                 # runtime behavior, 5 steps
    s = scheduler(shallow + [deep])
    order = drain(s)
    # Two replays in total: one for /api/ping, one for the deep behavior; the
    # five equivalent request-only workflows are never replayed.
    assert [tid for tid, *_ in order] == ["s0", "deep"]
    assert s.summary()["equivalent_replays_skipped"] == 5
    assert s.summary()["structures_verified"] == 2


def test_equivalent_structures_are_validated_once_and_distinct_ones_each():
    twins = [transition("twinA", 2, "http://h/api/save/1"), transition("twinB", 2, "http://h/api/save/2")]
    pair = [transition("reviews", 2, "http://h/api/reviews"), transition("stock", 2, "http://h/api/stock")]
    s = scheduler(twins + pair)
    order = drain(s)
    targets = [t for _, lane, t in order if lane == "structure"]
    assert sorted(x for t in targets for x in t) == sorted({x for t in targets for x in t})  # no structure targeted twice
    assert len([tid for tid, *_ in order if tid.startswith("twin")]) == 1
    assert {tid for tid, *_ in order} >= {"reviews", "stock"}


def test_failed_structure_is_retried_on_another_workflow_then_given_up():
    candidates = [transition("a", 2, "http://h/api/claim"), transition("b", 3, "http://h/api/claim"),
                  transition("c", 4, "http://h/api/claim")]
    s = scheduler(candidates, attempts=2)
    order = drain(s, outcome=lambda item: False)
    # Two attempts on different workflows (structure lane, then the shallow
    # fallback), then the structure is given up and the third equivalent
    # workflow is skipped by both lanes.
    assert [tid for tid, *_ in order] == ["a", "b"]
    summary = s.summary()
    assert summary["structures_given_up"] == 1 and summary["structures_verified"] == 0
    assert s.failures["script GET /api/claim [] -"] == ["control_missing", "control_missing"]


def test_lanes_share_replay_actions_so_navigation_is_not_starved():
    nav = [NS(id=f"n{i}", workflow_path=[None], network=[], request_only=False) for i in range(10)]
    deep = [transition(f"d{i}", 5, f"http://h/api/deep{i}") for i in range(4)]
    s = ReplayScheduler([(t, request_structures(t.network), 6, True) for t in deep],
                        [(t, 2) for t in nav] + [(t, 6) for t in deep])
    order = drain(s)
    first_eight = [lane for _, lane, _ in order[:8]]
    assert "shallow" in first_eight and "structure" in first_eight
    spent = s.summary()["lane_actions"]
    assert abs(spent["structure"] - spent["shallow"]) <= 6


def test_ineligible_state_changing_structures_are_not_prioritized():
    post = NS(id="post", workflow_path=[None, None], request_only=True,
              network=[event(method="POST", url="http://h/api/order", params=("qty",), enc="json")])
    s = scheduler([post], eligible=lambda t: False)
    item = s.next(of)
    assert item.lane == "shallow"                # existing order only; never promoted by the structure lane
    assert s.summary()["structures_ineligible"] == 1


def test_route_pattern_normalizes_whole_uuids():
    from agent1.state import route_pattern
    for uuid in ("5f7d29c4-a401-4bdd-9ff0-15c32b09a2e1", "fdf4153b-1bcc-4514-811d-dfdf67d4470e"):
        assert route_pattern(f"http://h/canvases/{uuid}/shapes") == "/canvases/{instance}/shapes"
    assert route_pattern("http://h/items/42") == "/items/{instance}"


def test_state_changing_workflows_are_keyed_by_path_not_label():
    from agent1.replay_scheduler import state_changing_workflows, workflow_changes_state

    def step(cid, sig="Submit"):
        return NS(control_id=cid, signature=sig, interaction="click", behavior_revision=None)
    link_a, link_b = step("a", "Page A"), step("b", "Page B")
    create = NS(workflow_path=[link_a, step("post")], network=[event(method="POST", url="http://h/api/items")])
    after_create = NS(workflow_path=[link_a, step("post"), step("open", "Open")], network=[event(url="http://h/api/items/1")])
    same_label_get = NS(workflow_path=[link_b, step("get")], network=[event(url="http://h/api/report")])
    changing = state_changing_workflows([create, after_create, same_label_get])
    assert workflow_changes_state(create, changing)          # the POST step itself
    assert workflow_changes_state(after_create, changing)    # a prerequisite created state
    assert not workflow_changes_state(same_label_get, changing)  # another "Submit" that only reads
