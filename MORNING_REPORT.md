# EngramSec Agent 1 morning report

Date: 2026-10-28

## Outcome

Agent 1 is a working website-only Playwright mapper. It observes current controls, executes only registered safe controls on an explicitly configured loopback origin, records source/action/input-reference/result/network evidence, builds three-level Graph A output, archives return paths, checkpoints its frontier, and replay-validates complete workflows in fresh browser contexts. It does not inspect target source, verifier internals, exploit reports, or vulnerability answers.

The current SiyuCMS target is `http://127.0.0.1:51707/`. The browser smoke test succeeded with HTTP 200, title `SIYUCMS 官网`, 113 links, and a real navigation to `/index/user/login`. The Docker web container was available on port 51707 and its database container was healthy.

The strongest audited live result is 16 distinct replay-validated feature workflows in 10 minutes, with 77/77 replayed edges succeeding, for both exact-state and grouped-frontier policies. This is not evidence that grouping improves coverage. It is evidence that the browser/evidence/replay pipeline works on this target under anonymous access.

## What was implemented

- One configurable `agent1` package and CLI; no disconnected version directories.
- Chromium interaction for JavaScript navigation, links, buttons, forms, downloads, dialogs, and normal workflows.
- Stable observed control IDs, current-observation validation, loopback/same-origin guards, dangerous-action filtering, and POST disabled by default.
- Raw observations plus conservative reversible groups based on route shape, visible control/form shape, and explicit session context.
- Evidence statuses for advertised, observed, replay-validated, failed, and unresolved connections.
- Fresh-context replay of all prerequisites; cookies are never treated as proof that server state was restored.
- Saved return paths, checkpoint/resume, and `deepen --query` frontier prioritization for future agents.
- Graph A JSON, Mermaid, readable Markdown, metrics, trace JSONL, run artifact, and checkpoint outputs.
- Protected input references and URL query redaction for sensitive-looking keys.
- Deterministic, selective-model, and model-all policy interfaces with compact observations and a content/config decision cache.
- Repository-root `.env` loading via `python-dotenv`. Key values are never returned or logged. Groq generation additionally requires `GROQ_FREE_PLAN_CONFIRMED=true`; OpenAI remains hard-disabled even when its key exists.
- A persistent locked spending ledger with pre-call reservations, retries/outstanding-request accounting, a $20 ceiling, and an $18 paid-call stop. It is tested, but no paid provider is wired because verified pricing/account controls were not established.
- A sequential one-worker experiment runner, a Crawlee external-baseline adapter, and a post-run derived-feature audit tool that never rewrites raw evidence.

## Comparative review and reuse decisions

The focused review is in `RESEARCH_REVIEW.md` with primary sources and inspected implementation details. The architecture was revised toward a Crawljax-style event/state-flow archive plus Go-Explore-style saved return/replay, while retaining Playwright rather than wrapping a research stack. FragGen's fragment comparison, WebExplor's Q-learning, FormNexus's paid LLM workflow, and exact automata learning were not adopted before the core state/action/reset abstractions were measured.

Crawljax remains the established literature baseline. Its repository implementation was inspected, and Java 17 was installed, but the official CLI archive was about 987 MB, Maven was absent, and the FragGen path adds native OpenCV burden. It was not run; no performance claim is made against it. Crawlee 1.11 was run as the maintained practical external baseline, with its narrower link-crawling mechanism clearly labeled.

Exact distribution/leaderboard conditions for the already-running benchmark instance remain unresolved in this repository. Work therefore stayed website-only, anonymous, and independent-fixture-based for correctness tests.

## Experiments and comparable results

All live runs used the same URL, anonymous access, one worker, fresh contexts for attempts/replay, POST disabled, and $0 spend. SiyuCMS exposes no mapper-visible reset contract; no state-changing live POST was attempted.

- First matched 60-second run: exact 7 workflows with 14/14 replay; grouped 7 with 14/14. Both had 13 raw states, 10 groups, three redundant states, zero audited incorrect merges, and zero unsupported replay connections.
- Corrected 60-second repeat: exact 7 with 12/12 replay; grouped 8 with 11/11. This one-workflow difference is short-run ordering variance, not a demonstrated gain; the first run tied and the 10-minute run tied.
- Matched 10-minute run: exact and grouped each audited to 16 workflows and 77/77 replay. Each observed 27 raw states and 22 groups (five redundant states), with zero incorrect merges under the recorded route/control/form/session audit. Corrected validation progress was 0 at 420 seconds, 11 at 480 seconds, 16/15 at 540 seconds, and 16/16 by 600 seconds because 30% of the budget was reserved for replay.
- Selective local-model control, first 60-second run: 3 workflows, 11/11 replay, two successfully parsed model calls, 4,100 input and 188 output tokens, $0. Failed-call accounting was incomplete in this preserved run.
- Selective local-model accounting rerun: 2 workflows, 8/8 replay, nine calls, eight invalid/truncated JSON failures, 12,874 input and 4,213 output tokens, $0. The local `qwen2.5:0.5b` model hurt throughput and was not advanced to a 10-minute run.
- Crawlee 60-second external baseline: 20 pages, 16 route patterns, 7 distinct validated link workflows, 7/12 replay, five unsupported paths, 39 browser actions, $0. It does not operate buttons/forms or group UI state, so this is not a superiority comparison.
- Post-fix 45-second regression: 2 workflows and 6/6 replay. A browser hit-test removed the repeatedly attempted covered search submit; one theme-layout link still failed and remains visible. The shorter budget makes its feature count incomparable to the 60-second runs.

