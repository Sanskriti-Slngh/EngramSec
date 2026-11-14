"""Is there enough labelled data to train a "reveals new functionality" predictor?

Learning curve with a deliberately simple learner (pure-Python logistic regression on bag-of-
features from the action, the page route and run history), evaluated leave-apps-out: train on k
development apps, test on the others. If held-out quality is flat or near a hand-written
novelty heuristic as k grows, a LoRA fine-tune of a language model on the same data is not
justified (it sees the same examples with far more parameters).

  .venv/bin/python -m evaluation.model_learning_curve
"""
from __future__ import annotations

import json
import math
import random
import re
from collections import defaultdict
from statistics import mean, pstdev

from evaluation.comprehensive_config import ROOT
from evaluation.model_offline_rank import DATA

OUT = ROOT / "agent1" / "experiments" / "model_scaling" / "learning_curve.json"


def features(r: dict) -> list[str]:
    a = r["action"]
    toks = re.findall(r"[a-z]{3,}", (a.get("label") or "").lower())
    visited = set(r["history"]["visited_routes"])
    novel = bool(a.get("target_route")) and a["target_route"] not in visited
    f = [f"kind={a.get('kind')}", f"interaction={a.get('interaction')}", f"method={a.get('method')}",
         f"has_target={bool(a.get('target_route'))}", f"target_novel={novel}",
         f"has_fields={bool(a.get('fields'))}", f"steps_bucket={min(r['history']['steps'] // 10, 5)}"]
    f += [f"w={t}" for t in toks[:6]] + [f"field={x.lower()}" for x in (a.get("fields") or [])[:6]]
    return f


def train(rows: list[dict], epochs: int = 30, lr: float = 0.2, l2: float = 1e-3) -> dict[str, float]:
    w: dict[str, float] = defaultdict(float)
    data = [(features(r), r["label"]) for r in rows]
    rng = random.Random(0)
    for _ in range(epochs):
        rng.shuffle(data)
        for fs, y in data:
            z = w["bias"] + sum(w[f] for f in fs)
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            g = p - y
            w["bias"] -= lr * g
            for f in fs:
                w[f] -= lr * (g + l2 * w[f])
    return w


def predict(w: dict[str, float], r: dict) -> float:
    return w.get("bias", 0.0) + sum(w.get(f, 0.0) for f in features(r))


def auc(scores: list[float], labels: list[int]) -> float | None:
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main() -> None:
    rows = [json.loads(line) for line in DATA.open()]
    distinct = list({r["dedup_key"]: r for r in rows}.values())
    apps = sorted({r["app"] for r in distinct})
    novelty = lambda r: float(bool(r["action"].get("target_route")) and
                              r["action"]["target_route"] not in set(r["history"]["visited_routes"]))
    curve = []
    for k in range(1, len(apps)):
        aucs, base = [], []
        for seed in range(12):
            train_apps = set(random.Random(seed * 31 + k).sample(apps, k))
            tr = [r for r in distinct if r["app"] in train_apps]
            te = [r for r in distinct if r["app"] not in train_apps]
            w = train(tr)
            a = auc([predict(w, r) for r in te], [r["label"] for r in te])
            b = auc([novelty(r) for r in te], [r["label"] for r in te])
            if a is not None and b is not None:
                aucs.append(a)
                base.append(b)
        curve.append({"train_apps": k, "train_examples_mean": round(mean(
            len([r for r in distinct if r["app"] in set(random.Random(s * 31 + k).sample(apps, k))]) for s in range(12)), 1),
            "heldout_auc_mean": round(mean(aucs), 3), "heldout_auc_sd": round(pstdev(aucs), 3),
            "novelty_heuristic_auc_mean": round(mean(base), 3)})
        print(curve[-1])
    result = {"distinct_examples": len(distinct), "positives": sum(r["label"] for r in distinct), "apps": apps,
              "learner": "logistic regression, bag of action/page/history features, leave-apps-out, 12 resamples per k",
              "curve": curve}
    OUT.write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
