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
