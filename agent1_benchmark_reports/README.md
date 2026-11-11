# Agent 1 — per-benchmark reports

Written for: the EngramSec team. One report per benchmark: **what the input app is**, **what Agent 1
produced** (Graph A / ACG), and **whether it is accurate**. Read alongside
[`../AGENT1_ARCHITECTURE_AND_STATUS.md`](../AGENT1_ARCHITECTURE_AND_STATUS.md).

## How to read accuracy here

- **Track A (development fixtures)** have author-curated references, so some have **annotation
  recall/precision** — recall = fraction of *annotated* capabilities Agent 1 executed; precision = fraction
  of Agent 1's claims that match an annotated capability. These are *annotation-based*, **not independently
  established ground truth** (the summary says so itself), and ACG "roles" are cookie-session contexts.
- Fixtures with a **surface / server-state / none** reference have **no recall number** — we report an
  **inventory** (states/actions/workflows/capabilities) and reproducibility, not a coverage %.
- **Track B (real apps)** are **NOT MEASURABLE**: without capability ground truth, no coverage % can be
  claimed. Counts are inventories only.
- Two config regimes: the 17-environment **comprehensive sweep is read-only** (`allow_post_forms=false`),
  so *write* capabilities are structurally unreachable there; the **Stage 0/1/2** fixtures use a
  disposable-write, extended config with exact built-in ground truth.

## Index

**Track A — annotated (recall/precision available)**
- [stateful_lab](stateful_lab.md) — CRUD + destructive · recall 0.29
- [js_heavy_lab](js_heavy_lab.md) — client SPA · recall 0.21
- [replay_lab](replay_lab.md) — catalog/search/records · recall 0.68

**Track A — surface / server-state / contract (inventory + reproducibility)**
- [phase2_lab](phase2_lab.md) · [coverage_lab](coverage_lab.md) · [heldout_shop](heldout_shop.md)
- [transfer_library](transfer_library.md) · [restoration_lab](restoration_lab.md) · [hybrid_lab](hybrid_lab.md)
- [crawl_maze](crawl_maze.md) · [crawlground](crawlground.md) · [whiteboard](whiteboard.md)

**Track A — purpose-built GET benchmarks (exact ground truth, Stage 0/1/2)**
- [breadth_starved_lab](breadth_starved_lab.md) · [atlas](atlas.md) · [orchard](orchard.md)

**Track B — real apps (NOT MEASURABLE; inventories only)**
- [prestashop](prestashop.md) · [comfyui](comfyui.md) · [siyucms](siyucms.md) · [jetlinks](jetlinks.md) · [white-jotter](white-jotter.md)
