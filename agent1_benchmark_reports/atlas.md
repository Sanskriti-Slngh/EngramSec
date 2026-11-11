# atlas (held-out variant)

**Track A · reference: EXACT built-in ground truth · regime: research (Stage 1/2) · HELD OUT**

## Input — what the app is
A **held-out variant** of `breadth_starved_lab`, built with different section names, hub names/arity/depth
(`ledgers` 3×2, `controls` 4×1, `pipelines` 2×1), nav order, and release positions, so no policy can tune
to the original instance. GET-only, no auth/write/JS/destructive. Ground truth: **44 capabilities = 18
shallow + 26 deep (21 template-distinct + 5 semantic-only).**

## What Agent 1 produced & accuracy (exact, deterministic, 3 trials, 140 s)
| arm | executed | deep | template-distinct | **semantic** | restoration wall | caps/min | request-AUC |
|---|---|---|---|---|---|---|---|
| frozen baseline (A) | **31/44** | 13/26 | 13/21 | **0/5** | 87.1 s | 13.1 | 0.46 |
| + eager_child_expansion (B) | **33/44** | 15/26 | 15/21 | **0/5** | **67.3 s (−23%)** | **14.0** | **0.50** |

- **Accuracy:** executed capabilities are all true; misses are template-distinct deep caps (restoration/
  budget-bound) plus the **5 semantic release changelogs (0/5 on every arm)**. 0 rejected restorations,
  replays preserved, txfail 0, state-changing 0 on both arms.

## Verdict
**Confirms the breadth_starved result transfers to an unseen shape.** Eager expansion adds +2 deep caps and
cuts restoration wall-time ~23% with no safety cost; the semantic slice remains the reserved gap.
