# Agent 1 crawling breakthrough report

## Result

Agent 1 reached **39/59 official Crawlground markers (66%)** in one SERIOUS full-site crawl from `/`, compared with **13/59 (22%)** for frozen commit `2b8aa18` under the same 600-action/250-transition limits. This is a large measured improvement and exceeds the 30-marker stretch goal. It remains below ZAP's published 45/59 reference, which was not a matched-budget run.

The clean FAST result stayed at 3/59. The new architecture is therefore not a universal small-budget win; its gain appears after enough transitions to traverse the application. The independent Google Crawl Maze transfer result was only 4/91 expected resources (4.4%), so Agent 1 is not yet a competitive comprehensive web security crawler.

## Frozen setup and budgets

- Target: official [ZAP Crawlground](https://github.com/zaproxy/crawlground), commit `ba52303a5fd43795f461a6df39da45e2fe886c6b`, localhost only.
- Baseline mapper: commit `2b8aa18`, historical `coverage` policy, robust readiness, persistent discovery.
- Final mapper: this commit's `multidimensional` policy, extended interactions, hybrid observed links, robust readiness, persistent discovery.
- FAST: 60 seconds, 30 transitions, 140 browser actions.
- SERIOUS: 600 seconds, 250 transitions, 600 browser actions.
- One Chromium worker; no models, paid APIs, endpoint guessing, exploits, or credentials.
- Each valid score used a unique official `/set-tool` bucket. The mapper did not request scores or read evaluator expectations.

## Before and after

| Measure | Frozen FAST | Final FAST | Frozen SERIOUS | Final SERIOUS |
|---|---:|---:|---:|---:|
| Official markers | 3/59 | 3/59 | 13/59 | **39/59** |
| Replay successes/attempts | 17/27 | 14/23 | 15/33 | **25/38** |
| Browser actions | 135 | 127 | 600 | 599 |
| Observed/attempted transitions | 27/30 | 30/30 | 189/250 | 249/250 |
| Root reloads | 39 | 29 | 212 | **96** |
| Restoration actions | 4 | 0 | 142 | 168 |
| Live-state reuse | 23 | 26 | 134 | 195 |
| Action network events | 24 | 25 | 173 | 210 |
| Elapsed seconds | 37.1 | 61.2 | 195.5 | 361.8 |

Final SERIOUS marker efficiency was 15.4 total browser actions per marker versus 46.2 for the frozen serious run. Total actions include exploration, restoration, form filling, and replay, so this is an end-to-end efficiency measure rather than pure discovery cost.

| Category | Denominator | Frozen SERIOUS | Final SERIOUS |
|---|---:|---:|---:|
| Buttons | 2 | 1 | **2** |
| Dynamic content | 10 | 3 | **6** |
| Forms | 12 | 4 | **8** |
| Frames/shadow | 4 | 0 | **3** |
| JavaScript events | 14 | 2 | **10** |
| Links | 7 | 2 | **4** |
| Navigation | 9 | 1 | **6** |
| Other | 1 | 0 | 0 |

## Evidence integrity

The final Graph A contains 201 raw and 201 grouped states, 249 observed transitions, one failed transition, 210 action-triggered request events, full prerequisite descriptors, and separate status-bearing replay records. The export exposes frame, component, and interaction metadata. Raw browser observations and checkpoints remain local and ignored; compact Mermaid, metrics, and report artifacts are committed.

The 39 score means the application independently observed 39 marker-triggering interactions. It does not mean 39 vulnerability surfaces, functional business workflows, or replay-validated marker paths. Crawlground scoring is independent of Graph A replay. Agent 1 replayed 25/38 scheduled paths; 211 observed paths were not replayed within the action budget.

Failures are preserved. The initial multidimensional scheduler scored 1/59 after spending 237 actions on inferred gestures, mostly on a results listing. The breadth FAST baseline scored 0/59 despite 16/16 replay, showing that shallow replay reliability alone is not coverage. One hybrid iteration lacks an isolated marker score because the local evaluator activation call was sandbox-blocked; no score is inferred from it.

## Independent transfer result

The frozen final mapper ran once on official [Google Security Crawl Maze](https://github.com/google/security-crawl-maze), commit `2a0dd0a75e39925ded887bcd25016e8b3ce0f2b3`, in local Flask mode. It observed 38 transitions/35 states and replayed 12/12 attempted paths. A separate post-run evaluator found only 4 of 91 applicable expected resource paths in Graph A evidence (4.4%).

This falsifies the broadest version of the breakthrough hypothesis. The new system transfers as a reliable interactive/anchor mapper, but not as a comprehensive security resource crawler. It does not yet extract many URL-bearing HTML attributes, response headers, CSS resources, or script-disclosed static references. Passive-page readiness also limited the run to 103 actions in 181.5 seconds.

## Established-tool comparison

ZAP's architecture explains much of the remaining gap: its traditional spider handles many HTML/resource reference types, while the Client Spider uses a client map and browser event stream, crawls page components, follows component navigation, and adaptively waits ([traditional Spider](https://www.zaproxy.org/docs/desktop/addons/spider/), [Client Spider](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/spider/), [client integration](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/)). Agent 1 now implements part of the event/state-flow side, but its “lightweight crawler” recognizes primarily anchors and areas.

The published 45/59 ZAP figure and Agent 1's 39/59 are not directly comparable because time, action accounting, version, and replay work differ. No superiority claim is made.

## Reproduction

Start pinned Crawlground, activate an isolated score bucket, then run:

```bash
.venv/bin/python -m agent1.cli map \
  --url http://127.0.0.1:3456/ \
  --out agent1/experiments/crawlground-breakthrough-reproduction \
  --policy multidimensional --seconds 600 \
  --max-transitions 250 --max-browser-actions 600 \
  --allow-post-forms --robust-readiness \
  --exploration-mode persistent \
  --interaction-profile extended --hybrid-links
```

The exact setup, score-bucket, and transfer commands are documented in the relevant experiment reports and `agent1/README.md`.

## Cost and resource accounting

External API/model cost was $0. Cumulative browser evaluation time was approximately 33.6 minutes, below the 45-minute cap. The temporary Crawl Maze clone was 804 KB; its temporary Flask environment downloaded under 1 MB of packages. No large framework was installed and no WebExploitBench evaluation artifact was used.
