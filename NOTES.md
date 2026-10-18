# NOTES (agent checkpoint log)

## 2026-10-18 13:50 ET
- Timestral-209M verified: public, NOT gated, weights Modified-MIT (no use if company revenue > $20M/month w/o commercial license), code Apache-2.0.
  pip install git+https://github.com/mistralai/timestral.git ; TimestralForecaster.from_pretrained(...).forecast(context, prediction_length, past_covariates, known_covariates)
  context up to 32,768 steps, horizon up to 1,024 one pass; 21 quantiles; multivariate + past/known covariates.
- FR Y-9C: FFIEC NIC (ffiec.gov/npw) returns CAPTCHA 403 from box AND from Gus. Chicago Fed BHC archive discontinued 2021.
  Fallback used: FDIC BankFind API (api.fdic.gov/banks/financials), Call Report data for all FDIC-insured bank subs aggregated by RSSDHCR (verified HC RSSDs).
- 14:10 ET: data built (data/processed/top4_bhc_panel.parquet, 2001Q1-2026Q2, 102 q x 4 banks). Pipeline code written.
  Next: `uv run python -m bsforecast run --config configs/y9c_top4.yaml` (nohup, log reports/run.log)
- 14:00 ET scope narrowed to 15 aggregate lines (parent steering). Full run launched: reports/run.log
- 14:20 ET: full backtest done (8 models, 25 origins incl. live). Report in reports/y9c_top4/. ARIMAX regressors narrowed to
  unemployment, fed funds, Baa spread (6-regressor version overfit badly: rel MASE 1.83).
- Possible next steps: Y-9C proper (download BHCF zips manually in browser -> loader), log-transform levels, CRPS metric,
  Timestral-28M/123M size comparison, scenario runs with CCAR macro paths for the oracle models.
