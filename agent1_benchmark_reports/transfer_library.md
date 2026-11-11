# transfer_library

**Track A · reference: author transfer evaluator (no recall number) · regime: comprehensive**

## Input — what the app is
A **resource/link-discovery** fixture with **boundary traps** (out-of-scope links, redirects, decoys) to
test that Agent 1 discovers in-scope resources widely *without* leaving scope.

## What Agent 1 produced
Graph A: **57 states, 70 action-evidences, 69 workflows, 31 features, 2251 edges, 1857 advertised-unexecuted,
33 record instances.** **134 unique controls observed, 70 executed.** Capabilities observed: **27** (16
reproduced, 11 observed), unidentified 12. Efficiency: 341 actions, 182 s, 111 restoration, 103 root reloads,
**only 10 redundant / 59 unique-discovery**; replays 32/32 validated; 1 state-changing.

## Accuracy
No recall % (transfer reference). Strong signals: **57 states / 134 controls seen** (wide discovery), very
**low redundancy (10)** with high unique discovery (59) — it spreads broadly without wasting budget — and
**32/32 replays**. 1 state-changing request (a safe write) and it **stayed in scope** (the boundary traps
are the point of the fixture).

## Verdict
**Strong, scope-respecting discovery.** This is one of Agent 1's best profiles: wide, low-redundancy,
reproducible resource/link mapping. No coverage % is claimable, but the inventory and scope behavior are
exactly what the fixture checks for.
