# Company earnings (SEC XBRL, 23 large S&P 500 non-financials): headline findings

Setup: quarterly revenue, operating margin, net income and diluted EPS, 2009Q2-2026Q2, 30 rolling origins (2017Q1-2024Q2),
each a one-shot 8-quarter forecast. Relative MASE = model MASE / AutoARIMA MASE (geometric mean over series; <1 = better).
MASE is scaled by the seasonal (lag-4) naive error.

| Model | h=1 | h=4 | h=8 | Overall | 80% coverage |
|---|---|---|---|---|---|
| **Timestral, no covariates** | **0.87** | **0.90** | **0.89** | **0.886** | 0.74 |
| Timestral + past macro | 0.88 | 0.91 | 0.90 | 0.899 | 0.78 |
| Timestral + known-future macro | 0.90 | 0.97 | 1.00 | 0.969 | 0.82 |
| AutoETS | 0.98 | 0.99 | 0.97 | 0.972 | 0.71 |
| AutoARIMA (baseline) | 1 | 1 | 1 | 1 | 0.69 |
| Seasonal naive | 1.37 | 1.03 | 1.01 | 1.096 | 0.69 |

- Plain Timestral beats AutoARIMA by ~11% at every horizon; Diebold-Mariano: significantly better on 13% of series at h=1
  and h=8, significantly worse on 0-5%.
- Best by line: net income 0.84, EPS 0.85, operating margin 0.87; revenue only 0.98 (revenue is smooth, ARIMA does fine).
- Best companies: VZ 0.67, PG 0.71, CAT 0.77, NEE 0.77, MCD 0.78, CSCO 0.79. No edge on NVDA/AAPL/AMZN/INTC (~1.0), worse on UNH 1.05.
- **Known-future macro (GDP, nominal GDP, CPI, 10y, fed funds, unemployment) hurts**: 0.969 vs 0.886, worse at long horizons.
  Firm earnings are driven by company-specific factors; tying them to macro adds noise. It does help cyclicals: CAT 0.67 vs 0.77.
  Macro does make the bands better calibrated (82% vs 74% for 80% intervals).
- Known-future macro = realised macro path, i.e. a scenario-conditional test, not a real-time forecast.
- **Analyst consensus: not included** - no free historical consensus series was found/used; no comparison is invented.
- Data notes: Q4 = FY minus Q1-Q3 (approximate for EPS); fiscal quarters mapped to calendar quarters by period midpoint.
  Dropped: NKE, PFE, MRK (no OperatingIncomeLoss tag), JNJ, HON (sparse), LIN, GOOGL, DIS (new CIK, <50 quarters),
  COST (12/12/12/16-week quarters collide in calendar mapping).

Best plots: `figures/fundamentals/spaghetti_net_income.png`, `figures/relmase_line_x_variant.png`, `figures/macro_helps_by_line.png`.
