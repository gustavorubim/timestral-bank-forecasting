"""Macro horse race: Timestral-209M vs the NY Fed DSGE (Model1002 ss104) vs AR/RW/ARIMA/SPF.

Quarterly US targets (annualised log rates, percent): real GDP growth, core PCE, headline PCE,
CPI and GDP-deflator inflation, plus the fed funds rate and unemployment (levels). Expanding-window
origins 2005Q1..2024Q2 (last observed quarter T), direct forecasts T+1..T+8.

    python -m bsforecast macro-horse data     # build data/processed/macro_horse/{panel,spf}.csv
    python -m bsforecast macro-horse run      # backtest all non-DSGE models -> forecasts.parquet
    python -m bsforecast macro-horse report   # merge DSGE forecasts, metrics, figures, REPORT.md

DSGE forecasts are produced separately in the nydsge-python environment by
``experiments/macro_horse/dsge_runner.py`` (fixed published ss104 parameters).
"""

from __future__ import annotations

import logging
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

log = logging.getLogger(__name__)

TARGETS = ["gdp", "corepce", "pce", "cpi", "gdpdef", "ffr", "unrate"]
LABELS = {
    "gdp": "Real GDP growth",
    "corepce": "Core PCE inflation",
    "pce": "PCE inflation",
    "cpi": "CPI inflation",
    "gdpdef": "GDP deflator inflation",
    "ffr": "Fed funds rate",
    "unrate": "Unemployment rate",
}
PAST_COVS = ["unrate", "term_spread", "oil_growth", "ffr"]
QGRID = [round(0.05 * k, 2) for k in range(1, 20)]  # 0.05..0.95
H = 8
FIRST_ORIGIN, LAST_ORIGIN = "2005Q1", "2024Q2"
REGIMES = {  # classified by the *target* quarter being forecast
    "pre_covid": ("1900Q1", "2019Q4"),
    "covid": ("2020Q1", "2021Q2"),
    "inflation_surge": ("2021Q3", "2023Q2"),
    "post_2023": ("2023Q3", "2100Q4"),
}
GAUSS_MODELS = {"rw", "ar", "dsge", "dsge_sched"}


# ----------------------------------------------------------------------------------- data
def _q(s: pd.Series, how: str = "mean") -> pd.Series:
    s = s.dropna()
    g = s.groupby(s.index.to_period("Q"))
    return g.mean() if how == "mean" else g.last()


def build_panel(raw: Path, out: Path) -> pd.DataFrame:
    """Quarterly panel. GDP, GDP deflator, core PCE and DFF come from the same 2026-10-06 FRED
    snapshot the DSGE uses; PCEPI, CPI, UNRATE, oil and the 3m bill are fetched from FRED once."""
    from .data.fred import fetch_series

    snap = pd.read_csv(raw / "macro_horse" / "fred_levels_20261006.csv")
    snap.index = pd.PeriodIndex(snap.date.str.replace("-Q", "Q"), freq="Q")
    cache = raw / "macro_horse"
    extra = {k: _q(fetch_series(k, cache)) for k in ["PCEPI", "CPIAUCSL", "UNRATE", "WTISPLC", "TB3MS"]}
    df = pd.DataFrame(index=pd.period_range("1959Q1", "2026Q2", freq="Q"))
    lg = lambda s: 400 * np.log(s).diff()  # noqa: E731
    df["gdp"] = lg(snap.GDP / snap.GDPDEF)
    df["gdpdef"] = lg(snap.GDPDEF)
    df["corepce"] = lg(snap.PCEPILFE)
    df["ffr"] = snap.DFF
    df["pce"] = lg(extra["PCEPI"]).reindex(df.index)
    df["cpi"] = lg(extra["CPIAUCSL"]).reindex(df.index)
    df["unrate"] = extra["UNRATE"].reindex(df.index)
    df["term_spread"] = snap.GS10 - extra["TB3MS"].reindex(df.index)
    df["oil_growth"] = lg(extra["WTISPLC"]).reindex(df.index)
    df = df.loc["1959Q2":]
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "panel.csv", index_label="quarter")
    return df


