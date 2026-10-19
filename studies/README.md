# Studies index

One write-up per study. Each study has an **experiment** (config + scripts, in `experiments/<name>/`), its **outputs**
(backtest parquet, tables, figures, `REPORT.md`, in `outputs/<name>/`) and a findings narrative (the `.md` files here;
the same text is prepended to that study's `REPORT.md` via the config's `notes_file`).

Browsable version of everything: <https://gustavorubim.github.io/timestral-bank-forecasting/> (built from `docs/`).

Scores are **relative MASE** = geometric mean over series of MASE(model) / MASE(baseline); below 1 = better than the
baseline. "Known" = the model was given the *realised* future path of the covariates (a scenario test).

## Bank studies (FDIC call reports for JPM, BAC, C, WFC)

| Study | Question | Data | Models (baseline first) | Headline | Links |
|---|---|---|---|---|---|
| [Top-4 banks: aggregate lines](y9c_top4.md) | Can zero-shot Timestral match AutoARIMA on one-shot 8q bank forecasts? | 15 aggregate lines x 4 banks, 2001-2026Q2, 24 origins 2018Q3-2024Q2 | AutoARIMA; naive, seasonal naive, ARIMAX (known macro), Timestral univariate / multivariate / past macro / known macro | Roughly a tie over 8q (0.99; joint Timestral 0.975). Wins 1-3q ahead (0.91 at h=1), strongest on NII/NIM. Known macro hurts (1.12). | [outputs](../outputs/y9c_top4/REPORT.md) · [config](../experiments/y9c_top4/config.yaml) |
| [Treasury curve as known covariate](term_structure.md) | Does knowing the future yield curve help forecast interest income and expense? | Interest income, expense, NII x 4 banks; 10-point CMT curve; 38 origins 2015Q1-2024Q2 | AutoARIMA; ARIMA + known level/slope, Timestral no rates / past curve / known curve / known level-slope-curvature | Known curve halves interest-expense error (0.51 vs 0.86 with no rates); all lines at h=8 0.66. NII only ~9% better (effects cancel). Hurts at the 2023 peak (lagged deposit repricing). | [outputs](../outputs/term_structure/REPORT.md) · [config](../experiments/term_structure/config.yaml) |
| [Granular lines x macro panel](macro_panel.md) | Does a CCAR-style 22-variable known macro path help granular income and balance-sheet lines? | 37 lines (7 income, 18 assets, 12 liabilities) x 4 banks; 22 FRED macro vars; 38 origins | AutoARIMA; ARIMA + 3 macro, Timestral no macro / full macro (22) / compact macro (6) | Plain Timestral best overall (0.965); full macro 1.04. Macro helps rate/credit lines (interest expense 0.58, allowance 0.74 vs plain) and hurts volumes (loans 1.28, sub debt 1.39). | [outputs](../outputs/macro_panel/REPORT.md) · [config](../experiments/macro_panel/config.yaml) |

## Other domains

