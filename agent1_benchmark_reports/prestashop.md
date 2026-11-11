# prestashop

**Track B · real app · reference: NONE · NOT MEASURABLE**

## Input — what the app is
**PrestaShop** — a production PHP e-commerce CMS. Mapped **blind once** (2026-10-28), evaluation-only.

## What Agent 1 produced
Graph A: **1 state, 15 action-evidences, 14 workflows, 0 features, 2698 edges, 2655 advertised-unexecuted.**
Efficiency: 32 actions, 19 s, 17 root reloads, 13 redundant. caps/min reported 0.0.

## Accuracy
**NOT MEASURABLE** — no capability ground truth, so no coverage % can be claimed; counts are inventories.
The run was **short and shallow (1 state, ~19 s)**: it hit a login/redirect boundary early, so the 14
workflows are mostly the public storefront surface. This is **not** evidence of good or bad coverage — only
that Agent 1 ran in scope and safely against a real PHP stack.

## Verdict
**Inventory only.** Honest reading: Agent 1 reached the storefront entry and stopped at the auth/redirect
wall; nothing about PrestaShop's true functional coverage can be asserted.
