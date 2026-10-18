#!/usr/bin/env bash
# Waits for all domains-a runs, writes HEADLINE.txt + stub FINDINGS.md (if none), rebuilds reports,
# commits reports/<domain> and pushes to main (pull --rebase, never force). Log: reports/autofinish_a.log
cd "$(dirname "$0")/.."
PY=${PY:-python}
while pgrep -f "run_domains_a.sh|/finish_a.sh|lanes_a.sh|experiments/(treasury_curve|credit_losses|inflation|electricity)/config.yaml" >/dev/null; do sleep 30; done
echo "runs finished $(date)"
for d in treasury_curve credit_losses inflation electricity; do
  ls reports/$d/backtest*.parquet >/dev/null 2>&1 || { echo "MISSING $d"; continue; }
  $PY -m bsforecast report --config experiments/$d/config.yaml > reports/$d/report.log 2>&1  # merges shards
  $PY experiments/headline.py reports/$d > reports/$d/HEADLINE.txt 2>&1
  if [ ! -f experiments/$d/FINDINGS.md ]; then
    { echo "## Headline numbers (auto-generated; narrative pending)"; echo; echo '```'; cat reports/$d/HEADLINE.txt; echo '```';
      echo; echo "Known-future variants use the realised covariate path (perfect-foresight scenario test), not real-time forecasts."; } > experiments/$d/FINDINGS.md
  fi
  $PY -m bsforecast report --config experiments/$d/config.yaml > reports/$d/report.log 2>&1 && echo "report $d ok"
done
git add reports/treasury_curve reports/credit_losses reports/inflation reports/electricity experiments 2>/dev/null
git reset -q reports/*/report.log 2>/dev/null
git commit -qm "domains-a: backtest results + reports (electricity, inflation, credit losses, treasury curve)" && \
  git pull -q --rebase origin main && git push -q origin HEAD:main && echo "PUSHED $(git rev-parse --short HEAD)"
echo AUTOFINISH_DONE