def build_spf(raw: Path, out: Path) -> pd.DataFrame:
    """SPF medians aligned to our origins. Survey in quarter Q (mid-quarter, real time) -> origin
    T = Q-1; SPF column 2 (current-quarter nowcast) is our h=1 ... column 6 is h=5."""
    spec = {
        "gdp": ("spf_growth_rgdp.csv", "drgdp"),
        "cpi": ("spf_level_cpi.csv", "CPI"),
        "corepce": ("spf_level_corepce.csv", "COREPCE"),
        "pce": ("spf_level_pce.csv", "PCE"),
        "unrate": ("spf_level_unemp.csv", "UNEMP"),
    }
    rows = []
    for tgt, (fn, stem) in spec.items():
        d = pd.read_csv(raw / "spf" / fn)
        for _, r in d.iterrows():
            survey = pd.Period(year=int(r.YEAR), quarter=int(r.QUARTER), freq="Q")
            for h in range(1, 6):
                v = pd.to_numeric(r.get(f"{stem}{h + 1}"), errors="coerce")
                if pd.isna(v):
                    continue
                if tgt != "unrate":  # SPF compounded annual % -> annualised log %
                    v = 400 * math.log1p(v / 400)
                rows.append({"model": "spf", "origin": str(survey - 1), "target": tgt, "h": h, "mean": v})
    spf = pd.DataFrame(rows)
    spf.to_csv(out / "spf.csv", index=False)
    return spf


# ----------------------------------------------------------------------------------- models
def rw_forecast(y: np.ndarray, h: int) -> tuple[np.ndarray, np.ndarray]:
    y = y[~np.isnan(y)]
    sig = np.std(np.diff(y), ddof=1)
    return np.full(h, y[-1]), sig * np.sqrt(np.arange(1, h + 1))


def ar_fit(y: np.ndarray, pmax: int = 8) -> tuple[int, np.ndarray, float]:
    """AR(p) with intercept by OLS, p in 0..pmax chosen by BIC on a common estimation sample."""
    y = y[~np.isnan(y)]
    n = len(y) - pmax
    best = None
    for p in range(pmax + 1):
        x = np.column_stack([np.ones(n)] + [y[pmax - k : len(y) - k] for k in range(1, p + 1)])
        yy = y[pmax:]
        b, *_ = np.linalg.lstsq(x, yy, rcond=None)
        e = yy - x @ b
        s2 = e @ e / n
        bic = n * np.log(s2) + (p + 1) * np.log(n)
        if best is None or bic < best[0]:
            best = (bic, p, b, float(np.sqrt(e @ e / max(n - p - 1, 1))))
    return best[1], best[2], best[3]


def ar_forecast(y: np.ndarray, h: int, pmax: int = 8) -> tuple[np.ndarray, np.ndarray, int]:
    p, b, sig = ar_fit(y, pmax)
    hist = list(y[~np.isnan(y)])
    mean = []
    for _ in range(h):
        v = b[0] + sum(b[k] * hist[-k] for k in range(1, p + 1))
        mean.append(v)
        hist.append(v)
    psi = [1.0]  # MA(inf) weights for the h-step error variance
    for j in range(1, h):
        psi.append(sum(b[k] * psi[j - k] for k in range(1, min(p, j) + 1)))
    sd = sig * np.sqrt(np.cumsum(np.square(psi)))
    return np.asarray(mean), sd, p


def _gauss_rows(model, origin, tgt, mean, sd):
    z = norm.ppf(QGRID)
    for i in range(len(mean)):
        r = {"model": model, "origin": origin, "target": tgt, "h": i + 1, "mean": mean[i], "sd": sd[i]}
        r.update({f"q{q:.2f}": mean[i] + z[k] * sd[i] for k, q in enumerate(QGRID)})
        yield r


def _quant_rows(model, origin, tgt, qarr, qs):
    """qarr (H, len(qs)) on the QGRID quantile levels."""
    for i in range(qarr.shape[0]):
        r = {"model": model, "origin": origin, "target": tgt, "h": i + 1}
        r.update({f"q{q:.2f}": float(qarr[i, k]) for k, q in enumerate(qs)})
        r["mean"] = r["q0.50"]
        r["sd"] = (r["q0.95"] - r["q0.05"]) / (2 * 1.6449)
        yield r


def origins() -> pd.PeriodIndex:
    return pd.period_range(FIRST_ORIGIN, LAST_ORIGIN, freq="Q")


