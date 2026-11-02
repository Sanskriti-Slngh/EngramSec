"""Information-gain arithmetic (EXPLORATION_PLANNER_DESIGN.md §5.2 B–F). Pure functions."""
from __future__ import annotations

import math


def h(ps: list[float]) -> float:
    return -sum(p * math.log2(p) for p in ps if p > 0)


def hb(p: float) -> float:
    return h([p, 1 - p])


def binary_eig(p: float, s: float, f: float) -> float:
    """Mutual information between a binary claim (prior p) and a noisy pos/neg outcome."""
    return hb(p * s + (1 - p) * f) - (p * hb(s) + (1 - p) * hb(f))


def bayes(p: float, positive: bool, s: float, f: float) -> float:
    if positive:
        return p * s / (p * s + (1 - p) * f)
    return p * (1 - s) / (p * (1 - s) + (1 - p) * (1 - f))


def kl_bernoulli(post: float, prior: float) -> float:
    """Bayesian surprise in bits; its expectation over outcomes is the EIG."""
    out = 0.0
    for a, b in ((post, prior), (1 - post, 1 - prior)):
        if a > 0:
            out += a * math.log2(a / max(b, 1e-12))
    return max(0.0, out)


def run_local_prior(confirmed: int, tested: int) -> float:
    return (confirmed + 1) / (tested + 2)


def bind_distribution(fails_kind: int, attempts_kind: int, f1: int, n_area: int,
                      family_counts: dict[str, int]) -> dict[str, float]:
    """Categorical outcome of executing an unbound affordance (§5.2 D).

    FAIL from the interaction kind's run-local failure rate; NEW from the
    smoothed Good–Turing estimate for the area; the remaining mass is shared
    by each signature already seen in the family plus NO_EFFECT, in proportion
    to count + 0.5.
    """
    p_fail = (fails_kind + 1) / (attempts_kind + 2)
    p_new = (1 - p_fail) * (f1 + 1) / (n_area + 2)
    rest = max(0.0, 1 - p_fail - p_new)
    seen = dict(family_counts)
    seen.setdefault("NO_EFFECT", 0)
    total = sum(c + 0.5 for c in seen.values())
    out = {"FAIL": p_fail, "NEW": p_new}
    for sig, c in sorted(seen.items()):
        out[sig] = rest * (c + 0.5) / total
    return out


def cost(restore: float, actions: float, oracle: float, p_fail: float) -> float:
    return (restore + actions + oracle) / max(1e-6, 1 - p_fail)
