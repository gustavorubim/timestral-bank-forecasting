"""CPI components (FRED, no key) as a long monthly panel: id = component, target = y/y inflation (%).

Known-future covariates: WTI y/y % change, 3m / 2y / 10y Treasury yields, unemployment rate.
Run: python -m bsforecast.data.inflation  -> data/processed/inflation.parquet
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .fred import fetch_series

COMPONENTS = {
    "headline": "CPIAUCSL",
    "core": "CPILFESL",
    "shelter": "CUSR0000SAH1",
    "energy": "CPIENGSL",
    "food": "CPIUFDSL",
    "core_goods": "CUSR0000SACL1E",
    "core_services": "CUSR0000SASLE",
    "medical": "CPIMEDSL",
    "transportation": "CPITRNSL",
}


def monthly(fid: str, cache: Path) -> pd.Series:
    return fetch_series(fid, cache).resample("ME").mean()


def covariates(cache: Path) -> pd.DataFrame:
    x = pd.DataFrame(
        {
            "wti_yoy": 100 * np.log(monthly("MCOILWTICO", cache)).diff(12),
            "ust_3m": monthly("TB3MS", cache),
            "ust_2y": monthly("GS2", cache),
            "ust_10y": monthly("GS10", cache),
            "unemployment": monthly("UNRATE", cache),
        }
    )
    x["term_spread"] = x["ust_10y"] - x["ust_3m"]
    return x


def build(raw_dir: Path = Path("data/raw"), out_dir: Path = Path("data/processed"), start: str = "1990-01-31"):
    cache = raw_dir / "fred"
    x = covariates(cache)
    rows = []
    for name, fid in COMPONENTS.items():
        s = monthly(fid, cache)
        d = pd.DataFrame({"yoy": 100 * np.log(s).diff(12)}).join(x, how="left")
        d = d[d.index >= start].dropna(subset=["yoy"])
        d["id"] = name
        rows.append(d.reset_index(names="date"))
    df = pd.concat(rows, ignore_index=True)
    df[x.columns] = df.groupby("id")[list(x.columns)].ffill()
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "inflation.parquet", index=False)
    return df


if __name__ == "__main__":
    d = build()
    print(d.groupby("id")["date"].agg(["min", "max", "count"]))
    print(d.tail(3))
