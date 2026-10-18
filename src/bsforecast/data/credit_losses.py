"""Fed charge-off and delinquency rates (all commercial banks, SA, %) by loan type, quarterly.

Long panel: id = loan type, targets = chargeoff, delinquency. Known-future macro from the CCAR-style
panel (unemployment, GDP growth, HPI, CRE prices, Baa spread, 10y).
Run: python -m bsforecast.data.credit_losses  -> data/processed/credit_losses.parquet
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .fred import ccar_macro_panel, fetch_series

# loan type -> (charge-off series, delinquency series)
LOANS = {
    "all_loans": ("CORALACBS", "DRALACBS"),
    "business": ("CORBLACBS", "DRBLACBS"),
    "resi_mortgage": ("CORSFRMACBS", "DRSFRMACBS"),
    "cre_ex_farm": ("CORCREXFACBS", "DRCRELEXFACBS"),
    "consumer": ("CORCACBS", "DRCLACBS"),
    "credit_card": ("CORCCACBS", "DRCCLACBS"),
    "other_consumer": ("COROCLACBS", "DROCLACBS"),
}
MACRO = ["unemployment", "gdp_growth", "hpi_growth", "cre_price_growth", "baa_spread", "ust_10y"]


def build(raw_dir: Path = Path("data/raw"), out_dir: Path = Path("data/processed"), start: str = "1991-03-31"):
    cache = raw_dir / "fred"
    macro = ccar_macro_panel(cache)[MACRO]
    rows = []
    for name, (co, dq) in LOANS.items():
        d = pd.DataFrame(
            {
                "chargeoff": fetch_series(co, cache).resample("QE").last(),
                "delinquency": fetch_series(dq, cache).resample("QE").last(),
            }
        ).join(macro, how="left")
        d = d[d.index >= start].dropna(subset=["chargeoff", "delinquency"], how="all")
        d["id"] = name
        rows.append(d.reset_index(names="date"))
    df = pd.concat(rows, ignore_index=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "credit_losses.parquet", index=False)
    return df


if __name__ == "__main__":
    d = build()
    print(d.groupby("id")[["chargeoff", "delinquency"]].agg(["first", "last", "count"]))
    print(d.dropna().date.max(), d.date.max())
