# Non-bank domains (worker A): electricity, inflation, credit losses, Treasury curve

Same harness as the bank experiments (`python -m bsforecast run --config ...`): rolling origins, one-shot
multi-step quantile forecasts, relative MASE vs a baseline, Diebold-Mariano tests, 80% interval coverage,
spaghetti grids (columns = models, rows = series, colour = origin date, black = actual).

| Domain | Data | Horizon | Origins | Baseline | Known-future covariates | Report |
|---|---|---|---|---|---|---|
| Electricity demand | EIA-930 bulk CSVs, 7 balancing authorities, daily GWh 2022-2026 | 7 days | 78 weekly | MSTL (7, 365) + AutoETS trend; also seasonal naive | Open-Meteo realised daily temperature, CDD, HDD | [outputs/electricity](../outputs/electricity/REPORT.md) |
| Inflation components | FRED CPI, 9 components, y/y % monthly 1990-2026 | 24 months | 36 (every 3 months) | AutoARIMA; also random walk | WTI y/y, 3m/2y/10y UST, term spread, unemployment | [outputs/inflation](../outputs/inflation/REPORT.md) |
| Credit losses | FRED / Fed charge-off and delinquency rates, 7 loan types, quarterly 1991-2026 | 8 quarters | 36 | AutoARIMA; also random walk | unemployment, GDP growth, HPI, CRE prices, Baa spread, 10y | [outputs/credit_losses](../outputs/credit_losses/REPORT.md) |
| Treasury curve | FRED daily constant-maturity yields -> quarterly avg, 3m..30y | 8 quarters | 40 | random walk; also AutoARIMA | fed funds path; unemployment + core CPI | [outputs/treasury_curve](../outputs/treasury_curve/REPORT.md) |

Rebuild everything:

```bash
for d in electricity inflation credit_losses treasury_curve; do python -m bsforecast.data.$d; done
bash experiments/_runners/run_domains_a.sh            # sequential; or pass domain names
python experiments/_runners/headline.py outputs/<domain>   # headline numbers
```

Caveat for every "known" variant: the covariate path given over the forecast window is what actually
happened (a perfect-foresight scenario). It measures how well the model *uses* a scenario, not real-time
accuracy.
