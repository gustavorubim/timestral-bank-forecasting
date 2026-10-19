# Study: Timestral-209M vs the NY Fed DSGE (Model1002 ss104) on core US macro

Experiment: [`experiments/macro_horse/`](../experiments/macro_horse/). Full report with charts:
[`outputs/macro_horse/REPORT.md`](../outputs/macro_horse/REPORT.md). Site page: `docs/macro_horse/`.

78 expanding-window origins (2005Q1 to 2024Q2), h = 1..8 quarters. Latest-vintage pseudo-out-of-sample
(no ALFRED key). DSGE uses the published ss104 default parameters, fixed, with no re-estimation. AR(p) by BIC is
the reference (relative RMSE below 1 = better than AR).

## Bottom line (plain language)

* **GDP growth and core PCE inflation: Timestral is a bit more consistent, but it isn't a clear win.** Over 78
  quarterly starting points from 2005 to 2024, Timestral's error is 0 to 6% below a simple autoregression's (AR) at
  every horizon. The DSGE ranges from 9% better to 33% worse than AR. Excluding the COVID quarters, the DSGE trails AR
  by 4–19% on GDP; on core PCE it trails AR by 7–15% at 1–4 quarters and beats it by 7–8% at 6–8 quarters. Pitting
  Timestral against the DSGE directly, none of the Diebold-Mariano tests on GDP or core PCE is significant.
* **The DSGE did better before 2020 and much worse after.** Before COVID (target quarters up to 2019Q4), the DSGE
  beats the AR on GDP (0.90) and core PCE (0.82). That's better than Timestral on GDP (0.96) and close to it on
  core PCE (0.78). During the
  2021–23 inflation surge and after 2023, its GDP error is 1.9 to 2.4 times the AR's, and its fed funds error 1.3 to
  2.6 times. Timestral degrades much less. The post-2020 ss104 setup has COVID regimes, a flexible
  average-inflation-targeting credibility path, and no survey or expectations data after 2021, and that's where the
  fixed-parameter DSGE suffers.
* **Fed funds rate: Timestral wins clearly.** The joint Timestral (all seven series together) has 0.65–0.79 times the
  AR's error, and 0.29–0.80 times the DSGE's. The gain over the DSGE is significant at the 5% level 1 to 3 quarters
  ahead, and at the 10% level out to 6 quarters. Without
  expectations data, the unconditional DSGE pulls the policy rate quickly back toward its steady state, including
  during 2009–15, when the rate stayed at zero.
* **GDP deflator inflation: the DSGE's one long-horizon edge.** The DSGE is better 5 to 8 quarters out (0.87 vs 0.96 at 8 quarters;
  the DM test favours the DSGE at the 5% level 5 to 7 quarters ahead).
* **What the DSGE doesn't forecast.** It has no observables for headline PCE, CPI or unemployment. On those,
  Timestral beats AR and AutoARIMA (PCE and CPI 0.93–0.98, unemployment 0.6–0.85).
* **The professional forecasters (SPF) beat everyone in the first 1–2 quarters.** That's mostly an information
  advantage: the survey is taken mid-quarter with that month's data in hand. At 2 to 5 quarters ahead, Timestral is
  within about 0–6% of the SPF on GDP, PCE and CPI, but well behind it on unemployment.
* **Uncertainty bands.** Timestral's distributions score better on CRPS, a measure of probabilistic accuracy, but
  are slightly too narrow (80% bands catch 72–83% of outcomes on average, depending on the variable). The DSGE's bands are too wide on GDP and core PCE
  (80% bands catch 88–94%), and its post-2020 densities are unstable.
* **Worth adding to Econer's notes? Yes, as a benchmark row, not a replacement.** A Timestral line next to the DSGE
  path is a cheap check, taking seconds per run on a CPU. It is most informative for the policy-rate path and for the
  variables the DSGE lacks (headline PCE, CPI, unemployment). It shouldn't be presented as more accurate than the
  DSGE on GDP or core PCE, because this backtest doesn't support that.


## Headline relative RMSE vs AR

