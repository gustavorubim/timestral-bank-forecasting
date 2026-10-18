## Findings: Treasury curve (3m..30y), 8-quarter one-shot, 41 quarterly origins 2014Q3..2024Q3

Relative MASE vs random walk (<1 = better; geometric mean over the 10 maturities):

| Model | h=1 | h=2 | h=4 | h=8 | Overall | 80% coverage |
|---|---|---|---|---|---|---|
| **Timestral joint + known fed funds path** | 0.67 | 0.59 | 0.42 | **0.30** | **0.39** | 0.86 |
| Timestral joint + known unemployment & core CPI | 0.80 | 0.79 | 0.78 | 0.77 | 0.78 | 0.84 |
| Timestral joint + past macro | 0.86 | 0.88 | 0.91 | 0.95 | 0.93 | 0.73 |
| Timestral joint (no covariates) | 0.87 | 0.89 | 0.92 | 0.97 | 0.94 | 0.71 |
| Timestral univariate | 0.85 | 0.87 | 0.93 | 0.98 | 0.95 | 0.71 |
| AutoARIMA | 0.90 | 0.93 | 1.00 | 1.09 | 1.03 | 0.81 |

- **Without covariates Timestral beats the random walk** (0.94 overall), which is a notoriously hard benchmark for
  yields; AutoARIMA does not (1.03). The gain is all at the short end (3m 0.69, 1y 0.76, 2y 0.86); at 10y-30y
  every model loses to the random walk (1.11-1.19).
- **Joint (multivariate) vs univariate:** only marginal (0.936 vs 0.947); it helps the front end slightly and the long end not at all.
- **Known fed funds path is by far the strongest input:** error falls 61% overall and 70% at 8 quarters
  (3m 0.12, 2y 0.28, 5y 0.46, 10y 0.75), and the gain grows with horizon. It transmits correctly along the curve:
  large at the front, fading to ~1 at 20-30y. In the 2022 hiking window MASE drops from 5.7 to 1.9.
- **Known macro path (unemployment, core CPI)** helps too (0.78) - the model has learned a Taylor-rule-like link -
  but not in the 2022 hikes (5.8 vs 5.7): inflation took time to show up in policy rates.
- **Past-only macro** adds almost nothing (0.93 vs 0.94).
- **Intervals:** without covariates the 80% bands cover only ~71% (too narrow); with the policy path they are about right (86%).
- **Significance:** only 10 series (one curve), so DM tests have little power; Timestral joint is significantly better than
  random walk on 30-40% of maturities at h=1 and h=8, never significantly worse.

Caveat: "known" variants are given the realised path over the forecast window (perfect-foresight scenario). The fed funds
result shows how well the model maps a policy scenario onto the curve, not real-time skill. Fed funds futures history is not
freely available, so a market-implied comparison was skipped.
