"""Metro house prices and rents: FHFA all-transactions metro HPI (quarterly) and Zillow ZHVI/ZORI (monthly)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import requests

FHFA_URL = "https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_at_metro.csv"
ZHVI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)
ZORI_URL = "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv"

# short id -> (FHFA metro / metro-division name, Zillow RegionName)
METROS = {
    "Tampa": ("Tampa, FL (MSAD)", "Tampa, FL"),
    "Orlando": ("Orlando-Kissimmee-Sanford, FL", "Orlando, FL"),
    "Miami": ("Miami-Miami Beach-Kendall, FL (MSAD)", "Miami, FL"),
    "Atlanta": ("Atlanta-Sandy Springs-Roswell, GA (MSAD)", "Atlanta, GA"),
    "Charlotte": ("Charlotte-Concord-Gastonia, NC-SC", "Charlotte, NC"),
    "Nashville": ("Nashville-Davidson--Murfreesboro--Franklin, TN", "Nashville, TN"),
    "Washington": ("Washington, DC-MD (MSAD)", "Washington, DC"),
    "NewYork": ("New York-Jersey City-White Plains, NY-NJ (MSAD)", "New York, NY"),
    "Boston": ("Boston, MA (MSAD)", "Boston, MA"),
    "Philadelphia": ("Philadelphia, PA (MSAD)", "Philadelphia, PA"),
    "Chicago": ("Chicago-Naperville-Schaumburg, IL (MSAD)", "Chicago, IL"),
    "Detroit": ("Detroit-Dearborn-Livonia, MI (MSAD)", "Detroit, MI"),
    "Minneapolis": ("Minneapolis-St. Paul-Bloomington, MN-WI", "Minneapolis, MN"),
    "Dallas": ("Dallas-Plano-Irving, TX (MSAD)", "Dallas, TX"),
    "Houston": ("Houston-Pasadena-The Woodlands, TX", "Houston, TX"),
    "Austin": ("Austin-Round Rock-San Marcos, TX", "Austin, TX"),
    "Denver": ("Denver-Aurora-Centennial, CO", "Denver, CO"),
    "Phoenix": ("Phoenix-Mesa-Chandler, AZ", "Phoenix, AZ"),
    "LasVegas": ("Las Vegas-Henderson-North Las Vegas, NV", "Las Vegas, NV"),
    "LosAngeles": ("Los Angeles-Long Beach-Glendale, CA (MSAD)", "Los Angeles, CA"),
    "SanFrancisco": ("San Francisco-San Mateo-Redwood City, CA (MSAD)", "San Francisco, CA"),
    "Seattle": ("Seattle-Bellevue-Kent, WA (MSAD)", "Seattle, WA"),
}


def _download(url: str, path: Path) -> Path:
    if not path.exists():
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return path


def monthly_macro(raw_dir: Path) -> pd.DataFrame:
    """Mortgage rate, unemployment, real disposable income growth (y/y %), monthly."""
    from .fred import fetch_series

    mort = fetch_series("MORTGAGE30US", raw_dir).resample("ME").mean()
    unr = fetch_series("UNRATE", raw_dir).resample("ME").mean()
    rdi = fetch_series("DSPIC96", raw_dir).resample("ME").mean()
    df = pd.DataFrame({"mortgage_rate": mort, "unemployment": unr, "rdi_growth": 100 * np.log(rdi).diff(12)})
    df.index = df.index.normalize()
    return df.rename_axis("date")


def fhfa_panel(raw_dir: Path) -> pd.DataFrame:
    p = _download(FHFA_URL, raw_dir / "housing" / "hpi_at_metro.csv")
    df = pd.read_csv(p, header=None, names=["metro", "cbsa", "year", "qtr", "hpi", "se"], na_values=["-"])
    inv = {v[0]: k for k, v in METROS.items()}
    df = df[df.metro.isin(inv)].assign(id=lambda d: d.metro.map(inv))
    df["date"] = pd.PeriodIndex.from_fields(year=df.year, quarter=df.qtr, freq="Q").end_time.normalize()
    df["hpi"] = pd.to_numeric(df["hpi"], errors="coerce")
    return df[["id", "date", "hpi"]]


def zillow_panel(raw_dir: Path) -> pd.DataFrame:
    inv = {v[1]: k for k, v in METROS.items()}
    out = []
    for name, url in (("zhvi", ZHVI_URL), ("zori", ZORI_URL)):
        p = _download(url, raw_dir / "housing" / url.rsplit("/", 1)[1])
        w = pd.read_csv(p)
        w = w[w.RegionName.isin(inv)]
        long = w.melt(id_vars=["RegionName"], value_vars=[c for c in w.columns if c[:2] in ("19", "20")])
        long = long.assign(id=long.RegionName.map(inv), date=pd.to_datetime(long.variable), var=name)
        out.append(long[["id", "date", "var", "value"]])
    z = pd.concat(out).pivot_table(index=["id", "date"], columns="var", values="value").reset_index()
    z["zhvi"] /= 1e3  # $ thousands
    return z


def build_housing(raw_dir: Path, out_dir: Path) -> dict[str, pd.DataFrame]:
    mm = monthly_macro(raw_dir)
    q = fhfa_panel(raw_dir)
    mq = mm.resample("QE").mean()
    mq.index = mq.index.normalize()
    q = q.merge(mq.reset_index(), on="date", how="left")
    q = q[q.date >= "1991-03-31"]
    z = zillow_panel(raw_dir).merge(mm.reset_index(), on="date", how="left")
    cov = list(mm.columns)
    z[cov] = z.groupby("id")[cov].ffill()  # latest month's macro release can lag by a month
    q[cov] = q.groupby("id")[cov].ffill()
    out_dir.mkdir(parents=True, exist_ok=True)
    q.to_parquet(out_dir / "housing_fhfa_panel.parquet", index=False)
    z.to_parquet(out_dir / "housing_zillow_panel.parquet", index=False)
    missing = sorted(set(METROS) - set(q.id)) + sorted(set(METROS) - set(z.id))
    if missing:
        print("metros missing:", missing)
    return {"fhfa": q, "zillow": z}