| Study | Question | Data | Models (baseline first) | Headline | Links |
|---|---|---|---|---|---|
| [Electricity demand + temperature](electricity.md) | Can Timestral use a known weather path at high frequency? | EIA-930 daily load, 7 balancing authorities incl. FPL; Open-Meteo temperature; 78 weekly origins, 7 days ahead | MSTL; seasonal naive, Timestral plain / past temp / known temp | Plain 0.77; known temperature **0.41** (0.54 day 1 -> 0.36 day 7), significant in every region. Clearest known-input win. | [outputs](../outputs/electricity/REPORT.md) · [config](../experiments/electricity/config.yaml) |
| [Inflation components](inflation.md) | Do known oil and rate paths improve 24-month CPI component forecasts? | 9 CPI components y/y, FRED; 36 origins 2015-12..2024-09 | AutoARIMA; random walk, ARIMAX, Timestral plain / known oil / known macro | Plain 0.89 (core services, medical 0.76). Known macro 0.66; energy 0.38. Timestral uses the scenario better than ARIMA (0.66 vs 0.85). Bands too narrow. | [outputs](../outputs/inflation/REPORT.md) · [config](../experiments/inflation/config.yaml) |
| [Credit losses by loan type](credit_losses.md) | Does a known macro path help forecast charge-offs and delinquencies? | Fed charge-off + delinquency rates, 7 loan types; 36 origins 2015Q3-2024Q2 | AutoARIMA; random walk, ARIMAX (known macro), Timestral plain / joint / past macro / known macro / known unemployment | Plain 0.85, joint 0.81 (CRE 0.73, cards 0.75). Known macro **hurts** (1.19; 0.94 ex-COVID) because COVID broke the unemployment link; best model in the 2022-23 loss rise. | [outputs](../outputs/credit_losses/REPORT.md) · [config](../experiments/credit_losses/config.yaml) |
| [Treasury yield curve](treasury_curve.md) | Can Timestral beat the random walk on yields, and how far does a known fed funds path propagate? | CMT yields 3m-30y, quarterly; 40 origins 2014Q4-2024Q3 | Random walk; AutoARIMA, Timestral univariate / joint / joint + past macro / joint + known fed funds / joint + known unemployment & core CPI | Plain joint 0.94 (only no-input model beating RW; gain at short end). Known fed funds 0.39 overall: 0.12 at 3m, 0.28 at 2y, 0.75 at 10y, none at 30y. | [outputs](../outputs/treasury_curve/REPORT.md) · [config](../experiments/treasury_curve/config.yaml) |
| [Company earnings](earnings.md) | Can a zero-shot model forecast company fundamentals? | SEC XBRL revenue, op. margin, net income, EPS for 23 large non-financials; 30 origins 2017Q1-2024Q2 | AutoARIMA; seasonal naive, ETS, Timestral plain / past macro / known macro | Plain 0.886 (net income 0.84, EPS 0.85, revenue 0.98); best on steady firms (VZ 0.67, PG 0.71). Known macro hurts (0.97) except cyclicals. | [outputs](../outputs/earnings/REPORT.md) · [config](../experiments/earnings/config.yaml) |
| [Housing: FHFA metro HPI](housing_fhfa.md) | How well does Timestral forecast metro house prices (incl. Tampa)? | FHFA HPI, 22 metros, 1991-2026Q2; 37 origins 2015Q2-2024Q2 + live | AutoARIMA; seasonal naive, ETS, Timestral plain / past macro / known macro | ~0.83; ties at h=1, ~21% better at h=8; 80% bands cover 80% (ARIMA 58%). Tampa 0.73. Live Tampa to 2028Q2: +2.6%. | [outputs](../outputs/housing/fhfa/REPORT.md) · [config](../experiments/housing/fhfa.yaml) |
| [Housing: Zillow values + rents](housing_zillow.md) | Same question at monthly frequency, values and rents | Zillow ZHVI + ZORI, 22 metros; 31 origins 2019-2024 + live, 24 months | AutoETS (ARIMA dropped); seasonal naive, Timestral plain / past macro / known macro | 0.87-0.89; rents gain more than values. Live Tampa: value flat ~$357k, rent +1.4% to ~$2,020. | [outputs](../outputs/housing/zillow/REPORT.md) · [config](../experiments/housing/zillow.yaml) · [live script](../experiments/housing/live_tampa.py) |
| [Retail: Census sales](retail_census.md) | Retail sales by category, with calendar and macro inputs | 14 Census categories (NSA), 1992-2026; 36 origins, 24 months | AutoETS (ARIMA dropped); seasonal naive, Timestral plain / known calendar / past macro / known macro | Plain 0.915 (online 0.74, clothing 0.79). Known macro 0.80, mostly gas stations (0.23, future pump price is an input). Calendar helps only at h=1. | [outputs](../outputs/retail/census/REPORT.md) · [config](../experiments/retail/census.yaml) |
| [Retail: M5 Walmart](retail_m5.md) | Daily store x department sales with genuinely known calendar inputs | M5, 10 stores x 7 depts = 70 series; 24 origins, 28 days | Seasonal naive (ARIMA dropped); ETS, Timestral plain / known calendar + SNAP / all known | Plain 0.70, with calendar/SNAP 0.675 (not a scenario test: calendar is known ahead). | [outputs](../outputs/retail/m5/REPORT.md) · [config](../experiments/retail/m5.yaml) |
| [Macro horse race: Timestral vs NY Fed DSGE](macro_horse.md) | Does Timestral beat the NY Fed DSGE (Model1002 ss104, fixed published parameters) on core US macro? | Real GDP, core/headline PCE, CPI, GDP deflator, fed funds, unemployment; 78 expanding origins 2005Q1-2024Q2, h=1..8, latest vintage | AR(p) by BIC; random walk, AutoARIMA, DSGE ss104, SPF median, Timestral univariate / joint / past macro / realised-future scenario | GDP and core PCE are close to a tie (Timestral 0.94-0.99 vs AR; DSGE 0.91-1.33; no significant DM vs DSGE). Timestral is clearly better on fed funds (0.65-0.79 vs AR, 0.29-0.80 vs DSGE). The DSGE is better on the GDP deflator at 5-8q and before 2020, and much worse after 2021. SPF wins h=1-2. | [outputs](../outputs/macro_horse/REPORT.md) · [config](../experiments/macro_horse/config.yaml) |

Cross-domain chart and table: [`outputs/summary_relmase.png`](../outputs/summary_relmase.png),
[`docs/summary.csv`](../docs/summary.csv).

## Overall summary

- **Plain zero-shot Timestral beat the standard baselines in every domain**, except bank balance-sheet volumes at long
  horizons, where it only ties AutoARIMA. Gains are usually largest at short horizons; its 80% bands are generally
  better calibrated than ARIMA's.
- **Known inputs help most when they directly drive the target:** temperature for electricity (0.41), fed funds for
  short-term yields (0.39), the yield curve for bank interest expense (0.51), oil for energy inflation (0.38).
- **Known inputs hurt where the usual macro link broke**, mostly around COVID: credit losses (unemployment up,
  charge-offs down), and bank loan and deposit volumes, which reflect management decisions more than macro.
- Rich macro panels are not better than small ones; the issue is *which* lines get macro, not how many inputs.
  The natural next step is a hybrid: macro only on rate/credit lines, plain Timestral on volumes.

## Caveats

- **Known-future covariates are scenario tests**: the realised path over the forecast window was given, so they
  measure how well a model follows a scenario, not real-time accuracy. No real-time data vintages were used.
- **Baselines differ by domain** (AutoARIMA, random walk, MSTL, AutoETS, seasonal naive); AutoARIMA was dropped where it
  was too slow (electricity, Zillow, Census, M5). Scores are not comparable 1:1 across rows.
- **Banks:** FR Y-9C downloads are CAPTCHA-blocked, so bank data are FDIC call reports summed over each holding company's
  bank subsidiaries; nonbank subsidiaries are missing, so totals run low (most for Citi and BofA).
- Long-horizon gains often rest on few series and overlapping windows; Diebold-Mariano significance is mostly at short
  horizons.
- **Timestral-209M weights license** (Modified MIT): free only for companies under $20M/month revenue; larger
  companies (e.g. an employer like Citi) need a commercial license from Mistral. Personal experiments are fine.
