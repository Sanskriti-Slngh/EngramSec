# Agent 1 run agent1-20261028T115034Z

- Code revision: `65b075ab8b339460dadb446c79b03fa6de03fa7c`
- Policy: `grouped`
- Target: `http://127.0.0.1:51707/`
- Elapsed: 17.887 seconds
- Browser actions (including setup/replay): 22
- Validated feature workflows: 3
- Replay success: 3/3
- Unsupported connections: 0
- Incorrect state merges found by audit: 0
- Redundant raw states: 0
- Model calls / cost: 0 / $0.000000

## Replay-validated workflows

- `feature_7f051c9a4d36ecc5` — 首 页 leads to SIYUCMS 官网
- `feature_822de3cec67fcc92` — 铅笔盒 leads to 铅笔盒-精选产品_SIYUCMS
- `feature_a8274a912b8e41ca` — 钢笔 leads to 钢笔-精选产品_SIYUCMS

## Observed but not replay-validated

- None.

## Failed or blocked transitions

- `tr_a22ac4ba6eb75c0a16b3` — unnamed button: RuntimeError: saved return path did not restore the expected source state
- `tr_96b24c39f70d0cf267a4` — Previous: RuntimeError: saved return path did not restore the expected source state
- `tr_f1487855e4921115dc02` — Next: RuntimeError: saved return path did not restore the expected source state
- `tr_15d10ab48603c6f552d5` — 资质荣誉四: RuntimeError: saved return path did not restore the expected source state
- `tr_45d78b7d3d41e6f8efdf` — 资质荣誉六: RuntimeError: saved return path did not restore the expected source state
- `tr_46b09dde011326b285bd` — 资质荣誉五: RuntimeError: saved return path did not restore the expected source state
- `tr_0a105553eb071ccf8b0c` — 资质荣誉: RuntimeError: saved return path did not restore the expected source state
- `tr_f9a7090d6c39a7e7448b` — 资料下载: RuntimeError: saved return path did not restore the expected source state
- `tr_ca7143a9d1bce1d29ac5` — 联系我们: RuntimeError: saved return path did not restore the expected source state

## Notes

- Website-only browser evidence; target source and verifier internals were not inspected.
- A browser-observed edge is not counted as a validated feature until its complete path replays.
- Query values with sensitive-looking keys are redacted from stored network evidence.
