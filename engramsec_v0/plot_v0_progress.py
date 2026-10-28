#!/usr/bin/env python3
"""Plot EngramSec V0 discovery curves from an existing graph_a.json.

Usage (from ~/EngramSec/engramsec_v0):
    python plot_v0_progress.py \
        --graph outputs/siyucms_bfs_40/graph_a.json \
        --out outputs/analysis

Requires matplotlib. Analysis-only; makes no HTTP requests.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


def form_signature(form: dict) -> tuple:
    """A structural signature, not proof that two forms behave identically."""
    fields = tuple((f.get("name", ""), f.get("type", ""))
                   for f in form.get("field_names", []))
    return (form.get("method", "GET"), form.get("action"), fields)


def get_progress(graph: dict) -> list[dict]:
    by_page = defaultdict(list)
    for form in graph["forms"]:
        by_page[form["page"]].append(form)

    seen = set()
    total_forms = 0
    deepest = 0
    rows = []
    for event in graph["trace"]:
        url = event["url"]
        forms = by_page.get(url, [])
        total_forms += len(forms)
        for form in forms:
            seen.add(form_signature(form))
        depth = int(event["depth"])
        deepest = max(deepest, depth)
        rows.append({
            "get_requests": int(event["step"]),
            "forms_observed": total_forms,
            "distinct_form_signatures": len(seen),
            "current_request_depth": depth,
            "maximum_depth_reached": deepest,
            "new_urls_from_request": event["new_urls"],
        })
    return rows


def plot_forms(rows: list[dict], out: Path) -> None:
    x = [r["get_requests"] for r in rows]
    y_total = [r["forms_observed"] for r in rows]
    y_unique = [r["distinct_form_signatures"] for r in rows]
    fig, ax = plt.subplots(figsize=(9.5, 5.3))
    a, = ax.plot(x, y_total, linewidth=2.4, label="All HTML form occurrences")
    ax.set_xlabel("GET requests used (budget)")
    ax.set_ylabel("Form occurrences")
    ax.set_ylim(bottom=0)
    ax.set_xlim(left=1, right=max(x))
    ax.grid(alpha=0.22)
    ax2 = ax.twinx()
    b, = ax2.step(x, y_unique, where="post", linewidth=2.4,
                   linestyle="--", label="Distinct form signatures")
    ax2.set_ylabel("Distinct form signatures")
    ax2.set_ylim(0, max(y_unique) + 1)
    ax.legend([a, b], [a.get_label(), b.get_label()], loc="upper left")
    # Identify the exact requests at which a distinct form was first observed.
    last = 0
    for r in rows:
        n = r["distinct_form_signatures"]
        if n > last:
            ax2.annotate(f'{n} distinct @ GET {r["get_requests"]}',
                         (r["get_requests"], n), xytext=(8, 9),
                         textcoords="offset points", fontsize=8)
            last = n
    fig.suptitle("SiyuCMS V0: form discovery vs. GET budget", weight="bold")
    ax.set_title("Two y-axes: repeated forms and unique signatures have very different scales",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "01_forms_vs_requests.png", dpi=190)
    plt.close(fig)


def plot_depth(rows: list[dict], configured_cap: int, out: Path) -> None:
    x = [r["get_requests"] for r in rows]
    current = [r["current_request_depth"] for r in rows]
    reached = [r["maximum_depth_reached"] for r in rows]
    fig, ax = plt.subplots(figsize=(9.5, 5.3))
    ax.scatter(x, current, marker="|", s=145, alpha=0.75,
               label="Depth of each fetched page")
    ax.step(x, reached, where="post", linewidth=2.6,
            label="Maximum depth reached so far")
    ax.axhline(configured_cap, linestyle="--", linewidth=1.6,
               label=f"Configured maximum depth = {configured_cap}")
    ax.set_xlabel("GET requests used (budget)")
    ax.set_ylabel("Link depth from starting URL")
    ax.set_ylim(-0.25, max(configured_cap, max(reached)) + 0.55)
    ax.set_yticks(range(max(configured_cap, max(reached)) + 1))
    ax.set_xlim(left=1, right=max(x))
    ax.grid(alpha=0.22)
    ax.legend(loc="upper left")
    first_at_depth = {}
    for r in rows:
        first_at_depth.setdefault(r["current_request_depth"], r["get_requests"])
    for d, step in sorted(first_at_depth.items()):
        if d > 0:
            ax.annotate(f"First depth {d}: GET {step}",
                        (step, d), xytext=(8, 12), textcoords="offset points",
                        fontsize=9)
    fig.suptitle("SiyuCMS V0: actual depth vs. GET budget", weight="bold")
    ax.set_title("A permitted depth of 4 does not mean BFS reaches depth 4", fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "02_depth_vs_requests.png", dpi=190)
    plt.close(fig)



def plot_depth_sweep(graphs: list[dict], out: Path) -> None:
    """Compare actual depth and distinct forms for runs with different depth caps.

    Runs should share start URL and max_pages, but shallow caps may exhaust
    their queue before the request budget is fully used.
    """
    runs = []
    for graph in graphs:
        rows = get_progress(graph)
        if not rows:
            continue
        runs.append({
            "cap": int(graph["limits"]["max_depth"]),
            "requests": rows[-1]["get_requests"],
            "reached": rows[-1]["maximum_depth_reached"],
            "distinct": rows[-1]["distinct_form_signatures"],
        })
    runs.sort(key=lambda r: r["cap"])
    if len({r["cap"] for r in runs}) < 2:
        raise ValueError("Provide at least two graphs with different max_depth caps")
    xs = [r["cap"] for r in runs]
    fig, ax = plt.subplots(figsize=(9.5, 5.3))
    actual, = ax.plot(xs, [r["reached"] for r in runs], marker="o", linewidth=2,
                      label="Maximum depth actually reached")
    capline, = ax.plot(xs, xs, linestyle=":", linewidth=2,
                       label="Depth limit (reference)")
    ax.set_xlabel("Configured --max-depth")
    ax.set_ylabel("Link depth reached")
    ax.set_ylim(bottom=0)
    ax.set_xticks(xs)
    ax.grid(alpha=0.22)
    ax2 = ax.twinx()
    forms, = ax2.plot(xs, [r["distinct"] for r in runs], marker="s",
                      linestyle="--", linewidth=2,
                      label="Distinct form signatures")
    ax2.set_ylabel("Distinct form signatures")
    ax2.set_ylim(bottom=0)
    ax.legend([actual, capline, forms],
              [actual.get_label(), capline.get_label(), forms.get_label()],
              loc="upper left")
    for r in runs:
        ax.annotate(f'{r["requests"]} GETs', (r["cap"], r["reached"]),
                    xytext=(6, 9), textcoords="offset points", fontsize=8)
    fig.suptitle("SiyuCMS V0: what changing the depth cap actually does", weight="bold")
    ax.set_title("Annotations show requests used; shallow runs may terminate early",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "02_depth_cap_sweep.png", dpi=190)
    plt.close(fig)

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path,
                        default=Path("outputs/siyucms_bfs_40/graph_a.json"))
    parser.add_argument("--out", type=Path, default=Path("outputs/analysis"))
    parser.add_argument("--depth-sweep", type=Path, nargs="*", default=[],
                        help="Optional other graph_a.json files with different max_depth settings")
    args = parser.parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    rows = get_progress(graph)
    if not rows:
        parser.error("No crawl trace found")
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "progress.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plot_forms(rows, args.out)
    if args.depth_sweep:
        sweep = [graph] + [json.loads(p.read_text(encoding="utf-8")) for p in args.depth_sweep]
        plot_depth_sweep(sweep, args.out)
    else:
        plot_depth(rows, int(graph["limits"]["max_depth"]), args.out)
    print(f'GET requests: {len(rows)}')
    print(f'Forms observed: {rows[-1]["forms_observed"]}')
    print(f'Distinct form signatures: {rows[-1]["distinct_form_signatures"]}')
    print(f'Maximum depth reached: {rows[-1]["maximum_depth_reached"]}')
    print(f'Output: {args.out.resolve()}')


if __name__ == "__main__":
    main()
