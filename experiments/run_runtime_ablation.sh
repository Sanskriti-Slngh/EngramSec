#!/bin/zsh
# usage: experiments/run_runtime_ablation.sh APP ROOT SECONDS ARM...
# APP: crawlmaze | transfer-library | js-heavy | heldout-shop
# START_PATH (env, transfer-library only): start below the root, e.g. /desk
# All arms use identical budgets (SECONDS, 300 browser actions, 120 transitions,
# 1 worker, 1,000 shared HTTP requests of which 30% are held for replay,
# typed total 100, caps 70/20/10/20).
#   D0    frozen combined baseline (legacy frontier, content-length reader)
#   E2NS  E2 with b4a9a40 cookie semantics (passive Set-Cookie dropped)
#   A     E2: repaired deterministic pipeline (passive cookie sync on)
#   B     A + DevTools listener observation (candidates; revisions as evidence only)
#   C     A + listener observation + safe handler-revision re-exploration
cd "$(dirname "$0")/.."
APP=$1; ROOT=$2; SECS=$3; shift 3
E2=(--resource-frontier-model persistent --passive-document-max-depth 6 --budget-aware-deepening
    --hard-max-resource-depth 8 --html-extraction standards --response-body-reader bounded_stream)
post=()
[[ $APP == heldout-shop ]] && post=(--allow-post-forms)
for ARM in "$@"; do
  base=${ARM%%_*}
  case $base in
    D0)   extra=(--html-extraction extended);;
    E2NS) extra=($E2 --no-passive-cookie-sync);;
    A)    extra=($E2);;
    B)    extra=($E2 --runtime-listener-observation observe);;
    C)    extra=($E2 --runtime-listener-observation revisit);;
    *)    echo "unknown arm $ARM"; exit 2;;
  esac
  echo "=== $ARM start $(date +%T)"
  start=()
  [[ -n $START_PATH ]] && start=(--start-path $START_PATH)
  PYTHONPATH=. .venv/bin/python experiments/run_resource_spider_ablation.py --app $APP $post $start --root $ROOT \
    --variants adaptive_readiness --tag $ARM --seconds $SECS --max-transitions 120 \
    --max-browser-actions 300 --max-resource-fetches 100 --document-budget 70 \
    --script-budget 20 --stylesheet-budget 10 --asset-budget 20 \
    --max-total-http-requests 1000 --exploration-policy multidimensional \
    --resource-allocation shared_http --max-speculative-fetches 25 --http-verification-reserve 0.3 $extra > $ROOT/log_$ARM.txt 2>&1
  echo "=== $ARM exit $? $(date +%T)"
done
