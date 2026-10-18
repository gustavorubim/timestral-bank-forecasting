"""Granular balance-sheet / income-statement panel for the top-4 BHCs + a CCAR-style macro panel.

FDIC BankFind Call Report field codes used (all $ thousands in the source, converted to $ millions):

Assets
  cash_due        CHBAL     cash & due from depository institutions
  ib_balances     CHBALI    interest-bearing balances (subset of CHBAL)
  ffs_repo        FREPO     fed funds sold & securities purchased under agreements to resell
  sec_afs         SCAF      available-for-sale securities
  sec_htm         SCHA      held-to-maturity securities
  securities      SC        total securities
  trading_assets  TRADE     trading account assets
  loans_total     LNLSGR    total loans & leases (gross)
  loans_re        LNRE      real-estate loans
  loans_resi      LNRERES   1-4 family residential RE loans
  loans_cre       LNREMULT + LNRENRES + LNRECONS   multifamily + nonfarm nonresidential + construction & land
  loans_ci        LNCI      commercial & industrial loans
  loans_consumer  LNCON     consumer loans
  loans_card      LNCRCD    credit-card loans (subset of LNCON)
  loans_other     LNOTHER + LNAG + LNMUNI + LNDEP + LNFG   nondep. fin. inst. & other, agri, muni, dep. inst., foreign govt
  allowance       LNATRES   allowance for loan & lease losses
  other_assets    BKPREM + ORE + INTAN + AOA   premises, OREO, intangibles, all other assets
  total_assets    ASSET
Liabilities
  deposits        DEP;  dep_dom DEPDOM; dep_for DEPFOR; dep_ib DEPI; dep_nib DEPNI
  ffp_repo        FREPP     fed funds purchased & repos
  trading_liab    TRADEL
  other_borrowed  OTHBRF
  sub_debt        SUBND
  other_liab      ALLOTHL
  total_liab      LIAB
  equity          EQTOT
Income (YTD in the source, de-cumulated to quarters)
  interest_income INTINC; interest_expense EINTEXP; nii NIM; nonint_income NONII; nonint_expense NONIX;
  provisions ELNATR; net_income NETINC
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import fdic, fred
from .build import TOP4

STOCK = [
    "ASSET",
    "CHBAL",
    "CHBALI",
    "FREPO",
    "SCAF",
    "SCHA",
    "SC",
    "TRADE",
    "LNLSGR",
    "LNLSNET",
    "LNRE",
    "LNRERES",
    "LNREMULT",
    "LNRENRES",
    "LNRECONS",
    "LNCI",
    "LNCON",
    "LNCRCD",
    "LNOTHER",
    "LNAG",
    "LNMUNI",
    "LNDEP",
    "LNFG",
    "LNATRES",
    "BKPREM",
    "ORE",
    "INTAN",
    "AOA",
    "DEP",
    "DEPDOM",
    "DEPFOR",
    "DEPI",
    "DEPNI",
    "FREPP",
    "TRADEL",
    "OTHBRF",
    "SUBND",
    "ALLOTHL",
    "LIAB",
    "EQTOT",
]
FLOW = ["INTINC", "EINTEXP", "NIM", "NONII", "NONIX", "ELNATR", "NETINC"]

LINES = {
    "income": {
        "interest_income": ["INTINC"],
        "interest_expense": ["EINTEXP"],
        "nii": ["NIM"],
        "nonint_income": ["NONII"],
        "nonint_expense": ["NONIX"],
        "provisions": ["ELNATR"],
        "net_income": ["NETINC"],
    },
    "assets": {
        "cash_due": ["CHBAL"],
        "ib_balances": ["CHBALI"],
        "ffs_repo": ["FREPO"],
        "sec_afs": ["SCAF"],
        "sec_htm": ["SCHA"],
        "securities": ["SC"],
        "trading_assets": ["TRADE"],
        "loans_total": ["LNLSGR"],
        "loans_re": ["LNRE"],
        "loans_resi": ["LNRERES"],
        "loans_cre": ["LNREMULT", "LNRENRES", "LNRECONS"],
        "loans_ci": ["LNCI"],
        "loans_consumer": ["LNCON"],
        "loans_card": ["LNCRCD"],
        "loans_other": ["LNOTHER", "LNAG", "LNMUNI", "LNDEP", "LNFG"],
        "allowance": ["LNATRES"],
        "other_assets": ["BKPREM", "ORE", "INTAN", "AOA"],
        "total_assets": ["ASSET"],
    },
    "liabilities": {
        "deposits": ["DEP"],
        "dep_dom": ["DEPDOM"],
        "dep_for": ["DEPFOR"],
        "dep_ib": ["DEPI"],
        "dep_nib": ["DEPNI"],
        "ffp_repo": ["FREPP"],
        "trading_liab": ["TRADEL"],
        "other_borrowed": ["OTHBRF"],
        "sub_debt": ["SUBND"],
        "other_liab": ["ALLOTHL"],
        "total_liab": ["LIAB"],
        "equity": ["EQTOT"],
    },
}

# (name, total, [components], [signs]) accounting checks
CHECKS = [
    ("nii = int. income - int. expense", "nii", ["interest_income", "interest_expense"], [1, -1]),
    ("securities = AFS + HTM", "securities", ["sec_afs", "sec_htm"], [1, 1]),
    ("RE loans >= resi + CRE", "loans_re", ["loans_resi", "loans_cre"], [1, 1]),
    (
        "loans = RE + C&I + consumer + other",
        "loans_total",
        ["loans_re", "loans_ci", "loans_consumer", "loans_other"],
        [1, 1, 1, 1],
    ),
    (
        "assets = cash + FFS + sec + trading + loans - ALLL + other",
        "total_assets",
        ["cash_due", "ffs_repo", "securities", "trading_assets", "loans_total", "allowance", "other_assets"],
        [1, 1, 1, 1, 1, -1, 1],
    ),
    ("deposits = domestic + foreign", "deposits", ["dep_dom", "dep_for"], [1, 1]),
    ("deposits = int.-bearing + nonint.-bearing", "deposits", ["dep_ib", "dep_nib"], [1, 1]),
    (
        "liabilities = dep + FFP + trading + borrowed + sub + other",
        "total_liab",
        ["deposits", "ffp_repo", "trading_liab", "other_borrowed", "sub_debt", "other_liab"],
        [1] * 6,
    ),
    ("assets = liabilities + equity", "total_assets", ["total_liab", "equity"], [1, 1]),
]


def bank_lines(raw_dir: Path, start: str = "19950101") -> pd.DataFrame:
    fields = ["CERT", "REPDTE", "RSSDHCR"] + STOCK + FLOW
    frames = []
    for ticker, rssd in TOP4.items():
        df = fdic.fetch_financials(rssd, start=start, cache_dir=raw_dir / "granular", fields=fields)
        df = fdic.ytd_to_quarterly(df, FLOW)
        for f in STOCK + FLOW:
            df[f] = pd.to_numeric(df[f], errors="coerce")
        g = df.groupby("date")
        agg = g[STOCK + FLOW].sum(min_count=1)
        agg["n_banks"] = g["CERT"].nunique()
        agg["bank"] = ticker
        frames.append(agg.reset_index())
    src = pd.concat(frames, ignore_index=True)
    out = src[["date", "bank", "n_banks"]].copy()
    for group in LINES.values():
        for name, codes in group.items():
            out[name] = src[codes].sum(axis=1, min_count=len(codes)) * 1e-3
    out["date"] = out["date"] + pd.offsets.QuarterEnd(0)
    return out


def check_identities(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, total, comps, signs in CHECKS:
        s = sum(sg * panel[c] for sg, c in zip(signs, comps, strict=True))
        gap = 100 * (s - panel[total]) / panel[total].abs()
        for bank, g in gap.groupby(panel["bank"]):
            g = g.dropna()
            rows.append(
                {
                    "check": name,
                    "bank": bank,
                    "n_quarters": len(g),
                    "median_gap_pct": g.median(),
                    "max_abs_gap_pct": g.abs().max(),
                    "share_over_1pct": (g.abs() > 1).mean(),
                }
            )
    return pd.DataFrame(rows)


def coverage(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group, lines in LINES.items():
        for line, codes in lines.items():
            for bank, g in panel.groupby("bank"):
                v = g.set_index("date")[line]
                nz = v[v.abs() > 0]
                rows.append(
                    {
                        "group": group,
                        "line": line,
                        "fdic_codes": "+".join(codes),
                        "bank": bank,
                        "first": v.first_valid_index(),
                        "n_obs": int(v.notna().sum()),
                        "n_nonzero": int(len(nz)),
                    }
                )
    return pd.DataFrame(rows)


def build_macro_panel(raw_dir: Path, out_dir: Path, start_panel: str = "2001-03-31") -> pd.DataFrame:
    banks = bank_lines(raw_dir)
    macro = fred.ccar_macro_panel(raw_dir)
    panel = banks.merge(macro.reset_index(), on="date", how="left")
    panel = panel[panel["date"] >= start_panel].sort_values(["bank", "date"]).reset_index(drop=True)
    panel = panel.replace([np.inf, -np.inf], np.nan)
    out_dir.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(out_dir / "macro_panel.parquet", index=False)
    macro.reset_index().to_csv(out_dir / "ccar_macro_quarterly.csv", index=False)
    check_identities(panel).to_csv(out_dir / "macro_panel_identity_checks.csv", index=False)
    coverage(panel).to_csv(out_dir / "macro_panel_coverage.csv", index=False)
    return panel
