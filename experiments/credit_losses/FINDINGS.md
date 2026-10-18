## Findings: Fed charge-off and delinquency rates, 7 loan types, 8-quarter one-shot, 36 quarterly origins 2015Q3..2024Q2 (+ live)

Relative MASE vs AutoARIMA (<1 = better; geometric mean over 14 series = 7 loan types x {charge-off, delinquency}):

| Model | h=1 | h=2 | h=4 | h=8 | Overall | 80% coverage |
|---|---|---|---|---|---|---|
| **Timestral joint (charge-off + delinquency together)** | 0.87 | 0.86 | 0.83 | 0.79 | **0.81** | 0.82 |
| Timestral + past macro | 0.90 | 0.89 | 0.85 | 0.79 | 0.82 | 0.85 |
| Timestral (univariate) | 0.92 | 0.91 | 0.87 | 0.83 | 0.85 | 0.81 |
| Random walk | 1.08 | 1.05 | 0.94 | 0.76 | 0.86 | 0.90 |
| Timestral + known unemployment & Baa spread | 1.12 | 1.16 | 1.24 | 1.11 | 1.14 | 0.83 |
| Timestral + known macro (6 vars) | 1.17 | 1.50 | 1.35 | 1.08 | 1.19 | 0.87 |
| ARIMAX + known unemployment & Baa spread | 2.07 | 1.93 | 1.60 | 1.30 | 1.49 | 0.87 |

- **Without covariates Timestral beats AutoARIMA by ~15%**, and forecasting each loan type's charge-off and delinquency
  jointly is best (0.81; significantly better than ARIMA on 21-29% of series per horizon, never worse). Biggest wins:
  all loans 0.50, CRE 0.73, credit cards 0.75, resi mortgages 0.83. AutoARIMA is a weak baseline here: even the random
  walk beats it at 8 quarters (0.76).
- **Surprise: a known macro path hurts** (1.19), the opposite of the bank-provisions result. The cause is COVID: unemployment
  hit 13% in 2020 but charge-offs *fell* (stimulus, forbearance), so any model that maps unemployment to losses badly
  overshoots (COVID-slice MASE 5.8 vs 2.8). ARIMAX is hurt most (6.3).
- **Excluding the 2019Q2-2020Q2 origins**, known macro is better than ARIMA (0.94) but still ~10% worse than plain Timestral;
  past macro is best overall (0.77).
- **Where macro does help: the 2022-23 normalisation.** With losses rising from record lows while unemployment stayed low,
  known macro gives the lowest error of any model in that window (MASE 1.12 vs 1.60 plain Timestral, 1.91 ARIMA).
- **Intervals:** Timestral 80% bands cover 81-87%, close to nominal; ARIMA's are wide (94%).

Caveats: known paths are realised values (a perfect-foresight scenario test). Aggregate all-bank rates, not a single
portfolio; 14 series and overlapping 8-quarter windows limit DM power. COVID is a structural break for macro-to-loss links.
