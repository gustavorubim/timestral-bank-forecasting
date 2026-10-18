# NOTES_A (domains-a worker checkpoint log: electricity, inflation, credit losses, treasury curve)

## 2026-10-18 16:43 ET
- Worktree /workspace/tbf-domains-a, branch domains-a. Python = main repo venv
  (`PY=/workspace/timestral-bank-forecasting/.venv/bin/python PYTHONPATH=src`).
- Shared-code edits (backward compatible): backtest.max_context; models auto_ets / mstl;
  plots.spaghetti_targets + generic horizon titles; plots.id_heatmaps / spaghetti_targets_grid; fan_grid window = horizon.
- Data built: data/processed/{electricity,inflation,credit_losses,treasury_curve}.parquet
  (loaders: python -m bsforecast.data.<domain>). EIA-930 bulk CSVs 2022..2026H2, Open-Meteo archive daily temps.
- Runs: nohup bash experiments/run_domains_a.sh > reports/domains_a_run.log (sequential; per-domain logs reports/run_<d>.log).
  If cut off: check which domains printed OK, rerun the rest with `bash experiments/run_domains_a.sh <domain>`,
  then write experiments/<d>/FINDINGS.md and `python -m bsforecast report --config experiments/<d>/config.yaml`.
