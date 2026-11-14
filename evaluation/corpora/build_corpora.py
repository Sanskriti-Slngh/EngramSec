"""Generate the frozen T1/T3 evidence logs (run once; outputs are committed).

The logs are synthetic `acg-evidence/1` records written to the published
contract, independent of any resolver. Expected results live separately in
`t1/expected.json` and `t3/expected.json` and were written by hand.
Run: .venv/bin/python -m evaluation.corpora.build_corpora
"""
from __future__ import annotations

from pathlib import Path

from agent1.model.evidence import (AffordanceEvidence as A, Capture, FieldShape, MessageEvidence, Record,
                                   RequestEvidence as Rq, Source, write_log)

BASE = "http://127.0.0.1:9"
HERE = Path(__file__).parent


class Log:
    def __init__(self, name: str, capture: Capture) -> None:
        self.name, self.records = name, []
        self.folder = name.split("_", 1)[0]
        self._add(Record(id="ev:manifest", seq=0, kind="capture_manifest", source=self._src("manifest"),
                         capture=capture, synthetic=True, application=name))

    def _src(self, pointer: str) -> Source:
        return Source(artifact=f"evaluation/corpora/{self.folder}/{self.name}.jsonl", pointer=pointer)

    def _add(self, record: Record) -> None:
        self.records.append(record.model_copy(update={"seq": len(self.records)}))

    def obs(self, oid: str, path: str, affs: list[A], context: str = "exploration", title: str = "",
            regions: dict[str, str] | None = None, storage: list[str] | None = None) -> str:
        self._add(Record(id=f"ev:obs:{oid}", seq=0, kind="observation", source=self._src(f"obs/{oid}"), obs_id=oid,
                         context=context, url=BASE + path, role="anonymous", storage_keys=storage or [],
                         affordances=affs, regions=regions, title=title))
        return oid

    def act(self, aid: str, src: str, res: str | None, aff: A, requests: list[Rq] | None = None,
            received: list[MessageEvidence] | None = None, status: str = "observed") -> None:
        self._add(Record(id=f"ev:act:{aid}", seq=0, kind="action", source=self._src(f"act/{aid}"), action_id=aid,
                         source_obs=src, result_obs=res, affordance=aff, status=status, requests=requests or [],
                         received=received))

    def replay(self, rid: str, aid: str, res: str, kind: str = "standard", requests: list[Rq] | None = None,
               verification: dict | None = None, received: list[MessageEvidence] | None = None) -> None:
        self._add(Record(id=f"ev:replay:{rid}", seq=0, kind="replay", source=self._src(f"replay/{rid}"), replay_id=rid,
                         action_id=aid, result_obs=res, status="replay_validated", independent_context=True,
                         verification_kind=kind, requests=requests or [], verification=verification or {},
                         received=received))

    def save(self) -> None:
        write_log(self.records, HERE / self.folder / f"{self.name}.jsonl")


def link(path: str, label: str, locator: str, component: str = "main") -> A:
    return A(kind="link", role_attr="link", interaction="click", component=component, locator=locator,
             target=BASE + path, label=label)


def button(label: str, locator: str, component: str = "main", revision: str | None = None,
           kind: str = "button", interaction: str = "click") -> A:
    return A(kind=kind, role_attr="button", interaction=interaction, component=component, locator=locator,
             label=label, behavior_revision=revision)


def get(path: str, rtype: str = "xhr", params: list[str] | None = None, filled: list[str] | None = None) -> Rq:
    return Rq(method="GET", url=BASE + path, status=200, resource_type=rtype, param_names=sorted(params or []),
              engine_filled=filled or [])


def post(path: str, params: list[str], method: str = "POST", filled: list[str] | None = None) -> Rq:
    return Rq(method=method, url=BASE + path, status=200, resource_type="fetch", param_names=params,
              body_encoding="json", engine_filled=filled or [])


