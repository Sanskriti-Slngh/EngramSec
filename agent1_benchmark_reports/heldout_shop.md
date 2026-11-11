# heldout_shop

**Track A · reference: author surface truth (no recall number) · regime: comprehensive + Stage-2 transfer**

## Input — what the app is
A **small e-commerce** site (catalog, product pages, cart-ish flows). Originally a held-out validation
fixture; now a development surface (per the summary, "formerly validation; not held out").

## What Agent 1 produced
Graph A: **16 states, 75 action-evidences, 75 workflows, 34 features, 1299 edges, 971 advertised-unexecuted,
2 record instances.** Capabilities observed: **17** (10 reproduced, 7 observed), unidentified 8. Efficiency:
313 actions, 152 s, **112 restoration, 94 root reloads, 59 redundant**, caps/min 6.7; replays 18/18 validated;
0 state-changing.

## Accuracy
No recall % (surface reference). Clean reproducibility (18/18). **59 redundant actions** is the highest of
the surface fixtures — some breadth re-enumeration remains here. Used as a **Stage-2 transfer/safety
target**: eager on batched 2 GET children, replays unchanged (16), **0 destructive, state-changing
unchanged (2)** — i.e. the saver transfers safely to an independent e-commerce app.

## Verdict
**Solid inventory, reproducible, and Stage-2-safe.** The redundant-action count is the main efficiency
note; coverage % is not claimable (surface reference).