def run_backtest(panel: pd.DataFrame, models: list[str] | None = None, threads: int | None = None) -> pd.DataFrame:
    """All non-DSGE models. Every model sees panel rows <= T only (latest-vintage pseudo-OOS)."""
    from .config import ModelConfig
    from .models import AutoARIMAModel, Batch, TimestralModel

    models = models or ["rw", "ar", "arima", "timestral", "timestral_mv", "timestral_cov", "timestral_scenario"]
    rows: list[dict] = []
    tcfg = lambda **p: ModelConfig(name="t", type="timestral", **p)  # noqa: E731
    ts_uni = TimestralModel(tcfg(params={"clip_nonnegative": True}), QGRID)
    ts_cov = TimestralModel(tcfg(covariates="past"), QGRID)
    ts_scn = TimestralModel(tcfg(covariates="known_oracle"), QGRID)
    arima = AutoARIMAModel(ModelConfig(name="arima", type="auto_arima", params={"season_length": 1}), QGRID)
    if threads:
        import os

        os.environ["BSF_THREADS"] = str(threads)
    t0 = time.time()
    for k, o in enumerate(origins()):
        hist = panel.loc[:o]
        fut = panel.loc[o + 1 : o + H]
        ys = np.stack([hist[t].to_numpy() for t in TARGETS])  # (V, T)
        so = str(o)
        for j, tgt in enumerate(TARGETS):
            if "rw" in models:
                m, s = rw_forecast(ys[j], H)
                rows += _gauss_rows("rw", so, tgt, m, s)
            if "ar" in models:
                m, s, _ = ar_forecast(ys[j], H)
                rows += _gauss_rows("ar", so, tgt, m, s)
        if "arima" in models:
            q = arima.predict(Batch(y=ys[:, None, :], x_past=np.zeros((len(TARGETS), 0, ys.shape[1])),
                                    x_future=np.zeros((len(TARGETS), 0, H)), horizon=H, freq="QE"))
            for j, tgt in enumerate(TARGETS):
                rows += _quant_rows("arima", so, tgt, q[j, 0], QGRID)
        empty_p = np.zeros((len(TARGETS), 0, ys.shape[1]))
        empty_f = np.zeros((len(TARGETS), 0, H))
        if "timestral" in models:
            q = ts_uni.predict(Batch(y=ys[:, None, :], x_past=empty_p, x_future=empty_f, horizon=H))
            for j, tgt in enumerate(TARGETS):
                rows += _quant_rows("timestral", so, tgt, q[j, 0], QGRID)
        if "timestral_mv" in models:
            q = ts_uni.predict(Batch(y=ys[None], x_past=empty_p[:1], x_future=empty_f[:1], horizon=H))
            for j, tgt in enumerate(TARGETS):
                rows += _quant_rows("timestral_mv", so, tgt, q[0, j], QGRID)
        for name, mdl in (("timestral_cov", ts_cov), ("timestral_scenario", ts_scn)):
            if name not in models:
                continue
            for j, tgt in enumerate(TARGETS):  # per target: its own covariate set (never itself)
                covs = [c for c in PAST_COVS if c != tgt]
                xp = np.stack([hist[c].to_numpy() for c in covs])[None]
                if len(fut) == H:
                    xf = np.stack([fut[c].to_numpy() for c in covs])[None]
                else:
                    xf = np.repeat(xp[:, :, -1:], H, axis=2)
                q = mdl.predict(Batch(y=ys[j][None, None], x_past=xp, x_future=xf, horizon=H))
                rows += _quant_rows(name, so, tgt, q[0, 0], QGRID)
        log.info("origin %s done (%d/%d, %.0fs)", o, k + 1, len(origins()), time.time() - t0)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------------- metrics
