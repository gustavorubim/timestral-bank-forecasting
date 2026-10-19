#!/usr/bin/env bash
# Session-3 restart of zillow + census without AutoARIMA. Log: experiments/queue_b.log
cd "$(dirname "$0")/../.." || exit 1
log=experiments/queue_b.log
for c in experiments/housing/zillow.yaml experiments/retail/census.yaml; do
  ( out=$(grep '^output_dir:' "$c" | awk '{print $2}'); mkdir -p "$out"; echo "$(date) restart $c" >>"$log"
    uv run python -m bsforecast run --config "$c" >"$out/run.log" 2>&1 && echo "$(date) done $c" >>"$log" || echo "$(date) FAILED $c" >>"$log" ) &
done
wait
echo "$(date) RESTART_DONE" >>"$log"
