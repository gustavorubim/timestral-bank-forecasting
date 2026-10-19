## Findings: CPI components (y/y %), 24-month one-shot, 36 origins every 3 months 2015-12..2024-09 (+ a live forecast)

Relative MASE vs AutoARIMA (<1 = better; geometric mean over 9 components):

| Model | h=1 | h=6 | h=12 | h=24 | Overall | 80% coverage |
|---|---|---|---|---|---|---|
| **Timestral + known macro (WTI, 3m/2y/10y, term spread, unemployment)** | 0.87 | 0.71 | 0.68 | **0.62** | **0.66** | 0.76 |
| Timestral + known oil only | 0.87 | 0.71 | 0.68 | 0.64 | 0.68 | 0.74 |
| ARIMAX + known WTI & unemployment | 0.94 | 0.89 | 0.86 | 0.82 | 0.85 | 0.66 |
| Timestral + past macro | 0.95 | 0.91 | 0.91 | 0.83 | 0.88 | 0.72 |
| Timestral (no covariates) | 0.99 | 0.91 | 0.92 | 0.85 | 0.89 | 0.73 |
| Random walk | 1.09 | 1.04 | 1.05 | 1.11 | 1.07 | 0.59 |

- **Plain Timestral beats AutoARIMA by ~11%**, mostly on core components (core services 0.76, medical 0.76, core 0.79);
  it is no better on energy/transportation/headline (~1.0-1.1), which are driven by oil.
- **Known oil path does almost all the work:** oil alone gets 0.68 vs 0.66 for the full panel. Energy falls to 0.38-0.40,
  transportation 0.45-0.47, headline 0.65-0.67. The full panel adds a little on shelter (0.62) and core services (0.66).
- **Timestral uses the scenario far better than ARIMAX** (0.66 vs 0.85 with the same kind of information).
- **2021-22 surge origins:** every model's error is ~2.5x normal; known macro cuts Timestral's MASE from 13.1 to 11.5,
  ARIMAX gets no help there (14.3).
- **Intervals are too narrow** for all models (74-76% for Timestral with covariates, 66-68% for ARIMA/ARIMAX).
- **Significance is weak:** 9 series and 37 overlapping origins; known-macro Timestral is significantly better on 22% of
  components at h=1, and no model is significantly better at h=24.

Caveats: known paths are realised values (perfect-foresight scenario). Context capped at the last 240 months. Fed SEP
was not added as a reference (it projects annual PCE, not monthly CPI).
