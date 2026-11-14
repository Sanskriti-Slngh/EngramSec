"""Materialize the Application Capability Graph from an evidence log.

Contract: PROPOSED_APPLICATION_MODEL.md §2–§5 (signatures §5.3, grounding
§5.6), smallest version. Identity comes only from structure, requests,
messages and observable effects; display text is copied into `labels` with
the record it came from and is never read by any resolver.

Incremental use: `Materializer.add()` normalizes each record once on arrival.
Cross-record resolution (dispatch parameters, identifier positions, entity
types, capabilities, predicates) is recomputed by `export()`, so that later
evidence can revise or split earlier groupings. The result always equals a full
rebuild from the same records; the tests check this at every cut point.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urlsplit

from .evidence import Capture, Record
from .routes import (DISPATCH_VALUE, STRONG_IDENTIFIER, identifier_segments, is_identifier, path_route, split,
                     strip_positions)
from .schema import (ACGExport, Affordance, BehavioralClass, Binding, Capability, Claim, Effect, EntityInstance,
                     EntityType, Gap, Label, LearnedPredicate, Operation, Status, Template, ViewState, STATUS_RANK)
from .tokens import token

RESOLVER_VERSION = "acg-resolvers/2"
STATIC_RESOURCES = {"script", "stylesheet", "image", "font", "media", "manifest", "texttrack", "ping"}
READ_METHODS = {"GET", "HEAD", "OPTIONS"}
# Experiment channels (EXPLORATION_PLANNER_DESIGN.md §5.2 table C).
REPRODUCE_S, REPRODUCE_F = 0.90, 0.05
ORACLE = {"differential": (0.95, 0.05), "cross_view": (0.90, 0.05)}
CLASS_ORDER = ("instance_creation", "instance_removal", "instance_modification", "collection_query",
               "server_job_submission", "instance_view", "navigation", "client_view_change")


def _digest(value: Any, n: int = 12) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()[:n]


def _bucket(n: int) -> str:
    return "0" if n == 0 else "1" if n == 1 else "2-10" if n <= 10 else ">10"


def _bayes(p: float, positive: bool, s: float, f: float) -> float:
    if positive:
        return p * s / (p * s + (1 - p) * f)
    return p * (1 - s) / (p * (1 - s) + (1 - p) * (1 - f))


@dataclass(frozen=True)
class OpKey:
    channel: str
    method: str | None
    route: str
    params: tuple[str, ...]
    encoding: str | None
    dispatch: tuple[tuple[str, str], ...]
    message_class: str | None

    @property
    def writes(self) -> bool:
        return self.channel == "websocket_send" or (self.method or "GET") not in READ_METHODS

    @property
    def id(self) -> str:
        return "op_" + _digest([self.channel, self.method, self.route, self.params, self.encoding, self.dispatch,
                                self.message_class])


@dataclass
class Context:
    records: list[Record]
    ns: str
    capture: Capture
    application: str | None
    synthetic: bool
    obs: dict[str, Record] = field(default_factory=dict)
    dispatch: set[tuple[str, str, str]] = field(default_factory=set)
    filled_routes: set[tuple[str, str]] = field(default_factory=set)


class Materializer:
    def __init__(self, namespace: str | None = None) -> None:
        self.namespace = namespace
        self._records: dict[str, Record] = {}

    def add(self, records: Iterable[Record]) -> None:
        for record in records:
            known = self._records.get(record.id)
            if known is not None and known != record:
                raise ValueError(f"evidence is append-only; conflicting record {record.id}")
            self._records[record.id] = record

    def export(self) -> ACGExport:
        return _resolve(sorted(self._records.values(), key=lambda r: (r.seq, r.id)), self.namespace)


def materialize(records: Iterable[Record], namespace: str | None = None) -> ACGExport:
    m = Materializer(namespace)
    m.add(records)
    return m.export()


# ------------------------------------------------------------------ structure
def _aff_signature(aff) -> tuple:
    target = path_route(urlsplit(aff.target).path) if aff.target else ""
    return (aff.kind, aff.role_attr, aff.interaction, aff.component, aff.locator, target,
            (aff.method or "").upper(), aff.provenance, aff.frame)


def _detect_dispatch(ctx: Context) -> None:
    values: dict[tuple[str, str, str], dict[tuple, set[str]]] = defaultdict(lambda: defaultdict(set))
    filled: set[tuple[str, str, str]] = set()
    if not ctx.capture.http_query_values:
        return
    for a in ctx.records:
        if a.kind != "action" or a.status != "observed" or a.affordance is None:
            continue
        for q in a.requests or []:
            if q.channel != "http":
                continue
            path, pairs, _ = split(q.url)
            route = path_route(path)
            for name, value in pairs:
                key = ((q.method or "GET").upper(), route, name)
                if name in q.engine_filled:
                    filled.add(key)
                    ctx.filled_routes.add((key[0], route))
                values[key][_aff_signature(a.affordance)].add(value)
    for key, per in values.items():
        every = set().union(*per.values())
        if key in filled or len(every) < 2 or any(len(v) != 1 for v in per.values()):
            continue
        if all(DISPATCH_VALUE.match(v) and not is_identifier(v) for v in every):
            ctx.dispatch.add(key)


def _route_of(ctx: Context, url: str, method: str = "GET") -> str:
    path, pairs, _ = split(url)
    route = path_route(path)
    named = dict(pairs)
    parts = [f"{n}={token(ctx.ns, named[n])}" if (method, route, n) in ctx.dispatch else n for n in sorted(named)]
    return route + ("?" + "&".join(parts) if parts else "")


def _op_key(ctx: Context, q) -> OpKey | None:
    if q.channel == "websocket_send":
        return OpKey("websocket_send", None, path_route(urlsplit(q.url).path), (), None, (),
                     _digest([q.message_skeleton, q.message_discriminator]))
    if q.resource_type in STATIC_RESOURCES:
        return None
    method = (q.method or "GET").upper()
    path, pairs, _ = split(q.url)
    route = path_route(path)
    dispatch = tuple(sorted((n, token(ctx.ns, v)) for n, v in pairs if (method, route, n) in ctx.dispatch))
    params = tuple(sorted(set(q.param_names) | {n for n, _ in pairs}))
    return OpKey("http", method, route, params, q.body_encoding, dispatch, None)


def _engine_input(record: Record) -> bool:
    return any(q.engine_filled for q in record.requests or [])


# ------------------------------------------------------------------ resolver
def _resolve(records: list[Record], namespace: str | None) -> ACGExport:
    manifest = next((r for r in records if r.kind == "capture_manifest"), None)
    ctx = Context(records=records, ns=namespace or "acg-offline:" + ((manifest.application if manifest else None) or ""),
                  capture=(manifest.capture if manifest and manifest.capture else Capture()),
                  application=manifest.application if manifest else None,
                  synthetic=bool(manifest and manifest.synthetic))
    ctx.obs = {r.obs_id: r for r in records if r.kind == "observation" and r.obs_id}
    actions = [r for r in records if r.kind == "action"]
    replays = [r for r in records if r.kind == "replay"]
    gaps: dict[str, Gap] = {}

    def gap(kind: str, detail: str) -> None:
        if kind in gaps:
            gaps[kind].count += 1
        else:
            gaps[kind] = Gap(kind=kind, detail=detail)

    _detect_dispatch(ctx)

    # Templates (route with dispatch tokens × role) and observations.
    tpl_of_obs: dict[str, str] = {}
    templates: dict[str, dict[str, Any]] = {}
    for o in ctx.obs.values():
        route = _route_of(ctx, o.url or "")
        tid = "tpl_" + _digest([route, o.role])
        templates.setdefault(tid, {"route": route, "role": o.role or "unknown", "obs": []})["obs"].append(o)
        tpl_of_obs[o.obs_id] = tid
        if o.url_confidence != "exact":
            gap("group_representative_urls", "Observation URL known only as its legacy state group's representative.")

    def aff_key(tid: str, aff) -> tuple:
        target = _route_of(ctx, aff.target) if aff.target else ""
        locator = strip_positions(aff.locator) if "{id}" in target else aff.locator
        return (tid, aff.kind, aff.role_attr, aff.interaction, aff.component, locator, target,
                (aff.method or "").upper(), tuple((f.name, f.input_type, f.required) for f in aff.fields),
                aff.provenance, aff.frame)

    def aff_id(key: tuple) -> str:
        return "aff_" + _digest(list(key))

    # Identifier positions, tokens, entity types (union by shared values = ID flow).
    occurrences: dict[str, dict[str, list[tuple[int, str, str]]]] = defaultdict(lambda: defaultdict(list))

    def urls_of(r: Record) -> list[str]:
        out = []
        if r.url:
            out.append(r.url)
        for a in (r.affordances or []) + ([r.affordance] if r.affordance else []):
            if a.target:
                out.append(a.target)
        out.extend(q.url for q in r.requests or [] if q.channel == "http")
        return out

    for r in records:
        for url in urls_of(r):
            path, pairs, _ = split(url)
            for route, index, value in identifier_segments(path):
                occurrences[f"{route}#{index}"][value].append((r.seq, r.id, path))
            route = path_route(path)
            for name, value in pairs:
                if is_identifier(value):
                    occurrences[f"{route}?{name}"][value].append((r.seq, r.id, path))
    positions = sorted(occurrences)
    parent = {p: p for p in positions}

    def find(p: str) -> str:
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p
    union_evidence: dict[tuple[str, str], list[str]] = {}
    for i, p in enumerate(positions):
        for q in positions[i + 1:]:
            shared = set(occurrences[p]) & set(occurrences[q])
            if any(STRONG_IDENTIFIER.match(v) for v in shared) or len(shared) >= 2:
                a, b = sorted((find(p), find(q)))
                if a != b:
                    parent[b] = a
                union_evidence[(p, q)] = sorted({rid for v in sorted(shared)[:3] for _, rid, _ in
                                                 occurrences[p][v][:1] + occurrences[q][v][:1]})
    groups: dict[str, list[str]] = defaultdict(list)
    for p in positions:
        groups[find(p)].append(p)
    type_of_position: dict[str, str] = {}
    entity_types: list[EntityType] = []
    for n, root in enumerate(sorted(groups, key=lambda g: min(groups[g])), 1):
        tid = f"E{n}"
        candidates = []
        for p in sorted(groups[root]):
            type_of_position[p] = tid
            if "#" in p:
                route, index = p.rsplit("#", 1)
                segs = [s for s in route.split("/") if s]
                i = int(index)
                if i > 0 and segs[i - 1] != "{id}":
                    word = segs[i - 1]
                    first = min((o for v in occurrences[p].values() for o in v), key=lambda o: (o[0], o[1]))
                    if word not in {c.text for c in candidates}:
                        candidates.append(Label(text=word, evidence_id=first[1]))
        entity_types.append(EntityType(id=tid, positions=sorted(groups[root]), label_candidates=candidates))
    instances: dict[tuple[str, str], dict[str, Any]] = {}
    first_seen: dict[tuple[str, str], int] = {}
    for p, by_value in occurrences.items():
        etype = type_of_position[p]
        for value, occ in by_value.items():
            item = instances.setdefault((etype, value), {"records": set(), "paths": set(), "obs": set()})
            for seq, rid, path in occ:
                item["records"].add(rid)
                item["paths"].add(path)
                first_seen[(etype, value)] = min(first_seen.get((etype, value), seq), seq)
    for o in ctx.obs.values():
        for (etype, value), item in instances.items():
            if o.id in item["records"] and o.url and value in urlsplit(o.url).path.split("/"):
                item["obs"].add(o.obs_id)

    token_cache: dict[str, frozenset[tuple[str, str]]] = {}

    def tokens_in(url: str) -> frozenset[tuple[str, str]]:
        # Pure function of the URL once entity types are fixed; memoized per resolve.
        hit = token_cache.get(url)
        if hit is None:
            hit = token_cache[url] = frozenset(_tokens_in(url))
        return hit

    def _tokens_in(url: str) -> set[tuple[str, str]]:
        path, pairs, _ = split(url)
        out = {(type_of_position[f"{route}#{i}"], v) for route, i, v in identifier_segments(path)
               if f"{route}#{i}" in type_of_position}
        route = path_route(path)
        out |= {(type_of_position[f"{route}?{n}"], v) for n, v in pairs if f"{route}?{n}" in type_of_position}
        return out

    def page_tokens(o: Record) -> set[tuple[str, str]]:
        return tokens_in(o.url or "")

    def link_tokens(o: Record) -> set[tuple[str, str]]:
        out: set[tuple[str, str]] = set()
        for a in o.affordances or []:
            if a.target:
                out |= tokens_in(a.target)
        return out

    seen_templates: dict[str, int] = {}
    for o in sorted(ctx.obs.values(), key=lambda r: r.seq):
        seen_templates.setdefault(tpl_of_obs[o.obs_id], o.seq)

    # Effects between two observations.
    def effects(source: Record | None, result: Record | None, received, requests=None) -> set[tuple[str, str]]:
        out: set[tuple[str, str]] = set()
        for m in received or []:
            out.add(("message_received", "msg_" + _digest([m.message_skeleton, m.message_discriminator])))
        if result is None:
            return out
        rt = tpl_of_obs[result.obs_id]
        st = tpl_of_obs.get(source.obs_id) if source else None
        same_page = source is not None and st == rt and urlsplit(source.url or "").path == urlsplit(result.url or "").path
        # A top-level document load of the result page is a navigation even when it
        # reloads the page the action started from.
        reloaded = any(q.channel == "http" and q.resource_type == "document" and
                       urlsplit(q.url).path == urlsplit(result.url or "").path for q in requests or [])
        if source is None or st != rt or not same_page or reloaded:
            out.add(("navigated", rt))
        if ctx.capture.dom_affordances and result.affordances is not None:
            for etype, value in page_tokens(result) | link_tokens(result):
                if first_seen.get((etype, value), -1) >= result.seq:
                    # first mention ever, in a view of a template seen before
                    target_tpl = rt if (etype, value) in page_tokens(result) else None
                    if target_tpl is None:
                        target_tpl = next(("tpl_" + _digest([_route_of(ctx, a.target), result.role])
                                           for a in result.affordances if a.target and (etype, value) in tokens_in(a.target)), None)
                    if target_tpl and seen_templates.get(target_tpl, 10**12) < result.seq:
                        out.add(("instance_appeared", etype))
        if source is None or not same_page:
            return out
        if source.affordances is not None and result.affordances is not None:
            gone = link_tokens(source) - link_tokens(result)
            out |= {("instance_disappeared", etype) for etype, _ in gone}
            # A region that appears or disappears is a component change. Collection
            # effects apply only inside regions present on both sides.
            comps_s = {a.component for a in source.affordances}
            comps_r = {a.component for a in result.affordances}
            for component in comps_s ^ comps_r:
                out.add(("component_state_changed", component))
            shared = comps_s & comps_r
            fam_s, fam_r = defaultdict(set), defaultdict(set)
            plain_s, plain_r = set(), set()
            dis_s: dict[tuple, bool | None] = {}
            dis_r: dict[tuple, bool | None] = {}
            for o, fam, plain, dis in ((source, fam_s, plain_s, dis_s), (result, fam_r, plain_r, dis_r)):
                for a in o.affordances:
                    if a.component not in shared:
                        continue
                    key = aff_key(rt, a)
                    if "{id}" in key[6]:
                        fam[aff_id(key)] |= tokens_in(a.target or "")
                    else:
                        plain.add(key)
                        dis[key] = a.disabled
            for fid in set(fam_s) | set(fam_r):
                if _bucket(len(fam_s.get(fid, set()))) != _bucket(len(fam_r.get(fid, set()))):
                    out.add(("collection_size_changed", fid))
                elif fam_s.get(fid, set()) != fam_r.get(fid, set()):
                    out.add(("collection_membership_changed", fid))
            # Inside a shared region, the effect names which affordances changed, so two
            # actions that alter the same region differently stay distinct.
            changed: dict[str, list[str]] = defaultdict(list)
            for key in plain_s ^ plain_r:
                changed[key[4]].append(("+" if key in plain_r else "-") + aff_id(key))
            # A control that became enabled or disabled is a component state change
            # (only when both observations captured the flag).
            for key in plain_s & plain_r:
                if dis_s[key] is not None and dis_r[key] is not None and dis_s[key] != dis_r[key]:
                    changed[key[4]].append(("d" if dis_r[key] else "e") + aff_id(key))
            for component, keys in changed.items():
                out.add(("component_state_changed", component + "/" + _digest(sorted(keys), 8)))
        if source.storage_keys is not None and result.storage_keys is not None and source.storage_keys != result.storage_keys:
            out.add(("client_state_changed", "storage"))
        if split(source.url or "")[2] != split(result.url or "")[2]:
            out.add(("client_state_changed", "fragment"))
        if source.regions is not None and result.regions is not None:
            for region in sorted(set(source.regions) | set(result.regions)):
                if source.regions.get(region) != result.regions.get(region):
                    out.add(("visual_region_changed", region))
        return out

    def op_keys(requests) -> set[OpKey]:
        return {k for k in (_op_key(ctx, q) for q in requests or []) if k is not None}

    # Capabilities from executed actions.
    signatures: dict[str, tuple] = {}
    action_aff: dict[str, str] = {}
    op_index: dict[str, tuple[OpKey, list[str]]] = {}
    cap_actions: dict[tuple, list[Record]] = defaultdict(list)
    no_effect: list[Record] = []
    for a in actions:
        source = ctx.obs.get(a.source_obs or "")
        result = ctx.obs.get(a.result_obs or "")
        tid = tpl_of_obs.get(source.obs_id) if source else "tpl_unknown"
        if a.affordance is not None:
            action_aff[a.action_id] = aff_id(aff_key(tid, a.affordance))
        if a.status != "observed":
            continue
        if source is None or result is None:
            gap("action_without_observations", "Executed action whose source or result observation is missing.")
        keys = op_keys(a.requests)
        for k in keys:
            op_index.setdefault(k.id, (k, []))[1].append(a.id)
        eff = effects(source, result, a.received, a.requests)
        if not keys and not eff:
            no_effect.append(a)
            continue
        role = (source or result).role if (source or result) else "unknown"
        sig = (role, tuple(sorted(k.id for k in keys)), tuple(sorted(eff)), None if keys else tid)
        signatures[a.action_id] = sig
        cap_actions[sig].append(a)

    # Reproduction from independent replays.
    by_action = {a.action_id: a for a in actions}
    replays_of: dict[tuple, list[tuple[Record, bool]]] = defaultdict(list)
    for rp in replays:
        a = by_action.get(rp.action_id or "")
        if a is None or a.action_id not in signatures:
            continue
        sig = signatures[a.action_id]
        ok = rp.status == "replay_validated" and rp.independent_context
        if ok:
            res = ctx.obs.get(rp.result_obs or "")
            src = ctx.obs.get(a.source_obs or "")
            if res is None:
                ok = False
            else:
                if sig[1] and rp.requests is None:
                    gap("replay_requests_not_captured", "A replay passed its legacy checks, but its requests were not recorded, so operation reproduction cannot be established.")
                    continue
                rp_keys = op_keys(rp.requests) if rp.requests is not None else set()
                # A replay's requests span its whole path, so whether the final step reloaded
                # the page is taken from the action itself; the result page is the replay's own.
                ok = set(sig[1]) <= {k.id for k in rp_keys} and set(sig[2]) == effects(src, res, rp.received, a.requests)
        replays_of[sig].append((rp, ok))
    tested = sum(1 for sig in cap_actions if replays_of.get(sig))
    confirmed = sum(1 for sig in cap_actions if any(ok for _, ok in replays_of.get(sig, [])))
    prior = (confirmed + 1) / (tested + 2)

    # Learned context predicates (affordances that bind to several capabilities).
    # "No observable effect" is an outcome too: an affordance that did nothing once
    # and something later (e.g. after a handler revision) needs an explanation.
    by_aff: dict[str, list[Record]] = defaultdict(list)
    for a in [a for acts in cap_actions.values() for a in acts] + no_effect:
        by_aff[action_aff.get(a.action_id, "")].append(a)
    outcome = lambda a: signatures.get(a.action_id, ("no_observable_effect",))
    predicates: list[LearnedPredicate] = []
    predicate_kind: dict[str, tuple[str, str]] = {}      # template id -> (kind, affordance id)
    underdetermined: list[tuple[str, list[Record]]] = []
    tpl_route = {tid: t["route"] for tid, t in templates.items()}

    def feature(kind: str, a: Record) -> Any:
        src = ctx.obs.get(a.source_obs or "")
        if kind == "view_structure":
            if src is None or src.affordances is None:
                return None
            tid = tpl_of_obs[src.obs_id]
            return (tid, tuple(sorted(aff_id(aff_key(tid, x)) for x in src.affordances)))
        if kind == "behavior_revision":
            return a.affordance.behavior_revision if a.affordance else None
        if kind == "record_instance":
            return tuple(sorted(page_tokens(src))) if src else None
        return tuple(src.storage_keys) if src and src.storage_keys is not None else None
    for aid, acts in sorted(by_aff.items()):
        acts = sorted(acts, key=lambda a: (a.seq, a.id))
        if len({outcome(a) for a in acts}) < 2:
            continue
        for kind in ("view_structure", "behavior_revision", "record_instance", "storage_keys"):
            mapping: dict[Any, set] = defaultdict(set)
            for a in acts:
                mapping[feature(kind, a)].add(outcome(a))
            if len(mapping) >= 2 and all(len(v) == 1 for v in mapping.values()):
                if kind == "view_structure":
                    break      # already explained by distinct view states; nothing new to learn
                src = ctx.obs.get(acts[0].source_obs or "")
                tid = tpl_of_obs.get(src.obs_id, "tpl_unknown") if src else "tpl_unknown"
                predicates.append(LearnedPredicate(id="pred_" + _digest([aid, kind]), template_id=tid,
                                                   template_route=tpl_route.get(tid, ""), affordance_id=aid, kind=kind,
                                                   evidence_ids=sorted(a.id for a in acts)))
                predicate_kind.setdefault(tid, (kind, aid))
                break
        else:
            underdetermined.append((aid, acts))

    # View states: template + affordance structure + learned predicate values.
    view_states: dict[str, dict[str, Any]] = {}
    for o in sorted(ctx.obs.values(), key=lambda r: r.seq):
        tid = tpl_of_obs[o.obs_id]
        if o.affordances is None:
            key: list[Any] = [tid, "affordances_not_captured"]
            preds: list[dict[str, Any]] = [{"kind": "affordances_not_captured"}]
        else:
            key = [tid, sorted(aff_id(aff_key(tid, a)) for a in o.affordances)]
            preds = []
            if tid in predicate_kind:
                kind, aid = predicate_kind[tid]
                if kind == "behavior_revision":
                    value = next((a.behavior_revision for a in o.affordances if aff_id(aff_key(tid, a)) == aid), None)
                elif kind == "record_instance":
                    value = sorted(page_tokens(o))
                else:
                    value = o.storage_keys
                key.append([kind, value])
                preds.append({"kind": kind, "affordance_id": aid, "value_class": _digest(value, 8)})
        vid = "vs_" + _digest(key)
        view_states.setdefault(vid, {"template": tid, "preds": preds, "obs": []})["obs"].append(o.obs_id)
        templates[tid].setdefault("views", set()).add(vid)

    # Affordances and their labels.
    aff_nodes: dict[str, dict[str, Any]] = {}

    def note_aff(tid: str, aff, record: Record) -> str:
        aid = aff_id(aff_key(tid, aff))
        node = aff_nodes.setdefault(aid, {"template": tid, "key": aff_key(tid, aff), "labels": {}, "evidence": set(),
                                          "actions": [], "blocked": None, "disabled": set(), "enabled": set()})
        node["evidence"].add(record.id)
        if record.kind == "observation" and aff.disabled is not None:
            node["disabled" if aff.disabled else "enabled"].add(record.id)
        if aff.label.strip() and aff.label not in node["labels"]:
            node["labels"][aff.label] = record.id
        if not aff.safe and node["blocked"] is None:
            node["blocked"] = aff.skip_reason or "unsafe"
        return aid
    for o in ctx.obs.values():
        for a in o.affordances or []:
            note_aff(tpl_of_obs[o.obs_id], a, o)
    for a in actions:
        if a.affordance is None:
            continue
        src = ctx.obs.get(a.source_obs or "")
        aid = note_aff(tpl_of_obs.get(src.obs_id, "tpl_unknown") if src else "tpl_unknown", a.affordance, a)
        aff_nodes[aid]["actions"].append(a)

    # Capabilities, grounding and claims.
    claims: dict[str, Claim] = {}

    def claim(subject: str, predicate: str, obj: str, status: Status, evidence: Iterable[str], *,
              p: float | None = None, support: int = 0, against: int = 0, rule: str | None = None,
              reason: str | None = None) -> None:
        ev = sorted(set(evidence))
        kinds = sorted({rid.split(":")[1] if rid.count(":") >= 2 else "evidence" for rid in ev})
        cid = "cl_" + _digest([subject, predicate, obj])
        claims[cid] = Claim(id=cid, subject=subject, predicate=predicate, object=obj, status=status, p=p,
                            support=support, against=against, evidence_ids=ev, sources=kinds, rule=rule, reason=reason)

    def fired(name: str, sig: tuple, acts: list[Record], status: Status, reps: list[tuple[Record, bool]]):
        """Closed grounding rules (§5.6). Returns (target, rule, status, evidence ids) or None."""
        ops = [op_index[o][0] for o in sig[1]]
        eff = dict(sig[2])
        kinds = {k for k, _ in sig[2]}
        writes = any(o.writes for o in ops)
        reproduced = STATUS_RANK.get(status, 0) >= STATUS_RANK[Status.REPRODUCED]
        good = [rp for rp, ok in reps if ok]
        inputs = any(_engine_input(a) for a in acts)
        if name == "navigation" and reproduced and "navigated" in kinds and not writes and not inputs:
            target = eff["navigated"]
            if "{id}" not in tpl_route.get(target, "") and not kinds & {"instance_appeared", "instance_disappeared",
                                                                        "collection_size_changed",
                                                                        "collection_membership_changed"}:
                return target, "navigation/1", Status.REPRODUCED, [r.id for r in good]
        if name == "instance_view" and reproduced and "navigated" in kinds and not writes and not inputs:
            target_tpl = eff["navigated"]
            route = tpl_route.get(target_tpl, "")
            if "{id}" in route:
                ok = True
                for a in acts:
                    res = ctx.obs.get(a.result_obs or "")
                    if not (a.affordance and a.affordance.target and res and res.url):
                        ok = False
                        break
                    shown = page_tokens(res)
                    if len(shown) != 1 or shown != tokens_in(a.affordance.target):
                        ok = False
                        break
                if ok:
                    etype = next(iter(page_tokens(ctx.obs[acts[0].result_obs])))[0]
                    return etype, "instance_view/1", Status.REPRODUCED, [r.id for r in good]
        if name == "client_view_change" and reproduced and not ops and kinds and kinds <= {"component_state_changed",
                                                                                           "client_state_changed"}:
            return sorted(t for _, t in sig[2])[0].split("/", 1)[0], "client_view_change/1", Status.REPRODUCED, [r.id for r in good]
        if name == "server_job_submission" and reproduced and writes and "message_received" in kinds:
            mine = {t for k, t in sig[2] if k == "message_received"}
            others = {("message_received", "msg_" + _digest([m.message_skeleton, m.message_discriminator]))
                      for x in actions if x.action_id not in {a.action_id for a in acts} for m in x.received or []}
            unique = [t for t in mine if ("message_received", t) not in others]
            received_again = [rp for rp in good if any("msg_" + _digest([m.message_skeleton, m.message_discriminator])
                                                       in unique for m in rp.received or [])]
            if unique and received_again:
                return sorted(unique)[0], "server_job_submission/1", Status.REPRODUCED, [r.id for r in received_again]
        if name == "collection_query":
            fields = sorted({n for a in acts for q in a.requests or [] for n in q.engine_filled})
            outcomes, ids = [], []
            for rp in replays:
                if rp.action_id not in {a.action_id for a in acts} or rp.verification_kind != "paired_search":
                    continue
                if rp.status != "replay_validated" or not rp.independent_context:
                    continue
                vids = rp.verification.get("verification_observation_ids") or []
                if len(vids) != 4 or not all(v in ctx.obs for v in vids):
                    continue
                b1, r1, b2, r2 = (ctx.obs[v] for v in vids)
                targets = lambda o: {_route_of(ctx, a.target) + "|" + urlsplit(a.target).path
                                     for a in o.affordances or [] if a.target}
                primary, contrast = targets(r1) - targets(b1), targets(r2) - targets(b2)
                if primary != contrast and (primary or contrast):
                    outcomes.append(_digest([sorted(primary), sorted(contrast)]))
                    ids.append(rp.id)
            if fields and len(outcomes) >= 2 and len(set(outcomes)) == 1:
                return fields[0], "collection_query/1", Status.VERIFIED, ids
        if name == "instance_creation" and writes and "instance_appeared" in kinds:
            etype = eff["instance_appeared"]
            for rp in replays:
                if rp.action_id not in {a.action_id for a in acts} or rp.verification_kind != "cross_view":
                    continue
                if not any(r is rp and ok for r, ok in reps):
                    continue
                vids = rp.verification.get("verification_observation_ids") or []
                if len(vids) != 2 or not all(v in ctx.obs for v in vids):
                    continue
                detail, collection = ctx.obs[vids[0]], ctx.obs[vids[1]]
                new = {(t, v) for t, v in page_tokens(detail) if t == etype and first_seen.get((t, v), -1) >= detail.seq}
                if new and tpl_of_obs[collection.obs_id] != tpl_of_obs[detail.obs_id] and new <= link_tokens(collection):
                    return etype, "instance_creation/1", Status.VERIFIED, [rp.id, detail.id, collection.id]
        # instance_removal and instance_modification need removal checks under isolation or
        # per-field digests; no development evidence captures either, so they cannot fire.
        return None

    capabilities: list[Capability] = []
    for sig in sorted(cap_actions, key=lambda s: _digest(list(s))):
        acts = cap_actions[sig]
        reps = replays_of.get(sig, [])
        good = [rp for rp, ok in reps if ok]
        status = Status.REPRODUCED if good else Status.OBSERVED
        p = prior
        for _, ok in reps:
            p = _bayes(p, ok, REPRODUCE_S, REPRODUCE_F)
        cap_id = "cap_" + _digest(list(sig))
        found = None
        for name in CLASS_ORDER:
            hit = fired(name, sig, acts, status, reps)
            if hit:
                found = (name, *hit)
                break
        bclass = None
        if found:
            name, target, rule, cstatus, ev = found
            bclass = BehavioralClass(name=name, target=target, rule=rule, status=cstatus, evidence_ids=sorted(ev))
            if STATUS_RANK[cstatus] > STATUS_RANK[status]:
                status = cstatus
                s, f = ORACLE["differential" if name == "collection_query" else "cross_view"]
                p = _bayes(p, True, s, f)
        bindings: dict[str, list[str]] = defaultdict(list)
        for a in acts:
            bindings[action_aff.get(a.action_id, "aff_unknown")].append(a.action_id)
        labels: dict[str, str] = {}
        for aid in sorted(bindings):
            for text, rid in aff_nodes.get(aid, {}).get("labels", {}).items():
                labels.setdefault(text, rid)
        evidence = sorted({a.id for a in acts} | {rp.id for rp, _ in reps})
        cap = Capability(
            id=cap_id, role=sig[0], operation_ids=list(sig[1]), effects=[Effect(kind=k, target=t) for k, t in sig[2]],
            entry_template_id=sig[3], status=status, p=round(p, 6),
            bindings=[Binding(affordance_id=aid, action_ids=sorted(ids)) for aid, ids in sorted(bindings.items())],
            action_ids=sorted(a.action_id for a in acts), reproduction_ids=sorted(rp.id for rp in good),
            behavioral_class=bclass, unidentified=bclass is None,
            reason=None if bclass else ("no grounding rule fired at its minimum status" if sig[1] or sig[2] else None),
            evidence_ids=evidence, labels=[Label(text=t, evidence_id=r) for t, r in sorted(labels.items())])
        capabilities.append(cap)
        claim(cap_id, "has_behavior_signature", _digest(list(sig)), status, evidence, p=cap.p,
              support=len(acts) + sum(ok for _, ok in reps), against=sum(not ok for _, ok in reps),
              reason=None if reps else "untested: no independent replay")
        if bclass:
            claim(cap_id, "has_behavioral_class", f"{bclass.name}:{bclass.target}", bclass.status, bclass.evidence_ids,
                  rule=bclass.rule)
        for aid, ids in bindings.items():
            claim(aid, "binds", cap_id, Status.OBSERVED, [by_action[i].id for i in ids])
        if len(bindings) >= 2:
            claim(cap_id, "equivalent_interfaces", ",".join(sorted(bindings)), status, evidence)
    cap_of_action = {a: c.id for c in capabilities for a in c.action_ids}

    affordances: list[Affordance] = []
    for aid, node in sorted(aff_nodes.items()):
        executed = [a for a in node["actions"] if a.status == "observed"]
        caps = sorted({cap_of_action[a.action_id] for a in executed if a.action_id in cap_of_action})
        if caps:
            status, reason = "bound", None
        elif executed:
            status, reason = "executed_no_effect", "executed; no operation or observable effect evidence"
            claim(aid, "no_observable_effect", "", Status.OBSERVED, [a.id for a in executed], reason=reason)
        elif any(a.status == "failed" for a in node["actions"]):
            status, reason = "failed", "every execution failed"
        elif node["disabled"] and not node["enabled"] and not node["actions"]:
            status, reason = "blocked", "disabled"
        elif node["blocked"] or any(a.status in {"not_tested", "blocked"} for a in node["actions"]):
            status = "blocked"
            reason = node["blocked"] or next((a.error or a.status for a in node["actions"]), "not_tested")
            claim(aid, "execution", "blocked", Status.BLOCKED, node["evidence"], reason=str(reason))
        else:
            status, reason = "unbound", "observed but never executed"
        k = node["key"]
        affordances.append(Affordance(
            id=aid, template_id=node["template"],
            family={"kind": k[1], "role": k[2], "interaction": k[3], "component": k[4], "locator": k[5],
                    "target_route": k[6], "method": k[7], "fields": [list(f) for f in k[8]], "provenance": k[9]},
            labels=[Label(text=t, evidence_id=r) for t, r in sorted(node["labels"].items())], status=status,
            capability_ids=caps, action_ids=sorted(a.action_id for a in node["actions"]),
            evidence_ids=sorted(node["evidence"]), reason=reason))

    # Conditions (minimal, evidence-backed): a control observed disabled, and an
    # executed capability after which a disabled control on the same page became
    # enabled (or the reverse). Nothing is inferred from co-occurrence.
    for aid, node in sorted(aff_nodes.items()):
        if node["disabled"]:
            claim(aid, "observed_disabled", "", Status.OBSERVED, node["disabled"], rule="disabled_control/1")
    conditions: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for a in actions:
        cap = cap_of_action.get(a.action_id)
        src, res = ctx.obs.get(a.source_obs or ""), ctx.obs.get(a.result_obs or "")
        if not cap or src is None or res is None or src.affordances is None or res.affordances is None:
            continue
        tid = tpl_of_obs[src.obs_id]
        if tpl_of_obs[res.obs_id] != tid:
            continue
        before = {aff_id(aff_key(tid, x)): x.disabled for x in src.affordances}
        for x in res.affordances:
            xid = aff_id(aff_key(tid, x))
            if before.get(xid) is True and x.disabled is False:
                conditions[(cap, "establishes", "enabled:" + xid)] |= {a.id, src.id, res.id}
            elif before.get(xid) is False and x.disabled is True:
                conditions[(cap, "invalidates", "enabled:" + xid)] |= {a.id, src.id, res.id}
    for (cap, predicate, obj), ev in sorted(conditions.items()):
        claim(cap, predicate, obj, Status.OBSERVED, ev, rule="enablement/1")
    for pred in predicates:
        claim(pred.affordance_id, "behavior_depends_on", pred.kind, Status.OBSERVED, pred.evidence_ids,
              rule="context_split/1")
    for aid, acts in underdetermined:
        claim(aid, "behavior_depends_on", "unknown", Status.OBSERVED, [a.id for a in acts],
              reason="different signatures, and no observed feature separates them")

    operations = [Operation(id=k.id, channel=k.channel, method=k.method, route=k.route, params=list(k.params),
                            encoding=k.encoding, dispatch=dict(k.dispatch), message_class=k.message_class,
                            evidence_ids=sorted(ids)) for _, (k, ids) in sorted(op_index.items())]
    template_nodes = []
    for tid, t in sorted(templates.items()):
        obs_ids = sorted(o.obs_id for o in t["obs"])
        template_nodes.append(Template(id=tid, route=t["route"], role=t["role"], observation_ids=obs_ids,
                                       view_state_ids=sorted(t.get("views", set()))))
        claim(tid, "observed_template", t["route"], Status.OBSERVED, [o.id for o in t["obs"]])
    view_nodes = [ViewState(id=vid, template_id=v["template"], predicates=v["preds"], observation_ids=sorted(v["obs"]))
                  for vid, v in sorted(view_states.items())]
    instance_nodes = []
    for (etype, value), item in sorted(instances.items()):
        iid = "ei_" + token(ctx.ns, f"{etype}|{value}")
        instance_nodes.append(EntityInstance(id=iid, type_id=etype, token=token(ctx.ns, value),
                                             observation_ids=sorted(item["obs"]), evidence_ids=sorted(item["records"]),
                                             observed_paths=sorted(item["paths"])))
        claim(iid, "instance_of", etype, Status.OBSERVED, item["records"])
    for (p, q), ev in sorted(union_evidence.items()):
        claim(type_of_position[p], "positions_share_identifiers", f"{p}|{q}", Status.OBSERVED, ev, rule="id_flow_union/1")

    if not ctx.capture.dom_affordances:
        gap("dom_affordances_not_captured", "No per-observation affordances: new-instance, collection and component effects cannot be computed.")
    for name, detail in (("websocket", "WebSocket frames were not recorded."),
                         ("response_shapes", "Response shapes were not recorded; entity identity is limited to URL identifiers."),
                         ("instance_fields", "Per-field digests were not recorded; instance_modification cannot be grounded."),
                         ("visual_regions", "Canvas/SVG region digests were not recorded.")):
        if not getattr(ctx.capture, name):
            gap(f"{name}_not_captured", detail)

    statuses = defaultdict(int)
    for c in capabilities:
        statuses[str(c.status)] += 1
    summary = {
        "page_templates": len(template_nodes), "view_states": len(view_nodes), "entity_types": len(entity_types),
        "entity_instances": len(instance_nodes), "capabilities": len(capabilities),
        "unidentified_operations": sum(c.unidentified for c in capabilities),
        "classified_capabilities": sum(not c.unidentified for c in capabilities),
        "equivalent_interface_groupings": sum(len(c.bindings) >= 2 for c in capabilities),
        "capabilities_by_status": dict(sorted(statuses.items())),
        "affordances_by_status": dict(sorted(_count(a.status for a in affordances).items())),
        "learned_predicates": len(predicates), "underdetermined_behaviors": len(underdetermined),
        "executed_actions": sum(a.status == "observed" for a in actions),
        "actions_without_capability": len(no_effect),
        "reproduction_prior": round(prior, 6),
    }
    return ACGExport(
        application=ctx.application, evidence_log_digest=_digest([[r.id, r.seq] for r in records], 16),
        resolver_version=RESOLVER_VERSION, synthetic_evidence=ctx.synthetic, capture=ctx.capture.model_dump(),
        templates=template_nodes, view_states=view_nodes, entity_types=entity_types, entity_instances=instance_nodes,
        affordances=affordances, operations=operations, capabilities=capabilities, learned_predicates=sorted(
            predicates, key=lambda p: p.id), claims=sorted(claims.values(), key=lambda c: c.id),
        gaps=sorted(gaps.values(), key=lambda g: g.kind), summary=summary)


def _count(items: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for item in items:
        out[item] += 1
    return dict(out)
