"""Retail: Census monthly retail sales by kind of business (FRED, NSA) and an M5 Walmart store x department panel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import requests

# FRED not-seasonally-adjusted retail sales by category ($ millions, monthly, 1992+).
RETAIL = {
    "motor_vehicles": "RSMVPDN",
    "furniture": "RSFHFSN",
    "electronics": "RSEASN",
    "building_materials": "RSBMGESDN",
    "food_beverage_stores": "RSDBSN",
    "health_personal": "RSHPCSN",
    "gasoline": "RSGASSN",
    "clothing": "RSCCASN",
    "sporting_hobby": "RSSGHBMSN",
    "general_merch": "RSGMSN",
    "misc_stores": "RSMSRN",
    "nonstore": "RSNSRN",
    "food_services": "RSFSDPN",
    "total_ex_food_services": "RSXFSN",
}

M5_BASE = "https://huggingface.co/datasets/kashif/M5/resolve/main/"


def calendar_features(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Deterministic (truly known) monthly calendar: seasonality + weekend/trading-day counts."""
    m = dates.month
    days = [pd.date_range(d.replace(day=1), d, freq="D") for d in dates]
    return pd.DataFrame(
        {
            "month_sin": np.sin(2 * np.pi * m / 12),
            "month_cos": np.cos(2 * np.pi * m / 12),
            "n_weekend_days": [int((d.dayofweek >= 5).sum()) for d in days],
            "n_days": [len(d) for d in days],
        },
        index=dates,
    )


def build_retail_census(raw_dir: Path, out_dir: Path) -> pd.DataFrame:
    from .fred import fetch_series

    rows = []
    for name, fid in RETAIL.items():
        s = fetch_series(fid, raw_dir).resample("ME").last() / 1e3  # $ billions
        rows.append(pd.DataFrame({"id": name, "date": s.index.normalize(), "sales": s.to_numpy()}))
    df = pd.concat(rows, ignore_index=True).dropna()
    dates = pd.DatetimeIndex(sorted(df.date.unique()))
    cal = calendar_features(dates)
    cpi = fetch_series("CPIAUCNS", raw_dir).resample("ME").mean()
    unr = fetch_series("UNRATE", raw_dir).resample("ME").mean()
    rdi = fetch_series("DSPIC96", raw_dir).resample("ME").mean()
    gas = fetch_series("GASREGW", raw_dir).resample("ME").mean()
    macro = pd.DataFrame(
        {
            "cpi_inflation": 100 * np.log(cpi).diff(12),
            "unemployment": unr,
            "rdi_growth": 100 * np.log(rdi).diff(12),
            "gas_price": gas,
        }
    )
    macro.index = macro.index.normalize()
    x = cal.join(macro.reindex(dates).ffill()).rename_axis("date").reset_index()
    df = df.merge(x, on="date", how="left")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "retail_census_panel.parquet", index=False)
    return df


def _m5_file(raw_dir: Path, name: str) -> Path:
    p = raw_dir / "m5" / name
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(M5_BASE + name, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(p, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    return p


def build_m5(raw_dir: Path, out_dir: Path, start: str = "2013-01-01") -> pd.DataFrame:
    """Store x department daily unit sales (10 stores x 7 departments = 70 series) + known covariates."""
    cal = pd.read_csv(_m5_file(raw_dir, "calendar.csv"), parse_dates=["date"])
    sales = pd.read_csv(_m5_file(raw_dir, "sales_train_evaluation.csv"))
    dcols = [c for c in sales.columns if c.startswith("d_")]
    agg = sales.groupby(["store_id", "dept_id"])[dcols].sum()
    del sales
    long = agg.stack().rename("units").reset_index().rename(columns={"level_2": "d"})
    long = long.merge(cal[["d", "date", "wm_yr_wk"]], on="d")
    # Relative price index per store x dept: mean over items of price / item's own mean price.
    pr = pd.read_csv(
        _m5_file(raw_dir, "sell_prices.csv"),
        dtype={"store_id": "category", "item_id": "category", "wm_yr_wk": "int32", "sell_price": "float32"},
    )
    pr["dept_id"] = pr["item_id"].astype(str).str.rsplit("_", n=1).str[0]
    pr["rel"] = pr["sell_price"] / pr.groupby(["store_id", "item_id"], observed=True)["sell_price"].transform("mean")
    pidx = pr.groupby(["store_id", "dept_id", "wm_yr_wk"], observed=True)["rel"].mean().rename("price_index")
    del pr
    long = long.merge(pidx.reset_index().astype({"store_id": str}), on=["store_id", "dept_id", "wm_yr_wk"], how="left")
    long["price_index"] = long.groupby(["store_id", "dept_id"])["price_index"].ffill().bfill()
    c = cal.set_index("date")
    feats = pd.DataFrame(index=c.index)
    feats["dow_sin"] = np.sin(2 * np.pi * c["wday"] / 7)
    feats["dow_cos"] = np.cos(2 * np.pi * c["wday"] / 7)
    ev = c[["event_type_1", "event_type_2"]]
    for t in ["Sporting", "Cultural", "National", "Religious"]:
        feats[f"event_{t.lower()}"] = ev.eq(t).any(axis=1).astype(float)
    christmas = (c.index.month == 12) & (c.index.day == 25)
    feats["christmas"] = christmas.astype(float)  # stores are closed
    long = long.merge(feats.rename_axis("date").reset_index(), on="date")
    long["snap"] = 0.0
    for st in ["CA", "TX", "WI"]:
        m = long.store_id.str.startswith(st)
        long.loc[m, "snap"] = long.loc[m, "date"].map(c[f"snap_{st}"]).astype(float)
    long["id"] = long.store_id + "|" + long.dept_id
    long = long[long.date >= start].drop(columns=["d", "wm_yr_wk"]).sort_values(["id", "date"])
    out_dir.mkdir(parents=True, exist_ok=True)
    long.to_parquet(out_dir / "m5_store_dept_panel.parquet", index=False)
    return long
