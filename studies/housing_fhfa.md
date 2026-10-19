# Housing, FHFA metro HPI (quarterly, 22 metros incl. Tampa): headline findings

Setup: FHFA all-transactions HPI, 1991Q1-2026Q2, 37 rolling origins (2015Q2-2024Q2) + a live origin (2026Q2),
one-shot 8-quarter forecasts. Relative MASE vs AutoARIMA (<1 = better).

| Model | h=1 | h=2 | h=4 | h=8 | Overall | 80% coverage |
|---|---|---|---|---|---|---|
| **Timestral + known-future macro** | 1.03 | 0.95 | **0.84** | 0.79 | **0.825** | **0.80** |
| Timestral, no covariates | 1.01 | 0.96 | 0.87 | 0.79 | 0.833 | 0.79 |
| Timestral + past macro | 1.03 | 0.98 | 0.89 | 0.80 | 0.844 | 0.78 |
| AutoETS | 1.17 | 1.08 | 0.91 | **0.77** | 0.845 | 0.63 |
| AutoARIMA (baseline) | 1 | 1 | 1 | 1 | 1 | 0.58 |
| Seasonal naive | 6.20 | 3.21 | 1.59 | 1.32 | 1.868 | 0.38 |

- Timestral ties ARIMA one quarter ahead and wins by ~20% at 8 quarters; it is the only family with calibrated 80% bands
  (79-80% vs ARIMA 58%, ETS 63%).
- Known-future mortgage rate, unemployment and income help only slightly overall (0.825 vs 0.833); the edge is at h=4
  (DM significantly better on 18% of metros at h=4). House prices are dominated by their own momentum.
- Rate shock 2022 origins: ARIMA collapses (MASE 12.3), Timestral 7.6, ETS 6.9 - ARIMA extrapolated the 2021 boom.
- Tampa: Timestral 0.73 vs ARIMA (ETS 1.12). Biggest Timestral wins: Austin 0.61, Denver 0.67, Phoenix 0.70, Nashville 0.73.
- Known-future = realised macro path (scenario test). Covariates are national, not metro-level.
- Live Tampa forecast from 2026Q2 (FHFA HPI 516.6): Timestral median +2.6% by 2028Q2 (80% band 487-564); with flat macro +2.8%; ARIMA -2.2%; ETS +9.1%. Plot: `outputs/housing/figures/live_tampa.png` (Zillow panels pending).

Best plots: `figures/house_prices/spaghetti_hpi.png`, `figures/error_by_horizon_mase.png`, `figures/coverage_by_horizon.png`.
