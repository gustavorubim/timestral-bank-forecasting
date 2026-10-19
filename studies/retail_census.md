# Retail, Census retail sales by kind of business (FRED, NSA, 14 categories): headline findings

Setup: monthly, 1992-2026-09 (context capped at 240 months), 36 origins every 3 months (2015-12..2024-09),
one-shot 24-month forecasts. **AutoARIMA was dropped** (seasonal m=12, h=24 too slow on the shared box); the reference
baseline is AutoETS, with seasonal naive also shown. Relative MASE vs AutoETS (<1 = better); MASE scaled by lag-12 naive.
Run on Gus, report built on the box.

| Model | h=1 | h=6 | h=12 | h=24 | Overall | 80% coverage |
|---|---|---|---|---|---|---|
| **Timestral + known-future macro + calendar** | **0.72** | **0.81** | **0.80** | **0.81** | **0.803** | 0.76 |
| Timestral, no covariates | 0.86 | 0.91 | 0.93 | 0.94 | 0.915 | 0.74 |
| Timestral + past macro | 0.79 | 0.91 | 0.94 | 0.95 | 0.921 | 0.75 |
| Timestral + calendar only (truly known) | 0.80 | 0.91 | 0.95 | 0.97 | 0.938 | 0.76 |
| AutoETS (baseline) | 1 | 1 | 1 | 1 | 1 | 0.64 |
| Seasonal naive | 2.01 | 1.32 | 1.06 | 1.12 | 1.323 | 0.54 |

- Plain Timestral beats ETS by ~9%; Diebold-Mariano significantly better on 14-21% of categories at h=1-12, never worse at h=24.
- Known-future macro (CPI inflation, unemployment, real income, **retail gasoline price**) gives the biggest gain (0.80),
  but it is concentrated where the covariate is nearly the target: **gasoline stations 0.23** (knowing the future pump price),
  food services 0.63. Without those it is ~0.9. This is a scenario test (realised macro path), not a real-time forecast.
- Calendar-only covariates (month, weekend-day and day counts) help at h=1 (0.80 vs 0.86) but not at long horizons:
  Timestral already learns the seasonal pattern from 20 years of context.
- 2022 inflation origins: known-macro MASE 1.18 vs ETS 1.62 (nominal sales track the price level).
- Strongest categories for plain Timestral: nonstore/e-commerce 0.74, clothing 0.79; weakest: building materials 1.07,
  general merchandise 1.05, total ex food services 1.02.

Best plots: `figures/retail_sales/spaghetti_sales.png`, `figures/error_by_horizon_mase.png`, `figures/help_timestral_macro_known_vs_timestral.png`.
