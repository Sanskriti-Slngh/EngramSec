# js_heavy_lab

**Track A · reference: capability (annotated) · regime: comprehensive (read-only)**

## Input — what the app is
A **client-rendered SPA** with two roles, where much of the functionality (workspaces, reports,
preferences, a member mode, a multi-step setup) is constructed by JavaScript at runtime rather than served
as plain links.

## What Agent 1 produced
Graph A: **3 states, 9 action-evidences, 9 workflows, 6 features, 101 edges, 62 advertised-unexecuted.**
Capabilities observed: **3** (all `reproduced`). Efficiency: 31 actions, 15 s, 6 restoration, 13 root
reloads, caps/min 12.0; replays 3/3 validated.

## Accuracy
- **Annotation recall 0.21, precision 1.00.** What it found reproduces; it found little.
- **Missed (all trials, 11):** `open_workspace`, `workspace_detail`, `open_reports`, `load_late_reports`,
  `open_workflow`, `continue_setup`, `enter_member_mode`, `member_preferences`, `load_preferences`,
  `alias_area`, `alias_data` — **10 × no-matching-advertised-control**, 1 × scope refusal.
- **Why:** "no matching advertised control" = the control **does not exist in the DOM snapshot** the
  explorer sees, because it is built by JS after load / behind client-side interactions. The heuristic
  explorer does not drive SPA-constructed controls.

## Verdict
**Accurate on what it can see, but recall is capped by a real capability gap: client-rendered UI.** This is
one of the top two open problems for Agent 1 (see architecture §7). No safety issues.
