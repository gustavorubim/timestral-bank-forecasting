"""FRED macro covariates via fredgraph CSV (no key) or the API if FRED_API_KEY is set."""

from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# name -> (FRED id, aggregation to quarter)
SERIES = {
    "gdpc1": ("GDPC1", "last"),
    "unrate": ("UNRATE", "mean"),
    "fedfunds": ("FEDFUNDS", "mean"),
    "dgs10": ("GS10", "mean"),
    "tb3ms": ("TB3MS", "mean"),
    "cpi": ("CPIAUCSL", "mean"),
    # ICE BofA BBB OAS on FRED is limited to a short window; Moody's Baa-10y is the long proxy.
    "baa10y": ("BAA10Y", "mean"),
    "hpi": ("USSTHPI", "last"),
}


def fetch_series(fred_id: str, cache_dir: Path | None = None) -> pd.Series:
    cache = cache_dir / f"fred_{fred_id}.csv" if cache_dir else None
    if cache and cache.exists():
        text = cache.read_text()
    else:
        key = os.environ.get("FRED_API_KEY")
        if key:
            r = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={"series_id": fred_id, "api_key": key, "file_type": "json"},
                timeout=60,
            )
            r.raise_for_status()
            obs = pd.DataFrame(r.json()["observations"])[["date", "value"]]
            text = obs.to_csv(index=False)
        else:
            r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": fred_id}, timeout=60)
            r.raise_for_status()
            text = r.text
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(text)
    df = pd.read_csv(io.StringIO(text))
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"])
    return pd.to_numeric(df.set_index("date")["value"], errors="coerce")


def quarterly_macro(cache_dir: Path | None = None) -> pd.DataFrame:
    cols = {}
    for name, (fid, how) in SERIES.items():
        s = fetch_series(fid, cache_dir)
        q = s.resample("QE").agg(how)
        cols[name] = q
    m = pd.DataFrame(cols)
    out = pd.DataFrame(index=m.index)
    out["gdp_growth"] = 400 * np.log(m["gdpc1"]).diff()  # q/q annualised, %
    out["unemployment"] = m["unrate"]
    out["fed_funds"] = m["fedfunds"]
    out["ust10y"] = m["dgs10"]
    out["ust3m"] = m["tb3ms"]
    out["term_spread"] = m["dgs10"] - m["tb3ms"]
    out["cpi_inflation"] = 100 * np.log(m["cpi"]).diff(4)  # y/y, %
    out["baa_spread"] = m["baa10y"]
    out["hpi_growth"] = 100 * np.log(m["hpi"]).diff(4)  # y/y, %
    out.index.name = "date"
    return out


# Constant-maturity Treasury yields (daily, H.15). Maturity in years.
CURVE = {
    "ust_3m": ("DGS3MO", 0.25),
    "ust_6m": ("DGS6MO", 0.5),
    "ust_1y": ("DGS1", 1.0),
    "ust_2y": ("DGS2", 2.0),
    "ust_3y": ("DGS3", 3.0),
    "ust_5y": ("DGS5", 5.0),
    "ust_7y": ("DGS7", 7.0),
    "ust_10y": ("DGS10", 10.0),
    "ust_20y": ("DGS20", 20.0),
    "ust_30y": ("DGS30", 30.0),
}


def fill_curve_gaps(curve: pd.DataFrame) -> pd.DataFrame:
    """Fill maturity gaps (20y: 1987-93, 30y: 2002-06) via the spread to the next-shorter maturity.

    The spread is interpolated linearly in time between observed quarters (held flat at the ends),
    then added back to the shorter yield. Gaps where the shorter yield is itself missing stay NaN.
    """
    out = curve.copy()
    cols = list(curve.columns)
    for k in range(1, len(cols)):
        c, short = cols[k], cols[k - 1]
        if out[c].isna().any():
            spread = (out[c] - out[short]).interpolate(limit_area="inside").ffill().bfill()
            inside = out[c].ffill().notna() & out[c].bfill().notna()  # interior gaps only, no extrapolation
            out[c] = out[c].where(~inside | out[c].notna(), out[short] + spread)
    return out


def quarterly_curve(cache_dir: Path | None = None) -> pd.DataFrame:
    """Quarterly-average Treasury curve + empirical level / slope / curvature factors."""
    raw = pd.DataFrame({name: fetch_series(fid, cache_dir) for name, (fid, _) in CURVE.items()})
    q = raw.resample("QE").mean()
    q = q[q.notna().sum(axis=1) >= 3]  # drop pre-1962 / empty quarters
    n_filled = int((q.isna() & fill_curve_gaps(q).notna()).sum().sum())
    q = fill_curve_gaps(q)
    q["curve_level"] = q[["ust_3m", "ust_2y", "ust_10y"]].mean(axis=1, skipna=False)
    q["curve_slope"] = q["ust_10y"] - q["ust_3m"]
    q["curve_curvature"] = 2 * q["ust_2y"] - q["ust_3m"] - q["ust_10y"]
    q.attrs["n_gap_filled"] = n_filled
    q.index.name = "date"
    return q


def ccar_macro_panel(cache_dir: Path | None = None) -> pd.DataFrame:
    """~22 quarterly macro variables loosely following the CCAR/DFAST scenario variable list.

    Growth rates are q/q annualised (GDP, income) or y/y (prices, payrolls, IP); rates are quarterly
    averages; VIX is the quarterly maximum (as in the CCAR scenarios). Equity: the Wilshire 5000 is no
    longer on FRED and DJIA/S&P 500 only have 10 years there, so the NASDAQ Composite y/y return is used.
    CRE prices: Fed Z.1 commercial real estate price index (FL075035503.Q), the series CCAR uses.
    """

    def q(fid: str, how: str = "mean") -> pd.Series:
        return fetch_series(fid, cache_dir).resample("QE").agg(how)

    def qoq_ann(s: pd.Series) -> pd.Series:
        return 400 * np.log(s).diff()

    def yoy(s: pd.Series) -> pd.Series:
        return 100 * np.log(s).diff(4)

    curve = quarterly_curve(cache_dir)
    m = pd.DataFrame(index=curve.index)
    m["gdp_growth"] = qoq_ann(q("GDPC1", "last"))
    m["ngdp_growth"] = qoq_ann(q("GDP", "last"))
    m["rdi_growth"] = qoq_ann(q("DSPIC96"))
    m["unemployment"] = q("UNRATE")
    m["cpi_inflation"] = qoq_ann(q("CPIAUCSL"))
    for c in ["ust_3m", "ust_2y", "ust_5y", "ust_10y", "curve_level", "curve_slope"]:
        m[c] = curve[c]
    m["term_spread"] = curve["ust_10y"] - curve["ust_3m"]
    m["baa_spread"] = q("BAA10Y")
    m["mortgage_rate"] = q("MORTGAGE30US")
    m["prime_rate"] = q("DPRIME")
    m["fed_funds"] = q("FEDFUNDS")
    m["equity_return"] = yoy(q("NASDAQCOM"))
    m["vix"] = q("VIXCLS", "max")
    m["hpi_growth"] = yoy(q("USSTHPI", "last"))
    m["cre_price_growth"] = yoy(q("BOGZ1FL075035503Q", "last"))
    m["payrolls_growth"] = yoy(q("PAYEMS"))
    m["ip_growth"] = yoy(q("INDPRO"))
    m["sentiment"] = q("UMCSENT")
    m["nfci"] = q("NFCI")
    m.index.name = "date"
    return m
