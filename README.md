# timestral-bank-forecasting

Experimental harness for **one-shot 8-quarter bank balance-sheet / income-statement forecasting**,
comparing the zero-shot time-series foundation model
[Timestral-209M](https://huggingface.co/mistralai/Timestral-209M) (Mistral AI) with an
AutoARIMA / ARIMAX baseline and naive benchmarks, on the four largest US bank holding companies
(JPMorgan Chase, Bank of America, Citigroup, Wells Fargo) plus FRED macro covariates.

The pipeline is generic: point a YAML config at **any CSV/parquet panel** with a date column,
an optional id column, target columns and optional covariates, and it runs the same rolling-origin
backtest, metrics, plots and markdown report.

## Quick start

```bash
uv sync                                         # Python 3.12, CPU torch, statsforecast, timestral
uv run python -m bsforecast fetch-y9c-top4      # -> data/processed/top4_bhc_panel.{parquet,csv}
uv run python -m bsforecast run --config configs/y9c_top4.yaml
open reports/y9c_top4/REPORT.md                 # tables + figures/ PNGs
uv run python -m bsforecast report --config configs/y9c_top4.yaml        # re-plot without re-forecasting
uv run python -m bsforecast run --config configs/y9c_top4.yaml --models timestral arima   # partial re-run
uv run pytest && uv run ruff check .
```

Timestral weights (~0.8 GB) download from the Hugging Face Hub on first use (not gated). 209M
parameters run comfortably on CPU: the full 25-origin x 88-series backtest takes well under a
minute per Timestral variant; AutoARIMA is the slow part (~2 min).

## Headline results (top-4 BHCs, 24 origins 2018Q3–2024Q2, 15 lines × 4 banks, h = 1..8)

Full report: [`reports/y9c_top4/REPORT.md`](reports/y9c_top4/REPORT.md). Relative MASE is the geometric mean over series
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

## Design

```
src/bsforecast/
  data/fdic.py     FDIC BankFind API client: call-report rows for all bank subs of a BHC (by RSSDHCR), YTD->quarterly
  data/fred.py     FRED macro (fredgraph CSV, or API if FRED_API_KEY is set)
  data/build.py    builds the tidy top-4 panel + derived metrics (ROA, ROE, NIM, efficiency, LDR, CET1, NCO rate)
  config.py        YAML schema (data / backtest / models / evaluation / identities / plots)
  dataset.py       any CSV/parquet -> dense (id, target, time) cube on a regular calendar (gaps = NaN)
  models.py        Naive, SeasonalNaive, AutoARIMA(+X), Timestral; common batch interface returning quantiles
  backtest.py      rolling-origin, direct H-step forecasts from each origin + a live forecast
  metrics.py       MAE, RMSE, MAPE (median APE), sMAPE, MASE, 80% coverage, directional accuracy,
                   Diebold-Mariano (HLN), win rates, relative MASE, accounting-identity gaps
  plots.py / report.py   PNGs + REPORT.md + tables/*.csv + summary.json
```

**One-shot horizon.** Every model is asked for all H=8 quarters at once from each origin. Nothing in
the harness chains one-step forecasts. For Timestral, 8 steps fit inside a single 32-step output
patch, so the whole path comes from one forward pass. AutoARIMA's multi-step forecast is the model's
own recursive state-space projection, which is how ARIMA is normally used in practice.

**Model variants** (all in `configs/y9c_top4.yaml`):

| name | what |
|---|---|
| `naive`, `snaive` | random walk / seasonal random walk with sqrt(h) Gaussian bands |
| `arima` | statsforecast AutoARIMA (season 4), univariate, per series |
| `arimax_oracle` | AutoARIMA with macro regressors, using the **realised** future macro path |
| `timestral` | zero-shot, univariate, per series |
| `timestral_cov` | + macro as *past-only* covariates (a real-time-feasible forecast) |
| `timestral_cov_oracle` | + macro as *known-future* covariates (realised path) |
| `timestral_mv` | all 22 targets of a bank forecast jointly as one multivariate series |

`*_oracle` models are **scenario-conditional** forecasts (like CCAR/DFAST, where the macro path is given).
They are not real-time forecasts. Compare them with each other, not with the unconditional models.

## Pointing it at a new dataset

```yaml
name: my_run
output_dir: reports/my_run
data:
  path: path/to/panel.csv        # or .parquet; long-by-id, wide-by-variable
  date_col: quarter_end
  id_col: entity                 # omit the column in the file for a single series
  freq: QE                       # pandas offset alias: QE, ME, W, D ...
  targets: [assets, deposits]    # empty -> all numeric non-covariate columns
  covariates: [unemployment]     # optional
  groups: {bs: [assets, deposits]}
backtest: {horizon: 8, n_origins: 12, min_train: 24, stress_windows: {covid: ["2019-06-30", "2020-06-30"]}}
models:
  - {name: arima, type: auto_arima, season_length: 4}
  - {name: timestral, type: timestral}
evaluation: {baseline: arima, challenger: timestral, mase_season: 1}
identities: [{name: assets, total: assets, components: [loans, other]}]
plots: {fan_series: [assets], fan_origins: ["2022-06-30"]}
```

Then run `uv run python -m bsforecast run --config configs/my_run.yaml`. Any new model only needs a
`predict(Batch) -> (B, V, H, Q)` method and an entry in `models.REGISTRY`.

## Data sources and caveats (read this)

* **FR Y-9C was not directly downloadable.** The FFIEC NIC "Financial Data Download" (`ffiec.gov/npw`)
  returns a CAPTCHA page (HTTP 403) to scripted clients, and the Chicago Fed BHC archive was retired in 2021.
  The top-4 panel therefore uses the **FDIC BankFind API** (Call Report data): every FDIC-insured bank
  subsidiary whose regulatory high holder (`RSSDHCR`) is the BHC at each report date is summed to the
  holding-company level. That is the **bank-subsidiary consolidation of each BHC**, *not* the full Y-9C. It
  excludes nonbank subsidiaries (e.g. broker-dealers), so totals are below Y-9C totals. That matters most for
  Citi's and BofA's markets businesses. If you have Y-9C `BHCF*.zip` files (download them in a browser from NIC), a
  loader can map BHCK items such as `BHCK2170` (total assets) to the same column names. The rest of the pipeline is unchanged.
* RSSD IDs were verified against the FDIC institutions API: JPM 1039502 (lead bank JPMorgan Chase Bank NA,
  CERT 628), BAC 1073757 (CERT 3510), C 1951350 (Citibank NA, CERT 7213), WFC 1120754 (CERT 3511).
* Income items are year-to-date in the Call Report and are converted to discrete quarters. Holding-company
  structure changes such as Wachovia into WFC (2009) and Countrywide/Merrill bank subs into BAC show up as level jumps,
  as they would in Y-9C.
* CET1 ratio is RWA-weighted across subsidiaries and only exists from about 2014. Earlier quarters are NaN, which Timestral
  handles natively. ARIMA uses the observed segment.
* BBB spread: ICE BofA OAS history on FRED is truncated, so Moody's Baa minus 10y (`BAA10Y`) is used as the long proxy.
* Raw downloads are cached under `data/raw/` (git-ignored). The processed panel (~0.3 MB) is committed.

## License note

Code here: MIT. Timestral code is Apache-2.0. **Timestral weights are under a Modified MIT license that
forbids use by any company (or the user's employer) with consolidated revenue above $20M/month without a
commercial license from Mistral AI.** Fine for personal experimentation. Check before any work use.
