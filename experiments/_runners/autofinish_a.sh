#!/usr/bin/env bash
# Waits for all domains-a runs, writes HEADLINE.txt + stub FINDINGS.md (if none), rebuilds reports,
# commits outputs/<domain> and pushes to main (pull --rebase, never force). Log: outputs/autofinish_a.log
cd "$(dirname "$0")/../.."
PY=${PY:-python}
while pgrep -f "run_domains_a.sh|/finish_a.sh|lanes_a.sh|experiments/(treasury_curve|credit_losses|inflation|electricity)/config.yaml" >/dev/null; do sleep 30; done
echo "runs finished $(date)"
for d in treasury_curve credit_losses inflation electricity; do
  ls outputs/$d/backtest*.parquet >/dev/null 2>&1 || { echo "MISSING $d"; continue; }
  $PY -m bsforecast report --config experiments/$d/config.yaml > outputs/$d/report.log 2>&1  # merges shards
  $PY experiments/_runners/headline.py outputs/$d > outputs/$d/HEADLINE.txt 2>&1
  if [ ! -f studies/$d.md ]; then
    { echo "## Headline numbers (auto-generated; narrative pending)"; echo; echo '```'; cat outputs/$d/HEADLINE.txt; echo '```';
      echo; echo "Known-future variants use the realised covariate path (perfect-foresight scenario test), not real-time forecasts."; } > studies/$d.md
  fi
  $PY -m bsforecast report --config experiments/$d/config.yaml > outputs/$d/report.log 2>&1 && echo "report $d ok"
done
git add outputs/treasury_curve outputs/credit_losses outputs/inflation outputs/electricity experiments 2>/dev/null
git reset -q outputs/*/report.log 2>/dev/null
git commit -qm "domains-a: backtest results + reports (electricity, inflation, credit losses, treasury curve)" && \
  git pull -q --rebase origin main && git push -q origin HEAD:main && echo "PUSHED $(git rev-parse --short HEAD)"
echo AUTOFINISH_DONE
