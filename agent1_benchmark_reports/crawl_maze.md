# crawl_maze

**Track A · reference: third-party testbed expected-path endpoint · regime: comprehensive**

## Input — what the app is
A **crawler testbed** (link / JS / HTML discovery traps) with its **own expected-path endpoint** queried
after the run — a semi-independent reference.

## What Agent 1 produced
Graph A: **64 states, 65 action-evidences, 65 workflows, 64 features, 779 edges, 456 advertised-unexecuted.**
Capabilities observed: **65** (34 reproduced, 31 observed), unidentified 31. Efficiency: 368 actions, 182 s,
125 restoration, 100 root reloads, **0 redundant / 65 unique-discovery**, **caps/min 21.5, caps/100act 17.7**
(both the highest of any fixture); replays 34/34 validated; **24 dangerous controls skipped**.

## Accuracy
Reference is the testbed's own path list. The standout is **throughput with zero redundancy**: 65 distinct
capabilities, 0 redundant actions, highest caps/min — excellent on plain link/HTML discovery, which is
Agent 1's core strength. 31 "observed-not-reproduced" caps are seen but not yet replay-confirmed. Safety
held (24 dangerous skipped, 0 destructive).

## Verdict
**Best-in-class on pure crawl/discovery.** Where structure is plain links/HTML, Agent 1 is fast, broad, and
non-redundant. (JS/interaction-gated nodes are where testbeds like crawlground expose the gap.)