def attach_actuals(fc: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    fc = fc.copy()
    o = pd.PeriodIndex(fc.origin, freq="Q")
    fc["tq"] = (o + fc.h.to_numpy()).astype(str)
    long = panel[TARGETS].stack().rename("actual").reset_index()
    long.columns = ["tq", "target", "actual"]
    long["tq"] = long.tq.astype(str)
    fc = fc.merge(long, on=["tq", "target"], how="left")
    fc["err"] = fc["mean"] - fc["actual"]
    fc["regime"] = regime_of(fc.tq)
    return fc


def regime_of(tq: pd.Series) -> np.ndarray:
    p = pd.PeriodIndex(tq, freq="Q")
    out = np.empty(len(p), dtype=object)
    for name, (a, b) in REGIMES.items():
        out[(p >= pd.Period(a, freq="Q")) & (p <= pd.Period(b, freq="Q"))] = name
    return out


def crps_quantiles(qvals: np.ndarray, y: np.ndarray) -> np.ndarray:
    """CRPS approx: 2 * mean pinball loss over the 0.05..0.95 grid. qvals (N, Q)."""
    tau = np.asarray(QGRID)
    q = np.sort(qvals, axis=1)
    d = y[:, None] - q
    return 2 * np.mean(np.maximum(tau * d, (tau - 1) * d), axis=1)


def crps_gaussian(mu, sd, y):
    z = (y - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def add_density(fc: pd.DataFrame) -> pd.DataFrame:
    fc = fc.copy()
    qcols = [f"q{q:.2f}" for q in QGRID]
    has_q = fc[qcols[0]].notna().to_numpy() if qcols[0] in fc else np.zeros(len(fc), bool)
    fc["crps"] = np.nan
    if has_q.any():
        fc.loc[has_q, "crps"] = crps_quantiles(fc.loc[has_q, qcols].to_numpy(), fc.loc[has_q, "actual"].to_numpy())
    fc["cov80"] = np.where(has_q, (fc.actual >= fc.get("q0.10")) & (fc.actual <= fc.get("q0.90")), np.nan)
    fc["cov90"] = np.where(has_q, (fc.actual >= fc.get("q0.05")) & (fc.actual <= fc.get("q0.95")), np.nan)
    return fc


def common_sample(fc: pd.DataFrame, models: list[str]) -> pd.DataFrame:
    """Keep (origin, target, h) cells where every listed model has a non-NaN error."""
    sub = fc[fc.model.isin(models)].dropna(subset=["err"])
    n = sub.groupby(["origin", "target", "h"]).model.nunique()
    keep = n[n == len(models)].index
    return sub.set_index(["origin", "target", "h"]).loc[keep].reset_index()


def rel_table(fc: pd.DataFrame, metric: str = "rmse", base: str = "ar", by=("target", "h")) -> pd.DataFrame:
    """Relative RMSE / MAE / CRPS vs ``base`` on each model's common sample with the base."""
    by = list(by)
    out = []
    for m in fc.model.unique():
        s = common_sample(fc, [m, base]) if m != base else fc[fc.model == base].dropna(subset=["err"])
        if metric == "crps":
            s = s.dropna(subset=["crps"])
        g = s.groupby(["model"] + by)
        if metric == "rmse":
            v = g.err.apply(lambda e: np.sqrt(np.mean(e**2)))
        elif metric == "mae":
            v = g.err.apply(lambda e: np.mean(np.abs(e)))
        else:
            v = g.crps.mean()
        v = v.unstack("model")
        if base not in v:
            continue
        r = (v[m] / v[base]).rename("rel").reset_index()
        r["model"] = m
        r["n"] = s[s.model == m].groupby(by).size().reindex(pd.MultiIndex.from_frame(r[by])).to_numpy()
        out.append(r)
    return pd.concat(out, ignore_index=True)


def dm_tests(fc: pd.DataFrame, challenger: str, baseline: str) -> pd.DataFrame:
    from .metrics import diebold_mariano

    s = common_sample(fc, [challenger, baseline])
    a = s[s.model == challenger].set_index(["target", "h", "origin"]).err
    b = s[s.model == baseline].set_index(["target", "h", "origin"]).err
    j = pd.concat([a.rename("e1"), b.rename("e2")], axis=1).dropna().reset_index()
    rows = []
    for (t, h), g in j.groupby(["target", "h"]):
        g = g.sort_values("origin")
        st, p = diebold_mariano(g.e1.to_numpy(), g.e2.to_numpy(), int(h))
        rmse_ratio = np.sqrt(np.mean(g.e1**2) / np.mean(g.e2**2))
        rows.append({"challenger": challenger, "baseline": baseline, "target": t, "h": h,
                     "rel_rmse": rmse_ratio, "dm_stat": st, "p_value": p, "n": len(g)})
    return pd.DataFrame(rows)
