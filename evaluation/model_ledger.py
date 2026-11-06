"""Persistent spend ledger for paid model calls in the model & scaling experiment.

Hard cap: $10.00 total across every paid call of the experiment, retries included.
Before each call a worst-case cost is reserved (input estimate and the full output limit, at
1.5x the list price); a call that could cross the cap is refused. After the call the actual
billed usage is recorded. API keys are read from .env inside the process and never printed.

Prices verified 2026-11-06 from developers.openai.com (gpt-5.4-mini: $0.75 / 1M input,
$4.50 / 1M output).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from evaluation.comprehensive_config import ROOT

CAP_USD = 10.00
SAFETY = 1.5
PRICES = {"gpt-5.4-mini": (0.75e-6, 4.50e-6)}           # (input, output) USD per token
LEDGER = ROOT / "agent1" / "experiments" / "model_scaling" / "spend_ledger.json"


class BudgetExceeded(RuntimeError):
    pass


def _load() -> dict[str, Any]:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"cap_usd": CAP_USD, "spent_usd": 0.0, "calls": 0, "refused": 0, "failed_calls": 0, "entries": []}


def _save(state: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(LEDGER)


def spent() -> float:
    return _load()["spent_usd"]


def _key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("OPENAI_API_KEY not configured")


def openai_json(model: str, prompt: str, purpose: str, max_output_tokens: int = 600,
                retries: int = 1) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """One JSON-mode chat call under the ledger. Returns (parsed JSON or None, usage meta)."""
    pin, pout = PRICES[model]
    est_in = len(prompt) / 3                               # conservative chars-per-token
    reserve = SAFETY * (est_in * pin + max_output_tokens * pout)
    last_meta: dict[str, Any] = {}
    for attempt in range(retries + 1):
        state = _load()
        if state["spent_usd"] + reserve > CAP_USD:
            state["refused"] += 1
            _save(state)
            raise BudgetExceeded(f"cap ${CAP_USD:.2f} would be exceeded (spent ${state['spent_usd']:.4f})")
        body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                           "response_format": {"type": "json_object"},
                           "max_completion_tokens": max_output_tokens, "reasoning_effort": "low"}).encode()
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body, headers={
            "Authorization": f"Bearer {_key()}", "Content-Type": "application/json"})
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError) as exc:
            # A failed request may still be billed; charge the full reservation to stay conservative.
            state = _load()
            state["spent_usd"] = round(state["spent_usd"] + reserve, 6)
            state["calls"] += 1
            state["failed_calls"] += 1
            state["entries"].append({"purpose": purpose, "attempt": attempt, "error": type(exc).__name__,
                                     "charged_usd": round(reserve, 6)})
            _save(state)
            last_meta = {"error": type(exc).__name__, "latency_s": round(time.monotonic() - t0, 2)}
            continue
        usage = data.get("usage") or {}
        tin, tout = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        cost = tin * pin + tout * pout
        state = _load()
        state["spent_usd"] = round(state["spent_usd"] + cost, 6)
        state["calls"] += 1
        state["entries"].append({"purpose": purpose, "attempt": attempt, "input_tokens": tin,
                                 "output_tokens": tout, "cost_usd": round(cost, 6)})
        _save(state)
        meta = {"latency_s": round(time.monotonic() - t0, 2), "input_tokens": tin, "output_tokens": tout,
                "cost_usd": round(cost, 6)}
        try:
            return json.loads(data["choices"][0]["message"]["content"] or ""), meta
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            return None, meta
    return None, last_meta