| Variable | h | DSGE ss104 | best fair Timestral | AR = 1 (AR RMSE, pp) | SPF | AutoARIMA |
|---|---|---|---|---|---|---|
| Real GDP growth | 1 | 0.91 | 0.97 (timestral) | 1 (6.61) | 0.35 | 1.00 |
| Real GDP growth | 4 | 1.03 | 0.99 (timestral) | 1 (5.75) | 0.99 | 1.01 |
| Real GDP growth | 8 | 1.01 | 0.99 (timestral) | 1 (5.74) |  | 1.00 |
| Core PCE inflation | 1 | 1.05 | 0.97 (timestral_mv) | 1 (0.86) | 0.92 | 1.01 |
| Core PCE inflation | 4 | 0.97 | 0.94 (timestral_mv) | 1 (1.23) | 0.99 | 1.04 |
| Core PCE inflation | 8 | 0.96 | 0.97 (timestral_mv) | 1 (1.45) |  | 1.07 |
| PCE inflation | 1 |  | 0.98 (timestral_cov) | 1 (1.82) | 0.62 | 1.06 |
| PCE inflation | 4 |  | 0.93 (timestral_cov) | 1 (2.27) | 0.90 | 1.09 |
| PCE inflation | 8 |  | 0.94 (timestral_cov) | 1 (2.36) |  | 1.11 |
| CPI inflation | 1 |  | 0.98 (timestral_cov) | 1 (2.57) | 0.58 | 1.03 |
| CPI inflation | 4 |  | 0.94 (timestral_cov) | 1 (2.99) | 0.88 | 1.07 |
| CPI inflation | 8 |  | 0.93 (timestral_cov) | 1 (3.01) |  | 1.12 |
| GDP deflator inflation | 1 | 1.03 | 0.99 (timestral_mv) | 1 (1.26) |  | 1.03 |
| GDP deflator inflation | 4 | 0.96 | 1.01 (timestral_mv) | 1 (1.79) |  | 1.09 |
| GDP deflator inflation | 8 | 0.87 | 0.96 (timestral_mv) | 1 (2.20) |  | 1.14 |
| Fed funds rate | 1 | 2.26 | 0.65 (timestral_mv) | 1 (0.41) |  | 0.94 |
| Fed funds rate | 4 | 1.56 | 0.75 (timestral_mv) | 1 (1.49) |  | 0.95 |
| Fed funds rate | 8 | 0.99 | 0.79 (timestral_mv) | 1 (2.55) |  | 0.88 |
| Unemployment rate | 1 |  | 0.60 (timestral) | 1 (1.91) | 0.21 | 0.98 |
| Unemployment rate | 4 |  | 0.59 (timestral) | 1 (2.90) | 0.52 | 0.92 |
| Unemployment rate | 8 |  | 0.85 (timestral) | 1 (2.53) |  | 0.98 |

Excluding COVID target quarters 2020Q1-2021Q2:

| Variable | h | DSGE ss104 | best fair Timestral | SPF | AutoARIMA |
|---|---|---|---|---|---|
| Real GDP growth | 1 | 1.07 | 1.01 (timestral) | 0.80 | 1.05 |
| Real GDP growth | 4 | 1.06 | 0.97 (timestral) | 0.96 | 1.03 |
| Real GDP growth | 8 | 1.07 | 0.95 (timestral) |  | 0.99 |
| Core PCE inflation | 1 | 1.09 | 0.92 (timestral_mv) | 0.98 | 1.00 |
| Core PCE inflation | 4 | 1.07 | 0.94 (timestral_mv) | 1.06 | 1.03 |
| Core PCE inflation | 8 | 0.93 | 0.96 (timestral_mv) |  | 1.07 |
| PCE inflation | 1 |  | 0.99 (timestral_cov) | 0.61 | 1.06 |
| PCE inflation | 4 |  | 0.93 (timestral_cov) | 0.91 | 1.10 |
| PCE inflation | 8 |  | 0.93 (timestral_cov) |  | 1.12 |
| CPI inflation | 1 |  | 0.99 (timestral_cov) | 0.58 | 1.05 |
| CPI inflation | 4 |  | 0.95 (timestral_cov) | 0.89 | 1.08 |
| CPI inflation | 8 |  | 0.93 (timestral_cov) |  | 1.13 |
| GDP deflator inflation | 1 | 1.06 | 0.95 (timestral_mv) |  | 1.04 |
| GDP deflator inflation | 4 | 1.02 | 1.02 (timestral_mv) |  | 1.09 |
| GDP deflator inflation | 8 | 0.84 | 0.96 (timestral_mv) |  | 1.14 |
| Fed funds rate | 1 | 2.28 | 0.66 (timestral_mv) |  | 0.94 |
| Fed funds rate | 4 | 1.65 | 0.75 (timestral_mv) |  | 0.97 |
| Fed funds rate | 8 | 1.00 | 0.79 (timestral_mv) |  | 0.91 |
| Unemployment rate | 1 |  | 0.78 (timestral) | 0.54 | 1.01 |
| Unemployment rate | 4 |  | 0.76 (timestral) | 0.64 | 1.06 |
| Unemployment rate | 8 |  | 0.75 (timestral) |  | 0.98 |

