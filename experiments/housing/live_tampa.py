"""Live forecast plot for Tampa from the latest data (FHFA quarterly + Zillow monthly).

uv run python experiments/housing/live_tampa.py
Reads reports/housing/{fhfa,zillow}/backtest.parquet (live origin rows) and the processed panels.
Known-covariate models hold the last observed macro value flat over the horizon (a "no change" scenario).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODELS = {"arima": "tab:orange", "ets": "tab:green", "timestral": "tab:blue", "timestral_macro_known": "tab:purple"}
PANELS = [
    ("fhfa", "hpi", "housing_fhfa_panel.parquet", "FHFA all-transactions HPI (quarterly)", 40),
    ("zillow", "zhvi", "housing_zillow_panel.parquet", "Zillow ZHVI, $k (monthly)", 96),
    ("zillow", "zori", "housing_zillow_panel.parquet", "Zillow ZORI rent, $ (monthly)", 96),
]


def main(metro: str = "Tampa") -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.4))
    rows = []
    for ax, (src, tgt, fname, title, hist) in zip(axes, PANELS, strict=True):
        bt_path = ROOT / "reports/housing" / src / "backtest.parquet"
        if not bt_path.exists():  # that experiment has not finished yet
            ax.set_title(f"{metro}: {title} (pending)", fontsize=10)
            continue
        bt = pd.read_parquet(bt_path)
        live = bt[bt.live & (bt.id == metro) & (bt.target == tgt)]
        hst = pd.read_parquet(ROOT / "data/processed" / fname)
        hst = hst[hst.id == metro].dropna(subset=[tgt]).tail(hist)
        ax.plot(hst.date, hst[tgt], color="k", lw=2, label="actual")
        for m, col in MODELS.items():
            d = live[live.model == m].sort_values("h")
            if d.empty:
                continue
            x = pd.DatetimeIndex([d.origin.iloc[0]]).append(pd.DatetimeIndex(d.date))
            ax.plot(x, [d.y_origin.iloc[0], *d["q0.5"]], color=col, lw=1.6, label=m)
            ax.fill_between(d.date, d["q0.1"], d["q0.9"], color=col, alpha=0.12)
            last = d.iloc[-1]
            rows.append(
                {
                    "series": tgt,
                    "model": m,
                    "origin": d.origin.iloc[0].date(),
                    "end": last.date.date(),
                    "last_actual": round(float(d.y_origin.iloc[0]), 2),
                    "median_end": round(float(last["q0.5"]), 2),
                    "pct_change": round(100 * (last["q0.5"] / d.y_origin.iloc[0] - 1), 1),
                    "p10_end": round(float(last["q0.1"]), 2),
                    "p90_end": round(float(last["q0.9"]), 2),
                }
            )
        ax.set_title(f"{metro}: {title}", fontsize=10)
        ax.tick_params(labelsize=8)
    axes[0].legend(fontsize=8)
    fig.suptitle(f"{metro} live forecast from latest data (median, 80% band); macro held flat for *_known", y=1.02)
    fig.tight_layout()
    out = ROOT / "reports/housing/figures"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"live_{metro.lower()}.png"
    fig.savefig(path, dpi=110, bbox_inches="tight")
    tbl = pd.DataFrame(rows)
    tbl.to_csv(out / f"live_{metro.lower()}.csv", index=False)
    print(tbl.to_string(index=False))
    return path


if __name__ == "__main__":
    main()
