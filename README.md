# EngramSec Agent 1

Agent 1 is a **deterministic, safety-bounded browser functionality mapper**. It drives a real Chromium
browser over an unfamiliar web app and emits a model of *what the app can do* — **Graph A** (observed states,
actions, and replayable workflows) and the **ACG** (distinct capabilities: API operations, roles, effects).
It runs **no LLM in the mapping loop**, never reads the target's source, never types credentials, and never
fires a destructive request.

For the architecture, safety model, capabilities, and benchmark results, see **[AGENT1_REPORT.md](AGENT1_REPORT.md)**.

## Setup

```bash
cd /Users/sanskritisingh/EngramSec
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-agent1.txt
.venv/bin/python -m playwright install chromium
```

Optional model keys live only in the git-ignored repo-root `.env` (template: `.env.example`); `GROQ_API_KEY`
and `OPENAI_API_KEY` are supported and never printed. Paid OpenAI calls are disabled even when a key exists.

## Run — point it at any website

```bash
# Safe, read-only, works on any site (incl. production). The recommended default.
python -m agent1.cli map --url http://127.0.0.1:8000/ --out agent1/outputs/site --profile general
```

Profiles bundle the validated flag set so you don't hand-set a dozen options:

| profile | writes | use |
|---|---|---|
| `general` | none (read-only) | map any site safely |
| `pentest` | disposable, authorized | `general` + write-chaining; **mutates the target**, requires `--attestation "disposable: <why>"` (disposable/authorized targets only) |
| `default` | none | frozen baseline; hand-tune individual flags |

Common add-ons (apply with any profile):

```bash
  --seconds 300                       # time budget
  --storage-state session.json        # operator-captured authenticated session (agent never types creds)
  --context-label admin               # label the role for the authenticated surface
  --ignore-https-errors               # accept self-signed TLS on a local target
  --typed-resource-spider             # also discover API/asset endpoints from response bodies
```

Capture an authenticated session for `--storage-state` (operator does the login once):

```bash
python -m agent1.auth_capture --url http://127.0.0.1:8000/login --user admin --password '***' --out session.json
```

Authorized write-chaining against a **disposable** target:

```bash
python -m agent1.cli map --url http://127.0.0.1:8000/ --out agent1/outputs/pentest \
  --profile pentest --attestation "disposable: throwaway docker instance"
```

Resume or deepen a saved run (`deepen` only re-prioritizes the frontier; it never turns a suggestion into
evidence):

```bash
python -m agent1.cli resume  --checkpoint agent1/outputs/site/checkpoint.json --seconds 120
python -m agent1.cli deepen  --checkpoint agent1/outputs/site/checkpoint.json --query login --seconds 120
```

`--profile default` exposes the full low-level flag set (readiness, resource spider, replay policy, listener
observation, model assistance, etc.); run `python -m agent1.cli map --help` for the complete list.

## Output contract (written to `--out`)

- `graph_a.json` — feature / state / action-evidence levels plus status-bearing edges.
- `graph_a.mmd` — Mermaid diagram derived from the JSON.
- `run.json` — complete compact artifact (observations, saved return paths). The ACG is built from this via
  `agent1/model/importer.py` → `materialize.py`.
- `trace.jsonl` — one transition per line; sensitive values are references, never credentials.
- `checkpoint.json` — resumable frontier and evidence.
- `metrics.json`, `report.md` — measured results, including failures and unvalidated paths.

Request evidence records method, sanitized URL, status, resource type, parameter *names*, and body encoding —
never request values. State nodes expose cookie/storage *names* only.

**Edge/action statuses:** `advertised` (seen, not executed) · `observed` (executed, observation captured) ·
`replay_validated` (a fresh context replayed the full path and matched group/route/title/content/outcome) ·
`functional_verified` (also reproduced an explicit success signal) · `validation_failure` (reproduced an
observed error — behavior, not success) · `navigation_only` · `not_tested` · `failed` · `unresolved`.

## Tests

```bash
.venv/bin/python -m pytest tests -q
```

Fixture app behavior is in `tests/fixtures/interactive_app.py`; its ground truth is separate
(`tests/fixtures/ground_truth.py`). The mapper package imports neither.
