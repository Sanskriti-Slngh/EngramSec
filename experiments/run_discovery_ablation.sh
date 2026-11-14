#!/bin/zsh
# usage: experiments/run_discovery_ablation.sh ROOT SECONDS ARM...   (arm = A|B|C|D with optional suffix _rN)
# A frozen baseline; B shared-HTTP passive document allocation; C extended
# extraction; D both. Matched budgets: browser actions, total HTTP, typed-resource
# total and class caps are identical; only the two optional policies differ.
# Expects the Crawl Maze target on 127.0.0.1:3460.
cd "$(dirname "$0")/.."
ROOT=$1; SECS=$2; shift 2
SPEC=${SPECULATIVE_FETCHES:-25}
for ARM in "$@"; do
  base=${ARM%%_*}
  extra=()
  case $base in
    A) extra=();;
    B) extra=(--resource-allocation shared_http);;
    C) extra=(--html-extraction extended --max-speculative-fetches $SPEC);;
    D) extra=(--resource-allocation shared_http --html-extraction extended --max-speculative-fetches $SPEC);;
  esac
  echo "=== $ARM start $(date +%T)"
  PYTHONPATH=. .venv/bin/python experiments/run_resource_spider_ablation.py --root $ROOT \
    --variants adaptive_readiness --tag $ARM --seconds $SECS --max-transitions 120 \
    --max-browser-actions 300 --max-resource-fetches 100 --document-budget 70 \
    --script-budget 20 --stylesheet-budget 10 --asset-budget 20 \
    --max-total-http-requests 1000 --exploration-policy multidimensional $extra > $ROOT/log_$ARM.txt 2>&1
  echo "=== $ARM exit $? $(date +%T)"
done
