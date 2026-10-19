# Macro horse race: Timestral-209M vs the NY Fed DSGE (Model1002 ss104)

**Question.** Does the zero-shot time-series foundation model Timestral-209M forecast core US macro variables better
than the NY Fed DSGE (Model1002, subspec ss104, as ported in `gustavorubim/nydsge-python`) over 1 to 8 quarters?

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

## Design

| Item | Choice |
|---|---|
| Targets | Real GDP growth, core PCE, headline PCE, CPI and GDP deflator inflation (annualised quarterly log rates, %); fed funds rate and unemployment (quarterly averages, levels) |
| Origins | 78 quarterly expanding-window origins; last observed quarter T from 2005Q1 to 2024Q2; forecasts for T+1..T+8 |
| Data vintage | **Latest vintage, pseudo-out-of-sample, the same for every model.** There's no `FRED_API_KEY`, so no ALFRED real-time vintages. GDP, GDP deflator, core PCE, fed funds and the 10-year yield come from the same FRED snapshot (2026-10-06) that the nydsge port uses. Headline PCE, CPI, unemployment, WTI oil and the 3-month bill were fetched from FRED on 2026-10-18. |
| Information set | At each origin every model sees only data dated ≤ T. The DSGE's transformed observables are rebuilt from the levels truncated at T, so the HP-filtered population trend uses data only up to T. The DSGE uses its own 13+ observables (wages, hours, spreads, TFP and so on), while the statistical models use the target histories (plus the covariates listed below). |
| DSGE | Model1002 ss104, **fixed DSGE.jl published-code default parameters**, the same ones nydsge's `forecast_ss104_nyfed_params.py` uses. No estimation at any origin. Kalman filter on 1959Q3..T, then an unconditional mean forecast and a closed-form Gaussian density (filtered state covariance propagated with the shock covariance; no parameter uncertainty). GDP adds back population growth at T. Run in a fresh nydsge clone (`main` e2ff029) via `experiments/macro_horse/dsge_runner.py`; Econer's tree and routines were not touched. |
| DSGE regimes | **Headline:** origins before 2020Q1 freeze the regime in force at T, so there's no foreknowledge of COVID. From 2020Q1 on, origins follow ss104's dated regime schedule (ZLB, then a flexible-AIT credibility path), which is the model's own forward assumption. Sensitivity runs: `dsge_frozen` (always frozen; freezing the one-quarter COVID shock-variance regimes gives absurd densities) and `dsge_sched` (always scheduled, so pre-2020 origins "know" about the COVID regimes). Filtering 2020–21 data uses the COVID regime parameters, which were designed after the fact; this mildly flatters the DSGE at origins from 2020 to 2021. |
| Survey and expectations data | ss104's expected-FFR (OIS/survey) observables are missing for much of the sample and entirely after 2021 in the public snapshot, so the DSGE filters without them. This probably accounts for much of its weak policy-rate forecasting. |
| Models | Random walk; **AR(p)**, p≤8 chosen by BIC on each window (the reference, with analytic Gaussian bands); AutoARIMA; Timestral zero-shot univariate; Timestral joint (all 7 targets as one multivariate series); Timestral with past-only covariates (unemployment, 10y–3m term spread, oil growth, fed funds; a target is never its own covariate); a **labelled scenario variant** given the realised future covariate path (not a fair forecast); SPF median. |
| Not run | Timestral fine-tuning, because the installed `timestral` package has no fine-tuning API. DSGE unemployment, because there's no observable (nydsge has an hours-to-unemployment bridge, but it's an add-on, not the model). DSGE headline PCE and CPI, because there are no observables. Fed SEP, because it's annual. |
| SPF | Philadelphia Fed median forecasts (RGDP, CPI, core PCE, PCE, UNEMP). The survey in quarter Q corresponds to origin T = Q−1, so SPF's current-quarter nowcast is our h=1, giving h=1..5. Compounded rates are converted to log rates. Core PCE and PCE start in 2007. |
| Metrics | RMSE and MAE relative to AR by variable and horizon, on each model's common sample with AR. HLN-corrected Diebold-Mariano tests on squared errors. CRPS (19-quantile grid, the same grid for Gaussian and quantile models) and 80%/90% coverage. Regimes by **target quarter**: pre-COVID ≤2019Q4, COVID 2020Q1–2021Q2, inflation surge 2021Q3–2023Q2, post-2023 from 2023Q3. |

Reproduce:

```bash
uv run python -m bsforecast macro-horse data          # panel + SPF (needs data/raw/spf, see NOTES.md)
(cd /path/to/nydsge-python && uv run python <repo>/experiments/macro_horse/dsge_runner.py \
     --out <repo>/data/processed/macro_horse/dsge_forecasts.csv)   # ~80 s
BSF_THREADS=6 uv run python -m bsforecast macro-horse run          # ~5 min on 8 cores
uv run python -m bsforecast macro-horse report
```

**Caveats.** All scores use the latest data vintage (pseudo-out-of-sample), so the SPF's real-time forecasts are
scored against revised data that the other models also train on. The DSGE uses public default parameters, not the
FRBNY production posterior, and isn't re-estimated. 78 overlapping origins give few independent observations at
long horizons, so treat differences under about 5% as noise.
