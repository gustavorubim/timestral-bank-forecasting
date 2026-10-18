#!/usr/bin/env bash
# Chain 2 (after arima on daily load proved too slow under CPU contention): inflation, then electricity w/o AutoARIMA.
cd "$(dirname "$0")/.."
PY=${PY:-python}
echo "=== inflation start $(date)"
$PY -m bsforecast run --config experiments/inflation/config.yaml > reports/run_inflation.log 2>&1 && echo "=== inflation OK $(date)" || echo "=== inflation FAILED $(date)"
echo "=== electricity start $(date)"
$PY -m bsforecast run --config experiments/electricity/config.yaml --models seasonal_naive mstl timestral timestral_temp_past timestral_temp_known > reports/run_electricity.log 2>&1 && echo "=== electricity OK $(date)" || echo "=== electricity FAILED $(date)"
echo CHAIN2_DONE
