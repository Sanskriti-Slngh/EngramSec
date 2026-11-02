"""All tunable planner constants (EXPLORATION_PLANNER_DESIGN.md §5.2 table I).

No other constants influence a decision. Changing any of these values
invalidates the T2 preregistration.
"""
from __future__ import annotations

DUCB_GAMMA = 0.9                 # discounted UCB discount per decision
DUCB_C = 1.0                     # exploration coefficient
CLASS_FLOORS = {"discovery": 0.40, "verification": 0.20}
VERIFICATION_FLOOR_MIN_OBSERVED = 3   # verification floor applies once >= 3 capabilities are OBSERVED
AREA_FLOOR = 0.05                # each area with open discovery questions
AREA_CAP = 0.40
WINDOW = 50                      # floor/cap window (decisions)
LAMBDA_UNLOCK = 1.0
CHANNELS = {                     # (sensitivity s, false-positive rate f); None = 1 - eps_env (or its square)
    "reproduce": (None, 0.05),
    "differential": (0.95, 0.05),
    "cross_view": (0.90, 0.05),
    "inverse": (0.90, 0.10),
    "dependency": ("squared", 0.05),
    "equivalence": (None, 0.05),
    "split": (None, 0.05),
    "availability": (0.70, 0.20),
}
EPS_ENV_INITIAL = 0.10
MAX_INCONCLUSIVE = 2
SAMPLE_INSTANCE_K = 3
SATURATION_P_NEW = 0.05
SATURATION_MIN_N = 10
SATURATION_VALUE_FRACTION = 0.10
AGENDA_CAP_PER_AREA = 200

QUESTION_CLASS = {
    "bind_affordance": "discovery", "find_entry_point": "discovery", "sample_instance": "discovery",
    "reproduce": "verification", "verify_effect": "verification",
    "test_dependency": "structure", "test_equivalence": "structure", "split_test": "structure",
}
