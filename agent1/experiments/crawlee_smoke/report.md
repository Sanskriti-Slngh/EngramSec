# Crawlee external baseline

- Target: `http://127.0.0.1:51707/`
- Elapsed: 33.904 seconds
- Pages / route patterns: 10 / 10
- Validated link workflows: 2
- Replay success: 2/6
- Unsupported connections: 4
- Browser actions: 18

## Limitations

- Crawlee is a maintained browser crawler, not a state-flow testing system.
- This adapter replays visible link paths, but does not interact with buttons or forms.
- Direct crawl visits and replay time are both included in elapsed time.
