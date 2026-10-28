# Agent 1 baseline audit

Baseline revision: `6082c6d`. This audit predates mapper behavior changes in this milestone.

## Benchmark integrity

Public documentation was reviewed, but no WebExploitBench challenge instance, vulnerability metadata, `Location` value, verifier implementation, exploit report, protected output, or evaluation trace was read or used. CAGE recursively discovers self-describing targets from `challenge.json`; a benchmark adapter interprets the challenge identity/target configuration and vulnerability metadata rather than exposing the raw file to the agent. Web vulnerability entries can contain evaluation metadata such as a `Location`, but that is scorer/hint material, not mapper input. CAGE launches an isolated target, records agent activity and snapshots, and submits saved/live evidence to benchmark-owned scoring. At l0 the agent receives no vulnerability hint, l1 supplies partial hints, and l2 can expose stronger type/location guidance. CAGE's scorer—not Agent 1—determines whether the benchmark objective was met. The full WebExploitBench dataset is gated and evaluation-only; its terms prohibit using benchmark material or derived evaluation output for agent optimization. Development in this milestone therefore uses only independent local applications.

Primary sources: [CAGE](https://github.com/AgentCyberRange/CAGE), [benchmark integration](https://github.com/AgentCyberRange/CAGE/blob/main/examples/agent_pentest_bench/README.md), [benchmark authoring](https://github.com/AgentCyberRange/CAGE/blob/main/docs/writing-benchmarks/README.md), [repository architecture](https://github.com/AgentCyberRange/CAGE/blob/main/docs/repo-architecture.md), and the [WebExploitBench dataset terms](https://huggingface.co/datasets/AgentCyberRange/WebExploitBench/blob/main/README.md?code=true).

## What `6082c6d` actually represents

- UI states: raw observations plus reversible groups keyed by route shape, safe control/form structure, configured context label, and meaningful page-content fingerprint.
- Controls/forms: visible links, native buttons, submit/button inputs, `role=button`, and several disclosure attributes; form field names, types, labels, constraints, and protected value references are retained.
- Instances: raw URLs, labels, text, and signatures preserve instances; grouped link shapes can combine records, while each raw observation remains available.
- Requests: action-attached document/Fetch/XHR method, redacted URL, status, resource type, and failure. POST/JSON/form parameter structure and request initiator are absent.
- Session/authentication: only a caller-supplied `context_label`; browser-observed cookie/storage marker names are absent.
- Prerequisites: full action descriptors, shortest return paths, checkpoints, and fresh-context replay are present.
- Blocked controls: observed unsafe controls are retained with skip reasons; controls absent from the extracted selector cannot be advertised as blocked or untested.
- Evidence: source/action/result observations, networks, replay results, functional status, and referential connection-evidence audits exist. Referential completeness does not establish application completeness.

## Concrete discovery gaps

1. `EXTRACT_SCRIPT` omits standard interactive semantics such as `role=tab`, `<summary>`, keyboard launchers, and generic `data-action` controls. It has no hover-readiness pass.
2. Frontier order is mostly form/button/link type plus shallow path length. It does not prioritize globally novel controls, form shapes, fragments, or request structures, and repeatedly executes site-wide navigation.
3. Every frontier attempt starts from the root and replays its path. Archived paths exist, but there is no state archive/context reuse or restoration-cost term.
4. State identity is whole-page rather than fragment-aware. This is conservative for content changes but lets shared chrome dominate representation and supplies no component novelty signal.
5. Request evidence cannot represent POST field names or JSON structure, so reachable input surface is systematically undercounted.
6. Static session labels cannot demonstrate that anonymous/member or multi-role observations were actually distinct.
7. Ineffective controls are recorded as observed transitions and can replay successfully; navigation replay alone does not prove useful effect.
8. The self-audit for incorrect merges compares evidence close to the grouping inputs. Independent ground truth is required to measure false merges and unnecessary splits.

## Historical SiyuCMS interpretation

The historical `16` categories are navigation group counts, not functional coverage. Likewise, `77/77` replays measure reproducibility of attempted paths, and `436/436` evidence references measure internal referential completeness. None has an independent reachable-surface denominator. Existing SiyuCMS runs remain useful development history for navigation, actions, and search verification, but they are neither held-out generalization evidence nor an application-completeness claim.

## Frozen development baseline

The independent Coverage Lab evaluator excluded one intentionally blocked area and one outside-origin area from ordinary recall denominators. Under 30 transitions / 140 configured browser actions, `6082c6d` achieved:

| Measure | Baseline |
|---|---:|
| Reachable area recall | 6/10 (60.0%) |
| Relevant control recall | 11/17 (64.7%) |
| Request-structure recall | 6/10 (60.0%) |
| Replayed prerequisite paths | 5/10 (50.0%) |
| Record instances discovered/distinct | 2/2; yes |
| Observed contexts | 1/2 (50.0%) |
| Navigation replay | 19/19 (100%) |
| Browser actions | 142 (two-action replay overshoot) |

The strongest initial hypothesis is that semantic-control readiness will recover entire currently invisible branches. The next bottleneck is action efficiency/frontier novelty, followed by request/session evidence.
