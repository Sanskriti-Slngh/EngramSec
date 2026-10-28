# EngramSec Agent 1

Agent 1 maps an explicitly configured loopback website using a real Chromium browser. It records observed controls, browser outcomes, compact network evidence, conservative state groups, saved return paths, and fresh-context workflow replays. It never reads target source code.

## Setup

```bash
cd /Users/sanskritisingh/EngramSec
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-agent1.txt
.venv/bin/python -m playwright install chromium
```

Optional model keys belong only in the ignored repository-root `.env`; use `.env.example` as the template. The loader supports `GROQ_API_KEY` and `OPENAI_API_KEY` without printing them. OpenAI paid calls are intentionally disabled even when the key exists.

## Run

Short model-free smoke run:

```bash
.venv/bin/python -m agent1.cli map \
  --url http://127.0.0.1:51707/ \
  --out agent1/outputs/siyucms-smoke \
  --policy grouped --seconds 60 --max-transitions 20 --max-browser-actions 80
```

Selective local-model run:

```bash
.venv/bin/python -m agent1.cli map \
  --url http://127.0.0.1:51707/ \
  --out agent1/outputs/siyucms-local-model \
  --policy selective_model --provider ollama --model qwen2.5:0.5b \
  --seconds 600 --max-transitions 200 --max-browser-actions 800
```

POST forms are skipped by default. Enable `--allow-post-forms` only for a disposable fixture or when the configured target workflow is explicitly safe to mutate.

## Resume or request deeper exploration

```bash
.venv/bin/python -m agent1.cli resume \
  --checkpoint agent1/outputs/siyucms-smoke/checkpoint.json \
  --seconds 120 --max-transitions 40 --max-browser-actions 160

.venv/bin/python -m agent1.cli deepen \
  --checkpoint agent1/outputs/siyucms-smoke/checkpoint.json \
  --query login --seconds 120 --max-transitions 40 --max-browser-actions 160
```

The `deepen` command only changes frontier priority; it does not turn a model suggestion into evidence.

Rebuild feature nodes from preserved raw evidence after an identity-rule audit without modifying the original run:

```bash
.venv/bin/python experiments/audit_run.py \
  agent1/experiments/siyucms_10m_comparison/grouped-r1/run.json \
  --out agent1/experiments/siyucms_10m_comparison/grouped-r1/audited-new
```

## Matched experiments

```bash
.venv/bin/python experiments/run_agent1_experiments.py \
  --url http://127.0.0.1:51707/ \
  --out agent1/experiments/siyucms-10m \
  --seconds 600 --max-transitions 200 --max-browser-actions 800 \
  --variants exact grouped selective_model
```

Runs are sequential with one worker. Each attempted transition and replay starts from a fresh browser context and replays prerequisites. The live SiyuCMS target has no mapper-visible reset contract, so server-side state changes would limit comparability; POST forms stay disabled in the supplied live experiments.

## Output contract

- `graph_a.json`: feature, state, and action/evidence levels plus status-bearing edges.
- `graph_a.mmd`: Mermaid diagram derived from the JSON.
- `run.json`: complete compact artifact, including observations and saved return paths.
- `trace.jsonl`: one transition per line; protected values are references, not credentials.
- `checkpoint.json`: resumable frontier and evidence.
- `metrics.json` and `report.md`: measured results, including failures and unvalidated paths.

Statuses mean:

- `advertised`: a control was visible but not executed.
- `observed`: the browser executed it and captured a resulting observation.
- `replay_validated`: a fresh context replayed the full path and matched group, route, and title checks.
- `failed`: execution, return, or replay failed.
- `unresolved`: reserved for connections that cannot yet be attempted.

## Tests

```bash
.venv/bin/python -m pytest tests -q
PYTHONPATH=engramsec_v0 .venv/bin/python -m pytest engramsec_v0/tests -q
```

The Agent 1 integration tests include a state-changing fixture whose private outcome requires a cookie set by a preceding form submission. Replay must reproduce that prerequisite; restoring cookies alone is never used as proof.
