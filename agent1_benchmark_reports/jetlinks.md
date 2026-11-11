# jetlinks

**Track B · real app · reference: NONE · NOT MEASURABLE**

## Input — what the app is
**JetLinks** — a Java IoT platform with a **SPA** front end. **Never built or run before this evaluation**
(the cleanest blind target), evaluation-only.

## What Agent 1 produced
Graph A: **1 state, 0 action-evidences, 0 workflows, 0 features, 0 edges.** Efficiency: **1 action, 1.1 s.**

## Accuracy
**NOT MEASURABLE — and effectively blocked.** The run did essentially nothing: **1 action, 1 state, no
edges.** A Java SPA typically renders nothing actionable in the initial DOM (and often gates behind a login
the blind run cannot cross), so the explorer found no controls to drive.

## Verdict
**A hard negative worth keeping.** JetLinks is the clearest case where the current DOM-snapshot approach +
auth wall yields **zero** on a real SPA — a baseline the SPA/auth work (architecture §7.2, §7.6) must beat.
No coverage claim is possible or implied.
