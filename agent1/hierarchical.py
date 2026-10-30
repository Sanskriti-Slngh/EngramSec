"""Area-tour scheduling over observed paths; it never merges browser states."""
from __future__ import annotations

from itertools import permutations
from urllib.parse import urlsplit

from .schema import FrontierItem, Observation
from .state import digest


def area_key(observation: Observation) -> tuple[str, str]:
    """A scheduling area only: exact states and record identities remain intact."""
    route = urlsplit(observation.url).path or "/"
    segments = [segment for segment in route.split("/") if segment]
    area = "/" + segments[0] if segments else "/"
    context = digest([observation.session_context, observation.session_markers], 16)
    return context, area


def _signatures(item: FrontierItem) -> tuple[str, ...]:
    return tuple(step.signature for step in item.path)


def _distance(a: tuple[str, ...], b: tuple[str, ...], prefix_reuse: bool = False) -> int:
    """Estimated browser actions to move from live path ``a`` to source path ``b``.

    This mirrors the executor: there is no free "walk back up" the tree. Without
    prefix reuse every move is a root reload plus the full return path; with it,
    a descendant of the live state costs only the remaining suffix. The executor
    still verifies every restored state.
    """
    if a == b:
        return 0
    if prefix_reuse and b[:len(a)] == a:
        return len(b) - len(a)
    if prefix_reuse and a and b[:len(a) - 1] == a[:-1]:
        return 1 + len(b) - (len(a) - 1)  # one verified history step to the parent
    return 1 + len(b)


class AreaTourPlanner:
    """Plan a bounded multi-area tour, then exhaust a local area before switching."""

    def __init__(self, prefix_reuse: bool = False, area_action_limit: int = 8) -> None:
        self.prefix_reuse = prefix_reuse
        self.area_action_limit = area_action_limit
        self.tour: list[tuple[str, str]] = []
        self.last_area: tuple[str, str] | None = None
        self.area_actions = 0

    def choose(self, frontier: list[FrontierItem], observations: dict[str, Observation],
               live: Observation, live_path: list) -> int:
        groups: dict[tuple[str, str], list[int]] = {}
        for i, item in enumerate(frontier):
            source = observations.get(item.source_observation_id)
            if source is not None:
                groups.setdefault(area_key(source), []).append(i)
        if not groups:
            return 0
        self.tour = [area for area in self.tour if area in groups]
        if self.tour and self.tour[0] == self.last_area and self.area_actions >= self.area_action_limit:
            self.tour.append(self.tour.pop(0))
            self.area_actions = 0
        current = area_key(live)
        if not self.tour:
            # Bound planning cost, reserve deterministic order for the rest;
            # all pending areas eventually enter a later tour.
            representatives = {
                area: min((_signatures(frontier[i]) for i in indexes), key=lambda p: (len(p), p))
                for area, indexes in groups.items()
            }
            live_signatures = tuple(step.signature for step in live_path)
            ordered = sorted(groups, key=lambda a: (_distance(live_signatures, representatives[a], self.prefix_reuse), a))
            window = ordered[:5]
            best = min(
                permutations(window),
                key=lambda tour: (
                    _distance(live_signatures, representatives[tour[0]], self.prefix_reuse)
                    + sum(_distance(representatives[x], representatives[y], self.prefix_reuse) for x, y in zip(tour, tour[1:])),
                    tour,
                ),
            )
            self.tour = list(best) + ordered[5:]
            if current in groups:
                self.tour.remove(current)
                self.tour.insert(0, current)
        area = self.tour[0]
        self.area_actions = self.area_actions + 1 if area == self.last_area else 1
        self.last_area = area
        indexes = groups[area]
        live_signatures = tuple(step.signature for step in live_path)
        return min(indexes, key=lambda i: (
            frontier[i].expected_source_group != live.group_signature,
            _distance(live_signatures, _signatures(frontier[i]), self.prefix_reuse),
            -frontier[i].priority, frontier[i].action.signature,
        ))
