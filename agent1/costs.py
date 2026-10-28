from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class BudgetError(RuntimeError):
    pass


class SpendingLedger:
    """Persistent conservative reservations for paid calls.

    The ledger is provider-agnostic. Callers reserve the maximum possible charge
    before a request, then commit the actual charge or release the reservation.
    """

    def __init__(self, path: Path, *, budget_usd: float = 20.0, stop_usd: float = 18.0):
        if budget_usd > 20 or stop_usd > 18 or stop_usd > budget_usd:
            raise ValueError("budget must stay within the task's $20/$18 limits")
        self.path = path
        self.budget_usd = round(budget_usd, 6)
        self.stop_usd = round(stop_usd, 6)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"spent_usd": 0.0, "reservations": {}})

    @contextmanager
    def _locked(self) -> Iterator[dict]:
        import fcntl

        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            data = json.loads(self.path.read_text(encoding="utf-8"))
            yield data
            self._write(data)
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _write(self, data: dict) -> None:
        fd, temporary = tempfile.mkstemp(prefix=self.path.name, dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def snapshot(self) -> dict:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        reserved = round(sum(float(v) for v in data["reservations"].values()), 6)
        return {
            "spent_usd": round(float(data["spent_usd"]), 6),
            "reserved_usd": reserved,
            "remaining_to_stop_usd": round(self.stop_usd - float(data["spent_usd"]) - reserved, 6),
            "outstanding_requests": len(data["reservations"]),
        }

    def reserve(self, request_id: str, maximum_charge_usd: float) -> None:
        if maximum_charge_usd <= 0:
            raise ValueError("reservation must be positive")
        with self._locked() as data:
            if request_id in data["reservations"]:
                raise BudgetError("request already reserved")
            total = float(data["spent_usd"]) + sum(float(v) for v in data["reservations"].values())
            if total + maximum_charge_usd > self.stop_usd:
                raise BudgetError("reservation would cross the $18 paid-call stop")
            if total + maximum_charge_usd > self.budget_usd:
                raise BudgetError("reservation would exceed the overall budget")
            data["reservations"][request_id] = round(maximum_charge_usd, 6)

    def commit(self, request_id: str, actual_charge_usd: float) -> None:
        if actual_charge_usd < 0:
            raise ValueError("actual charge cannot be negative")
        with self._locked() as data:
            maximum = data["reservations"].pop(request_id, None)
            if maximum is None:
                raise BudgetError("request was not reserved")
            if actual_charge_usd > float(maximum) + 1e-9:
                raise BudgetError("actual charge exceeds conservative reservation")
            data["spent_usd"] = round(float(data["spent_usd"]) + actual_charge_usd, 6)

    def release(self, request_id: str) -> None:
        with self._locked() as data:
            if data["reservations"].pop(request_id, None) is None:
                raise BudgetError("request was not reserved")
