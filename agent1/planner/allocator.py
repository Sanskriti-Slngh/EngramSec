"""L3 area allocator (§5.1): deterministic discounted UCB with floors and caps."""
from __future__ import annotations

import math
from collections import deque

from .constants import AREA_CAP, AREA_FLOOR, CLASS_FLOORS, DUCB_C, DUCB_GAMMA, WINDOW


class Allocator:
    def __init__(self) -> None:
        self.n: dict[str, float] = {}
        self.s: dict[str, float] = {}
        self.chosen: set[str] = set()
        self.recent: deque[tuple[str, str]] = deque(maxlen=WINDOW)    # (area, question class)
        self.max_yield = 0.0

    def reward(self, area: str, bits: float, actions: int) -> None:
        """Discount every area once per decision, then credit the decided area."""
        for a in self.n:
            self.n[a] *= DUCB_GAMMA
            self.s[a] *= DUCB_GAMMA
        y = bits / max(1, actions)
        self.max_yield = max(self.max_yield, y)
        self.n[area] = self.n.get(area, 0.0) + 1.0
        self.s[area] = self.s.get(area, 0.0) + (y / self.max_yield if self.max_yield > 0 else 0.0)

    def note(self, area: str, qclass: str) -> None:
        self.chosen.add(area)
        self.recent.append((area, qclass))

    def _count(self, *, area: str | None = None, qclass: str | None = None) -> int:
        return sum(1 for a, c in self.recent if (area is None or a == area) and (qclass is None or c == qclass))

    def starved_classes(self, open_classes: set[str], observed_caps: int, saturated: bool) -> list[str]:
        out = []
        for qclass, floor in CLASS_FLOORS.items():
            if qclass not in open_classes:
                continue
            if qclass == "discovery" and saturated:
                continue
            if qclass == "verification" and observed_caps < 3:
                continue
            if self._count(qclass=qclass) < floor * len(self.recent):
                out.append(qclass)
        return out

    def starving_areas(self, discovery_areas: set[str]) -> list[str]:
        return sorted((a for a in discovery_areas if self._count(area=a) < AREA_FLOOR * len(self.recent)),
                      key=lambda a: (self._count(area=a), a))

    def ranked(self, areas: set[str]) -> list[str]:
        """Areas by discounted UCB, never-chosen first, capped areas last; ties by area id."""
        total = sum(self.n.values())

        def ucb(a: str) -> float:
            n = self.n.get(a, 0.0)
            if a not in self.chosen or n <= 0:
                return math.inf
            return self.s.get(a, 0.0) / n + DUCB_C * math.sqrt(max(0.0, math.log(max(total, 1.0))) / n)
        capped = {a for a in areas if self._count(area=a) > AREA_CAP * WINDOW}
        return sorted(areas, key=lambda a: (a in capped, -ucb(a), a))
