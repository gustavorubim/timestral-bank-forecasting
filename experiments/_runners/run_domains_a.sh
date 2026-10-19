#!/usr/bin/env bash
# Sequential runner for domains-a (electricity, inflation, credit losses, treasury curve).
# Usage: nohup bash experiments/_runners/run_domains_a.sh [domain ...] > outputs/domains_a_run.log 2>&1 &
set -u
PY=${PY:-python}
cd "$(dirname "$0")/../.."
doms=${*:-"treasury_curve credit_losses inflation electricity"}
for d in $doms; do
  echo "=== $d start $(date)"
  $PY -m bsforecast run --config experiments/$d/config.yaml > outputs/run_$d.log 2>&1 && echo "=== $d OK $(date)" || echo "=== $d FAILED $(date)"
done
echo ALL_DONE
