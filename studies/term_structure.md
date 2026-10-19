## Headline findings: does knowing the Treasury curve help forecast interest income and expense?

Setup: 4 BHCs (FDIC call-report aggregation), targets are total interest income (`INTINC`), total interest expense
(`EINTEXP`) and NII. At build time the panel checks that INTINC − EINTEXP = NII (max relative gap 1.6e-6). There are 38
quarterly origins from 2015Q1 to 2024Q2, each with a one-shot 8-quarter forecast. The 10-point CMT curve (3m–30y,
quarterly averages, with 20y/30y gaps filled through spreads) is the covariate. *Known-future* means the **realised**
curve over the forecast window, a scenario/oracle setup like stress testing, not a real-time forecast.

Relative MASE vs AutoARIMA (geometric mean over 4 banks; <1 = better):

| variant | interest expense | interest income | NII | all, h=1 | all, h=8 |
|---|---|---|---|---|---|
| Timestral, no covariates | 0.86 | 0.90 | 0.97 | 0.74 | 0.95 |
| Timestral, past-only curve | 0.75 | 0.80 | 0.95 | 0.64 | 0.89 |
| **Timestral, known-future curve** | **0.51** | **0.58** | 0.88 | 0.60 | **0.66** |
| Timestral, known-future level/slope/curvature | 0.52 | 0.61 | 0.89 | 0.58 | 0.70 |
| ARIMAX, known-future level + slope | 0.69 | 0.86 | 1.27 | 1.01 | 0.88 |

* **Yes, the known curve helps interest expense, and the help grows with horizon, as deposit-beta lags imply.**
  Against the same model without covariates, the known curve cuts interest-expense MASE by 40% overall: 26% at h=1,
  rising to 44% at h=8. For interest income the cut is 35%; for NII it is only 9%. In NII the rate effects on income
  and expense largely offset.
* Three factors (level/slope/curvature) recover almost all of the full-curve gain. The full curve is marginally better.
* The past-only curve already helps (−12% on expense), so Timestral uses the *recent* rate path as a leading
  indicator even without a scenario.
* **2021Q4, just before the hikes, is the defining case.** Unconditional models (ARIMA and plain Timestral) project flat
  expense, while the known-curve model gets the direction and roughly half the size of the surge. Interest-expense MASE
  there is 6.9 vs 15.1 for ARIMA and 15.5 for plain Timestral. It still under-predicts how fast expense rose.
* **2023Q2, the rate peak, is the exception.** Knowing the curve *hurts* (expense MASE 4.5 vs 2.2 for plain Timestral).
  Rates plateaued and then fell, but deposit costs kept repricing upward with a lag. The model maps the flat-to-lower
  curve into falling expense too early. That is the deposit-beta lag working against a level-only mapping.
* 2019Q2 (cuts) and 2020Q1 (zero lower bound): the known curve gets the direction of the expense collapse right, while
  ARIMA and plain Timestral extrapolate the rise. All models under-predict how fast deposit costs fell.
* ARIMAX with the same oracle information helps expense (0.69) but hurts NII (1.27). Linear regressors on levels are a
  much weaker way to use the scenario than Timestral's known-covariate conditioning.
* **Calibration:** with the known curve, 80% bands cover 79% (expense) / 89% (income) / 86% (NII). Without it, interest
  income and expense coverage is only 62–69%: ARIMA and plain Timestral bands are too narrow through the regime changes.
* **Diebold-Mariano:** at h=1 most variants beat ARIMA significantly on 58–83% of series. Beyond h=2 there are few
  significant results (only 4 series per line and 38 overlapping origins, so power is low). Read the point estimates
  above as indicative.
