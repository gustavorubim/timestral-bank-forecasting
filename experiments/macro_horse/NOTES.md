# macro_horse checkpoint notes

Session 1 (2026-10-18 ~20:00 ET)
- nydsge-python cloned fresh to /workspace/nydsge-horse (main e2ff029). /workspace/nydsge untouched.
- DSGE runner: experiments/macro_horse/dsge_runner.py -> data/processed/macro_horse/dsge_forecasts.csv
  (78 origins 2005Q1..2024Q2, ~1 s/origin; variants dsge [frozen regime at T] and dsge_sched [ss104 dated schedule]).
- No FRED_API_KEY in env -> no ALFRED vintages; latest-vintage pseudo-OOS for all models.
- SPF medians (Philadelphia Fed medianGrowth/medianLevel.xlsx) -> data/raw/spf/*.csv -> data/processed/macro_horse/spf.csv.
- Timestral has no fine-tuning API in the installed package -> fine-tuning skipped.
- Non-DSGE backtest: experiments/macro_horse/run_backtest.py -> data/processed/macro_horse/forecasts.parquet
- Backtest done (CLI `macro-horse run`, ~5 min, BSF_THREADS=6). Report: `macro-horse report` -> outputs/macro_horse.
- Headline DSGE = frozen regime for origins < 2020Q1, dated ss104 schedule from 2020Q1 (frozen COVID variance
  regimes gave GDP sd > 150pp). dsge_frozen / dsge_sched kept as sensitivities.
- Site page docs/macro_horse rebuilt on branch macro-horse-race only; studies/macro_horse.md added.
- State: COMPLETE (session 1, ~20:40 ET). PR opened from macro-horse-race, not merged.