def t1() -> list[Log]:
    logs = []
    # T1.1 query-dispatched operations on one endpoint.
    lg = Log("t1_1_dispatch", Capture())
    page = [button("Show cart totals", "main > button:nth-of-type(1)"), button("Show stock", "main > button:nth-of-type(2)")]
    lg.obs("o1", "/admin", page)
    lg.act("a1", "o1", lg.obs("o2", "/admin", page), page[0], [get("/index.php?controller=cart&ajax=1", params=["ajax", "controller"])])
    lg.act("a2", "o2", lg.obs("o3", "/admin", page), page[1], [get("/index.php?controller=stock&ajax=1", params=["ajax", "controller"])])
    lg.act("a3", "o3", lg.obs("o4", "/admin", page), page[0], [get("/index.php?controller=cart&ajax=1", params=["ajax", "controller"])])
    logs.append(lg)
    # T1.2 same behavior behind different labels/languages; one never-executed affordance.
    lg = Log("t1_2_labels", Capture())
    page = [button("Save", "main > form > button", component="main:form"),
            button("保存", "aside > button", component="aside"),
            button("Export", "main > button.export")]
    lg.obs("o1", "/settings", page)
    lg.act("a1", "o1", lg.obs("o2", "/settings", page), page[0], [post("/api/profile", ["display_name"])])
    lg.act("a2", "o2", lg.obs("o3", "/settings", page), page[1], [post("/api/profile", ["display_name"])])
    logs.append(lg)
    # T1.3 client-only effects in different regions; one action with no observable effect.
    lg = Log("t1_3_client", Capture())
    base = [button("Filters", "aside > button", component="aside"), button("Help", "header > button", component="header"),
            button("Refresh status", "main > button#refresh")]
    lg.obs("o1", "/board", base)
    lg.act("a1", "o1", lg.obs("o2", "/board", base + [A(kind="button", role_attr="checkbox", interaction="toggle",
                                                       component="dialog:filters", locator="dialog#filters > input",
                                                       label="Open only")]), base[0])
    lg.obs("o3", "/board", base)
    lg.act("a2", "o3", lg.obs("o4", "/board", base + [link("/docs", "Guide", "dialog#help > a", "dialog:help")]), base[1])
    lg.obs("o5", "/board", base)
    lg.act("a3", "o5", lg.obs("o6", "/board", base), base[2])
    logs.append(lg)
    # T1.4 WebSocket message classes.
    lg = Log("t1_4_websocket", Capture(websocket=True))
    page = [button("Follow", "main > button:nth-of-type(1)"), button("Unfollow", "main > div.row > button"),
            button("Follow", "aside > button", component="aside")]
    ack = [MessageEvidence(url="ws://127.0.0.1:9/socket", message_skeleton="sk:count,type", message_discriminator="tok:ack")]

    def ws(disc: str) -> Rq:
        return Rq(channel="websocket_send", url="ws://127.0.0.1:9/socket", message_skeleton="sk:channel,type",
                  message_discriminator=disc)
    lg.obs("o1", "/live", page)
    lg.act("a1", "o1", lg.obs("o2", "/live", page), page[0], [ws("tok:subscribe")], ack)
    lg.act("a2", "o2", lg.obs("o3", "/live", page), page[1], [ws("tok:unsubscribe")], ack)
    lg.act("a3", "o3", lg.obs("o4", "/live", page), page[2], [ws("tok:subscribe")], ack)
    logs.append(lg)
    # T1.5 canvas-only effects: two different gestures, identical observable evidence.
    lg = Log("t1_5_canvas", Capture(visual_regions=True))
    page = [button("", "aside > div.palette-item", component="aside", kind="gesture", interaction="drag"),
            button("", "main > canvas", component="main:canvas", kind="gesture", interaction="drag")]
    lg.obs("o1", "/editor", page, regions={"main > canvas": "d0"})
    lg.act("a1", "o1", lg.obs("o2", "/editor", page, regions={"main > canvas": "d1"}), page[0])
    lg.act("a2", "o2", lg.obs("o3", "/editor", page, regions={"main > canvas": "d2"}), page[1])
    logs.append(lg)
    # T1.6 a dynamic handler revision on the same visible button.
    lg = Log("t1_6_revision", Capture())
    lg.obs("o1", "/loans", [button("Check loans", "main > button#step")])
    rev = [button("Check loans", "main > button#step", revision="rev1")]
    lg.act("a1", "o1", lg.obs("o2", "/loans", rev), button("Check loans", "main > button#step"), [get("/api/first")])
    lg.act("a2", "o2", lg.obs("o3", "/loans", rev), rev[0], [get("/api/second")])
    lg.act("a3", "o3", lg.obs("o4", "/loans", rev), rev[0], [get("/api/second")])
    logs.append(lg)
    # T1.7 two entry points to one capability; three instances share one template.
    lg = Log("t1_7_entry_points", Capture())
    u = ["aaaaaaaa-0000-4000-8000-000000000001", "bbbbbbbb-0000-4000-8000-000000000002",
         "cccccccc-0000-4000-8000-000000000003"]
    form = A(kind="form_submit", role_attr="button", component="main:form", locator="main > form > button",
             method="POST", fields=[FieldShape(name="name", input_type="text")], label="+ Create canvas")
    empty = button("Create your first canvas", "main > section.empty > button", component="main:section")
    back = link("/", "Back", "nav > a", "nav")

    def dash(ids: list[str]) -> list[A]:
        return [link(f"/canvas/{i}", f"Canvas {n}", f"main > ul > li:nth-of-type({n}) > a")
                for n, i in enumerate(ids, 1)] + [form, empty]
    lg.obs("o1", "/", dash(u[:1]))
    lg.act("a0", "o1", lg.obs("o2", f"/canvas/{u[0]}", [back]), dash(u[:1])[0], [get(f"/canvas/{u[0]}", "document")])
    lg.act("b1", "o2", lg.obs("o3", "/", dash(u[:1])), back, [get("/", "document")])
    lg.act("a1", "o3", lg.obs("o4", f"/canvas/{u[1]}", [back]), form,
           [post("/api/canvases", ["name"], filled=["name"]), get(f"/canvas/{u[1]}", "document")])
    lg.act("b2", "o4", lg.obs("o5", "/", dash(u[:2])), back, [get("/", "document")])
    lg.act("a2", "o5", lg.obs("o6", f"/canvas/{u[2]}", [back]), empty,
           [post("/api/canvases", ["name"]), get(f"/canvas/{u[2]}", "document")])
    logs.append(lg)
    # T1.8 two settings saved through one endpoint, same parameters, no dispatch.
    lg = Log("t1_8_indistinguishable", Capture())
    page = [button("Dark mode", "main > ul > li:nth-of-type(1) > button"),
            button("Email digest", "main > ul > li:nth-of-type(2) > button")]
    lg.obs("o1", "/preferences", page)
    lg.act("a1", "o1", lg.obs("o2", "/preferences", page), page[0], [post("/api/settings", ["key", "value"], "PUT")])
    lg.act("a2", "o2", lg.obs("o3", "/preferences", page), page[1], [post("/api/settings", ["key", "value"], "PUT")])
    logs.append(lg)
    return logs


