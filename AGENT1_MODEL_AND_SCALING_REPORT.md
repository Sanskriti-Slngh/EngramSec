# Agent 1: do models, training or more compute help?

Status: **in progress.** Offline model and training results are final; the live model variant and the budget comparison are pending (§6).

## 1. Baseline and prior work (not repeated)

**Baseline.** The strongest existing configuration is the integrated configuration ([AGENT1_RECOVERY_AND_TRANSFER_REPORT.md](AGENT1_RECOVERY_AND_TRANSFER_REPORT.md)):
- multidimensional frontier, extended interactions, hybrid links, persistent mode;
- typed spider with standards extraction, shared HTTP budget, listener revisit, structure replay, adaptive readiness;
- read-only enforced.

Its reproduced results: Crawl Maze 61/91 (180 s), Crawlground 49–50/59 (600 s).

**Prior model work** ([MORNING_REPORT.md](MORNING_REPORT.md), [VALIDATION_REPORT.md](VALIDATION_REPORT.md), [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md)):
- `qwen2.5:0.5b` as a live action selector was negative: 8 of 9 calls returned invalid JSON, it slowed exploration, and it was not advanced.
- `llama3.2` form assistance fixed one validation case.
- The recorded next step was to screen a larger JSON-capable model **offline** first and go live only if it beats deterministic order.

This experiment follows that path. It reuses the existing providers' contract (rank only observed, safe control ids) and the existing `SpendingLedger`.

## 2. Labelled data (development fixtures only)

[evaluation/model_dataset.py](evaluation/model_dataset.py).

**Label.** Did executing an already-observed, safety-approved action reveal genuinely new functionality? That means a route pattern, request structure or form schema not seen earlier in the run. The label comes from the agent's own outcome only.

**Sources.** Runs positively identified as development fixtures or the operator's whiteboard:
- 11 apps, 164 runs;
- Crawlground, Crawl Maze and every WebExploitBench target excluded by name and port;
- no benchmark scorer, marker or ground truth read.

| | Count |
|---|---:|
| labelled actions (raw) | 6,215 (1,794 positive) |
| distinct after collapsing identical fixture reruns | **425 (140 positive)** |
| ranking situations (same page state, ≥1 positive and ≥1 negative) | 582 raw, **85 distinct** |

## 3. Offline ranking (85 situations; same page, same history, labels hidden)

[evaluation/model_offline_rank.py](evaluation/model_offline_rank.py).

Rankers see the page, the safe candidate actions, the run's visited routes and its recent actions. The model may return only the given ids; others are discarded, with deterministic order as fallback for omissions.

| Ranker | Top-1 right | MRR | Latency / call | Cost |
|---|---:|---:|---:|---:|
| `qwen2.5:14b` (local, Ollama) | **0.80** | **0.875** | 11.4 s | $0 |
| `gpt-5.4-mini` (OpenAI) | 0.75 | 0.873 | 2.1 s | $0.11 for 85 calls |
| novelty heuristic (unvisited target first) | 0.73 | 0.84 | — | — |
| learned logistic scorer (leave-app-out) | 0.60 | 0.77 | — | — |
| explorer's per-page kind order | 0.60 | 0.73 | — | — |
| `llama3.2` 3B (local) | 0.33 | 0.55 | 1.9 s | $0 |
| random (analytic) | 0.35 | 0.55 | — | — |

- Parse rates were 97.6–100%. One invented id was returned in 170 strong-model calls, and it was discarded.
- **Reading:**
  - Strong models beat the explorer's per-page order clearly.
  - They beat the novelty heuristic, the closest analogue to the real `multidimensional` scoring, only modestly: about 2–6 more correct first choices of 85, suggestive at this sample size.
  - The small fast local model is at chance.
  - Only `gpt-5.4-mini` is both good and fast enough to test live.

## 4. Training: is a fine-tune justified?

[evaluation/model_learning_curve.py](evaluation/model_learning_curve.py): a deliberately simple learner (logistic regression on action, page and history features), leave-apps-out, 12 resamples per point.

| Training apps | Mean training examples | Held-out AUC (sd) | Novelty heuristic AUC |
|---:|---:|---:|---:|
| 1 | 35 | 0.82 (0.21) | 0.74 |
| 2 | 70 | 0.90 (0.03) | 0.74 |
| 3 | 110 | 0.92 (0.03) | 0.75 |
| 5 | 208 | 0.93 (0.03) | 0.76 |
| 7 | 270 | 0.93 (0.04) | 0.75 |
| 10 | 383 | 0.93 (0.08) | 0.71 |

**Conclusion: a LoRA fine-tune is not justified by the available data.**
- The signal is learnable, but it saturates after about 70 examples from 2 apps. More of the same author-built fixture data adds nothing measurable, so a fine-tuned language model would have no headroom to show on it.
- With 425 distinct examples from 11 small fixtures, a LoRA would mostly learn the fixtures' vocabulary.
- Per-action AUC also overstates ranking quality. As a within-page ranker the learned scorer reaches only 0.60 top-1 (§3), below both strong models.

What would justify training: **new, diverse labelled data** (many real applications), not more compute on this set. No fine-tune was run. No hardware limit applied: the Apple M5 with 16 GB could run a small `mlx-lm` LoRA.

## 5. Spend

$10.00 cap enforced by a ledger with worst-case reservations (1.5× list price, maximum output tokens), retries included. Prices verified from [OpenAI's pricing](https://developers.openai.com/api/docs/pricing) and the [GPT-5.4 mini model page](https://developers.openai.com/api/docs/models/gpt-5.4-mini): $0.75 / 1M input, $4.50 / 1M output.

Spent so far: **$0.115** (88 calls, 0 failed, 0 refused).

## 6. Pending

- Live model-ranking variant (opt-in, bounded weight, safe observed ids only) against deterministic exploration on Crawl Maze, Crawlground, White-Jotter and fixtures.
- Budget experiment: B1 (2× time and actions) and B2 (2× HTTP and resources, depth 5) on the same targets, never mixed with model changes.