The original 10-minute reports said 36 exact and 43 grouped workflows. Audit showed that this incorrectly counted a repeated global link once per source state. Those original outputs are preserved. `audited_v2/` collapses navigation by functional target while retaining all source states and evidence paths, excludes carousel Previous/Next from feature counts, and reports the corrected 16/16. No raw observation, transition, or replay was altered.

The historical HTTP-only outputs remain historical structural proxies: BFS 3 forms/22 routes, redirect-only 4/23, and hybrid 4/30 at 40 GET requests. They were not relabeled as verified workflow coverage.

## Failures, bottlenecks, and audit findings

The 10-minute exact/grouped runs kept 28/24 failed transition attempts. Of these, 23/19 were the same unnamed search submit covered by another rendered element; a focused Playwright hit-test confirmed the obstruction and motivated the extraction fix. Remaining failures were hidden/theme-layout or submenu controls. Replay failures were zero in Agent 1's deterministic 10-minute runs, while Crawlee had five.

Five groups in the 10-minute grouped run merged multiple raw signatures. Each retained one normalized route and the `anonymous` session context: honours detail, article detail, product detail, `/`, and `/index.html`. The automated form/control/session audit found no false merge. This is still a structural audit, not independent semantic ground truth.

The main remaining bottleneck is discovering UI prerequisites for temporarily covered controls without repeatedly attempting them on every page. Breadth also spends actions on repeated global navigation. A stronger content/fragment identity and an interaction-readiness prerequisite model are better next targets than Q-learning.

## Tests

- Agent 1: 10 passed, including evidence invariants, form/session false-merge protection, spending reservations and overcharge rejection, model control-ID validation, feature identity, a live state-changing fixture whose replay must reproduce its cookie-setting form prerequisite, and checkpoint resume.
- Preserved `engramsec_v0`: 8 passed.
- A sandboxed test attempt could not bind loopback fixtures; the authorized loopback-only reruns passed. This was an environment permission issue, not a test failure.

## Security, keys, cost, and setup

`.env` is ignored by `.gitignore`, is not tracked, and no configured key value was found elsewhere in the repository audit. `.env.example` contains names and disabled defaults only. Browser authentication state and credentials are not committed.

Ollama 0.34.0 and local models were available; `qwen2.5:0.5b` was used for the free model control. The Groq models endpoint authenticated successfully, but the endpoint cannot prove account tier, so no Groq generation was made. No OpenAI call was made. Total monetary spend was exactly $0.

One-time setup outside measured run time: Python 3.12 virtual environment/dependencies, Playwright Chromium 156, Crawlee 1.11, and OpenJDK 17. Dependency/browser installation time was not included in run budgets. Total working-session wall time was approximately 6 hours 50 minutes by the earliest plan timestamp; the six-hour boundary was reached while final verification/reporting was being completed, and no further long run was started.

Remaining setup blockers are: no supplied test-account credentials, unresolved benchmark distribution conditions, Crawljax's disproportionate package/build burden, and no confirmed Groq free-tier flag. None blocks the model-free mapper.

## Reproduce and resume

```bash
cd /Users/sanskritisingh/EngramSec
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-agent1.txt
.venv/bin/python -m playwright install chromium

.venv/bin/python -m pytest -q
env PYTHONPATH=engramsec_v0 .venv/bin/python -m pytest engramsec_v0/tests -q

.venv/bin/python -m agent1.cli map \
  --url http://127.0.0.1:51707/ \
  --out agent1/outputs/reproduction \
  --policy grouped --seconds 600 --max-transitions 200 --max-browser-actions 800

.venv/bin/python -m agent1.cli resume \
  --checkpoint agent1/outputs/reproduction/checkpoint.json \
  --seconds 120 --max-transitions 240 --max-browser-actions 960

.venv/bin/python -m agent1.cli deepen \
  --checkpoint agent1/outputs/reproduction/checkpoint.json \
  --query search --seconds 120 --max-transitions 240 --max-browser-actions 960

.venv/bin/python experiments/run_crawlee_baseline.py \
  --url http://127.0.0.1:51707/ \
  --out agent1/experiments/crawlee-reproduction --seconds 60 --max-pages 20
```

Representative corrected Graph A: `agent1/experiments/siyucms_10m_comparison/grouped-r1/audited_v2/graph_a.json` and its readable Mermaid diagram `graph_a.mmd`. The corresponding `run.json`, `trace.jsonl`, `checkpoint.json`, audit metadata, and failed transitions are beside them.

## Next most informative experiments

1. Add prerequisite discovery for covered menus/search drawers and ablate it against the final hit-test, measuring transition failures and validated workflows at the same 10-minute budget.
2. Repeat exact/grouped 10-minute runs at least twice. The current single long pair is insufficient for a grouping-effect claim.
3. Test a larger local JSON-capable Ollama model on the preserved compact observations before any live run; advance only if parse rate and ranking quality beat deterministic order offline.
4. Add content/fragment fingerprints as a reversible grouping layer and test false merges on fixtures with identical navigation but different workflow content.
5. Run Crawljax only if its large official artifact or a reproducible Maven setup becomes acceptable; keep installation cost separate and match worker/time/reset conditions.