def t3() -> Log:
    """One log in which each closed grounding rule has exactly the evidence it requires."""
    lg = Log("t3_grounding", Capture(websocket=True))
    nav = link("/docs", "Docs", "nav > a:nth-of-type(1)", "nav")
    notes = link("/notes", "Notes", "nav > a:nth-of-type(2)", "nav")
    home = [nav, notes]
    lg.obs("o0", "/", home)
    # navigation, reproduced in an independent context
    find = A(kind="form_submit", role_attr="button", component="main:form", locator="main > form > button",
             method="GET", target=BASE + "/docs/find", fields=[FieldShape(name="term", input_type="search")], label="Go")
    docs = home + [find]
    lg.act("a1", "o0", lg.obs("o1", "/docs", docs), nav, [get("/docs", "document")])
    lg.replay("r1", "a1", lg.obs("ro1", "/docs", docs, context="replay"), requests=[get("/docs", "document")])
    # collection query: differential input through two paired replays
    hits = lambda ids: docs + [link(f"/docs/{i}", f"Doc {i}", f"main > ol > li:nth-of-type({n}) > a")
                               for n, i in enumerate(ids, 1)]
    lg.act("a2", "o1", lg.obs("o2", "/docs/find?term=alpha", hits([1, 2])), find,
           [get("/docs/find?term=alpha", "document", ["term"], ["term"])])
    for k in (1, 2):
        ids = [lg.obs(f"p{k}b", "/docs", docs, context="replay"),
               lg.obs(f"p{k}r", "/docs/find?term=alpha", hits([1, 2]), context="replay"),
               lg.obs(f"c{k}b", "/docs", docs, context="replay"),
               lg.obs(f"c{k}r", "/docs/find?term=beta", hits([3]), context="replay")]
        lg.replay(f"r2{k}", "a2", ids[1], "paired_search", [get("/docs/find?term=alpha", "document", ["term"], ["term"])],
                  {"verification_observation_ids": ids})
    # instance view and creation on a /notes collection
    lst = lambda ids: home + [link(f"/notes/{i}", f"Note {i}", f"main > ul > li:nth-of-type({n}) > a")
                              for n, i in enumerate(ids, 1)] + [
        A(kind="form_submit", role_attr="button", component="main:form", locator="main > form > button", method="POST",
          fields=[FieldShape(name="title", input_type="text")], label="Add")]
    lg.act("a6x", "o2", lg.obs("o3", "/notes", lst([11, 12])), notes, [get("/notes", "document")])
    view = lst([11, 12])[2]
    lg.act("a6", "o3", lg.obs("o4", "/notes/11", home), view, [get("/notes/11", "document")])
    lg.replay("r6", "a6", lg.obs("ro6", "/notes/11", home, context="replay"), requests=[get("/notes/11", "document")])
    lg.act("a6y", "o4", lg.obs("o5", "/notes", lst([11, 12])), notes, [get("/notes", "document")])
    add = lst([11, 12])[-1]
    lg.act("a3", "o5", lg.obs("o6", "/notes/13", home), add,
           [post("/api/notes", ["title"], filled=["title"]), get("/notes/13", "document")])
    detail = lg.obs("ro3", "/notes/14", home, context="replay")
    collection = lg.obs("ro3c", "/notes", lst([11, 12, 13, 14]), context="replay")
    lg.replay("r3", "a3", detail, "cross_view",
              [post("/api/notes", ["title"], filled=["title"]), get("/notes/14", "document")],
              {"verification_observation_ids": [detail, collection]})
    # client-only view change, reproduced
    expand = button("Expand", "main > button.expand")
    lg.obs("o7", "/docs", docs + [expand])
    opened = docs + [expand, link("/docs/1", "Doc 1", "dialog#more > a", "dialog:more")]
    lg.act("a4", "o7", lg.obs("o8", "/docs", opened), expand)
    lg.replay("r4", "a4", lg.obs("ro4", "/docs", opened, context="replay"))
    # server job submission: write + a message class absent from every other action
    run = button("Run", "main > button.run")
    lg.obs("o9", "/docs", docs + [run])
    progress = [MessageEvidence(url="ws://127.0.0.1:9/socket", message_skeleton="sk:progress,type",
                                message_discriminator="tok:progress")]
    lg.act("a5", "o9", lg.obs("o10", "/docs", docs + [run]), run, [post("/api/jobs", ["graph"])], progress)
    lg.replay("r5", "a5", lg.obs("ro5", "/docs", docs + [run], context="replay"), requests=[post("/api/jobs", ["graph"])],
              received=progress)
    return lg


if __name__ == "__main__":
    for log in t1():
        log.save()
    t3().save()
