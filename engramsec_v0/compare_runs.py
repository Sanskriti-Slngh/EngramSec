#!/usr/bin/env python3
"""Compare any number of V0/V1 graph_a.json runs at the same GET budget.

Generates ONE figure with two small panels: cumulative novel form signatures
and cumulative visited route templates. Makes no network requests.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from hybrid import signature


def progression(g):
    node_lookup = {node["url"]: node for node in g["nodes"]}
    forms_by_page = defaultdict(list)
    for form in g["forms"]:
        forms_by_page[form["page"]].append(form)
    seen_forms = set()
    seen_routes = set()
    rows = []
    first_form_at = []
    for step in g["trace"]:
        new_forms = 0
        for form in forms_by_page[step["url"]]:
            sig = signature(form)
            if sig not in seen_forms:
                seen_forms.add(sig)
                new_forms += 1
                first_form_at.append({
                    "get": step["step"], "method": form["method"],
                    "action": form["action"],
                })
        seen_routes.add(node_lookup[step["url"]]["route_pattern"])
        rows.append({
            "get": step["step"], "distinct_forms": len(seen_forms),
            "route_patterns": len(seen_routes), "depth": step["depth"],
            "new_forms": new_forms,
        })
    return rows, first_form_at


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", nargs=2, metavar=("LABEL", "GRAPH_JSON"),
                   action="append", required=True)
    p.add_argument("--out", type=Path, default=Path("outputs/comparison"))
    a = p.parse_args()
    if len(a.run) < 2:
        p.error("Provide at least two --run LABEL PATH arguments")
    a.out.mkdir(parents=True, exist_ok=True)
    data = []
    for label, path in a.run:
        g = json.loads(Path(path).read_text(encoding="utf-8"))
        prog, forms = progression(g)
        if not prog:
            p.error(f"{label} has an empty trace")
        data.append({"label": label, "graph": g, "progress": prog, "first_forms": forms})
    budgets = {x["graph"]["limits"]["max_pages"] for x in data}
    starts = {x["graph"]["start_url"] for x in data}
    depths = {x["graph"]["limits"]["max_depth"] for x in data}
    if len(budgets) > 1 or len(starts) > 1 or len(depths) > 1:
        p.error("Runs must use identical start URL, --max-pages and --max-depth")

    summary = []
    fig, axes = plt.subplots(2, 1, figsize=(9.3, 7.8), sharex=True)
    for x in data:
        rows = x["progress"]
        label = x["label"]
        axes[0].step([r["get"] for r in rows], [r["distinct_forms"] for r in rows],
                     where="post", linewidth=2.2, label=label)
        axes[1].step([r["get"] for r in rows], [r["route_patterns"] for r in rows],
                     where="post", linewidth=2.2, label=label)
        summary.append({
            "policy": label,
            "GETs_used": len(rows),
            "unique_forms": rows[-1]["distinct_forms"],
            "unique_route_patterns": rows[-1]["route_patterns"],
            "max_depth_reached": x["graph"]["metrics"]["max_depth_visited"],
            "unique_form_AUC": sum(r["distinct_forms"] for r in rows),
            "first_form_GETs": ";".join(str(z["get"]) for z in x["first_forms"]),
        })
    axes[0].set_ylabel("Cumulative distinct form signatures")
    axes[1].set_ylabel("Cumulative visited route patterns")
    axes[1].set_xlabel("GET requests used")
    for ax in axes:
        ax.grid(alpha=0.25)
        ax.legend(loc="upper left")
        ax.set_xlim(left=1, right=max(len(x["progress"]) for x in data))
        ax.set_ylim(bottom=0)
    fig.suptitle("EngramSec — policy comparison at equal GET budget", fontsize=14)
    fig.tight_layout()
    fig.savefig(a.out / "policy_comparison.png", dpi=170)
    plt.close(fig)

    with (a.out / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    for r in summary:
        print(r)
    print("Wrote", a.out.resolve())


if __name__ == "__main__":
    main()
