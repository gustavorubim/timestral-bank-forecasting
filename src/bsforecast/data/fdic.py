"""FDIC BankFind Suite API client.

Used as the fallback source for bank holding company (BHC) data when the FFIEC NIC
FR Y-9C download is behind a CAPTCHA. We pull Call Report financials for *every*
FDIC-insured bank subsidiary whose regulatory high holder (``RSSDHCR``) at the report
date is one of the target BHCs, then aggregate to the holding-company level.

Caveat: this is the *bank-subsidiary* view of the BHC. It excludes nonbank
subsidiaries (broker-dealers, parent-only debt, etc.) that a true FR Y-9C includes.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

API = "https://api.fdic.gov/banks"

# Call Report fields (FDIC names). Income-statement fields are year-to-date.
STOCK_FIELDS = [
    "ASSET",
    "LNLSNET",
    "LNLSGR",
    "LNATRES",
    "DEP",
    "DEPDOM",
    "SC",
    "CHBAL",
    "TRADE",
    "EQTOT",
    "INTAN",
    "ERNAST",
    "NCLNLS",
    "RWAJT",
    "RBCT1CER",
]
FLOW_FIELDS = ["INTINC", "EINTEXP", "NIM", "NONII", "NONIX", "ELNATR", "NETINC", "NTLNLS"]
FIELDS = ["CERT", "REPDTE", "RSSDHCR", "NAMEHCR"] + STOCK_FIELDS + FLOW_FIELDS


def verify_holding_companies(rssd_ids: list[int]) -> pd.DataFrame:
    """Return active FDIC-insured subsidiaries of each holding company RSSD ID."""
    flt = " OR ".join(str(i) for i in rssd_ids)
    r = requests.get(
        f"{API}/institutions",
        params={
            "filters": f"RSSDHCR:({flt}) AND ACTIVE:1",
            "fields": "NAME,CERT,FED_RSSD,RSSDHCR,NAMEHCR,ASSET",
            "limit": 100,
        },
        timeout=60,
    )
    r.raise_for_status()
    return pd.DataFrame([d["data"] for d in r.json()["data"]])


def fetch_financials(
    rssd_id: int, start: str = "19950101", cache_dir: Path | None = None, fields: list[str] | None = None
) -> pd.DataFrame:
    """All Call Report rows of banks held by ``rssd_id`` (at the report date)."""
    fields = fields or FIELDS
    cache = cache_dir / f"fdic_financials_{rssd_id}_{start}.json" if cache_dir else None
    if cache and cache.exists():
        rows = json.loads(cache.read_text())
    else:
        rows, offset = [], 0
        while True:
            r = requests.get(
                f"{API}/financials",
                params={
                    "filters": f"RSSDHCR:{rssd_id} AND REPDTE:[{start} TO 99991231]",
                    "fields": ",".join(fields),
                    "limit": 10000,
                    "offset": offset,
                    "sort_by": "REPDTE",
                    "sort_order": "ASC",
                },
                timeout=120,
            )
            r.raise_for_status()
            js = r.json()
            batch = [d["data"] for d in js["data"]]
            rows.extend(batch)
            offset += len(batch)
            if not batch or offset >= js["meta"]["total"]:
                break
            time.sleep(0.3)
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(rows))
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["REPDTE"], format="%Y%m%d")
    return df


def ytd_to_quarterly(df: pd.DataFrame, fields: list[str] = FLOW_FIELDS) -> pd.DataFrame:
    """Convert year-to-date income items to discrete quarterly flows, per bank (CERT)."""
    df = df.sort_values(["CERT", "date"]).copy()
    df["year"] = df["date"].dt.year
    df["q"] = df["date"].dt.quarter
    for f in fields:
        v = pd.to_numeric(df[f], errors="coerce")
        prev = v.groupby([df["CERT"], df["year"]]).shift(1)
        prev_q = df.groupby(["CERT", "year"])["q"].shift(1)
        out = np.where(df["q"] == 1, v, np.nan)
        contiguous = (prev_q == df["q"] - 1) & prev.notna()
        out = np.where(contiguous, v - prev, out)
        # Sub appearing mid-year (e.g. acquired charter): spread its YTD evenly (approximation).
        gap = (df["q"] > 1) & ~contiguous
        out = np.where(gap, v / df["q"], out)
        df[f] = out
    return df.drop(columns=["year", "q"])


def aggregate_to_hc(df: pd.DataFrame, rssd_id: int) -> pd.DataFrame:
    """Sum bank subsidiaries into a holding-company quarterly panel."""
    df = ytd_to_quarterly(df)
    for f in STOCK_FIELDS:
        df[f] = pd.to_numeric(df[f], errors="coerce")
    df["CET1_CAP"] = df["RBCT1CER"] / 100.0 * df["RWAJT"]
    sums = STOCK_FIELDS[:-1] + FLOW_FIELDS + ["CET1_CAP"]
    g = df.groupby("date")
    out = g[sums].sum(min_count=1)
    out["n_banks"] = g["CERT"].nunique()
    out["rssd_hc"] = rssd_id
    # Only meaningful once the ratio is reported (2014+ for advanced approaches banks).
    out.loc[g["RBCT1CER"].count() == 0, "CET1_CAP"] = np.nan
    return out.reset_index()
