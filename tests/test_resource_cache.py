"""ResourceCache: static-asset dedup is correct, bounded, and never caches dynamic content."""
from agent1.bounded_http import CACHEABLE_RESOURCE_TYPES, ResourceCache


def test_eligible_only_static_get():
    c = ResourceCache()
    assert c.eligible("GET", "script")
    assert c.eligible("get", "stylesheet")
    assert c.eligible("GET", "font")
    assert c.eligible("GET", "image")
    # never dynamic content or non-GET
    assert not c.eligible("GET", "document")
    assert not c.eligible("GET", "xhr")
    assert not c.eligible("GET", "fetch")
    assert not c.eligible("POST", "script")
    assert not c.eligible("GET", None)
    assert CACHEABLE_RESOURCE_TYPES == {"script", "stylesheet", "font", "image"}


def test_hit_returns_bytes_and_counts_savings():
    c = ResourceCache()
    assert c.get("http://x/a.js") is None
    c.put("http://x/a.js", 200, {"content-type": "application/javascript"}, b"BODY")
    hit = c.get("http://x/a.js")
    assert hit["status"] == 200 and hit["body"] == b"BODY"
    assert c.hits == 1 and c.bytes_saved == 4
    # a second hit accrues more savings; stays a single stored entry
    c.get("http://x/a.js")
    assert c.hits == 2 and c.bytes_saved == 8 and c.stats()["stored_entries"] == 1


def test_never_stores_non_200_or_no_store():
    c = ResourceCache()
    c.put("http://x/a.js", 404, {}, b"x")
    c.put("http://x/b.js", 200, {"cache-control": "no-store"}, b"x")
    c.put("http://x/c.js", 200, {"Cache-Control": "private, max-age=0"}, b"x")
    assert c.get("http://x/a.js") is None
    assert c.get("http://x/b.js") is None
    assert c.get("http://x/c.js") is None


def test_strips_hop_by_hop_headers():
    c = ResourceCache()
    c.put("http://x/a.js", 200, {"Content-Encoding": "gzip", "Content-Length": "9",
                                 "Set-Cookie": "s=1", "Content-Type": "application/javascript"}, b"decoded")
    h = c.get("http://x/a.js")["headers"]
    assert "content-type" in {k.lower() for k in h}
    assert not any(k.lower() in {"content-encoding", "content-length", "set-cookie"} for k in h)


def test_bounded_by_entries_and_bytes():
    c = ResourceCache(max_entries=2, max_total_bytes=100, max_entry_bytes=10)
    c.put("u1", 200, {}, b"12345")
    c.put("u2", 200, {}, b"12345")
    c.put("u3", 200, {}, b"12345")          # exceeds max_entries -> dropped
    assert c.stats()["stored_entries"] == 2
    big = ResourceCache(max_entry_bytes=4)
    big.put("u", 200, {}, b"toolong")        # exceeds max_entry_bytes -> dropped
    assert big.get("u") is None


def test_never_caches_session_dependent_vary_responses():
    c = ResourceCache()
    c.put("http://x/a.js", 200, {"Vary": "Cookie"}, b"x")
    c.put("http://x/b.js", 200, {"Vary": "Accept-Encoding, Authorization"}, b"x")
    c.put("http://x/c.js", 200, {"Vary": "*"}, b"x")
    assert c.get("http://x/a.js") is None
    assert c.get("http://x/b.js") is None
    assert c.get("http://x/c.js") is None
    # a benign Vary (encoding only) is still cacheable
    c.put("http://x/d.js", 200, {"Vary": "Accept-Encoding"}, b"ok")
    assert c.get("http://x/d.js") is not None


def test_mutable_api_types_are_never_eligible():
    c = ResourceCache()
    # XHR/fetch are how dynamic/authenticated data arrives; documents are pages. None may be cached.
    for rt in ("xhr", "fetch", "document", "websocket", "eventsource", "manifest", "other"):
        assert not c.eligible("GET", rt)


def test_cache_is_per_instance_so_accounts_cannot_share():
    # Each run owns its own cache (one per Explorer), so one account's assets can never be served to
    # another: there is no shared/global store. Two instances do not see each other's entries.
    a, b = ResourceCache(), ResourceCache()
    a.put("http://x/a.js", 200, {}, b"AAA")
    assert a.get("http://x/a.js") is not None
    assert b.get("http://x/a.js") is None
