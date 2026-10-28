# EngramSec Agent 1 plan

Updated: 2026-10-28

## Goal and evidence bar

Build a website-only mapper that records browser-observed states and actions, exports an evidence-backed Graph A, and replay-validates complete navigation paths. A feature is counted only when its path replays and its observable outcome matches. URL/form counts remain structural diagnostics, not functional coverage.

## Scope decisions after comparative review

- Use Playwright with one browser worker and an allowlisted origin.
- Use an event/state-flow archive inspired by Crawljax, plus saved return paths inspired by Go-Explore. Do not train an RL policy.
- Keep raw observations and conservative, reversible groups. Group only when route shape, visible control/form structure, and explicit session context agree.
- Treat every observed control as advertised, every executed browser transition as observed, and only full fresh-context replays as replay-validated.
- Use deterministic exploration first. Let a local/free model rank ambiguous controls or improve labels only after the model-free pipeline works.
- Preserve `engramsec_v0` HTTP BFS and hybrid unchanged as historical structural baselines.
- Select Crawljax as the established external state-flow baseline in the review. Java 17 was installed, but the official CLI archive was about 987 MB and Maven was absent, so a runnable Crawlee/Playwright baseline was added instead. Do not claim a Crawljax comparison.

## Work sequence

1. Preflight: repository, branch, target URL, browser, Docker, models, ignored credentials, dependencies.
2. Implement the smallest live slice: observe → choose current control → execute → evidence → Graph A → fresh replay.
3. Add conservative grouping, archived return paths, checkpoint/resume, network summaries, and Graph A diagram export.
4. Add secure provider interfaces, decision cache, and a paid-call ledger. Keep paid calls disabled.
5. Test evidence invariants, false merges, session separation, replay prerequisites, budget enforcement, and resume.
6. Run fixture smoke/ablation experiments, then matched SiyuCMS runs. Preserve every result.
7. Attempt Crawljax external baseline; otherwise record the setup failure and run the narrower Crawlee baseline without equating the two.
8. Audit feature descriptions and grouping decisions from stored evidence, iterate one factor at a time, and write `MORNING_REPORT.md`.

## Stop conditions

Stop after a working tested pipeline and report, six hours, a usage/cost limit, or a genuine blocker. External API spend remains $0 unless the separately tested ledger and explicit provider checks make a paid call safe; paid calls stop at $18 regardless of the $20 overall cap.

## Final status

Implementation, fixture/browser tests, matched short runs, one matched 10-minute ablation, the Crawlee baseline, evidence audit, and the handoff report are complete. The six-hour boundary was reached while final verification was being recorded; no further long experiment was started.
