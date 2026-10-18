## Findings: EIA-930 daily electricity demand, 7 balancing authorities, 7-day one-shot, 78 weekly origins 2025-04-16..2026-10-07 (+ live)

Relative MASE vs MSTL (weekly + annual seasonality, AutoETS trend; <1 = better; geometric mean over 7 BAs):

| Model | day 1 | day 3 | day 7 | Overall | 80% coverage |
|---|---|---|---|---|---|
| **Timestral + known temperature (mean, CDD, HDD)** | 0.54 | 0.39 | 0.36 | **0.41** | 0.75 |
| Timestral + past temperature | 0.74 | 0.78 | 0.73 | 0.77 | 0.78 |
| Timestral (no covariates) | 0.75 | 0.79 | 0.74 | 0.77 | 0.79 |
| MSTL | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 |
| Seasonal naive (last week) | 1.86 | 1.17 | 0.98 | 1.16 | 0.80 |

- **Plain Timestral beats MSTL by 23%** with no weather information, in every BA (0.73-0.81) and significantly
  (Diebold-Mariano at 5%) on all 7 BAs at day 1 and 4 of 7 at day 7.
- **Knowing the temperature cuts error a further ~45%** vs plain Timestral (PJM 0.43, ERCOT 0.47, MISO 0.51, ISO-NE 0.64)
  - 0.41 vs MSTL overall, significantly better in all 7 BAs at every horizon. Unlike the macro panels, the gain *grows* with
  horizon (0.54 at day 1 to 0.36 at day 7), because weather is what the model cannot extrapolate from the load history.
- **Past-only temperature adds nothing** (0.77 vs 0.77): the value is entirely in the future path.
- **Heat waves and cold snaps:** in summer 2025 origins MASE goes 1.24 (MSTL) -> 0.95 (Timestral) -> 0.49 (with temperature);
  in winter 2025-26 0.96 -> 0.76 -> 0.37.
- **Intervals** are somewhat narrow for Timestral (75-79% for nominal 80%); MSTL's are much too narrow (67%).

Caveats: "known" temperature is the realised daily mean at 3-4 load centres per BA (a perfect weather forecast), so real
7-day weather-forecast error would erode part of the gain, especially at days 5-7. Daily totals, not hourly; no holiday
calendar; AutoARIMA(7) was dropped as too slow on the shared CPU box. EIA's own day-ahead demand forecast in the bulk files
is a natural next benchmark.
