# Crawlee external baseline

- Target: `http://127.0.0.1:51707/`
- Elapsed: 60.032 seconds
- Pages / route patterns: 20 / 16
- Validated link workflows: 7
- Replay success: 7/12
- Unsupported connections: 5
- Browser actions: 39

## Limitations

- Crawlee is a maintained browser crawler, not a state-flow testing system.
- This adapter replays visible link paths, but does not interact with buttons or forms.
- Direct crawl visits and replay time are both included in elapsed time.
