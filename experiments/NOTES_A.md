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

## 2026-10-18 17:07 ET (checkpoint; code pushed to main as 85e593c)
- Box CPU heavily contended (worker B jobs + mine; load ~19 on 8 cores) -> Timestral multivariate runs are slow
  (treasury timestral_joint 367 s for 41 origins).
- Electricity AutoARIMA(season 7) dropped (too slow); electricity reruns via experiments/finish_a.sh after inflation.
- 17:10 status: treasury on variant 3/7 (joint_macro_past, 20+ min), inflation on timestral (3/7). Running: treasury_curve (pid 89823, started 16:43), inflation then electricity (finish_a.sh), credit_losses after treasury.
- Auto-finisher experiments/autofinish_a.sh (log reports/autofinish_a.log) waits for all runs, writes
  reports/<d>/HEADLINE.txt + stub experiments/<d>/FINDINGS.md, rebuilds reports, commits and pushes to main.
- Remaining manual step: replace stub FINDINGS.md with narrative (numbers from HEADLINE.txt), rerun
  `python -m bsforecast report --config experiments/<d>/config.yaml`, commit, push.

## 2026-10-18 17:35 ET
- Rebased onto origin/main de41733 (history rewrite; SEC email now SEC_USER_AGENT env - not touched here).
- 8-thread Timestral under load ~30 crawled (inflation timestral 1451 s; benchmark: 1 origin 58 s @8 threads vs 22 s @2).
  Added BSF_THREADS env override (models.py) and inflation max_context 240.
- Killed inflation/credit/electricity chains; relaunched as shards: experiments/lanes_a.sh 1|2 (logs reports/lane{1,2}.log,
  per-shard logs reports/run_<d>_<shard>.log). Treasury (pid 89823) continues unsharded (5/7 models done at 17:13).
- autofinish_a.sh restarted (own pid; waits for lanes too; `report` merges shards; then HEADLINE.txt, stub FINDINGS, commit, push).
