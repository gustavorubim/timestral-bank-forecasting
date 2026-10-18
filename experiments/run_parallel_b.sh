#!/usr/bin/env bash
# Parallel runner (session 2): small domains now, M5 after earnings finishes. Log: experiments/queue_b.log
cd "$(dirname "$0")/.." || exit 1
log=experiments/queue_b.log
run() {
  c=$1; out=$(grep '^output_dir:' "$c" | awk '{print $2}'); mkdir -p "$out"
  echo "$(date) start $c" >>"$log"
  uv run python -m bsforecast run --config "$c" >"$out/run.log" 2>&1 && echo "$(date) done $c" >>"$log" || echo "$(date) FAILED $c" >>"$log"
}
run experiments/housing/fhfa.yaml &
run experiments/housing/zillow.yaml &
run experiments/retail/census.yaml &
while pgrep -f "config experiments/earnings/config.yaml" >/dev/null; do sleep 20; done
echo "$(date) earnings finished" >>"$log"
run experiments/retail/m5.yaml &
wait
uv run python experiments/housing/live_tampa.py >>"$log" 2>&1
echo "$(date) QUEUE_DONE" >>"$log"
