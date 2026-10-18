"""Build the tidy top-4 BHC panel + macro covariates."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import fdic, fred

TOP4 = {
    "JPM": 1039502,
    "BAC": 1073757,
    "C": 1951350,
    "WFC": 1120754,
}


def build_bank_panel(raw_dir: Path, start: str = "19950101") -> pd.DataFrame:
    frames = []
    for ticker, rssd in TOP4.items():
        raw = fdic.fetch_financials(rssd, start=start, cache_dir=raw_dir)
        hc = fdic.aggregate_to_hc(raw, rssd)
        hc["bank"] = ticker
        frames.append(hc)
    df = pd.concat(frames, ignore_index=True)
    k = 1e-3  # FDIC reports $ thousands -> $ millions
    p = pd.DataFrame({"date": df["date"], "bank": df["bank"], "rssd_hc": df["rssd_hc"], "n_banks": df["n_banks"]})
    p["total_assets"] = df["ASSET"] * k
    p["loans_net"] = df["LNLSNET"] * k
    p["loans_gross"] = df["LNLSGR"] * k
    p["allowance"] = df["LNATRES"] * k
    p["deposits"] = df["DEP"] * k
    p["securities"] = df["SC"] * k
    p["cash_due"] = df["CHBAL"] * k
    p["trading_assets"] = df["TRADE"].fillna(0) * k
    p["other_assets"] = p["total_assets"] - p["loans_net"] - p["securities"] - p["cash_due"] - p["trading_assets"]
    p["equity"] = df["EQTOT"] * k
    p["nii"] = df["NIM"] * k
    p["interest_income"] = df["INTINC"] * k
    p["interest_expense"] = df["EINTEXP"] * k
    p["nonint_income"] = df["NONII"] * k
    p["nonint_expense"] = df["NONIX"] * k
    p["provisions"] = df["ELNATR"] * k
    p["net_income"] = df["NETINC"] * k
    p["net_chargeoffs"] = df["NTLNLS"] * k
    p["noncurrent_loans"] = df["NCLNLS"] * k
    p["rwa"] = df["RWAJT"] * k
    # Derived metrics (annualised where flows)
    avg_assets = p.groupby("bank")["total_assets"].transform(lambda s: (s + s.shift(1)) / 2)
    avg_equity = p.groupby("bank")["equity"].transform(lambda s: (s + s.shift(1)) / 2)
    earn = df["ERNAST"] * k
    avg_earn = earn.groupby(p["bank"]).transform(lambda s: (s + s.shift(1)) / 2)
    p["roa"] = 400 * p["net_income"] / avg_assets
    p["roe"] = 400 * p["net_income"] / avg_equity
    p["nim"] = 400 * p["nii"] / avg_earn
    p["efficiency_ratio"] = 100 * p["nonint_expense"] / (p["nii"] + p["nonint_income"])
    p["loan_to_deposit"] = 100 * p["loans_gross"] / p["deposits"]
    p["cet1_ratio"] = 100 * df["CET1_CAP"] / df["RWAJT"]
    p["equity_to_assets"] = 100 * p["equity"] / p["total_assets"]
    p["nco_rate"] = 400 * p["net_chargeoffs"] / p["loans_gross"]
    p = p.replace([np.inf, -np.inf], np.nan)
    return p.sort_values(["bank", "date"]).reset_index(drop=True)


def build(raw_dir: Path, out_dir: Path, start_panel: str = "2001-03-31") -> pd.DataFrame:
    banks = build_bank_panel(raw_dir)
    macro = fred.quarterly_macro(raw_dir)
    banks["date"] = banks["date"] + pd.offsets.QuarterEnd(0)
    panel = banks.merge(macro.reset_index(), on="date", how="left")
    panel = panel[panel["date"] >= start_panel].reset_index(drop=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(out_dir / "top4_bhc_panel.parquet", index=False)
    panel.to_csv(out_dir / "top4_bhc_panel.csv", index=False)
    macro.reset_index().to_csv(out_dir / "macro_quarterly.csv", index=False)
    long = panel.melt(id_vars=["date", "bank", "rssd_hc"], var_name="variable", value_name="value")
    long.to_parquet(out_dir / "top4_bhc_panel_long.parquet", index=False)
    return panel
