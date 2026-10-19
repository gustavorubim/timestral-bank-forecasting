# Top-4 banks: aggregate lines (Timestral vs AutoARIMA)

Setup: FDIC call-report aggregation of JPM, BAC, C and WFC (bank subsidiaries only, a Y-9C substitute), 15 aggregate
lines x 4 banks, 24 rolling origins 2018Q3-2024Q2 (+ live), one-shot 8-quarter forecasts, plus FRED macro covariates.

## Headline results (top-4 BHCs, 24 origins 2018Q3–2024Q2, 15 lines × 4 banks, h = 1..8)

Full report: [`outputs/y9c_top4/REPORT.md`](../outputs/y9c_top4/REPORT.md). Relative MASE is the geometric mean over series
of MASE(model) / MASE(AutoARIMA), so a value below 1 means the model beats ARIMA.

| h | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | overall |
|---|---|---|---|---|---|---|---|---|---|
| timestral (univariate, zero-shot) | **0.91** | 0.94 | 0.97 | 0.98 | 1.00 | 1.01 | 1.02 | 1.03 | 0.99 |
| timestral_mv (all lines of a bank jointly) | 0.90 | 0.95 | 0.97 | 0.98 | 0.98 | 0.99 | 0.98 | 0.99 | **0.975** |
| timestral_cov (macro, past-only) | 0.89 | 0.94 | 0.96 | 0.98 | 0.99 | 1.01 | 1.02 | 1.03 | 0.99 |
| timestral_cov_oracle (realised macro path) | 0.94 | 1.06 | 1.09 | 1.13 | 1.13 | 1.15 | 1.17 | 1.15 | 1.12 |
| arimax_oracle (UR, FF, Baa spread) | 1.22 | 1.23 | 1.21 | 1.20 | 1.18 | 1.18 | 1.17 | 1.11 | 1.18 |

* **Timestral is clearly better at short horizons and only matches ARIMA at long ones.** It is about 10% better at
  h=1 and 22% of series are DM-significant better there (3% worse), but by h=6–8 it is at parity or slightly worse.
  Its head-to-head win rate falls from 57% at h=1 to 48% at h=8.
* **Joint (multivariate) Timestral is the most robust one-shot 8q model.** It stays at or below ARIMA at every horizon,
  and on income lines it is 8% better even at h=8.
* By line: Timestral is strongest on **NII and NIM** (0.65–0.70 at h=1), **nonint expense** (0.82 at h=8), the
  asset lines and net income. It is weakest on **provisions** (1.33 at h=8), **equity**, ROA and efficiency at long
  horizons, where it mean-reverts less sharply than ARIMA.
* By bank: Timestral wins clearly on **WFC** (0.86, beating ARIMA on 80% of lines, likely helped by the asset cap's
  flat balance sheet). It is near parity on **C** (0.98) and loses on **JPM/BAC** (1.07) at h ≥ 4, where strong trend growth
  favours ARIMA's drift.
* **COVID stress** (origins 2019Q2–2020Q2): every model breaks down (MASE roughly doubles). ARIMA holds up slightly better
  (Timestral 1.06× ARIMA vs 0.96× in normal periods). Neither unconditional model can foresee the deposit surge or the
  provision spike and its release.
* **Giving the models the realised macro path did not help** in this setup, for either Timestral or ARIMAX. Macro is
  a weak, unstable driver of these aggregate levels over 2018–2024: deposits rose with QE as unemployment spiked. Naive
  regressions on 70–90 quarters overfit.
* Calibration: 80% intervals cover about 75–76% for both Timestral and ARIMA, so they are slightly too narrow.
* Earnings bridge (NII + nonint income − nonint expense − provisions vs net income): separately forecast lines from
  multivariate Timestral are the most coherent of the learned models. Their median excess gap vs actual is 10pp, against
  19pp for univariate Timestral and 26pp for ARIMA.
