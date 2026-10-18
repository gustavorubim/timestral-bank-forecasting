#!/usr/bin/env bash
# Sharded reruns (2 lanes, BSF_THREADS=3) after CPU oversubscription made 8-thread runs crawl.
# Each step: domain shard "models...". Shards merge on `python -m bsforecast report`.
cd "$(dirname "$0")/.."
PY=${PY:-python}
export BSF_THREADS=${BSF_THREADS:-3}
step() { d=$1; s=$2; shift 2
  echo "=== $d/$s start $(date)"
  $PY -m bsforecast run --config experiments/$d/config.yaml --shard $s --models "$@" > reports/run_${d}_$s.log 2>&1 \
    && echo "=== $d/$s OK $(date)" || echo "=== $d/$s FAILED $(date)"; }
if [ "$1" = 1 ]; then
  step inflation i1 naive arima arimax_macro_known timestral
  step inflation i2 timestral_macro_past timestral_oil_known
  step electricity e1 seasonal_naive mstl timestral
else
  step inflation i3 timestral_macro_known
  step credit_losses c1 naive arima arimax_macro_known timestral timestral_joint
  step credit_losses c2 timestral_macro_past timestral_unemp_known timestral_macro_known
  step electricity e2 timestral_temp_past timestral_temp_known
fi
echo LANE_DONE
