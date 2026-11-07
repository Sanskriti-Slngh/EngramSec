"""Authorized write sweep: promotion is gated on authorization, safety and the write cap."""
from types import SimpleNamespace as N

from agent1.explorer import Explorer
from agent1.write_policy import WritePolicy


def _form(method="POST", target="http://localhost/order/new", kind="form_submit"):
    return N(kind=kind, method=method, target=target)


def test_would_allow_gates_on_mode_destructive_and_cap():
    ro = WritePolicy("read_only")
    assert not ro.would_allow("POST", "http://x/order")          # read-only never promotes a write
    assert ro.would_allow("GET", "http://x/page")                # reads are always fine

    dp = WritePolicy("disposable", max_write_requests=2)
    assert dp.would_allow("POST", "http://x/order/new")          # safe write on disposable
    assert not dp.would_allow("DELETE", "http://x/thing")        # destructive method
    assert not dp.would_allow("POST", "http://x/account/delete") # destructive route
    assert not dp.would_allow("POST", "http://x/reset")          # destructive route
    # would_allow does not mutate the policy's counters
    assert dp.stats["allowed"] == 0 and dp.stats["blocked_destructive"] == 0


def test_would_allow_respects_the_write_cap():
    dp = WritePolicy("disposable", max_write_requests=1)
    assert dp.would_allow("POST", "http://x/a")
    dp.decide("POST", "http://x/a")                              # consume the one allowed write
    assert dp.stats["allowed"] == 1
    assert not dp.would_allow("POST", "http://x/b")              # cap reached -> not promotable


def _explorer(mode, attested):
    ex = object.__new__(Explorer)
    ex.write_policy = WritePolicy(mode, max_write_requests=10)
    ex.config = N(effective_write_policy=mode, environment_attestation=("att" if attested else None),
                  start_url="http://localhost/")
    return ex


def test_writes_authorized_only_on_attested_disposable():
    assert _explorer("disposable", True)._writes_authorized()
    assert not _explorer("disposable", False)._writes_authorized()   # no attestation
    assert not _explorer("read_only", True)._writes_authorized()     # wrong mode


def test_is_promotable_write_only_safe_non_get_forms():
    ex = _explorer("disposable", True)
    assert ex._is_promotable_write(_form("POST", "http://localhost/order/new"))
    assert not ex._is_promotable_write(_form("GET", "http://localhost/search"))      # GET is not a write
    assert not ex._is_promotable_write(_form("POST", "http://localhost/user/1/delete"))  # destructive
    assert not ex._is_promotable_write(_form("POST", "http://localhost/x", kind="link"))  # not a form submit
    # under read-only nothing is promotable
    ro = _explorer("read_only", True)
    assert not ro._is_promotable_write(_form("POST", "http://localhost/order/new"))


def test_focused_subtree_is_a_valid_opt_in_config():
    from agent1.schema import RunConfig
    c = RunConfig(start_url="http://127.0.0.1/", output_dir="/tmp/x")
    assert c.write_execution_policy == "deferred"          # default unchanged
    assert c.focus_max_steps == 12
    f = RunConfig(start_url="http://127.0.0.1/", output_dir="/tmp/x",
                  write_execution_policy="focused_subtree", focus_max_steps=20,
                  write_sweep_replay_floor=0.25)
    assert f.write_execution_policy == "focused_subtree" and f.focus_max_steps == 20
    assert f.write_sweep_replay_floor == 0.25


def test_focused_subtree_still_requires_attested_disposable():
    # the focus sweep is gated by the same authorization check as authorized_fair
    assert _explorer("disposable", True)._writes_authorized()
    assert not _explorer("read_only", True)._writes_authorized()
    assert not _explorer("disposable", False)._writes_authorized()
