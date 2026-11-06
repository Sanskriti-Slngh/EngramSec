"""Learned (logistic) ranker on the offline ranking situations, trained leave-app-out.

Same situations, metric and fallback as evaluation/model_offline_rank.py; the scorer for a
situation in app X is trained only on distinct examples from the other apps.
"""
from __future__ import annotations

import json
import random
from statistics import mean

from evaluation.comprehensive_config import ROOT
from evaluation.model_learning_curve import predict, train
from evaluation.model_offline_rank import DATA, situations, score

OUT = ROOT / "agent1" / "experiments" / "model_scaling" / "offline_rank" / "learned_lr.json"


def main() -> None:
    rows = [json.loads(line) for line in DATA.open()]
    distinct = list({r["dedup_key"]: r for r in rows}.values())
    sits = situations()
    random.Random(0).shuffle(sits)
    models = {}
    res = []
    for s in sits:
        if s["app"] not in models:
            models[s["app"]] = train([r for r in distinct if r["app"] != s["app"]])
        w = models[s["app"]]
        scored = sorted(s["candidates"], key=lambda c: -predict(w, {"action": c, "history": s["history"]}))
        res.append(score([c["id"] for c in scored], s))
    summary = {"situations": len(sits), "learned_lr": {"p_at_1": round(mean(x["p_at_1"] for x in res), 3),
                                                       "mrr": round(mean(x["mrr"] for x in res), 3)}}
    OUT.write_text(json.dumps(summary, indent=1))
    print(summary)


if __name__ == "__main__":
    main()
