#!/bin/zsh
# usage: experiments/run_root_cause_ablation.sh ROOT SECONDS ARM...
# All arms share the frozen combined configuration D (shared_http allocation,
# extended extraction, 25 speculative fetches) and identical budgets; each arm
# adds only the listed deterministic repair.
#   D0  frozen combined baseline (legacy frontier, content-length reader)
#   P   persistent frontier (state machine, lossless resume, depth relaxation); P2 = P after the lane fix
#   PC  P + separately bounded passive document depth (6)
#   PB  P + budget-aware deepening (hard max depth 8)
#   E   best depth option + standards extraction + bounded streaming reader; E2 = E after the speculative-lane fix
#   E/E2 depth flags: E_DEPTH_FLAGS was previously read from the caller's
#   environment and was undefined in a clean shell. The default below is the
#   value recorded in the saved E2 run (root_cause_ablation/adaptive_readiness_E2_r1
#   experiment_config.json); override it explicitly if needed.
cd "$(dirname "$0")/.."
ROOT=$1; SECS=$2; shift 2
: ${E_DEPTH_FLAGS:="--passive-document-max-depth 6 --budget-aware-deepening --hard-max-resource-depth 8"}
echo "E_DEPTH_FLAGS=$E_DEPTH_FLAGS"
for ARM in "$@"; do
  base=${ARM%%_*}
  extra=()
  case $base in
    D0) extra=();;
    P|P2)  extra=(--resource-frontier-model persistent);;
    PC) extra=(--resource-frontier-model persistent --passive-document-max-depth 6);;
    PB) extra=(--resource-frontier-model persistent --budget-aware-deepening --hard-max-resource-depth 8);;
    E|E2)  extra=(--resource-frontier-model persistent ${=E_DEPTH_FLAGS} --html-extraction standards --response-body-reader bounded_stream);;
  esac
  html=(--html-extraction extended)
  [[ $base == E || $base == E2 ]] && html=()
  echo "=== $ARM start $(date +%T)"
  PYTHONPATH=. .venv/bin/python experiments/run_resource_spider_ablation.py --root $ROOT \
    --variants adaptive_readiness --tag $ARM --seconds $SECS --max-transitions 120 \
    --max-browser-actions 300 --max-resource-fetches 100 --document-budget 70 \
    --script-budget 20 --stylesheet-budget 10 --asset-budget 20 \
    --max-total-http-requests 1000 --exploration-policy multidimensional \
    --resource-allocation shared_http --max-speculative-fetches 25 $html $extra > $ROOT/log_$ARM.txt 2>&1
  echo "=== $ARM exit $? $(date +%T)"
done
