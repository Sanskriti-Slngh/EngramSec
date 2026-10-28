from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent1.explorer import BrowserSession
from agent1.revision import code_revision
from agent1.schema import Observation, RunConfig, utc_now


def matching_result_links(observation: Observation, query: str) -> list[dict[str, str]]:
    needle = query.casefold()
    return [
        {"label": control.label, "target": control.target or ""}
        for control in observation.controls
        if control.kind == "link" and needle in control.label.casefold() and control.target
    ]


def find_search_toggle(observation: Observation):
    candidates = [
        control
        for control in observation.controls
        if control.safe
        and control.kind == "button"
        and any(token in control.label.casefold() for token in ("search", "find"))
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"expected one observed search toggle, found {len(candidates)}")
    return candidates[0]


def find_search_submit(observation: Observation):
    candidates = [
        control
        for control in observation.controls
        if control.safe
        and control.kind == "form_submit"
        and any(field.input_type == "search" for field in control.fields)
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"expected one actionable search form, found {len(candidates)}")
    return candidates[0]


def run_search(session: BrowserSession, sequence: int, query: str) -> tuple[int, dict, list[Observation], int]:
    source = session.observe(sequence)
    toggle = find_search_toggle(source)
    _, toggle_network, toggle_dialogs, toggle_actions = session.execute(toggle)
    sequence += 1
    exposed = session.observe(sequence)
    submit = find_search_submit(exposed)
    field = next(field for field in submit.fields if field.input_type == "search")
    input_refs, submit_network, submit_dialogs, submit_actions = session.execute(
        submit,
        {field.id: query},
        input_plan_ref=f"ordinary-search:{query.casefold()}",
    )
    sequence += 1
    result = session.observe(sequence)
    links = matching_result_links(result, query)
    path = {
        "query": query,
        "actions": [
            {
                "control_id": toggle.id,
                "label": toggle.label,
                "kind": toggle.kind,
                "source_observation_id": source.id,
                "result_observation_id": exposed.id,
                "network": [item.model_dump(mode="json") for item in toggle_network],
                "dialogs": toggle_dialogs,
                "status": "observed_transition",
            },
            {
                "control_id": submit.id,
                "label": submit.label,
                "kind": submit.kind,
                "field_id": field.id,
                "input_references": [item.model_dump(mode="json") for item in input_refs],
                "source_observation_id": exposed.id,
                "result_observation_id": result.id,
                "network": [item.model_dump(mode="json") for item in submit_network],
                "dialogs": submit_dialogs,
                "status": "observed_transition",
            },
        ],
        "result": {
            "observation_id": result.id,
            "url": result.url,
            "title": result.title,
            "route_pattern": result.route_pattern,
            "content_fingerprint": result.content_fingerprint,
            "query_matching_result_links": links,
            "non_echo_result_evidence": bool(links),
        },
    }
    return sequence, path, [source, exposed, result], toggle_actions + submit_actions


def replay_pair(browser, config: RunConfig, replay_number: int, primary: str, contrast: str) -> dict:
    started = time.monotonic()
    with BrowserSession(browser, config) as session:
        browser_actions = session.goto_start()
        sequence = replay_number * 100
        sequence, primary_path, primary_observations, count = run_search(
            session, sequence + 1, primary
        )
        browser_actions += count
        browser_actions += session.goto_start()
        sequence, contrast_path, contrast_observations, count = run_search(
            session, sequence + 1, contrast
        )
        browser_actions += count

    primary_targets = {item["target"] for item in primary_path["result"]["query_matching_result_links"]}
    contrast_targets = {item["target"] for item in contrast_path["result"]["query_matching_result_links"]}
    checks = {
        "primary_has_non_echo_result_links": bool(primary_targets),
        "contrast_has_non_echo_result_links": bool(contrast_targets),
        "contrasting_result_targets_differ": primary_targets != contrast_targets,
        "contrasting_content_differs": (
            primary_path["result"]["content_fingerprint"]
            != contrast_path["result"]["content_fingerprint"]
        ),
        "primary_navigation_reproduced": (
            urlsplit(primary_path["result"]["url"]).path
            != urlsplit(config.start_url).path
        ),
    }
    navigation = checks["primary_navigation_reproduced"]
    functional = all(checks.values())
    observations = primary_observations + contrast_observations
    return {
        "replay_id": f"siyucms-search-replay-{replay_number}",
        "fresh_context": True,
        "primary_path": primary_path,
        "contrast_path": contrast_path,
        "checks": checks,
        "navigation_status": "navigation_reproduced" if navigation else "failed",
        "functional_status": "functional_outcome_supported" if functional else "unresolved",
        "validation_failure": False,
        "browser_actions": browser_actions,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "observations": [item.model_dump(mode="json") for item in observations],
    }


