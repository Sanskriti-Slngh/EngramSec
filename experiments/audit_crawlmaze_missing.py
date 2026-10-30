#!/usr/bin/env python3
"""Offline per-path root-cause audit of Crawl Maze misses (diagnostic only).

Reads the pinned testbed's public expected-results file and EXISTING Agent 1
run artifacts (graph_a.json + run.json). It never runs a crawl, is never
imported by Agent 1, and its output is not crawler input.

Marker "reached" uses the same definition as score_crawlmaze_posthoc.py
(`any_fetch`): a 2xx browser response (exploration, restoration or replay) or a
2xx typed-spider GET recorded in the run's Graph A.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

# ---------------------------------------------------------------------------
# Testbed facts, hand-verified against /private/tmp/security-crawl-maze @ 2a0dd0a.
# container = the response whose body/headers carry the reference;
# parent = the page that loads/links that container (None if same / well-known).
# interaction: none | click | multi_click | form_enter | timer | navigate_header
# extractor: whether Agent 1's static extractors can recognize the mechanism
#   (yes / no / partial), from agent1/resource_spider.py at c4b4e8f.
# ---------------------------------------------------------------------------
H = "/html/"
def html(rel: str) -> str:
    return H + rel + ".html/"

FACTS: dict[str, dict] = {}

def fact(path, container, mechanism, *, parent=None, interaction="none", method="GET",
         extractor="yes", extractor_note="", browser_auto="no", supported="yes", support_note=""):
    FACTS[path] = dict(container=container, parent=parent, mechanism=mechanism, interaction=interaction,
                       method=method, extractor=extractor, extractor_note=extractor_note,
                       browser_auto=browser_auto, supported=supported, support_note=support_note)

UNBUILT = ("Plain Flask deployment serves the unbuilt framework source; README: 'Run locally as a Flask app "
           "(Does not support JS frameworks)'.")
fact("/javascript/frameworks/angular/event-handler.found", "/javascript/frameworks/angular/", "Angular event handler (built SPA)",
     interaction="click", extractor="no", supported="no", support_note=UNBUILT + " No index.html in source tree: every path under /javascript/frameworks/angular/ returns 404 (verified).")
fact("/javascript/frameworks/angular/router-outlet.found", "/javascript/frameworks/angular/", "Angular router-outlet route (built SPA)",
     extractor="no", supported="no", support_note=UNBUILT + " Every path returns 404 (verified).")
fact("/javascript/frameworks/angularjs/ng-href.found", "/javascript/frameworks/angularjs/", "AngularJS ng-href with hashbang route 'index.html#!ng-href.found'",
     interaction="click", extractor="no", extractor_note="ng-href is not an extracted attribute; value is an {{expression}}",
     supported="conditional", support_note="No build needed, but angular.min.js/angular-route.js load from ajax.googleapis.com (third-party CDN). "
     "The link resolves to a hashbang fragment; the expected path requires interpreting '#!ng-href.found' as a route. Catch-all returns 200 for the expected path.")
fact("/javascript/frameworks/polymer/event-handler.found", "/javascript/frameworks/polymer/", "Polymer event handler (built SPA)",
     interaction="click", extractor="no", supported="no", support_note=UNBUILT + " index.html loads /node_modules/...webcomponents-loader.js and /src/my-app.js "
     "(both 404, verified) and my-app.js uses bare module specifiers; the app cannot render. Catch-all returns index.html (200) for any path, but no reachable resource references the marker.")
fact("/javascript/frameworks/polymer/polymer-router.found", "/javascript/frameworks/polymer/", "Polymer router link (built SPA)",
     extractor="no", supported="no", support_note=UNBUILT + " Same as polymer/event-handler.")
fact("/javascript/frameworks/react/index.html/search.found", "/javascript/frameworks/react/", "React Router redirect (built SPA)",
     interaction="form_enter", extractor="no", supported="no", support_note=UNBUILT + " No index.html at root: every path returns 404 (verified).")
fact("/javascript/frameworks/react/route-path.found", "/javascript/frameworks/react/", "React Router Link (built SPA)",
     interaction="click", extractor="no", supported="no", support_note=UNBUILT + " Every path returns 404 (verified).")

fact("/test/css/font-face.found", "/css/font-face.css", "@font-face src:url() in a linked stylesheet", parent="/css/font-face.html/", browser_auto="no")
fact("/test/headers/content-location.found", "/headers/content-location/", "Content-Location response header (201)")
fact("/test/headers/link.found", "/headers/link/", "Link: <...>; rel=preload response header", browser_auto="yes")
fact("/test/headers/location.found", "/headers/location/", "301 Location header", interaction="navigate_header", browser_auto="yes")
fact("/test/headers/refresh.found", "/headers/refresh/", "Refresh: 999; url=... header")

def attr(rel, tagattr, ok, note="", auto="no", interaction="none", method="GET", container=None):
    fact(f"/test/html/{rel}.found", container or html(rel), f"HTML {tagattr}", extractor=ok, extractor_note=note,
         browser_auto=auto, interaction=interaction, method=method)

attr("body/a/href", "<a href>", "yes")
attr("body/a/ping", "<a ping> (no href)", "no", "ping not in attribute table", container=html("body/a/ping"))
attr("body/applet/archive", "<applet archive>", "yes")
attr("body/applet/codebase", "<applet codebase>", "yes")
attr("body/audio/source/src", "<audio><source src>", "yes", auto="maybe")
fact("/test/html/body/audio/source/srcset1x.found", html("body/audio/source/srcset"), "HTML <source srcset> 1x candidate", extractor="yes")
fact("/test/html/body/audio/source/srcset2x.found", html("body/audio/source/srcset"), "HTML <source srcset> 2x candidate", extractor="yes")
attr("body/audio/src", "<audio src>", "yes", auto="maybe")
attr("body/background", "<body background>", "no", "background only extracted on <table>", auto="maybe")
attr("body/blockquote/cite", "<blockquote cite>", "yes")
attr("body/embed/src", "<embed src>", "yes", auto="maybe")
attr("body/form/action-get", "<form action method=GET>, no submit button (implicit Enter submit)", "partial",
     "form action extracted as kind=api -> queue_decision observed_only_api (never fetched)", interaction="form_enter")
attr("body/form/action-post", "<form action method=POST>, no submit button", "partial",
     "form action extracted as kind=api -> observed_only_api; POST forms disabled (allow_post_forms=False); testbed /test route answers POST with 405",
     interaction="form_enter", method="POST")
attr("body/form/button/formaction", "<button formaction> submit", "yes", "formaction extracted as navigation", interaction="click")
fact("/test/html/body/frameset/frame/src.found", html("body/frameset/frame/src"), "HTML <frame src>", extractor="yes", browser_auto="yes")
attr("body/iframe/src", "<iframe src>", "yes", auto="yes")
attr("body/iframe/srcdoc", "<iframe srcdoc> containing <img src>", "no", "srcdoc HTML not parsed", auto="yes")
attr("body/img/dynsrc", "<img dynsrc>", "no", "dynsrc not in attribute table")
attr("body/img/longdesc", "<img longdesc>", "no", "longdesc not in attribute table")
attr("body/img/lowsrc", "<img lowsrc>", "no", "lowsrc not in attribute table")
attr("body/img/src-data", "<img src=data:image/svg+xml> with inner xlink:href", "no",
     "data: URI not decoded/parsed; browsers do not load external resources from SVG-as-image")
attr("body/img/src", "<img src>", "yes", auto="yes")
fact("/test/html/body/img/srcset1x.found", html("body/img/srcset"), "HTML <img srcset> 1x candidate", extractor="yes", browser_auto="maybe")
fact("/test/html/body/img/srcset2x.found", html("body/img/srcset"), "HTML <img srcset> 2x candidate", extractor="yes", browser_auto="maybe")
attr("body/input/src", "<input type=image src>", "yes", auto="yes")
attr("body/isindex/action", "<isindex action>", "no", "isindex not in attribute table")
attr("body/map/area/ping", "<area ping href=#>", "no", "ping not in attribute table; browser sends ping only on click with hyperlink auditing",
     interaction="click", method="POST")
attr("body/object/codebase", "<object codebase>", "no", "object codebase not in attribute table (only data)")
attr("body/object/data", "<object data>", "yes", auto="maybe")
attr("body/object/param/value", "<param value>", "yes")
attr("body/script/src", "<script src>", "yes", auto="yes")
attr("body/svg/image/xlink", "<svg><image xlink:href>", "yes", auto="yes")
attr("body/svg/script/xlink", "<svg><script xlink:href>", "no", "script tag extracts only src")
attr("body/table/background", "<table background>", "yes")
attr("body/table/td/background", "<td background>", "no", "background only extracted on <table>")
attr("body/video/poster", "<video poster>", "yes", auto="maybe")
attr("body/video/src", "<video src>", "yes", auto="maybe")
attr("body/video/track/src", "<video><track src>", "yes")
fact("/test/html/doctype.found", "/html/doctype.html/", "<!DOCTYPE html SYSTEM \"...\">", extractor="no", extractor_note="declarations not parsed")
attr("head/base/href", "<base href>", "no", "base href changes resolution but is not itself emitted as a reference")
fact("/test/html/head/comment-conditional.found", "/html/head/comment/comment-conditional.html/", "<link href> inside <!--[if true]> conditional comment",
     extractor="no", extractor_note="comments ignored by HTML parser")
attr("head/import/implementation", "<IMPORT implementation>", "no", "import tag not in attribute table")
attr("head/link/href", "<link rel=prefetch href>", "yes", auto="maybe")
attr("head/meta/content-csp", "CSP meta report-uri", "no", "CSP directives not parsed")
attr("head/meta/content-pinned-websites", "<meta name=msapplication-config content>", "yes")
attr("head/meta/content-reading-view", "<meta name=copyright content=\"<img src=...>\">", "no", "HTML inside meta content not parsed")
attr("head/meta/content-redirect", "<meta http-equiv=refresh content=\"10; url=...\">", "yes", "meta refresh extracted as navigation", auto="maybe")
fact("/test/html/head/profile.found", "/html/head/profile.html/", "<video poster> (file named profile)", extractor="yes", browser_auto="maybe")
fact("/test/html/manifest.found", "/html/manifest.html/", "<html manifest>", extractor="no", extractor_note="html[manifest] not in attribute table")
for name, form in [("dot-dot-slash-prefix", "'../test/...' in page text"), ("dot-slash-prefix", "'./test/...' in page text")]:
    fact(f"/test/html/misc/string/{name}.found", f"/html/misc/string/{name}.html/", f"URL-like string in visible text: {form}",
         extractor="no", extractor_note="no text-node URL extraction")
fact("/test/html/misc/string/string-known-extension.pdf", "/html/misc/string/string-known-extension.html/",
     "'/string-known-extension.pdf' text string combined with <base href=/test/html/misc/string>", extractor="no", extractor_note="no text-node URL extraction")
fact("/test/html/misc/string/url-string.found", "/html/misc/string/url-string/", "absolute URL in visible text", extractor="no", extractor_note="no text-node URL extraction")
fact("/test/html/misc/url/full-url.found", "/html/misc/url/full-url/", "<a href=absolute URL>", extractor="yes")
fact("/test/html/misc/url/path-relative-url.found", "/html/misc/url/path-relative-url/", "<base href=/test/> + relative <a href>", extractor="yes")
fact("/test/html/misc/url/protocol-relative-url.found", "/html/misc/url/protocol-relative-url/", "<a href=//host/...>", extractor="yes")
fact("/test/html/misc/url/root-relative-url.found", "/html/misc/url/root-relative-url.html/", "<a href=/...>", extractor="yes")

JSI = "/javascript/interactive/"
def jsi(name, page, mechanism, *, interaction="click", method="GET"):
    fact(f"/test/javascript/interactive/{name}.found", f"{JSI}{page}.html/", mechanism, interaction=interaction, method=method,
         extractor="partial", extractor_note="fetch() literal in inline script is extracted by the AST parser as kind=api -> observed_only_api (never fetched)")
jsi("js-delete", "js-delete", "onclick attribute -> fetch DELETE", method="DELETE")
jsi("js-post-event-listener", "js-post-event-listener", "addEventListener(click) on visible button -> fetch POST", method="POST")
jsi("js-post", "js-post", "onclick attribute -> fetch POST", method="POST")
jsi("js-put", "js-put", "onclick attribute -> fetch PUT", method="PUT")
jsi("listener-and-event-attribute-first", "listener-and-event-attribute", "addEventListener(click) -> fetch POST", method="POST")
jsi("listener-and-event-attribute-second", "listener-and-event-attribute", "onclick attribute on same button -> fetch POST", method="POST")
jsi("multi-step-request-event-attribute", "multi-step-request-event-attribute", "click 1 creates <button> with .onclick -> click 2 fetch GET", interaction="multi_click")
jsi("multi-step-request-event-listener-div-dom", "multi-step-request-event-listener-div-dom", "click 1 creates <div> + listener before DOM insert -> click 2 fetch GET", interaction="multi_click")
jsi("multi-step-request-event-listener-div", "multi-step-request-event-listener-div", "click 1 creates <div> + listener after DOM insert -> click 2 fetch GET", interaction="multi_click")
jsi("multi-step-request-event-listener-dom", "multi-step-request-event-listener-dom", "click 1 creates <button> + listener before insert -> click 2 fetch GET", interaction="multi_click")
jsi("multi-step-request-event-listener", "multi-step-request-event-listener", "click 1 creates <button> + listener -> click 2 fetch GET", interaction="multi_click")
jsi("multi-step-request-redefine-event-attribute", "multi-step-request-redefine-event-attribute", "click 1 redefines onclick -> click 2 on same button fetch GET", interaction="multi_click")
jsi("multi-step-request-remove-button", "multi-step-request-remove-button", "click 1 creates button; any other click removes it -> click 2 fetch GET", interaction="multi_click")
jsi("multi-step-request-remove-event-listener", "multi-step-request-remove-event-listener", "as remove-button, plus removeEventListener", interaction="multi_click")
jsi("two-listeners-first", "two-listeners", "first of two click listeners -> fetch POST", method="POST")
jsi("two-listeners-second", "two-listeners", "second of two click listeners -> fetch POST", method="POST")
fact("/test/javascript/misc/automatic-post.found", "/javascript/misc/automatic-post.html/", "setTimeout(5000) -> fetch POST on page load",
     interaction="timer", method="POST", extractor="partial", extractor_note="fetch() literal extracted as kind=api -> observed_only_api", browser_auto="after_5s")
for name, how in [("comment", "URL in a // comment"), ("string-concat-variable", "URL split across concatenated string variables"),
                  ("string-variable", "absolute URL in a string variable")]:
    fact(f"/test/javascript/misc/{name}.found", f"/javascript/misc/{name}.js", f"External script: {how}",
         parent=f"/javascript/misc/{name}.html/", extractor="no",
         extractor_note={"comment": "AST parser ignores comments",
                         "string-concat-variable": "constants are folded, but the folded value is never passed to a recognized sink",
                         "string-variable": "absolute URL literal assigned to a variable; AST parser emits literals only at recognized sinks (fetch/open/location/element attributes/imports)"}[name])
fact("/test/misc/known-files/robots.txt.found", "/robots.txt", "Disallow: line in /robots.txt (well-known file, not linked)",
     parent=None, extractor="no", extractor_note="robots parser extracts only Sitemap: lines (marker is on a Disallow: line); /robots.txt is never probed")
fact("/test/misc/known-files/sitemap.xml.found", "/sitemap.xml", "<loc> in /sitemap.xml (well-known file, not linked)",
     parent=None, extractor="yes", extractor_note="XML <loc> extractor exists, but /sitemap.xml is never requested (no well-known-file probing)")


def norm(path: str) -> str:
    path = unquote(path or "/")
    return path if path == "/" else path.rstrip("/")


def ok(status) -> bool:
    return status is not None and 200 <= int(status) < 300


class RunEvidence:
    def __init__(self, root: Path):
        self.name = root.name
        self.graph = json.loads((root / "graph_a.json").read_text())
        self.run = json.loads((root / "run.json").read_text())
        g, r = self.graph, self.run
        self.config = r["config"]
        self.metrics = r["metrics"]
        # Browser network events: exploration, restoration prerequisites, navigation and replays.
        self.events: list[dict] = []
        for nav in g.get("navigation_evidence", []):
            self.events += [dict(e, via=f"navigation:{nav['reason']}") for e in nav.get("network", [])]
        for action in g["nodes"].get("actions_evidence", []):
            self.events += [dict(e, via="action") for e in action.get("network", [])]
            for step in action.get("prerequisite_network", []):
                self.events += [dict(e, via="restoration") for e in step.get("network", [])]
        for replay in g.get("replays", []):
            self.events += [dict(e, via="replay") for e in replay.get("network", [])]
        self.events_by_path: dict[str, list[dict]] = defaultdict(list)
        for e in self.events:
            if e.get("url"):
                self.events_by_path[norm(urlsplit(e["url"]).path)].append(e)
        self.refs_by_path: dict[str, list[dict]] = defaultdict(list)
        self.refs_by_source: dict[str, list[dict]] = defaultdict(list)
        for item in g.get("resource_evidence", []):
            if item.get("url"):
                self.refs_by_path[norm(urlsplit(item["url"]).path)].append(item)
            if item.get("source_url"):
                self.refs_by_source[norm(urlsplit(item["source_url"]).path)].append(item)
        self.obs = {o["id"]: o for o in r["observations"]}
        self.states_by_path: dict[str, list[dict]] = defaultdict(list)
        for o in r["observations"]:
            self.states_by_path[norm(urlsplit(o["url"]).path)].append(o)
        self.transitions_by_source: dict[str, list[dict]] = defaultdict(list)
        for t in r["transitions"]:
            src = self.obs.get(t["source_observation_id"])
            if src:
                self.transitions_by_source[norm(urlsplit(src["url"]).path)].append(t)
        self.control_targets: set[str] = set()
        for o in r["observations"]:
            for c in o.get("controls", []):
                if c.get("target"):
                    self.control_targets.add(norm(urlsplit(c["target"]).path))

    def reached(self, path: str) -> bool:
        p = norm(path)
        if any(ok(e.get("status")) for e in self.events_by_path.get(p, [])):
            return True
        return any(r.get("status") == "fetched" and ok(r.get("http_status")) for r in self.refs_by_path.get(p, []))

    def container_status(self, path: str) -> str:
        p = norm(path)
        how = []
        if self.states_by_path.get(p):
            how.append("browser_state")
        if any(ok(e.get("status")) for e in self.events_by_path.get(p, [])):
            how.append("browser_2xx")
        if any(r.get("status") == "fetched" and ok(r.get("http_status")) for r in self.refs_by_path.get(p, [])):
            how.append("spider_fetched")
        if how:
            return "reached:" + "+".join(how)
        known = []
        if p in self.control_targets:
            known.append("advertised_link")
        refs = self.refs_by_path.get(p, [])
        if refs:
            known.append("resource_ref[" + ",".join(sorted({str(r.get('status')) for r in refs})) + "]")
        return ("known_not_reached:" + "+".join(known)) if known else "not_discovered"


def describe_refs(refs: list[dict]) -> dict[str, str]:
    if not refs:
        return dict(observed="no", extractor="", queue="", attempted="no", response="")
    srcs = sorted({f"{r.get('source_type')}:{r.get('source')}" for r in refs})
    queues = sorted({str(r.get("queue_decision")) for r in refs if r.get("queue_decision")})
    statuses = sorted({str(r.get("status")) for r in refs})
    attempted = any(r.get("status") in {"fetched", "failed"} for r in refs)
    http = sorted({str(r.get("http_status")) for r in refs if r.get("http_status") is not None})
    errors = sorted({str(r.get("error"))[:60] for r in refs if r.get("error")})
    return dict(observed="yes", extractor=";".join(srcs), queue=";".join(queues) + (" | status=" + ";".join(statuses)),
                attempted="yes" if attempted else "no", response=";".join(http + errors))


def interaction_facts(run: RunEvidence, container: str) -> dict[str, str]:
    p = norm(container)
    controls = {}
    for o in run.states_by_path.get(p, []):
        for c in o.get("controls", []):
            if c["interaction"] != "navigate":
                controls[c["signature"]] = c
    executed = [t for t in run.transitions_by_source.get(p, []) if t["action"]["interaction"] != "navigate"]
    executed_labels = sorted({f"{t['action']['label']}[{t['status']}]" for t in executed})
    advertised = sorted({f"{c['label']}({c['interaction']}{'' if c.get('safe') else ',unsafe:' + str(c.get('skip_reason'))})" for c in controls.values()})
    created = set()
    for t in executed:
        before = {c["signature"] for c in (run.obs.get(t["source_observation_id"]) or {}).get("controls", [])}
        after = (run.obs.get(t.get("result_observation_id")) or {}).get("controls", [])
        created |= {f"{c['label']}({c['interaction']})" for c in after if c["signature"] not in before and c["interaction"] != "navigate"}
    second_step = bool(created)
    page_controls = max((len(o.get("controls", [])) for o in run.states_by_path.get(p, [])), default=-1)
    click_counts = Counter(t["action"]["label"] for t in executed)
    methods = sorted({f"{e.get('method')}:{e.get('status')}" for t in executed for e in t.get("network", [])
                      if "/test/" in (e.get("url") or "")})
    return dict(advertised=";".join(advertised), executed=";".join(executed_labels),
                executed_counts=";".join(f"{k}x{v}" for k, v in sorted(click_counts.items())),
                created_controls=";".join(sorted(created)), page_controls=page_controls,
                second_step_control_observed="yes" if second_step else "no", executed_marker_requests=";".join(methods))


def classify(f: dict, b: dict) -> tuple[int, str, list[str], str]:
    """Primary cause (1-11), precise label, secondary blockers, confidence. Rules are applied
    along the causal chain of the mechanism the test case exercises."""
    sec: list[str] = []
    if f["supported"] == "no":
        return 1, "Unsupported in plain-Flask deployment (framework not built)", sec, "confirmed"
    cont = b["container_status"]
    parent_note = ""
    if f["parent"] and not cont.startswith("reached"):
        parent_note = f"parent {f['parent']}: {b['parent_status']}"
    if f["supported"] == "conditional":
        sec.append("AngularJS loads from third-party CDN; Agent 1 aborts cross-origin requests when an HTTP budget is set; hashbang route interpretation also required")
    if not cont.startswith("reached"):
        if cont.startswith("known_not_reached"):
            label = "Parent page discovered (advertised/referenced) but never visited or fetched"
        else:
            label = "Parent page never discovered"
        if f["extractor"] == "no":
            sec.append("3: static extractor would not recognize the mechanism even if the page were fetched")
        if f["interaction"] != "none":
            sec.append(f"requires interaction ({f['interaction']})")
        if "class_budget_limited" in cont:
            sec.append("5: parent page reference was class_budget_limited (70-document spider budget exhausted) and no browser action reached it")
        if parent_note:
            sec.append(parent_note)
        return 2, label, sec, "confirmed"
    ref = b["ref"]
    inter = b["inter"]
    if f["supported"] == "conditional":
        if inter["page_controls"] == 0:
            return 8, ("Third-party CDN scripts aborted by Agent 1's same-origin route (HTTP budget set; 2 cross-origin requests blocked); "
                       "AngularJS never rendered the ng-href link (0 controls on page)"), sec + [
                "10: even when rendered (S300, no route) the link is a client-side hashbang route; the expected server path is never requested"], "confirmed"
        return 10, "Hashbang client-side route; expected server path never requested", sec, "confirmed"
    if f["interaction"] in {"click", "multi_click", "timer"} and f["container"].startswith("/javascript/"):
        if ref["observed"] == "yes" and "observed_only_api" in ref["queue"]:
            sec.append("4: fetch() literal was extracted but classified kind=api (observed_only_api), so never fetched by the spider")
        if f["method"] != "GET":
            sec.append(f"10: intended request is {f['method']}; testbed /test route returns 405 to non-GET, so the 2xx scorer counts it only via a GET of the literal")
        if f["interaction"] == "timer":
            if b["marker_events"]:
                return 10, "Browser issued the request but non-2xx (405 to POST)", sec, "confirmed"
            return 6, ("Page behavior available but never exercised: 5 s timer never fired because the browser left the page "
                       "~3.5 s after navigating (B run.json observation 215)"), sec, "confirmed"
        if not inter["executed"]:
            return 6, "Clickable control advertised but never executed", sec, "confirmed" if inter["advertised"] else "likely"
        if f["interaction"] == "multi_click":
            if "redefine" in f["mechanism"]:
                return 7, ("First click executed (redefines the same button's onclick, no DOM change); the same control was "
                           "never clicked again"), sec, "confirmed"
            if inter["second_step_control_observed"] == "no":
                return 7, ("First click executed; the created element (" + ("<div> with addEventListener" if "div" in f["mechanism"] else "control")
                           + ") was not detected as a control"), sec, "confirmed"
            return 6, "Second-step control created and observed (" + inter["created_controls"] + ") but never clicked", sec, "confirmed"
        if b["marker_events"]:
            return 10, "Browser issued request after click but received non-2xx", sec, "confirmed"
        return 7, "Click executed but no request to the marker observed", sec, "likely"
    if ref["observed"] == "no" and not b["marker_events"]:
        if f["interaction"] == "form_enter":
            sec.append("form has no submit button; submission needs implicit Enter")
            return 3, "Form action not extracted and form not submitted", sec, "confirmed"
        if f["extractor"] == "no" or f["extractor"] == "partial":
            return 3, "Parent reached; mechanism not supported by static extractors (" + (f["extractor_note"] or f["mechanism"]) + ")", sec, "confirmed"
        return 11, "Parent reached; supported mechanism produced no recorded reference", sec, "unknown"
    if ref["observed"] == "yes" and ref["attempted"] == "no" and not b["marker_events"]:
        q = ref["queue"]
        if "observed_only_api" in q:
            if f["method"] == "POST":
                sec.append("8: POST form submission disabled (allow_post_forms=False); 10: testbed returns 405 to POST")
                return 8, "Form action extracted as API (observed only); POST forms disabled by safety policy", sec, "confirmed"
            return 4, "Reference extracted but classified kind=api (observed_only_api), never fetched", sec, "confirmed"
        if "class_budget_limited" in q or "budget_limited" in q:
            return 5, "Admitted but not fetched: typed-resource class budget exhausted", sec, "confirmed"
        if "duplicate_candidate" in q or "admitted" in q:
            return 5, "Admitted to queue but not attempted before the run's spider budget/time ended", sec, "likely"
        if "rejected" in q:
            return 4, f"Reference excluded ({q})", sec, "confirmed"
        return 11, f"Reference observed, not attempted ({q})", sec, "unknown"
    statuses = ref["response"] or ";".join(f"{e.get('method')}:{e.get('status')}" for e in b["marker_events"])
    return 9, f"Attempted but no 2xx ({statuses})", sec, "confirmed"


# ---------------------------------------------------------------------------
# Opportunity analysis: blockers per route to a scorer-countable 2xx, and which
# fix families would clear them. A fix is "sufficient alone" for a miss when it
# clears every blocker on at least one route.
# ---------------------------------------------------------------------------
FIXES = {
    "R1 HTML attribute/declaration/comment/srcdoc extractor coverage": {"extractor_gap:html"},
    "R2 Text-node and non-sink JS string/comment literal candidates": {"extractor_gap:text_js"},
    "R3 Well-known file probing (robots Disallow, sitemap)": {"well_known", "extractor_gap:robots"},
    "A1 Allocation: visit/fetch every discovered parent page (browser actions + document fetches)": {"parent_unvisited", "marker_class_budget"},
    "P1 Policy: fetch GET-method API literals (fetch(GET), GET form action)": {"api_get_policy"},
    "P2 Policy: GET re-check of non-GET API literals": {"nonget_api_policy"},
    "I1 Runtime interaction: listener-bearing elements, re-click after handler change, timer dwell": {"listener_only_control", "same_control_reclick", "dwell_timer"},
    "S1 Stateful prerequisites: implicit form submission and executing created controls": {"implicit_submit"},
    "E1 Evaluator: count observed non-2xx requests to marker URLs": {"nonget_405_scoring"},
    "T1 Testbed: build JS frameworks (Docker image)": {"unsupported"},
    "C1 Policy: allow-listed third-party script origins + hashbang route semantics": {"cdn_policy", "hashbang_semantics"},
}
HTML_TEXT = ("misc/string/",)


def routes(row: dict) -> list[set[str]]:
    path, ext, inter, method = row["expected_path"], row["static_extractor_support"], row["requires_browser_interaction"], row["intended_method"]
    if row["supported_by_deployment"] == "no":
        return [{"unsupported"}]
    if row["supported_by_deployment"] == "conditional":
        return [{"cdn_policy", "hashbang_semantics"}]
    base = set()
    cont = row["B_container_reached"]
    if cont == "not_discovered":
        base.add("well_known")
    elif not cont.startswith("reached"):
        base.add("parent_unvisited")
    static = set(base)
    if ext == "no":
        if "/known-files/robots" in path:
            static.add("extractor_gap:robots")
        elif any(t in path for t in HTML_TEXT) or path.startswith("/test/javascript/misc/"):
            static.add("extractor_gap:text_js")
        else:
            static.add("extractor_gap:html")
    elif ext == "partial":
        static.add("api_get_policy" if method == "GET" else "nonget_api_policy")
    if "class_budget_limited" in row["B_queue_decision"] and row["B_attempted_by_spider"] == "no":
        static.add("marker_class_budget")
    result = [static]
    dynamic = set(base)
    if inter == "click" and path.startswith("/test/javascript/"):
        if method != "GET":
            dynamic.add("nonget_405_scoring")
        result.append(dynamic)
    elif inter == "multi_click":
        if "redefine" in row["mechanism"]:
            dynamic.add("same_control_reclick")
        elif "<div>" in row["mechanism"]:
            dynamic.add("listener_only_control")
        result.append(dynamic)
    elif inter == "timer":
        result.append(dynamic | {"dwell_timer", "nonget_405_scoring"})
    elif inter == "form_enter":
        dyn = dynamic | {"implicit_submit"}
        if method != "GET":
            dyn |= {"post_form_policy", "nonget_405_scoring"}
        result.append(dyn)
    return result


def opportunity(rows: list[dict]) -> dict:
    missing = [r for r in rows if r["reached_B"] == "no"]
    out = {}
    for name, cleared in FIXES.items():
        alone = [r for r in missing if any(route <= cleared for route in routes(r))]
        with_alloc = [r for r in missing if any(route <= cleared | FIXES[next(k for k in FIXES if k.startswith("A1"))] for route in routes(r))]
        necessary = [r for r in missing if all(route & cleared for route in routes(r))]
        out[name] = {
            "sufficient_alone": len(alone),
            "sufficient_with_A1_allocation": len(with_alloc),
            "on_every_route_of": len(necessary),
            "distinct_test_pages_alone_or_with_A1": len({r["container"] for r in with_alloc}),
            "examples": [r["expected_path"] for r in with_alloc][:12],
        }
    return out


def offline_extractor_check(testbed: Path) -> dict[str, str]:
    """Run Agent 1's own static extractors on each case's container content, read
    from the pinned testbed on disk (templates rendered locally). No network."""
    import re
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from agent1.resource_spider import (extract_css_references, extract_html_references, extract_robots_sitemaps,
                                        extract_script_references, extract_xml_references)
    base = "http://127.0.0.1:3460/"

    def render(text: str) -> str:
        return re.sub(r'\{\{\s*url_for\("index",\s*_external=True(?:,\s*_scheme="")?\)\s*\}\}',
                      lambda m: "//127.0.0.1:3460/" if "_scheme" in m.group(0) else base, text)

    js = {"/javascript/misc/comment.js": "// " + base + "test/javascript/misc/comment.found",
          "/javascript/misc/string-variable.js": 'var url = "' + base + 'test/javascript/misc/string-variable.found";',
          "/javascript/misc/string-concat-variable.js": 'var domain = "' + base + '";var path = "test/javascript/misc/string-concat-variable.found";var full = domain + path;'}
    out = {}
    for path, f in FACTS.items():
        c = f["container"].rstrip("/")
        if f["supported"] != "yes" or c.startswith("/headers"):
            out[path] = "n/a (header or unsupported)"
            continue
        if c.startswith("/html/misc/url/") and not c.endswith(".html"):
            text, fn = render((testbed / "blueprints/html/templates/url" / (c.split("/")[-1] + ".html")).read_text()), extract_html_references
        elif c == "/html/misc/string/url-string":
            text, fn = render((testbed / "blueprints/html/templates/string/url-string.html").read_text()), extract_html_references
        elif c.endswith(".html"):
            text, fn = (testbed / "test-cases" / c.lstrip("/")).read_text(), extract_html_references
        elif c in js:
            text, fn = js[c], extract_script_references
        elif c == "/css/font-face.css":
            text, fn = "@font-face{font-family: leak;src: url(" + base + "test/css/font-face.found);}", extract_css_references
        elif c == "/robots.txt":
            text, fn = "User-agent: *\nDisallow: /test/misc/known-files/robots.txt.found", extract_robots_sitemaps
        elif c == "/sitemap.xml":
            text, fn = render((testbed / "templates/sitemap.xml").read_text()), extract_xml_references
        else:
            out[path] = "n/a"
            continue
        refs = fn(text, base.rstrip("/") + f["container"])
        match = [r for r in refs if norm(urlsplit(r.url).path) == norm(path)]
        out[path] = ("extracted " + ",".join(sorted({f"kind={r.kind} via {r.source}" for r in match}))) if match else "NOT extracted"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expected", type=Path, default=Path("/private/tmp/security-crawl-maze/blueprints/utils/resources/expected-results.json"))
    ap.add_argument("--best", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--serious", type=Path, required=True)
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--json", type=Path, required=True)
    args = ap.parse_args()
    expected = json.loads(args.expected.read_text())
    assert len(expected) == 91 and set(expected) == set(FACTS), sorted(set(expected) ^ set(FACTS))
    extractor_check = offline_extractor_check(args.expected.parents[3])
    runs = {"A": RunEvidence(args.baseline), "B": RunEvidence(args.best), "S300": RunEvidence(args.serious)}
    rows = []
    for path in expected:
        f = FACTS[path]
        category = path.split("/")[2] if path.startswith("/test/") else "javascript"
        row = {"expected_path": path, "category": category, "mechanism": f["mechanism"],
               "supported_by_deployment": f["supported"], "support_note": f["support_note"],
               "container": f["container"], "parent_page": f["parent"] or ""}
        for key, run in runs.items():
            row[f"reached_{key}"] = "yes" if run.reached(path) else "no"
        b = runs["B"]
        info = {
            "container_status": b.container_status(f["container"]),
            "parent_status": b.container_status(f["parent"]) if f["parent"] else "",
            "ref": describe_refs(b.refs_by_path.get(norm(path), [])),
            "inter": interaction_facts(b, f["container"]),
            "marker_events": b.events_by_path.get(norm(path), []),
        }
        row.update({
            "B_container_reached": info["container_status"],
            "B_parent_reached": info["parent_status"],
            "B_reference_observed": info["ref"]["observed"],
            "B_extractor": info["ref"]["extractor"],
            "B_queue_decision": info["ref"]["queue"],
            "B_attempted_by_spider": info["ref"]["attempted"],
            "B_browser_requests": ";".join(sorted({f"{e.get('method')}:{e.get('status')}:{e['via']}" for e in info["marker_events"]})),
            "B_response_or_failure": info["ref"]["response"],
            "static_extractor_support": f["extractor"],
            "offline_extractor_result": extractor_check[path],
            "extractor_note": f["extractor_note"],
            "requires_browser_interaction": f["interaction"],
            "intended_method": f["method"],
            "browser_auto_request_on_load": f["browser_auto"],
            "B_non_navigate_controls_advertised": info["inter"]["advertised"],
            "B_non_navigate_controls_executed": info["inter"]["executed"],
            "B_non_navigate_execution_counts": info["inter"]["executed_counts"],
            "B_controls_created_by_executed_clicks": info["inter"]["created_controls"],
            "B_second_step_control_observed": info["inter"]["second_step_control_observed"],
            "B_marker_requests_from_executed_actions": info["inter"]["executed_marker_requests"],
        })
        if row["reached_B"] == "yes":
            row.update(primary_cause="", primary_cause_label="reached", secondary_causes="", confidence="confirmed")
        else:
            cause, label, sec, conf = classify(f, info)
            row.update(primary_cause=cause, primary_cause_label=label, secondary_causes=" | ".join(sec), confidence=conf)
        # S300 short diagnosis for cross-run comparison.
        s = runs["S300"]
        row["S300_container_reached"] = s.container_status(f["container"])
        row["S300_reference"] = describe_refs(s.refs_by_path.get(norm(path), []))["queue"]
        row["evidence_refs"] = (f"B graph_a.json resource_evidence url={path}; B run.json observations url~{f['container']}; "
                                f"testbed {f['container']}")
        row["route_blockers"] = " || ".join("+".join(sorted(r)) for r in routes(row)) if row["reached_B"] == "no" else ""
        rows.append(row)
    fields = list(rows[0].keys())
    with args.csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    missing = [r for r in rows if r["reached_B"] == "no"]
    summary = {
        "reached": {k: sum(r[f"reached_{k}"] == "yes" for r in rows) for k in runs},
        "missing_B": len(missing),
        "missing_B_by_category": Counter(r["category"] for r in missing),
        "primary_causes": Counter(str(r["primary_cause"]) for r in missing),
        "primary_labels": Counter(f"{r['primary_cause']}: {r['primary_cause_label']}" for r in missing),
        "supported": Counter(r["supported_by_deployment"] for r in rows),
        "opportunity": opportunity(rows),
        "run_configs": {k: {x: run.config.get(x) for x in ("max_seconds", "max_browser_actions", "max_resource_fetches",
                                                            "max_total_http_requests", "allow_post_forms", "policy")}
                        for k, run in runs.items()},
    }
    args.json.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, default=dict) + "\n")
    print(json.dumps(summary, indent=2, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
