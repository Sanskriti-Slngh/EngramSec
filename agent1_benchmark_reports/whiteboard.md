# whiteboard

**Track A · reference: identity (templates/entities only; capabilities not annotated) · regime: comprehensive**

## Input — what the app is
An **authenticated collaborative whiteboard** (the user's own application), exercised **anonymous-only** —
so most functionality sits behind a login the run did not cross.

## What Agent 1 produced
Graph A: **2 states, 4 action-evidences, 4 workflows, 2 features, 39 edges, 23 advertised-unexecuted.**
Capabilities observed: **2** (1 reproduced, 1 observed), unidentified 1. Efficiency: 15 actions, 8.7 s,
caps/min 13.8; replays 2/2 validated; 0 state-changing.

## Accuracy
Capabilities are **not annotated** (reference is templates/entities only), so no recall %. The honest
reading: **anonymous access exposes almost nothing** (2 capabilities), which is *correct behavior* — the
app is auth-gated and the run was unauthenticated. The 23 advertised-unexecuted controls are the login-
gated surface.

## Verdict
**Correct but shallow because unauthenticated.** Not a coverage benchmark; it confirms Agent 1 maps the
public surface and stops at the auth wall. An authenticated run would be needed to say anything about the
app's real functionality.
