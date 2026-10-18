## Headline findings: does a CCAR-style macro panel help Timestral forecast granular bank lines?

**Caveat: scenario-style test.** The macro covariates are the **realised future paths** over each 8-quarter window
(known-future, like a CCAR/DFAST scenario), so this measures how well each model *uses* a scenario, not real-time
skill. Data: FDIC call-report sums for JPM, BAC, C and WFC (bank subsidiaries only, not full FR Y-9C), 37 lines,
38 quarterly origins from 2015Q1 to 2024Q2, one-shot 8-quarter forecasts. Full panel = 22 macro variables; compact
panel = curve level and slope, unemployment, GDP growth, Baa spread and house prices. Timestral ran with its default
symmetric averaging.

Relative MASE vs AutoARIMA (geometric mean over bank x line series; <1 = better than ARIMA):

| group | Timestral (no cov) | Timestral + full macro | Timestral + compact macro | ARIMAX (UR, curve level, Baa) |
|---|---|---|---|---|
| income (7 lines) | 0.930 | **0.873** | 0.939 | 1.106 |
| assets (18) | **0.974** | 1.093 | 1.081 | 1.159 |
| liabilities (12) | **0.972** | 1.066 | 1.062 | 1.247 |
| all 37 lines | **0.965** | 1.039 | 1.047 | 1.176 |

* **Macro helps rate- and credit-sensitive lines and hurts balance-sheet levels.** Comparing full-macro Timestral
  with plain Timestral (<1 = macro helps):
  * Biggest gains: interest expense 0.58, interest income 0.72, allowance (ALLL) 0.74, provisions 0.78,
    noninterest-bearing deposits 0.81. Those are deposit-beta, rate and credit-cycle channels.
  * Biggest losses: subordinated debt 1.39, noninterest expense 1.35, real-estate loans 1.33, CRE loans 1.32,
    total loans 1.28. Noninterest income is 1.25.
  * By group: income 0.94 (helps), assets 1.12 and liabilities 1.10 (hurt).
* **Full vs compact.** The full panel beats the compact one on income (0.87 vs 0.94 vs ARIMA). The gain comes from
  interest expense (0.49 vs 0.62) and interest income (0.65 vs 0.82), where the extra rates (prime, mortgage, fed
  funds, the curve) matter. On assets and liabilities the two panels are about equal, and both are worse than no
  covariates. So 22 covariates are not worse than 6. The problem is conditioning slow-moving, management-driven
  levels (loan books, debt issuance, expense programmes) on macro at all.
* **By horizon.** Plain Timestral beats ARIMA at every horizon (0.91 at h=1 to 0.985 at h=8). With macro, the whole
  panel goes from 0.96 at h=1 to 1.07 at h=8 vs ARIMA. Against plain Timestral it is 1.06 to 1.09 at all horizons,
  with no horizon where macro helps overall. Diebold-Mariano at h=8: full-macro Timestral is significantly worse than
  ARIMA on 22% of series and better on 4%.
* **By bank** (full macro vs plain Timestral): JPM 0.99, BAC 1.03, C 1.08, WFC 1.21. WFC's balance sheet, flat under its
  asset cap, plausibly responds least to macro.
* **Rate-regime origins** (relative MASE vs ARIMA on income lines; plain → full macro):
  * 2021Q4 (before the hikes): 1.02 → **0.72**. Knowing the rate path is decisive here, and compact gives 0.84.
  * 2015Q4 (liftoff): 0.90 → 0.87.
  * 2019Q2 (cuts) and 2020Q1 (zero lower bound): 1.01 → 1.25 and 0.86 → 0.94. At these origins macro hurts every
    group, liabilities most (1.34 and 1.40). The COVID deposit surge is the opposite of what the unemployment and GDP
    path would imply historically.
  * 2023Q2 (peak): 0.62 → 0.80. Lagged deposit repricing, as in the term-structure experiment.
* **Calibration.** 80% interval coverage is 85% with macro (both panels), 81% for plain Timestral and for ARIMA, and
  74% for ARIMAX.
* **ARIMAX** with three known-future regressors is the worst variant (1.18). It helps only interest income and expense
  and the ALLL, and it is badly off on sub debt (2.52) and RE loans (1.65).

Bottom line: with a known macro scenario, use the scenario for interest income and expense, provisions, the
allowance and deposit mix. Forecast balance-sheet volumes and noninterest lines without covariates.
