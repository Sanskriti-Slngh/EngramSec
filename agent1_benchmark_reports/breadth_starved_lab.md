# breadth_starved_lab

**Track A · reference: EXACT built-in ground truth · regime: research (Stage 0/1/2, disposable GET)**

## Input — what the app is
A purpose-built **GET-only** fixture (no auth/write/JS/destructive) with **6 breadth sections** (uniform
catalogs of 80 items each), **3 functional hubs** 2–3 levels deep (`/reports`, `/settings`, `/ops`), and
one **structurally-ambiguous list** (`/updates`) where 6 of 40 items are "releases" with a deeper
changelog — distinguishable only by the item's **content** ("Release N" vs "Note N"), not by template.
Every capability is reachable by a plain GET, so **any miss is attributable to exploration prioritization**.
Ground truth: **50 capabilities = 18 shallow + 32 deep (26 template-distinct + 6 semantic-only).**

## What Agent 1 produced & accuracy (exact, deterministic, 3 trials, 140 s)
| arm | executed | deep | template-distinct | **semantic** | restoration wall | caps/min |
|---|---|---|---|---|---|---|
| frozen baseline (A) | **30/50** | 12/32 | 12/26 | **0/6** | ~85 s | 12.4 |
| + eager_child_expansion (Stage-2 B) | **34/50** | 16/32 | 16/26 | **0/6** | **67 s (−21%)** | **14.5** |

- **Accurate where it executes:** every executed capability is a true capability (server-recorded), and
  all misses are *stranded* (parent reached), **0 undiscovered, 0 auth/write/JS/safety blocked, 0
  state-changing**. Precision is effectively perfect on this GET fixture.
- **What it misses:** the **6 semantic-only release changelogs (0/6 on every arm)** — reaching them needs
  content distinction ("Release" ≠ "Note"), which the structural explorer lacks; and the remaining
  template-distinct deep caps lost to **restoration cost + budget** (improved, not closed, by Stage 2).

## Verdict
**The cleanest accuracy picture in the suite.** Coverage is exact and honest: 68% of capabilities (34/50)
under the Stage-2 arm, misses are restoration-bound (improving) and semantic (reserved for a content-token
rule). No safety or precision issues.
