# NOTES_B (domains-b worker checkpoint log)

Branch `domains-b`, worktree /workspace/tbf-domains-b. Domains: earnings (SEC XBRL), housing (FHFA + Zillow), retail (FRED MRTS + M5).

## 2026-10-18 16:45 ET
- SEC data.sec.gov 403s with a noreply email in User-Agent; works with a real personal contact email. The UA now comes from env var SEC_USER_AGENT (never commit it).
- M5 mirror: HF datasets kashif/M5 (calendar, sales_train_evaluation, sell_prices). Downloading to data/raw/m5.
- Zillow ZHVI/ZORI metro CSVs and FHFA hpi_at_metro.csv reachable.

## 2026-10-18 17:05 ET
- Loaders: src/bsforecast/data/{earnings,housing,retail}.py; CLI `python -m bsforecast fetch-domain {earnings,housing,retail}`.
- Shared edits (backward compatible): models.py `auto_ets` type (AutoETSModel subclasses AutoARIMAModel via `_sf_model`),
  PlotConfig.spaghetti_ids (row subset), spaghetti title uses actual horizon.
- Earnings: 23 companies (dropped NKE/PFE/MRK no OperatingIncomeLoss tag; JNJ/HON sparse op income; LIN/GOOGL/DIS new CIKs <50q;
  COST 12/12/12/16-week quarters collide in calendar mapping). 2009Q2-2026Q2.
- Housing: 22 metros FHFA (1991Q1-2026Q2) + Zillow ZHVI (2000-01..2026-09) / ZORI (2015+).
- Retail: 14 FRED NSA MRTS categories 1992-2026-09; M5 70 store x dept series 2013-01-01..2016-05-22.
- M5 AutoARIMA dropped (1 origin >10 min on contended box). Baselines there: seasonal naive (baseline) + AutoETS.
- Box heavily contended (load ~23 on 8 cores, other worker's runs): timestral 30 origins took 764s vs ~100s idle.
- Runs: earnings started 16:44 (reports/earnings/run.log). Queue experiments/run_queue_b.sh (nohup) waits for earnings,
  then fhfa -> zillow -> census -> m5 -> live_tampa.py; progress in experiments/queue_b.log (ends with QUEUE_DONE).
- After queue: write experiments/<domain>/findings*.md (headline numbers), re-run `bsforecast report --config ...`
  to prepend them into REPORT.md, then ruff/pytest, commit, pull --rebase, push main.

## 2026-10-18 17:08 ET (session 1 end)
- Code pushed to main 7e2fee3 (rebased over domains-a 85e593c; their StatsForecastModel `auto_ets` kept, mine dropped).
- Earnings run: seasonal_naive/arima/ets/timestral done; timestral_macro_past + _known running (pid in `pgrep -f earnings/config`).
- Queue (experiments/run_queue_b.sh, nohup) will run fhfa -> zillow -> census -> m5 -> live_tampa automatically.
- Next session: check experiments/queue_b.log for QUEUE_DONE / FAILED; read reports/<domain>/summary.json + tables;
  write findings*.md; `uv run python -m bsforecast report --config <cfg>` for each; ruff+pytest; commit reports; pull --rebase; push.

## 2026-10-18 17:35 ET (session 2)
- Email removed from code/notes; UA from SEC_USER_AGENT env (main de41733 after history rewrite).
- Replaced sequential queue with experiments/run_parallel_b.sh (fhfa, zillow, census in parallel from 17:09; m5 after earnings).
  /tmp/headlines_b.sh writes reports/<domain>/headline.txt (experiments/headline.py) after QUEUE_DONE.
- Box load ~30 (domains-a runs + ours). Progress at 17:32: earnings on timestral_macro_past (since 17:04);
  fhfa baselines done, on timestral; zillow + census still in seasonal AutoARIMA (season 12, h=24).
- NOTE: box appears frozen while the agent is idle (AwaitShell without shell_id); keep a Shell `sleep` running to make progress.

## 2026-10-18 18:03 ET (session 3)
- Zillow + census restarted WITHOUT AutoARIMA (baseline = AutoETS, plus seasonal naive; census max_context 240), commit 5637833.
  Box restart via experiments/run_restart_b.sh (log experiments/queue_b.log, ends RESTART_DONE).
- Offloaded to Gus (Windows, 24 threads; clone C:\Users\gusta\master\tbf-gus, `python -m uv sync` took ~2 min):
  M5 (experiments/retail/m5_gus.yaml = m5.yaml with threads 12; M5 is NOT running on the box any more),
  plus duplicate races of earnings, zillow, census. Logs: C:\Users\gusta\master\tbf-gus\<domain>_<cfg>.err.log, m5_err.log.
  Results: C:\Users\gusta\master\tbf-gus\reports\<domain>\...\backtest.parquet -> CopyToBox into reports/<same path>,
  then `uv run python -m bsforecast report --config <cfg>` on the box (whichever copy finishes first wins).
- Box state 18:02: earnings still in timestral_macro_past (since 17:04); fhfa in timestral_macro_past;
  zillow + census done baselines + timestral, now on covariate variants.
- Gus state 18:02: earnings in arima (slow); zillow/census done timestral; m5 in timestral.
- Remaining after runs: experiments/housing/live_tampa.py; experiments/headline.py per report -> findings*.md
  (note ARIMA dropped for zillow/census/m5; known-future = scenario test); `bsforecast report`; ruff; pytest; commit; push.
