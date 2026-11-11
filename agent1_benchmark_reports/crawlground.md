# crawlground

**Track A · reference: third-party testbed marker scoring · regime: comprehensive**

## Input — what the app is
A **crawler testbed whose capabilities are interaction-gated**: a server-side marker is set only when a
specific input/interaction sequence is performed. Scored by the testbed's own marker endpoint.

## What Agent 1 produced
Graph A: **29 states, 98 action-evidences, 39 workflows, 35 features, 5193 edges, 4927 advertised-unexecuted,
8 record instances.** 92 controls observed, 90 executed. Capabilities observed: **22**, unidentified 1.
Efficiency: 332 actions, 173 s, 110 restoration, 126 root reloads, **59 failed actions**; replays 27/26
(1 failure); **197 dangerous controls skipped**.

## Accuracy
- **Testbed marker recall ≈ 0.068** — the lowest accuracy number in the suite.
- **Why:** markers require **specific interaction sequences** (exact inputs, ordered steps) that the
  heuristic explorer does not synthesize; it executed 90 controls but **59 attempts failed** to satisfy the
  gating. This is a genuine capability gap (input-sequence synthesis), not a bug.
- Safety still held strongly: **197 dangerous controls skipped, 0 destructive**.

## Verdict
**The clearest "what we're missing" fixture.** Interaction-gated markers expose that Agent 1 maps
*affordances* well but does not *solve* input sequences. A frontier for future work (not restoration or
breadth). Safety is unaffected.
