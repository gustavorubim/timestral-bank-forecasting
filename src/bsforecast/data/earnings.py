"""Quarterly company fundamentals from SEC EDGAR XBRL companyfacts (free, no key).

Fiscal quarters are mapped to calendar quarters by the quarter that contains the
period midpoint (end - 45 days), so e.g. a Nov-Jan retail quarter lands in Q4.
Q4 is rarely tagged as a 3-month fact: it is derived as FY minus Q1..Q3 (for EPS
this is approximate because the share count moves within the year).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# SEC asks for a descriptive User-Agent with a real contact address.
UA = "gustavorubim research REDACTED_EMAIL"

COMPANIES = {  # ticker -> sector (non-financials: operating income is well defined)
    "AAPL": "tech", "MSFT": "tech", "NVDA": "tech", "INTC": "tech", "CSCO": "tech", "ORCL": "tech",
    "AMZN": "consumer_disc", "HD": "consumer_disc", "MCD": "consumer_disc", "NKE": "consumer_disc",
    "WMT": "staples", "KO": "staples", "PEP": "staples", "PG": "staples",
    "JNJ": "health", "PFE": "health", "MRK": "health", "UNH": "health", "ABT": "health",
    "CAT": "industrials", "HON": "industrials", "UNP": "industrials", "LMT": "industrials",
    "VZ": "telecom", "T": "telecom", "DUK": "utilities", "NEE": "utilities", "LIN": "materials",
    "GOOGL": "comm", "META": "comm", "DIS": "comm",
}  # fmt: skip

TAGS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueGoodsNet",
        "RegulatedAndUnregulatedOperatingRevenue",
    ],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
}


def _get(url: str, cache: Path) -> dict:
    if cache.exists():
        return json.loads(cache.read_text())
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}, timeout=60)
    r.raise_for_status()
    time.sleep(0.2)  # well under the 10 req/s fair-access limit
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(r.text)
    return r.json()


def _cal_q(end: pd.Series) -> pd.Series:
    return (end - pd.Timedelta(days=45)).dt.to_period("Q").dt.end_time.dt.normalize()


def quarterly_facts(units: list[dict]) -> pd.Series:
    """3-month values by calendar quarter, deriving Q4 = FY - (Q1+Q2+Q3) where needed."""
    df = pd.DataFrame(units)
    if df.empty or "start" not in df:
        return pd.Series(dtype=float)
    df = df[df["form"].astype(str).str.startswith(("10-Q", "10-K"))].copy()
    df["start"], df["end"] = pd.to_datetime(df["start"]), pd.to_datetime(df["end"])
    df["days"] = (df["end"] - df["start"]).dt.days
    df = df.sort_values("filed").drop_duplicates(["start", "end"], keep="last")
    q = df[df.days.between(80, 100)][["start", "end", "val"]]
    a = df[df.days.between(350, 380)][["start", "end", "val"]]
    derived = []
    for _, r in a.iterrows():
        if ((q.end - r.end).abs() <= pd.Timedelta(days=7)).any():
            continue
        inner = q[(q.start >= r.start - pd.Timedelta(days=7)) & (q.end <= r.end - pd.Timedelta(days=60))]
        inner = inner.drop_duplicates("end")
        if len(inner) == 3:
            derived.append({"start": inner.end.max(), "end": r.end, "val": r.val - inner.val.sum()})
    if derived:
        q = pd.concat([q, pd.DataFrame(derived)], ignore_index=True)
    q = q.assign(date=_cal_q(q["end"])).sort_values("end").drop_duplicates("date", keep="last")
    return q.set_index("date")["val"].astype(float)


def company_panel(facts: dict) -> pd.DataFrame:
    g = facts.get("facts", {}).get("us-gaap", {})
    cols = {}
    for name, tags in TAGS.items():
        parts = []
        for t in tags:
            units = g.get(t, {}).get("units", {})
            u = units.get("USD/shares") if name == "eps" else units.get("USD")
            if u:
                parts.append(quarterly_facts(u))
        if parts:  # earlier tags in the list take priority period by period
            s = parts[0]
            for p in parts[1:]:
                s = s.combine_first(p)
            cols[name] = s
    return pd.DataFrame(cols)


def build_earnings(raw_dir: Path, out_dir: Path, min_coverage: float = 0.85) -> pd.DataFrame:
    from .fred import fetch_series

    raw = raw_dir / "sec"
    tick = _get("https://www.sec.gov/files/company_tickers.json", raw / "company_tickers.json")
    cik = {v["ticker"]: int(v["cik_str"]) for v in tick.values()}
    frames, dropped = [], {}
    for t, sector in COMPANIES.items():
        f = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik[t]:010d}.json", raw / f"cf_{t}.json")
        p = company_panel(f).reindex(columns=list(TAGS))
        p = p[p.index >= "2009-06-30"]
        p["op_margin"] = p["operating_income"] / p["revenue"]
        cov = p[["revenue", "op_margin", "net_income", "eps"]].notna().mean()
        if cov.min() < min_coverage or len(p) < 50:
            dropped[t] = cov.round(2).to_dict()
            continue
        p["revenue"] /= 1e9
        p["net_income"] /= 1e9
        p["operating_income"] /= 1e9
        frames.append(p.assign(company=t, sector=sector).rename_axis("date").reset_index())
    panel = pd.concat(frames, ignore_index=True)
    # Known-future macro covariates (quarterly).
    gdp = fetch_series("GDPC1", raw_dir).resample("QE").last()
    ngdp = fetch_series("GDP", raw_dir).resample("QE").last()
    cpi = fetch_series("CPIAUCSL", raw_dir).resample("QE").mean()
    macro = pd.DataFrame(
        {
            "gdp_growth": 400 * np.log(gdp).diff(),
            "ngdp_growth": 400 * np.log(ngdp).diff(),
            "cpi_inflation": 400 * np.log(cpi).diff(),
            "ust_10y": fetch_series("GS10", raw_dir).resample("QE").mean(),
            "fed_funds": fetch_series("FEDFUNDS", raw_dir).resample("QE").mean(),
            "unemployment": fetch_series("UNRATE", raw_dir).resample("QE").mean(),
        }
    ).rename_axis("date")
    macro.index = macro.index.normalize()
    panel = panel.merge(macro.reset_index(), on="date", how="left")
    last_q = panel.groupby("date")["revenue"].count()
    panel = panel[panel.date <= last_q[last_q >= 0.8 * panel.company.nunique()].index.max()]
    out_dir.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(out_dir / "earnings_panel.parquet", index=False)
    (out_dir / "earnings_dropped.json").write_text(json.dumps(dropped, indent=1))
    return panel
