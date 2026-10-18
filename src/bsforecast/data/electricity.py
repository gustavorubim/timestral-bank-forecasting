"""EIA-930 balancing-authority demand (bulk six-month CSVs, no API key) aggregated to daily GWh,
plus population-centre daily mean temperature from the Open-Meteo archive (free, no key).

Known-future covariates: temp_mean (deg C), cdd / hdd (base 18 C) - the realised weather, i.e. a
"perfect weather forecast" scenario test.
Run: python -m bsforecast.data.electricity  -> data/processed/electricity.parquet
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

URL = "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/EIA930_BALANCE_{y}_{p}.csv"
# BA code -> representative load centres (lat, lon); temperature = simple average across them.
BAS = {
    "FPL": [(25.76, -80.19), (26.64, -81.87), (29.21, -81.02)],
    "ERCO": [(29.76, -95.37), (32.78, -96.80), (30.27, -97.74), (29.42, -98.49)],
    "PJM": [(39.95, -75.17), (41.88, -87.63), (38.90, -77.04), (39.96, -82.99)],
    "CISO": [(34.05, -118.24), (38.58, -121.49), (36.74, -119.79), (37.34, -121.89)],
    "MISO": [(44.98, -93.27), (38.63, -90.20), (42.33, -83.05), (29.95, -90.07)],
    "NYIS": [(40.71, -74.01), (42.65, -73.75), (42.89, -78.88)],
    "ISNE": [(42.36, -71.06), (41.76, -72.67), (43.66, -70.26)],
}


def download(raw: Path, years=range(2022, 2027)) -> list[Path]:
    raw.mkdir(parents=True, exist_ok=True)
    files = []
    for y in years:
        for p in ("Jan_Jun", "Jul_Dec"):
            f = raw / f"EIA930_BALANCE_{y}_{p}.csv"
            if not f.exists():
                r = requests.get(URL.format(y=y, p=p), timeout=300)
                if r.status_code != 200:
                    continue
                f.write_bytes(r.content)
            files.append(f)
    return files


def daily_load(files: list[Path]) -> pd.DataFrame:
    parts = []
    for f in files:
        d = pd.read_csv(f, thousands=",", low_memory=False)
        d = d[d["Balancing Authority"].isin(BAS)]
        col = "Demand (MW) (Adjusted)" if "Demand (MW) (Adjusted)" in d else "Demand (MW)"
        d = d.assign(mw=pd.to_numeric(d[col], errors="coerce"), date=pd.to_datetime(d["Data Date"]))
        g = d.groupby(["Balancing Authority", "date"]).agg(gwh=("mw", "sum"), hours=("mw", "count"))
        parts.append(g)
    g = pd.concat(parts).groupby(level=[0, 1]).sum()
    g.loc[g.hours < 22, "gwh"] = np.nan  # incomplete / missing days
    g["gwh"] = g["gwh"] / 1000 * 24 / g["hours"].clip(lower=1)
    return g["gwh"].rename_axis(["id", "date"]).reset_index()


def temperature(start: str, end: str, cache: Path) -> pd.DataFrame:
    cache.mkdir(parents=True, exist_ok=True)
    out = []
    for ba, pts in BAS.items():
        f = cache / f"openmeteo_{ba}_{start}_{end}.csv"
        if not f.exists():
            r = requests.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params={
                    "latitude": ",".join(str(p[0]) for p in pts),
                    "longitude": ",".join(str(p[1]) for p in pts),
                    "start_date": start,
                    "end_date": end,
                    "daily": "temperature_2m_mean",
                    "timezone": "auto",
                },
                timeout=120,
            )
            r.raise_for_status()
            js = r.json()
            js = js if isinstance(js, list) else [js]
            t = pd.concat(
                [pd.Series(j["daily"]["temperature_2m_mean"], index=pd.to_datetime(j["daily"]["time"])) for j in js],
                axis=1,
            ).mean(axis=1)
            t.rename("temp_mean").rename_axis("date").to_csv(f)
            time.sleep(1)
        t = pd.read_csv(f, parse_dates=["date"]).assign(id=ba)
        out.append(t)
    t = pd.concat(out, ignore_index=True)
    t["cdd"] = (t.temp_mean - 18).clip(lower=0)
    t["hdd"] = (18 - t.temp_mean).clip(lower=0)
    return t


def build(raw_dir: Path = Path("data/raw"), out_dir: Path = Path("data/processed")) -> pd.DataFrame:
    load = daily_load(download(raw_dir / "eia930"))
    end = load.dropna().date.max() - pd.Timedelta(days=2)
    load = load[load.date <= end]
    start = load.date.min().strftime("%Y-%m-%d")
    temp = temperature(start, end.strftime("%Y-%m-%d"), raw_dir / "openmeteo")
    df = load.merge(temp, on=["id", "date"], how="left")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "electricity.parquet", index=False)
    return df


if __name__ == "__main__":
    d = build()
    print(d.groupby("id").agg(start=("date", "min"), end=("date", "max"), n=("gwh", "count"), mean=("gwh", "mean")))
    print(d.isna().sum())
