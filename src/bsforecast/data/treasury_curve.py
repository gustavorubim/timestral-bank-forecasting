"""Quarterly-average Treasury curve (3m..30y) as one multivariate id, plus macro covariates.

Covariates: fed funds (policy-path scenario), unemployment, core CPI y/y.
Run: python -m bsforecast.data.treasury_curve  -> data/processed/treasury_curve.parquet
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .fred import fetch_series, quarterly_curve

MATS = ["ust_3m", "ust_6m", "ust_1y", "ust_2y", "ust_3y", "ust_5y", "ust_7y", "ust_10y", "ust_20y", "ust_30y"]


def build(raw_dir: Path = Path("data/raw"), out_dir: Path = Path("data/processed"), start: str = "1985-03-31"):
    cache = raw_dir / "fred"
    c = quarterly_curve(cache)[MATS]

    def q(fid: str) -> pd.Series:
        return fetch_series(fid, cache).resample("QE").mean()

    c["fed_funds"] = q("FEDFUNDS")
    c["unemployment"] = q("UNRATE")
    c["core_cpi_yoy"] = 100 * np.log(q("CPILFESL")).diff(4)
    c = c[c.index >= start].dropna(subset=MATS, how="all")
    c = c[c.index <= pd.Timestamp.today()]
    df = c.reset_index(names="date").assign(id="UST")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "treasury_curve.parquet", index=False)
    return df


if __name__ == "__main__":
    d = build()
    print(d.head(2).T)
    print(d.tail(2).T)
    print(d[MATS].isna().sum())
