# Retail, M5 Walmart unit sales (10 stores x 7 departments = 70 daily series): headline findings

Setup: daily 2013-01-01..2016-05-22, 24 origins every 14 days, one-shot 28-day forecasts. **AutoARIMA was dropped**
(did not finish one origin in 10 min); baseline = seasonal naive (last week), AutoETS also shown. MASE scaled by lag-7 naive.
Data: original Kaggle M5 files via the Hugging Face mirror `kashif/M5`. Run on the box in 3 parallel shards.

| Model | day 1 | day 7 | day 14 | day 28 | Overall | 80% coverage |
|---|---|---|---|---|---|---|
| **Timestral + known calendar (SNAP, events, Christmas, day-of-week)** | 0.62 | **0.70** | 0.68 | 0.78 | **0.675** | 0.80 |
| Timestral + calendar + relative price index | **0.61** | 0.71 | 0.68 | 0.78 | 0.677 | 0.79 |
| Timestral, no covariates | 0.64 | 0.72 | **0.67** | **0.75** | 0.696 | 0.80 |
| AutoETS | 0.69 | 0.83 | 0.82 | 0.82 | 0.824 | 0.83 |
| Seasonal naive (baseline) | 1 | 1 | 1 | 1 | 1 | 0.90 |

- Plain Timestral is ~30% better than seasonal naive and ~16% better than AutoETS; Diebold-Mariano significantly better
  than seasonal naive on 49% of series at day 1, never worse. Its 80% bands are well calibrated (80%).
- Calendar covariates are genuinely known in advance (not a scenario test) and help modestly (0.675 vs 0.696), mostly
  in the first two weeks; at day 28 plain Timestral is slightly better. Adding the store x department price index adds nothing.
- Wins are broad across stores and departments (most series 0.55-0.85); FOODS_2 at CA_3/CA_1 are the best (~0.52-0.57).

Best plots: `figures/store_dept_units/spaghetti_units.png`, `figures/error_by_horizon_mase.png`, `figures/help_timestral_calendar_known_vs_timestral.png`.
