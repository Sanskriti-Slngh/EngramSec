#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawlee import ConcurrencySettings, Request
from crawlee.configuration import Configuration
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from playwright.async_api import async_playwright

from agent1.state import route_pattern, same_origin, sanitize_url
from agent1.revision import code_revision


DANGEROUS = re.compile(
    r"\b(delete|remove|destroy|drop|reset|shutdown|disable|unsubscribe|purge|clear|empty|logout|signout)\b",
    re.I,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runnable Crawlee Playwright external baseline")
    parser.add_argument("--url", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=600)
    parser.add_argument("--max-pages", type=int, default=200)
    return parser.parse_args()


async def crawl(args: argparse.Namespace) -> dict:
    started = time.monotonic()
    records: list[dict] = []
    browser_actions = 0
    with tempfile.TemporaryDirectory(prefix="engramsec-crawlee-") as storage:
        configuration = Configuration(
            storage_dir=storage,
            headless=True,
            purge_on_start=True,
            log_level="WARNING",
        )
        crawler = PlaywrightCrawler(
            headless=True,
            max_requests_per_crawl=args.max_pages,
            concurrency_settings=ConcurrencySettings(
                min_concurrency=1, max_concurrency=1, desired_concurrency=1
            ),
            configuration=configuration,
        )

        @crawler.router.default_handler
        async def handler(context: PlaywrightCrawlingContext) -> None:
            nonlocal browser_actions
            await context.page.wait_for_timeout(350)
            current = sanitize_url(context.page.url)
            raw_links = await context.page.locator("a[href]").evaluate_all(
                """els => els.map(el => ({
                    href: el.href,
                    label: (el.innerText || el.getAttribute('aria-label') || el.title || '').replace(/\\s+/g, ' ').trim(),
                    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
                }))"""
            )
            links = []
            for raw in raw_links:
                target = sanitize_url(raw["href"], current)
                if not raw["visible"] or not same_origin(args.url, target):
                    continue
                if DANGEROUS.search(f"{raw['label']} {urlsplit(target).path}"):
                    continue
                links.append({"href": target, "label": raw["label"][:120]})
            path = list((context.request.user_data or {}).get("path", []))
            records.append(
                {
                    "url": current,
                    "route_pattern": route_pattern(current),
                    "title": await context.page.title(),
                    "path": path,
                    "visible_same_origin_links": len(links),
                }
            )
            browser_actions += 1
            requests = []
            for link in links:
                requests.append(
                    Request.from_url(
                        link["href"],
                        user_data={"path": path + [link]},
                    )
                )
            if requests:
                await crawler.add_requests(requests)

        try:
            await asyncio.wait_for(
                crawler.run([Request.from_url(args.url, user_data={"path": []})]),
                timeout=args.seconds * 0.65,
            )
        except TimeoutError:
            pass

    crawl_elapsed = time.monotonic() - started
    replay_deadline = started + args.seconds
    replay_results = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            for record in sorted(records, key=lambda item: (len(item["path"]), item["url"])):
                if not record["path"] or time.monotonic() >= replay_deadline:
                    continue
                context = await browser.new_context()
                page = await context.new_page()
                actions = 1
                error = None
                try:
                    await page.goto(args.url, wait_until="domcontentloaded", timeout=10_000)
                    await page.wait_for_timeout(350)
                    for step in record["path"]:
                        candidates = page.locator("a[href]")
                        matched = None
                        for index in range(await candidates.count()):
                            candidate = candidates.nth(index)
                            href = await candidate.get_attribute("href")
                            if href and sanitize_url(urljoin(page.url, href)) == step["href"]:
                                matched = candidate
                                break
                        if matched is None:
                            raise RuntimeError(f"link missing for {step['href']}")
                        await matched.click(timeout=5_000)
                        actions += 1
                        try:
                            await page.wait_for_load_state("domcontentloaded", timeout=5_000)
                        except Exception:
                            pass
                        await page.wait_for_timeout(200)
                    checks = {
                        "route_pattern": route_pattern(sanitize_url(page.url)) == record["route_pattern"],
                        "title": (await page.title()).strip() == record["title"].strip(),
                    }
                    success = all(checks.values())
                    if not success:
                        error = "outcome checks did not match"
                except Exception as exc:
                    checks = {}
                    success = False
                    error = f"{type(exc).__name__}: {str(exc)[:240]}"
                finally:
                    await context.close()
                browser_actions += actions
                replay_results.append(
                    {
                        "url": record["url"],
                        "path_length": len(record["path"]),
                        "success": success,
                        "checks": checks,
                        "browser_actions": actions,
                        "error": error,
                    }
                )
        finally:
            await browser.close()
    validated_feature_keys = {
        record["route_pattern"]
        for record in records
        if record["path"]
        and any(result["url"] == record["url"] and result["success"] for result in replay_results)
        and record["route_pattern"] != route_pattern(args.url)
    }
    elapsed = round(time.monotonic() - started, 3)
    return {
        "schema_version": "crawlee-baseline-1.0",
        "baseline": "Crawlee PlaywrightCrawler 1.11.0",
        "code_revision": code_revision(ROOT),
        "mechanism": "visible same-origin link queue; no button or form interaction",
        "target": args.url,
        "limits": {"seconds": args.seconds, "max_pages": args.max_pages, "workers": 1},
        "metrics": {
            "elapsed_seconds": elapsed,
            "crawl_elapsed_seconds": round(crawl_elapsed, 3),
            "pages_visited": len(records),
            "route_patterns": len({record["route_pattern"] for record in records}),
            "browser_actions": browser_actions,
            "distinct_validated_feature_workflows": len(validated_feature_keys),
            "replay_success_numerator": sum(result["success"] for result in replay_results),
            "replay_success_denominator": len(replay_results),
            "unsupported_connections": sum(not result["success"] for result in replay_results),
            "incorrect_state_merges": "not_applicable_no_grouping",
            "redundant_states": len(records) - len({record["route_pattern"] for record in records}),
            "monetary_cost_usd": 0.0,
        },
        "visited": records,
        "replays": replay_results,
        "limitations": [
            "Crawlee is a maintained browser crawler, not a state-flow testing system.",
            "This adapter replays visible link paths, but does not interact with buttons or forms.",
            "Direct crawl visits and replay time are both included in elapsed time.",
        ],
    }


def report(result: dict) -> str:
    metrics = result["metrics"]
    return "\n".join(
        [
            "# Crawlee external baseline",
            "",
            f"- Target: `{result['target']}`",
            f"- Elapsed: {metrics['elapsed_seconds']} seconds",
            f"- Pages / route patterns: {metrics['pages_visited']} / {metrics['route_patterns']}",
            f"- Validated link workflows: {metrics['distinct_validated_feature_workflows']}",
            f"- Replay success: {metrics['replay_success_numerator']}/{metrics['replay_success_denominator']}",
            f"- Unsupported connections: {metrics['unsupported_connections']}",
            f"- Browser actions: {metrics['browser_actions']}",
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in result["limitations"]],
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"output directory is not empty: {args.out}")
    args.out.mkdir(parents=True, exist_ok=True)
    result = asyncio.run(crawl(args))
    (args.out / "baseline.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out / "report.md").write_text(report(result), encoding="utf-8")
    print(json.dumps(result["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