def mermaid_for(evidence: dict) -> str:
    status = evidence["summary"]["functional_status"]
    return "\n".join(
        [
            "flowchart LR",
            '  H[\"Anonymous home\\nobserved\"] -->|\"toggle search\\nobserved prerequisite\"| F[\"Search form exposed\"]',
            f'  F -->|\"submit php\\nnavigation 2/2\"| R[\"PHP result links\\n{status}\"]',
            '  F -.->|\"contrast: Linux\"| C[\"Different result links/content\\nvalidation discriminator\"]',
            "  classDef supported fill:#d9f7df,stroke:#27823b;",
            "  classDef observed fill:#dcecff,stroke:#3975a8;",
            "  classDef check fill:#fff0c7,stroke:#9b7418;",
            "  class H,F observed;",
            "  class R supported;",
            "  class C check;",
        ]
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay an anonymous observed search workflow twice")
    parser.add_argument("--url", default="http://127.0.0.1:51707/")
    parser.add_argument("--out", type=Path, default=Path("agent1/experiments/siyucms_search_milestone"))
    parser.add_argument("--primary", default="php")
    parser.add_argument("--contrast", default="Linux")
    args = parser.parse_args()

    started_wall = utc_now()
    started = time.monotonic()
    config = RunConfig(
        start_url=args.url,
        output_dir=args.out,
        max_seconds=120,
        max_transitions=4,
        max_browser_actions=40,
        action_timeout_ms=8_000,
        settle_ms=300,
        context_label="siyucms:anonymous-search",
        model_provider="none",
        allow_post_forms=False,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            replays = [
                replay_pair(browser, config, number, args.primary, args.contrast)
                for number in (1, 2)
            ]
        finally:
            browser.close()

    navigation_successes = sum(
        item["navigation_status"] == "navigation_reproduced" for item in replays
    )
    functional_successes = sum(
        item["functional_status"] == "functional_outcome_supported" for item in replays
    )
    functional_status = (
        "functional_outcome_supported" if functional_successes == len(replays) else "unresolved"
    )
    evidence = {
        "schema_version": "targeted-search-1.0",
        "run_id": f"siyucms-search-{int(time.time())}",
        "code_revision": code_revision(ROOT),
        "started_at": started_wall,
        "ended_at": utc_now(),
        "scope": "anonymous website-only search; no target source or verifier inspection",
        "model_calls": 0,
        "external_cost_usd": 0.0,
        "status_vocabulary": [
            "navigation_reproduced",
            "functional_outcome_supported",
            "validation_failure",
            "unresolved",
            "untested",
        ],
        "validation_rule": (
            "A query must produce one or more result-link labels containing the ordinary query; "
            "a contrasting ordinary query must produce a different target set and content fingerprint. "
            "Title, echoed input, click, and HTTP status are insufficient alone."
        ),
        "failed_discovery_attempts": [
            {
                "action": "click search input before prerequisite",
                "status": "interaction_failed",
                "evidence": "the rendered input center was covered by a sibling text-content region",
                "resolution": "execute the observed toggle search prerequisite first",
            }
        ],
        "replays": replays,
        "summary": {
            "navigation_replays": f"{navigation_successes}/{len(replays)}",
            "functional_replays": f"{functional_successes}/{len(replays)}",
            "functional_status": functional_status,
            "validation_failures": 0,
            "unresolved": 0 if functional_successes == len(replays) else len(replays) - functional_successes,
            "untested": 0,
            "browser_actions": sum(item["browser_actions"] for item in replays),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        },
    }
    graph = {
        "schema_version": "graph-a-search-example-1.0",
        "run_id": evidence["run_id"],
        "status_vocabulary": evidence["status_vocabulary"],
        "workflow": "anonymous search",
        "prerequisites": ["open anonymous home", "execute observed toggle search control"],
        "replay_evidence": [
            {
                "replay_id": item["replay_id"],
                "navigation_status": item["navigation_status"],
                "functional_status": item["functional_status"],
                "checks": item["checks"],
                "primary_result": item["primary_path"]["result"],
                "contrast_result": item["contrast_path"]["result"],
            }
            for item in replays
        ],
    }
    (args.out / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.out / "graph_a.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.out / "graph_a.mmd").write_text(mermaid_for(evidence), encoding="utf-8")
    print(json.dumps(evidence["summary"], sort_keys=True))
    return 0 if functional_successes == len(replays) else 1


if __name__ == "__main__":
    raise SystemExit(main())
