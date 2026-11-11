# orchard (held-out variant)

**Track A · reference: EXACT built-in ground truth · regime: research (Stage 1/2) · HELD OUT**

## Input — what the app is
A second **held-out variant** of `breadth_starved_lab` with yet another shape: hubs `yields` (4×2),
`policies` (2×2), `jobs` (3×1), different section names, nav order, and release positions. GET-only, no
auth/write/JS/destructive. Ground truth: **48 capabilities = 18 shallow + 30 deep (24 template-distinct +
6 semantic-only).**

## What Agent 1 produced & accuracy (exact, deterministic, 3 trials, 140 s)
| arm | executed | deep | template-distinct | **semantic** | restoration wall | caps/min | request-AUC |
|---|---|---|---|---|---|---|---|
| frozen baseline (A) | **28/48** | 10/30 | 10/24 | **0/6** | 86.3 s | 12.0 | 0.37 |
| + eager_child_expansion (B) | **31/48** | 13/30 | 13/24 | **0/6** | **71.1 s (−18%)** | **13.2** | **0.40** |

- **Accuracy:** all executed capabilities are true; misses are template-distinct deep (restoration/budget)
  plus the **6 semantic release changelogs (0/6 on every arm)**. 0 rejected restorations, replays
  preserved, txfail 0, state-changing 0 on both arms.

## Verdict
**Second independent confirmation.** Consistent +3 deep caps and ~18% less restoration wall-time with no
safety regression — the restoration saver generalizes; the semantic gap is unchanged (as expected).
