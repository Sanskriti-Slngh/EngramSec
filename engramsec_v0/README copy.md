# EngramSec — Agent 1 V0, quantitative black-box web mapper

**Research question:** At a fixed GET-request budget, how much of a running application can a deterministic breadth-first crawler discover? This is a baseline for a future adaptive exploration policy.

## Scope

- Takes only a **starting URL** from an authorized **localhost** test application.
- Fetches HTML with HTTP GET; **no model, browser, JS execution, or form submissions**.
- Does not read benchmark source, hidden metadata, challenge answers or verifiers.
- Does not follow redirects to other origins. Does not submit forms or change account data.
- Does not crawl external sites, does not brute force endpoints, does not test vulnerabilities.
- Skips URLs whose paths have obvious state-changing names such as `/logout` and `/delete`.
- Navigation itself may still trigger side effects on a poorly designed website. Only use with isolated, authorized targets.
- Features are **URL-path grouping heuristics**; not actual verified functionalities.

## Install

```bash
cd ~/EngramSec
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## One curl smoke test

```bash
curl -sS -I http://127.0.0.1:51707/
curl -sS http://127.0.0.1:51707/ | head -c 450
```

## Crawl running SiyuCMS

```bash
python crawler.py --url http://127.0.0.1:51707/ --max-pages 40 --max-depth 4 --delay 0.25 --out outputs/siyucms_bfs_40
```

### Files

- `graph_a.json`: discovered page nodes, link edges, grouped features, forms (not submitted), trace, metrics.
- `graph_a.mmd`: route-template diagram for Mermaid preview in VS Code/GitHub-compatible renderers.
- `metrics.json`: summary numbers.
- `trace.jsonl`: chronological per-GET event stream.
- `report.md`: readable feature and metric summary.

## Controls and fair comparisons

- The **URL** is an explicitly authorized local target; the crawler only visits that exact origin.
- Budget is *HTTP GET requests*, not tokens; set `--max-pages 10` to smoke-test first.
- The homepage is depth 0. Maximum depth applies to *link clicks* as represented by HTTP requests.
- New paths are recorded as `discovered_not_visited` if budget is exhausted.
- `route_patterns_visited` is a proxy for coverage and must not be treated as true functional or vulnerability coverage.
- Baseline policy uses a FIFO deque; later swap for a priority queue without changing `parse_page`, the graph schema, or the budget.
- Official CAGE Level 0 evaluation uses isolated per-task containers and must not expose hidden benchmark files; this local target-manager development run is not a scored benchmark trial.

## Next research checkpoints

1. Manual inspect ~10 observed URLs to gauge route and feature grouping precision.
2. A/B test 10, 20, 40 GET budgets. Record discovered features, frontier, depth, and cost.
3. Build a second policy that prioritizes novel route patterns; compare against this unchanged BFS baseline at the **same budget**.
4. Later add Playwright for JS-only buttons and multi-step client-side flows; keep HTTP-only V0 as the control.
