# Housing, Zillow ZHVI home values + ZORI rents (monthly, 22 metros incl. Tampa): headline findings

Setup: 2000-01..2026-09 (ZORI from 2015), 31 origins every 2 months (2019-2024) + a live origin (2026-09),
one-shot 24-month forecasts. **AutoARIMA was dropped** (seasonal m=12, h=24 too slow on the shared box); the reference
baseline is AutoETS, with seasonal naive also shown. Relative MASE vs AutoETS (<1 = better). Run on Gus, report built on the box.

| Model | h=1 | h=6 | h=12 | h=24 | Overall | 80% coverage |
|---|---|---|---|---|---|---|
| **Timestral + past macro** | **0.60** | **0.83** | **0.91** | **0.86** | **0.869** | 0.73 |
| Timestral, no covariates | 0.60 | 0.85 | 0.95 | 0.87 | 0.887 | 0.72 |
| Timestral + known-future macro | 0.63 | 0.84 | 0.93 | 0.89 | 0.892 | 0.73 |
| AutoETS (baseline) | 1 | 1 | 1 | 1 | 1 | 0.38 |
| Seasonal naive | 13.5 | 2.18 | 1.25 | 1.08 | 1.576 | 0.42 |

- Timestral beats ETS by 11-13% overall and by 40% one month ahead; ETS bands are far too narrow (38% coverage).
- Rents gain more than values: ZORI 0.83-0.85 vs ZHVI 0.91-0.94 for the macro variants.
- Known-future mortgage rate / unemployment / income does not beat past-only macro: house values and rents follow
  their own momentum; the realised macro path (scenario test) adds little.
- Tampa (vs ETS): ZHVI 0.85-0.88, ZORI 0.80-0.82 for the macro variants.
- Live Tampa from 2026-09: ZHVI $356.8k -> Timestral median $356.0k by 2028-09 (-0.2%, 80% band 323-381k); ETS -2.1%.
  ZORI $1,991 -> $2,018 (+1.4%). Plot: `outputs/housing/figures/live_tampa.png`.

Best plots: `figures/values_and_rents/spaghetti_zori.png`, `figures/values_and_rents/spaghetti_zhvi.png`, `figures/error_by_horizon_mase.png`.
