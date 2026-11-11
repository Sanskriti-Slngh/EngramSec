# comfyui

**Track B · real app · reference: NONE · NOT MEASURABLE**

## Input — what the app is
**ComfyUI** — a canvas/graph ML UI (Python backend, **WebSocket**, heavy client-side canvas). Mapped blind
once (2026-10-28), evaluation-only.

## What Agent 1 produced
Graph A: **11 states, 10 action-evidences, 0 workflows, 0 features, 162 edges, 157 advertised-unexecuted.**
Efficiency: 11 actions, 11.5 s. caps/min 0.0.

## Accuracy
**NOT MEASURABLE.** The informative detail is the **0 workflows / 0 features**: ComfyUI's functionality
lives almost entirely on a **JS canvas driven over WebSocket**, which the DOM-snapshot heuristic explorer
cannot enumerate as discrete controls. This mirrors the js_heavy_lab / client-rendered gap — on a
canvas/WS app it is especially severe.

## Verdict
**Essentially unmapped by design of the app.** A concrete, real-world instance of the SPA/canvas capability
gap (architecture §7.2). No coverage claim; the result argues for canvas/WS-aware exploration before Track-B
UIs like this are meaningful.
