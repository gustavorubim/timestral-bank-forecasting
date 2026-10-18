"""Analytics plots (PNG)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .dataset import Panel  # noqa: E402

PALETTE = {
    "timestral_macro_known": "#9467bd",
    "timestral_macro_compact": "#2ca02c",
    "arimax_macro_small": "#17becf",
    "timestral_curve_known": "#9467bd",
    "timestral_curve_past": "#ff7f0e",
    "timestral_factors_known": "#2ca02c",
    "arimax_curve_factors": "#17becf",
    "timestral": "#d62728",
    "timestral_cov": "#ff7f0e",
    "timestral_cov_oracle": "#9467bd",
    "timestral_mv": "#8c564b",
    "arima": "#1f77b4",
    "arimax_oracle": "#17becf",
    "naive": "#7f7f7f",
    "snaive": "#bcbd22",
}


def _c(m: str) -> str:
    return PALETTE.get(m, None) or f"C{abs(hash(m)) % 10}"


def fan_grid(bt, panel: Panel, series, origin, models, path: Path, title: str, history: int = 32):
    ids = panel.ids
    if not series:
        return
    fig, axes = plt.subplots(len(series), len(ids), figsize=(4.2 * len(ids), 2.8 * len(series)), squeeze=False)
    origin = pd.Timestamp(origin)
    o_idx = int(np.searchsorted(panel.dates, origin))
    for r, tgt in enumerate(series):
        j = panel.targets.index(tgt)
        for c, i in enumerate(ids):
            ax = axes[r, c]
            ii = ids.index(i)
            lo = max(0, o_idx - history)
            hi = min(len(panel.dates), o_idx + 9)
            ax.plot(panel.dates[lo:hi], panel.y[ii, j, lo:hi], color="k", lw=1.4, label="actual")
            for m in models:
                d = bt[(bt.model == m) & (bt.id == i) & (bt.target == tgt) & (bt.origin == origin)].sort_values("h")
                if d.empty:
                    continue
                x = pd.DatetimeIndex([origin]).append(pd.DatetimeIndex(d["date"]))
                y0 = d["y_origin"].iloc[0]
                ax.plot(x, np.r_[y0, d["q0.5"]], color=_c(m), lw=1.5, label=m)
                if "q0.1" in d:
                    ax.fill_between(d["date"], d["q0.1"], d["q0.9"], color=_c(m), alpha=0.18)
            ax.axvline(origin, color="grey", ls=":", lw=1)
            if r == 0:
                ax.set_title(i)
            if c == 0:
                ax.set_ylabel(tgt)
            ax.tick_params(labelsize=7)
    h, lab = axes[0, 0].get_legend_handles_labels()
    fig.suptitle(title, y=1.035)
    fig.legend(h, lab, loc="upper center", bbox_to_anchor=(0.5, 1.01), ncol=len(lab), fontsize=9, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def error_by_horizon(by_h: pd.DataFrame, path: Path, metric: str = "MASE", groups: dict | None = None):
    groups = groups or {"all": None}
    fig, axes = plt.subplots(1, len(groups), figsize=(4.6 * len(groups), 3.6), squeeze=False)
    for ax, (gname, _) in zip(axes[0], groups.items(), strict=True):
        d = by_h[by_h["group"] == gname]
        for m, g in d.groupby("model"):
            ax.plot(g["h"], g[metric], marker="o", ms=3, color=_c(m), label=m)
        ax.set_title(f"{metric} by horizon: {gname}")
        ax.set_xlabel("horizon (quarters ahead)")
        ax.grid(alpha=0.3)
    axes[0, 0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def heatmap(
    pv: pd.DataFrame,
    path: Path,
    title: str,
    center: float = 0.5,
    fmt: str = "{:.0%}",
    cmap: str = "RdBu",
    span: float = 0.5,
):
    fig, ax = plt.subplots(figsize=(max(7.5, 1.0 + 0.55 * pv.shape[1]), 1.2 + 0.35 * pv.shape[0]))
    im = ax.imshow(pv.to_numpy(float), cmap=cmap, vmin=center - span, vmax=center + span, aspect="auto")
    ax.set_xticks(range(pv.shape[1]), pv.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(pv.shape[0]), pv.index, fontsize=8)
    for r in range(pv.shape[0]):
        for c in range(pv.shape[1]):
            v = pv.iat[r, c]
            if pd.notna(v):
                ax.text(c, r, fmt.format(v), ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, fraction=0.03)
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def rel_mase_bars(rel: pd.DataFrame, rel_bank: pd.DataFrame, baseline: str, path: Path):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    r = rel.sort_values("rel_mase")
    axes[0].barh(r["model"], r["rel_mase"], color=[_c(m) for m in r["model"]])
    axes[0].axvline(1, color="k", lw=1)
    axes[0].set_title(f"Relative MASE vs {baseline} (geo-mean over series; <1 better)")
    for y, v in enumerate(r["rel_mase"]):
        axes[0].text(v, y, f" {v:.2f}", va="center", fontsize=8)
    pv = rel_bank.pivot(index="id", columns="model", values="rel_mase")
    pv = pv[[m for m in r["model"] if m in pv.columns]]
    pv.plot.bar(ax=axes[1], color=[_c(m) for m in pv.columns], width=0.8)
    axes[1].axhline(1, color="k", lw=1)
    axes[1].set_title("Relative MASE by bank")
    axes[1].legend(fontsize=7, ncol=2)
    axes[1].tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def identity_plot(gaps: pd.DataFrame, path: Path, name: str):
    d = gaps[~gaps["live"]]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    g = d.groupby(["model", "h"])["gap_pct"].apply(lambda s: s.abs().mean()).reset_index()
    for m, x in g.groupby("model"):
        axes[0].plot(x["h"], x["gap_pct"], marker="o", ms=3, color=_c(m), label=m)
    ga = d[d["model"] == d["model"].iloc[0]].groupby("h")["gap_actual_pct"].apply(lambda s: s.abs().mean())
    axes[0].plot(ga.index, ga.values, color="k", ls="--", lw=2, label="actual (reference)")
    axes[0].set_title(f"{name}: mean |sum(components) - total| / |total|, %", fontsize=9)
    axes[0].set_xlabel("horizon")
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=7)
    d = d.assign(excess=(d["gap_pct"] - d["gap_actual_pct"]).abs())
    piv = d.pivot_table(index="model", columns="id", values="excess", aggfunc="median")
    piv.plot.bar(ax=axes[1])
    axes[1].set_title("median |forecast gap - actual gap| by bank, pp (lower = more coherent)", fontsize=9)
    axes[1].tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def coverage_plot(by_h: pd.DataFrame, path: Path):
    d = by_h[by_h["group"] == "all"]
    fig, ax = plt.subplots(figsize=(6, 3.6))
    for m, g in d.groupby("model"):
        ax.plot(g["h"], g["coverage80"], marker="o", ms=3, color=_c(m), label=m)
    ax.axhline(0.8, color="k", ls="--", lw=1)
    ax.set_ylim(0, 1)
    ax.set_title("Empirical coverage of 80% interval by horizon")
    ax.set_xlabel("horizon")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def skill_curves(
    rel_h: pd.DataFrame,
    rel_bank_h: pd.DataFrame,
    win_h: pd.DataFrame,
    dm_sum: pd.DataFrame,
    chal: str,
    base: str,
    path: Path,
):
    """Four-panel 'how does Timestral do vs ARIMA as the horizon grows' figure."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    ax = axes[0, 0]
    for m, g in rel_h.groupby("model"):
        if m == base:
            continue
        ax.plot(g["h"], g["rel_mase"], marker="o", ms=3, color=_c(m), lw=2.2 if m == chal else 1.2, label=m)
    ax.axhline(1, color="k", lw=1)
    ax.set_title(f"Relative MASE vs {base} by horizon (<1 = beats {base})")
    ax.legend(fontsize=7)
    ax = axes[0, 1]
    d = rel_bank_h[rel_bank_h["model"] == chal]
    for i, g in d.groupby("id"):
        ax.plot(g["h"], g["rel_mase"], marker="o", ms=3, label=i)
    ax.axhline(1, color="k", lw=1)
    ax.set_title(f"{chal} / {base} relative MASE by bank")
    ax.legend(fontsize=8)
    ax = axes[1, 0]
    g = win_h.groupby("h")["win_rate"].mean()
    ax.bar(g.index, g.values, color=_c(chal))
    ax.axhline(0.5, color="k", lw=1)
    ax.set_ylim(0, 1)
    ax.set_title(f"{chal} head-to-head win rate vs {base} (|error|, all series x origins)")
    ax = axes[1, 1]
    ax.bar(dm_sum["h"] - 0.2, dm_sum["better"], width=0.4, color="#2ca02c", label=f"{chal} signif. better")
    ax.bar(dm_sum["h"] + 0.2, dm_sum["worse"], width=0.4, color="#d62728", label=f"{chal} signif. worse")
    ax.set_title("Diebold-Mariano at 5%: share of bank x line series")
    ax.legend(fontsize=8)
    for a in axes.ravel():
        a.set_xlabel("horizon (quarters ahead)")
        a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def origin_timeline(err: pd.DataFrame, models: list[str], path: Path, stress: dict | None = None):
    """Mean MASE across all series and horizons for each forecast origin."""
    fig, ax = plt.subplots(figsize=(11, 3.8))
    g = err[err["model"].isin(models)].groupby(["model", "origin"])["ase"].median().reset_index()
    for m, x in g.groupby("model"):
        ax.plot(x["origin"], x["ase"], marker="o", ms=3, color=_c(m), label=m)
    for name, (a, b) in (stress or {}).items():
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color="grey", alpha=0.15)
        ax.text(pd.Timestamp(a), ax.get_ylim()[1] * 0.95, f" {name} origins", fontsize=8)
    ax.set_title("Median scaled error (MASE) of the 8-quarter path, by forecast origin")
    ax.set_ylabel("median |e| / naive scale")
    ax.legend(fontsize=7, ncol=4)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def multi_origin_fans(bt, panel: Panel, target: str, origins, models, path: Path, before: int = 12):
    """Rows = ids, columns = origins; median + 80% band per model, actuals in black."""
    ids, j = panel.ids, panel.targets.index(target)
    origins = [pd.Timestamp(o) for o in origins]
    fig, axes = plt.subplots(len(ids), len(origins), figsize=(3.3 * len(origins), 2.5 * len(ids)), squeeze=False)
    for c, o in enumerate(origins):
        oi = int(np.searchsorted(panel.dates, o))
        lo, hi = max(0, oi - before), min(len(panel.dates), oi + 9)
        for r, i in enumerate(ids):
            ax = axes[r, c]
            ax.plot(panel.dates[lo:hi], panel.y[r, j, lo:hi], color="k", lw=1.4, label="actual")
            for m in models:
                d = bt[(bt.model == m) & (bt.id == i) & (bt.target == target) & (bt.origin == o)].sort_values("h")
                if d.empty:
                    continue
                x = pd.DatetimeIndex([o]).append(pd.DatetimeIndex(d["date"]))
                ax.plot(x, np.r_[d["y_origin"].iloc[0], d["q0.5"]], color=_c(m), lw=1.4, label=m)
                ax.fill_between(d["date"], d["q0.1"], d["q0.9"], color=_c(m), alpha=0.15)
            ax.axvline(o, color="grey", ls=":", lw=1)
            ax.tick_params(labelsize=6)
            if r == 0:
                ax.set_title(f"origin {o.date()}", fontsize=9)
            if c == 0:
                ax.set_ylabel(f"{i}\n{target}", fontsize=8)
    h, lab = axes[0, 0].get_legend_handles_labels()
    fig.suptitle(f"{target}: one-shot 8q forecasts from rate-regime origins (80% bands)", y=1.035)
    fig.legend(h, lab, loc="upper center", bbox_to_anchor=(0.5, 1.01), ncol=len(lab), fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def spaghetti(bt, panel: Panel, target: str, models, path: Path):
    """Every origin's 8q median path over the actual series; rows = ids, cols = models."""
    ids, j = panel.ids, panel.targets.index(target)
    d0 = bt[(bt.target == target) & ~bt.live]
    first = d0["origin"].min()
    fi = max(0, int(np.searchsorted(panel.dates, first)) - 4)
    fig, axes = plt.subplots(len(ids), len(models), figsize=(4.6 * len(models), 2.5 * len(ids)), squeeze=False)
    cmap = plt.get_cmap("viridis")
    origins = sorted(d0["origin"].unique())
    for c, m in enumerate(models):
        for r, i in enumerate(ids):
            ax = axes[r, c]
            ax.plot(panel.dates[fi:], panel.y[r, j, fi:], color="k", lw=2, zorder=5)
            d = d0[(d0.model == m) & (d0.id == i)]
            for k, (o, g) in enumerate(d.groupby("origin")):
                g = g.sort_values("h")
                x = pd.DatetimeIndex([o]).append(pd.DatetimeIndex(g["date"]))
                ax.plot(
                    x,
                    np.r_[g["y_origin"].iloc[0], g["q0.5"]],
                    color=cmap(k / max(1, len(origins) - 1)),
                    lw=0.9,
                    alpha=0.85,
                )
            ax.tick_params(labelsize=6)
            if r == 0:
                ax.set_title(m, fontsize=9)
            if c == 0:
                ax.set_ylabel(f"{i}\n{target}", fontsize=8)
    fig.suptitle(
        f"{target}: all {len(origins)} origins' 8-quarter median paths (colour = origin date) vs actual", y=1.01
    )
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def help_bars(by_target_bank: pd.DataFrame, by_h: pd.DataFrame, title: str, path: Path):
    """Relative MASE of model vs reference: grouped bars per target x id, and by horizon per target."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
    pv = by_target_bank.pivot(index="target", columns="id", values="rel_mase")
    pv.plot.bar(ax=axes[0], width=0.8)
    axes[0].axhline(1, color="k", lw=1)
    axes[0].set_title(f"{title}\nrelative MASE by line and bank (<1 = helps)", fontsize=9)
    axes[0].tick_params(axis="x", rotation=0)
    for t, g in by_h.groupby("target"):
        axes[1].plot(g["h"], g["rel_mase"], marker="o", ms=3, label=t)
    axes[1].axhline(1, color="k", lw=1)
    axes[1].set_title("by horizon (geo-mean over banks)", fontsize=9)
    axes[1].set_xlabel("horizon (quarters ahead)")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def yield_curves(panel: Panel, cols, mats, origins, path: Path, ahead: int = 8):
    """Curve at each highlighted origin (solid) and the realised curve `ahead` periods later (dashed)."""
    idx = [panel.covariates.index(c) for c in cols]
    x = panel.x[0][idx]  # covariates are common across ids
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
    for k, o in enumerate(origins):
        o = pd.Timestamp(o)
        oi = int(np.searchsorted(panel.dates, o))
        col = f"C{k}"
        axes[0].plot(mats, x[:, oi], marker="o", ms=3, color=col, label=f"{o.date()}")
        if oi + ahead < x.shape[1]:
            axes[0].plot(mats, x[:, oi + ahead], ls="--", color=col, lw=1)
    axes[0].set_xscale("log")
    axes[0].set_xticks(mats, [f"{m:g}y" for m in mats], fontsize=7)
    axes[0].set_title(f"Treasury curve at origin (solid) and {ahead}q later (dashed)", fontsize=9)
    axes[0].set_ylabel("%")
    axes[0].legend(fontsize=7)
    for c, name in [(0, cols[0]), (len(cols) // 2, cols[len(cols) // 2]), (len(cols) - 1, cols[-1])]:
        axes[1].plot(panel.dates, x[c], label=name)
    for o in origins:
        axes[1].axvline(pd.Timestamp(o), color="grey", ls=":", lw=1)
    axes[1].set_title("history; dotted lines = highlighted origins", fontsize=9)
    axes[1].legend(fontsize=7)
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def helps_by_line(hv: pd.DataFrame, gmap: dict, path: Path):
    """Horizontal bars of relative MASE (variant vs no-covariate twin) per line; groups shaded."""
    n, k = hv.shape
    fig, ax = plt.subplots(figsize=(9, 0.32 * n * max(1, k / 2) + 1.5))
    y = np.arange(n)
    w = 0.8 / k
    for j, col in enumerate(hv.columns):
        v = np.log(hv[col].to_numpy(float))
        ax.barh(y + (j - (k - 1) / 2) * w, v, height=w, label=col, color=f"C{j}")
    ax.axvline(0, color="k", lw=1)
    ticks = [-0.69, -0.36, -0.105, 0, 0.095, 0.26, 0.41]
    ax.set_xticks(ticks, [f"{np.exp(t):.2f}" for t in ticks])
    ax.set_yticks(y, hv.index, fontsize=8)
    ax.invert_yaxis()
    groups = [gmap.get(t, "") for t in hv.index]
    for i in range(1, n):
        if groups[i] != groups[i - 1]:
            ax.axhline(i - 0.5, color="grey", lw=0.8, ls="--")
    for g in dict.fromkeys(groups):
        first = groups.index(g)
        ax.text(ax.get_xlim()[1], first, f" {g}", va="center", fontsize=9, color="grey")
    ax.set_xlabel("relative MASE (log scale; left of 0 = covariates help)")
    ax.set_title("Does knowing the macro path help? (variant / no-covariate twin)")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
