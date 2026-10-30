#!/bin/zsh
# usage: experiments/run_architecture_comparison.sh ROOT SECONDS ARM...   (arm = A|B|C|D|E with optional suffix _rN)
# Arms: A baseline, B +ZAP seeds, C hierarchical, D C+ZAP, E D+verified state reuse,
# AH baseline+state reuse, CE hierarchical+state reuse. Expects the Crawl Maze target
# on 127.0.0.1:3460 and the sanitized ZAP export described in ZAP_DISCOVERY_COMPARISON.md.
cd "$(dirname "$0")/.."
ROOT=$1; SECS=$2; shift 2
ZAP=agent1/.cache/zap-comparison/traditional-seeds.json
for ARM in "$@"; do
  base=${ARM%%_*}
  extra=()
  case $base in
    A) extra=(--exploration-policy multidimensional);;
    B) extra=(--exploration-policy multidimensional --zap-evidence $ZAP --zap-source-origin http://crawlmaze:3460);;
    C) extra=(--exploration-policy hierarchical);;
    D) extra=(--exploration-policy hierarchical --zap-evidence $ZAP --zap-source-origin http://crawlmaze:3460);;
    E) extra=(--exploration-policy hierarchical --zap-evidence $ZAP --zap-source-origin http://crawlmaze:3460 --state-reuse prefix);;
    CE) extra=(--exploration-policy hierarchical --state-reuse prefix);;
    AH) extra=(--exploration-policy multidimensional --state-reuse prefix);;
  esac
  echo "=== $ARM start $(date +%T)"
  PYTHONPATH=. .venv/bin/python experiments/run_resource_spider_ablation.py --root $ROOT \
    --variants adaptive_readiness --tag $ARM --seconds $SECS --max-transitions 120 \
    --max-browser-actions 300 --max-resource-fetches 100 --document-budget 70 \
    --script-budget 20 --stylesheet-budget 10 --asset-budget 20 \
    --max-total-http-requests 1000 $extra > $ROOT/log_$ARM.txt 2>&1
  echo "=== $ARM exit $? $(date +%T)"
done
