#!/usr/bin/env bash
# Sequential runner for the domains-b experiments (nohup-friendly). Log: experiments/queue_b.log
cd "$(dirname "$0")/../.." || exit 1
log=experiments/queue_b.log
while pgrep -f "config experiments/earnings/config.yaml" >/dev/null; do sleep 30; done
echo "$(date) earnings run finished" >>"$log"
for c in experiments/housing/fhfa.yaml experiments/housing/zillow.yaml experiments/retail/census.yaml experiments/retail/m5.yaml; do
  out=$(grep '^output_dir:' "$c" | awk '{print $2}')
  mkdir -p "$out"
  if [ -f "$out/backtest.parquet" ]; then echo "$(date) skip $c (done)" >>"$log"; continue; fi
  echo "$(date) start $c" >>"$log"
  uv run python -m bsforecast run --config "$c" >"$out/run.log" 2>&1 && echo "$(date) done $c" >>"$log" || echo "$(date) FAILED $c" >>"$log"
done
uv run python experiments/housing/live_tampa.py >>"$log" 2>&1
echo "$(date) QUEUE_DONE" >>"$log"
