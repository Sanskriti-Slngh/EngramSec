# replay_lab

**Track A · reference: capability (annotated) · regime: comprehensive (read-only)**

## Input — what the app is
A larger catalog/search/records app with **equivalent interfaces** (several routes that reach the same
capability) and a multi-step **wizard** plus a few write/destructive operations.

## What Agent 1 produced
Graph A: **19 states, 43 action-evidences, 42 workflows, 31 features, 787 edges, 594 advertised-unexecuted,
1 record instance.** Capabilities observed: **22** (20 reproduced, 2 observed), unidentified 7. Efficiency:
172 actions, 83 s, 31 restoration, 68 root reloads, 18 redundant, caps/min 15.8; replays 24 attempted,
**22 validated, 2 failed**.

## Accuracy
- **Annotation recall 0.68, precision 0.77** — the best-recall annotated fixture. Precision < 1 because a
  few claimed interfaces map to the same annotated capability (the "equivalent interfaces" trap).
- **Missed (all trials, 8):** `wizard_begin/continue/finish`, `save_item`, `wipe_records` (writes/wizard),
  `load_details`, `reveal_details`, `check_loans_second` — 3 × not-safety-limited, 5 × no-control.
- **Why:** the **wizard and save/wipe are write-gated** (unreachable read-only); `load/reveal_details` are
  interaction-constructed. 2 replay failures are logged (not silently accepted).

## Verdict
**Good and honest.** High recall for a read-only run, precision slightly reduced by genuinely equivalent
interfaces (a labeling nuance, not a false claim), misses concentrated in writes + JS detail panels.
