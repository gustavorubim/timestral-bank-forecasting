"""Metrics, figures and REPORT.md for the macro horse race (outputs/macro_horse)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FormatStrFormatter  # noqa: E402

from . import macro_horse as mh  # noqa: E402

NAMES = {
    "rw": "Random walk",
    "ar": "AR(p), BIC",
    "arima": "AutoARIMA",
    "timestral": "Timestral (univariate)",
    "timestral_mv": "Timestral (joint, 7 vars)",
    "timestral_cov": "Timestral + past macro covs",
    "timestral_scenario": "Timestral + realised future covs (scenario, NOT fair)",
    "dsge": "NY Fed DSGE ss104 (headline)",
    "dsge_frozen": "DSGE ss104, regime frozen at T (sensitivity)",
    "dsge_sched": "DSGE ss104, dated regime schedule everywhere (sensitivity)",
    "spf": "SPF median (real time, h<=5)",
}
COLORS = {
    "rw": "#bbbbbb", "ar": "#555555", "arima": "#8c564b", "timestral": "#1f77b4",
    "timestral_mv": "#17becf", "timestral_cov": "#2ca02c", "timestral_scenario": "#98df8a",
    "dsge": "#d62728", "dsge_sched": "#ff9896", "dsge_frozen": "#e377c2", "spf": "#9467bd",
}
FAIR_TS = ["timestral", "timestral_mv", "timestral_cov"]
CORE = ["gdp", "corepce", "pce", "cpi", "ffr"]
DSGE_TARGETS = ["gdp", "corepce", "gdpdef", "ffr"]


def load_all(root: Path) -> pd.DataFrame:
    d = root / "data/processed/macro_horse"
    panel = pd.read_csv(d / "panel.csv", index_col=0)
    panel.index = pd.PeriodIndex(panel.index, freq="Q")
    fc = pd.read_parquet(d / "forecasts.parquet")
    dsge = pd.read_csv(d / "dsge_forecasts.csv")
    # Headline DSGE: origins before 2020Q1 freeze the regime at T (no foreknowledge of COVID regimes);
    # origins from 2020Q1 follow ss104's own dated regime schedule (ZLB -> flexible-AIT credibility path,
    # which is the model's forward assumption). Freezing a one-quarter COVID shock-variance regime
    # (2020Q1-Q3) for 8 quarters gives absurd densities (GDP sd > 150pp), so it is only a sensitivity run.
    pre = pd.PeriodIndex(dsge.origin, freq="Q") < pd.Period("2020Q1", freq="Q")
    hyb = pd.concat([dsge[(dsge.model == "dsge") & pre], dsge[(dsge.model == "dsge_sched") & ~pre]])
    dsge["model"] = dsge.model.replace({"dsge": "dsge_frozen"})
    dsge = pd.concat([hyb.assign(model="dsge"), dsge], ignore_index=True)
    z = mh.norm.ppf(mh.QGRID)
    for k, q in enumerate(mh.QGRID):
        dsge[f"q{q:.2f}"] = dsge["mean"] + z[k] * dsge["sd"]
    spf = pd.read_csv(d / "spf.csv")
    spf = spf[spf.origin.isin([str(o) for o in mh.origins()])]
    allfc = pd.concat([fc, dsge.drop(columns=["regime_T", "regime_h"]), spf], ignore_index=True)
    allfc = allfc[allfc.origin.isin([str(o) for o in mh.origins()])]
    return mh.add_density(mh.attach_actuals(allfc, panel)), panel


def best_timestral(rel: pd.DataFrame) -> dict[str, str]:
    """Per target, the fair Timestral variant with the lowest geometric-mean rel RMSE over h=1..8."""
    s = rel[rel.model.isin(FAIR_TS)].assign(lr=lambda x: np.log(x.rel))
    g = s.groupby(["target", "model"]).lr.mean().reset_index()
    return g.loc[g.groupby("target").lr.idxmin()].set_index("target").model.to_dict()


def _logy(ax):
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax.yaxis.set_minor_formatter(FormatStrFormatter("%.2f"))
    ax.tick_params(axis="y", which="minor", labelsize=7)


def _fmt(x, d=2):
    return "" if pd.isna(x) else f"{x:.{d}f}"


def build(root: Path = Path("."), out: Path | None = None) -> dict:
    out = out or root / "outputs/macro_horse"
    fig = out / "figures"
    fig.mkdir(parents=True, exist_ok=True)
    fc, panel = load_all(root)
    fc.to_parquet(out / "forecasts_scored.parquet", index=False)
    rel = mh.rel_table(fc, "rmse")
    relmae = mh.rel_table(fc, "mae")
    relcrps = mh.rel_table(fc[fc.model != "spf"], "crps")
    rel.to_csv(out / "rel_rmse_vs_ar.csv", index=False)
    relmae.to_csv(out / "rel_mae_vs_ar.csv", index=False)
    relcrps.to_csv(out / "rel_crps_vs_ar.csv", index=False)
    best = best_timestral(rel)
    rel_ex = mh.rel_table(fc[fc.regime != "covid"], "rmse")
    rel_ex.to_csv(out / "rel_rmse_vs_ar_ex_covid.csv", index=False)

    # absolute RMSE
    absr = fc.dropna(subset=["err"]).groupby(["model", "target", "h"]).err.apply(
        lambda e: np.sqrt(np.mean(e**2))).rename("rmse").reset_index()
    absr.to_csv(out / "rmse_abs.csv", index=False)

    # DM tests
    dms = []
    for t, b in best.items():
        sub = fc[fc.target == t]
        dms.append(mh.dm_tests(sub, b, "ar"))
        if t in DSGE_TARGETS:
            dms.append(mh.dm_tests(sub, b, "dsge"))
            dms.append(mh.dm_tests(sub, "dsge", "ar"))
        if t in ("gdp", "corepce", "pce", "cpi", "unrate"):
            dms.append(mh.dm_tests(sub, b, "spf"))
    dm = pd.concat(dms, ignore_index=True)
    dm.to_csv(out / "dm_tests.csv", index=False)

    # regimes (pooled over h=1..8), relative to AR on the same cells
    reg_rows = []
    for m in fc.model.unique():
        if m == "ar":
            continue
        s = mh.common_sample(fc, [m, "ar"])
        for (t, r), g in s.groupby(["target", "regime"]):
            a = np.sqrt(np.mean(g[g.model == m].err ** 2))
            b = np.sqrt(np.mean(g[g.model == "ar"].err ** 2))
            reg_rows.append({"model": m, "target": t, "regime": r, "rel_rmse": a / b,
                             "rmse": a, "rmse_ar": b, "n": int((g.model == m).sum())})
    reg = pd.DataFrame(reg_rows)
    reg.to_csv(out / "regime_rel_rmse.csv", index=False)

    # density
    dens = fc[fc.model != "spf"].dropna(subset=["crps"]).groupby(["model", "target", "h"])[
        ["crps", "cov80", "cov90"]].mean().reset_index()
    dens.to_csv(out / "density.csv", index=False)

    figs = _figures(fc, rel, relcrps, dens, reg, dm, best, panel, fig)
    _write_report(out, fc, rel, rel_ex, relmae, relcrps, absr, dm, reg, dens, best, figs)
    return {"best": best, "rel": rel, "dm": dm, "reg": reg, "dens": dens}


# ----------------------------------------------------------------------------------- figures
def _figures(fc, rel, relcrps, dens, reg, dm, best, panel, fig: Path) -> dict[str, Path]:
    paths = {}
    order = ["rw", "arima", "timestral", "timestral_mv", "timestral_cov", "timestral_scenario",
             "dsge", "dsge_frozen", "dsge_sched", "spf"]
    # 1. relative RMSE by horizon
    f, axs = plt.subplots(2, 4, figsize=(18, 8.5), sharex=True)
    for ax, t in zip(axs.flat, mh.TARGETS, strict=False):
        for m in order:
            r = rel[(rel.model == m) & (rel.target == t)].sort_values("h")
            if r.empty:
                continue
            ls = "--" if m in ("timestral_scenario", "dsge_sched", "dsge_frozen") else "-"
            ax.plot(r.h, r.rel, ls, marker="o", ms=3, lw=2.2 if m in ("dsge", best.get(t)) else 1.3,
                    color=COLORS[m], label=NAMES[m])
        ax.axhline(1, color="k", lw=0.8)
        _logy(ax)
        ax.set_title(mh.LABELS[t])
        ax.set_xticks(range(1, 9))
        ax.grid(alpha=0.3, which="both")
    axs.flat[-1].axis("off")
    h, lab = axs.flat[0].get_legend_handles_labels()
    for ax in axs.flat[1:7]:
        for hh, ll in zip(*ax.get_legend_handles_labels(), strict=False):
            if ll not in lab:
                h.append(hh)
                lab.append(ll)
    axs.flat[-1].legend(h, lab, loc="center", fontsize=9)
    f.suptitle("RMSE relative to AR(p) by horizon (below 1 = better than AR). Origins 2005Q1-2024Q2, latest vintage")
    f.supxlabel("horizon (quarters ahead of last observed quarter)")
    f.tight_layout()
    paths["rel_by_h"] = fig / "rel_rmse_by_horizon.png"
    f.savefig(paths["rel_by_h"], dpi=110)
    plt.close(f)

    # 2. heatmap model x (variable, horizon)
    models = [m for m in order if m in rel.model.unique()]
    cols = [(t, h) for t in mh.TARGETS for h in range(1, 9)]
    mat = np.full((len(models), len(cols)), np.nan)
    for i, m in enumerate(models):
        r = rel[rel.model == m].set_index(["target", "h"]).rel
        for j, c in enumerate(cols):
            mat[i, j] = r.get(c, np.nan)
    f, ax = plt.subplots(figsize=(22, 5.5))
    im = ax.imshow(np.log(mat), cmap="RdBu_r", vmin=-np.log(2.5), vmax=np.log(2.5), aspect="auto")
    for i in range(len(models)):
        for j in range(len(cols)):
            if np.isfinite(mat[i, j]):
                ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=6.5)
    ax.set_yticks(range(len(models)), [NAMES[m] for m in models], fontsize=8)
    ax.set_xticks(range(len(cols)), [f"h{h}" for _, h in cols], fontsize=6.5)
    for k, t in enumerate(mh.TARGETS):
        ax.text(k * 8 + 3.5, -0.9, mh.LABELS[t], ha="center", fontsize=9, fontweight="bold")
        if k:
            ax.axvline(k * 8 - 0.5, color="k", lw=1)
    cb = f.colorbar(im, ax=ax, fraction=0.02)
    cb.set_ticks(np.log([0.5, 0.75, 1, 1.5, 2]), labels=["0.5", "0.75", "1", "1.5", "2"])
    ax.set_title("Relative RMSE vs AR(p): model x variable x horizon (blue = better than AR)", pad=22)
    f.tight_layout()
    paths["heatmap"] = fig / "heatmap_rel_rmse.png"
    f.savefig(paths["heatmap"], dpi=110)
    plt.close(f)

    # 3. spaghetti grids
    for tgts, name in ((["gdp", "corepce"], "spaghetti_gdp_corepce"), (["pce", "cpi"], "spaghetti_pce_cpi"),
                       (["ffr", "unrate"], "spaghetti_ffr_unrate")):
        f, axs = plt.subplots(len(tgts), 4, figsize=(20, 4.3 * len(tgts)), sharex=True)
        for i, t in enumerate(tgts):
            colm = ["dsge" if t in DSGE_TARGETS else None, best.get(t, "timestral"), "ar", "spf"]
            act = panel.loc["2003Q1":, t]
            sub = fc[fc.target == t]
            vals = sub["mean"].dropna()
            lo, hi = np.nanpercentile(act, 1), np.nanpercentile(act, 99)
            pad = 0.25 * (hi - lo)
            for j, m in enumerate(colm):
                ax = axs[i, j]
                ax.plot(act.index.to_timestamp(), act.values, color="k", lw=1.2, label="actual")
                if m is None or sub[sub.model == m].empty:
                    ax.text(0.5, 0.5, "not produced by this model", transform=ax.transAxes, ha="center",
                            color="grey")
                else:
                    g = sub[sub.model == m]
                    cmap = plt.get_cmap("viridis")
                    os_ = sorted(g.origin.unique())
                    for k, o in enumerate(os_):
                        p = g[g.origin == o].sort_values("h")
                        x = (pd.PeriodIndex([o] * len(p), freq="Q") + p.h.to_numpy()).to_timestamp()
                        x0 = pd.Period(o, freq="Q").to_timestamp()
                        y0 = panel.loc[pd.Period(o, freq="Q"), t]
                        ax.plot([x0, *x], [y0, *p["mean"]], color=cmap(k / max(len(os_) - 1, 1)), lw=0.7,
                                alpha=0.75)
                    r = rel[(rel.model == m) & (rel.target == t)].set_index("h").rel
                    ax.text(0.02, 0.04, f"rel RMSE vs AR  h1 {_fmt(r.get(1))}  h4 {_fmt(r.get(4))}  h8 {_fmt(r.get(8))}", transform=ax.transAxes, fontsize=8,
                        bbox=dict(fc="white", alpha=0.8, lw=0))
                ax.set_ylim(min(lo - pad, vals.quantile(0.01)), max(hi + pad, vals.quantile(0.99)))
                ax.set_title(f"{mh.LABELS[t]} - {NAMES.get(m, 'DSGE (n/a)') if m else 'DSGE (n/a)'}", fontsize=9)
                ax.grid(alpha=0.3)
        f.suptitle("8-quarter forecast paths from every origin 2005Q1-2024Q2 (colour = origin date)")
        f.tight_layout()
        paths[name] = fig / f"{name}.png"
        f.savefig(paths[name], dpi=100)
        plt.close(f)

    # 4. regime bars
    regs = list(mh.REGIMES)
    bm = ["dsge", "timestral", "timestral_mv", "timestral_cov", "arima", "spf"]
    f, axs = plt.subplots(1, 5, figsize=(22, 4.8))
    for ax, t in zip(axs, CORE, strict=False):
        w = 0.8 / len(bm)
        for k, m in enumerate(bm):
            r = reg[(reg.model == m) & (reg.target == t)].set_index("regime").rel_rmse.reindex(regs)
            ax.bar(np.arange(len(regs)) + (k - len(bm) / 2 + 0.5) * w, r.values, w, color=COLORS[m],
                   label=NAMES[m])
        ax.axhline(1, color="k", lw=0.8)
        _logy(ax)
        ax.set_xticks(range(len(regs)), ["pre-COVID\n<=2019Q4", "COVID\n20Q1-21Q2", "infl. surge\n21Q3-23Q2",
                                         "post-2023\n23Q3-26Q2"], fontsize=8)
        ax.set_title(mh.LABELS[t])
        ax.grid(alpha=0.3, axis="y", which="both")
    axs[0].legend(fontsize=7)
    f.suptitle("RMSE relative to AR(p) by regime of the forecast target quarter (pooled h=1..8)")
    f.tight_layout()
    paths["regimes"] = fig / "regime_bars.png"
    f.savefig(paths["regimes"], dpi=110)
    plt.close(f)

    # 5. DM significance table
    pairs = [("vs DSGE", "dsge"), ("vs AR", "ar"), ("vs SPF", "spf")]
    f, axs = plt.subplots(1, 3, figsize=(20, 4.2))
    for ax, (lab, base) in zip(axs, pairs, strict=False):
        d = dm[(dm.baseline == base) & (dm.challenger != "dsge")]
        tg = [t for t in mh.TARGETS if t in d.target.unique()]
        m = np.full((len(tg), 8), np.nan)
        txt = [[""] * 8 for _ in tg]
        for i, t in enumerate(tg):
            for _, r in d[d.target == t].iterrows():
                j = int(r.h) - 1
                m[i, j] = np.log(r.rel_rmse)
                star = "***" if r.p_value < 0.01 else "**" if r.p_value < 0.05 else "*" if r.p_value < 0.1 else ""
                txt[i][j] = f"{r.rel_rmse:.2f}{star}"
        ax.imshow(m, cmap="RdBu_r", vmin=-np.log(2), vmax=np.log(2), aspect="auto")
        for i in range(len(tg)):
            for j in range(8):
                dark = np.isfinite(m[i, j]) and abs(m[i, j]) > 0.45
                ax.text(j, i, txt[i][j], ha="center", va="center", fontsize=8, color="white" if dark else "black")
        ax.set_yticks(range(len(tg)), [f"{mh.LABELS[t]}\n[{best[t]}]" for t in tg], fontsize=7)
        ax.set_xticks(range(8), [f"h{h}" for h in range(1, 9)])
        ax.set_title(f"Best fair Timestral {lab}: RMSE ratio, HLN-DM *10% **5% ***1%", fontsize=9)
    f.tight_layout()
    paths["dm"] = fig / "dm_table.png"
    f.savefig(paths["dm"], dpi=110)
    plt.close(f)

    # 6. CRPS + coverage
    dm_models = ["rw", "arima", "timestral", "timestral_mv", "timestral_cov", "dsge"]
    f, axs = plt.subplots(2, 5, figsize=(22, 8))
    for ax, t in zip(axs[0], CORE, strict=False):
        for m in dm_models:
            r = relcrps[(relcrps.model == m) & (relcrps.target == t)].sort_values("h")
            if len(r):
                ax.plot(r.h, r.rel, marker="o", ms=3, color=COLORS[m], label=NAMES[m],
                        ls="-")
        ax.axhline(1, color="k", lw=0.8)
        _logy(ax)
        ax.set_title(f"{mh.LABELS[t]}: CRPS rel. to AR")
        ax.grid(alpha=0.3, which="both")
    axs[0, 0].legend(fontsize=7)
    cm = ["ar", "arima", "timestral", "timestral_mv", "timestral_cov", "dsge"]
    for ax, t in zip(axs[1], CORE, strict=False):
        w = 0.8 / len(cm)
        for k, m in enumerate(cm):
            r = dens[(dens.model == m) & (dens.target == t)]
            if r.empty:
                continue
            ax.bar(k * 2 * w, r.cov80.mean(), w, color=COLORS[m])
            ax.bar(k * 2 * w + w, r.cov90.mean(), w, color=COLORS[m], alpha=0.5, hatch="//")
        ax.axhline(0.8, color="k", ls="--", lw=0.8)
        ax.axhline(0.9, color="k", ls=":", lw=0.8)
        ax.set_xticks([k * 2 * w + w / 2 for k in range(len(cm))], [m.replace("timestral", "ts") for m in cm],
                      rotation=30, fontsize=8)
        ax.set_ylim(0, 1.05)
        ax.set_title(f"{mh.LABELS[t]}: 80% (solid) / 90% (hatched) coverage")
    f.tight_layout()
    paths["density"] = fig / "crps_coverage.png"
    f.savefig(paths["density"], dpi=110)
    plt.close(f)
    return paths


# ----------------------------------------------------------------------------------- report
def _md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt(v) if isinstance(v, float) else str(v) for v in row) + " |")
    return "\n".join(lines)


def _write_report(out, fc, rel, rel_ex, relmae, relcrps, absr, dm, reg, dens, best, figs):
    r = rel.set_index(["model", "target", "h"]).rel
    a = absr.set_index(["model", "target", "h"]).rmse
    hl = ["| Variable | h | DSGE ss104 | best fair Timestral | AR = 1 (AR RMSE, pp) | SPF | AutoARIMA |",
          "|---|---|---|---|---|---|---|"]
    for t in mh.TARGETS:
        for h in (1, 4, 8):
            b = best[t]
            hl.append(f"| {mh.LABELS[t]} | {h} | {_fmt(r.get(('dsge', t, h)))} | {_fmt(r.get((b, t, h)))} "
                      f"({b}) | 1 ({_fmt(a.get(('ar', t, h)))}) | {_fmt(r.get(('spf', t, h)))} | "
                      f"{_fmt(r.get(('arima', t, h)))} |")
    headline = "\n".join(hl)
    rx = rel_ex.set_index(["model", "target", "h"]).rel
    hx = ["| Variable | h | DSGE ss104 | best fair Timestral | SPF | AutoARIMA |", "|---|---|---|---|---|---|"]
    for t in mh.TARGETS:
        for h in (1, 4, 8):
            b = best[t]
            hx.append(f"| {mh.LABELS[t]} | {h} | {_fmt(rx.get(('dsge', t, h)))} | {_fmt(rx.get((b, t, h)))} ({b}) | "
                      f"{_fmt(rx.get(('spf', t, h)))} | {_fmt(rx.get(('arima', t, h)))} |")
    headline_ex = "\n".join(hx)
    (out / "headline_table.md").write_text(headline + "\n\nExcluding COVID target quarters 2020Q1-2021Q2:\n\n"
                                           + headline_ex + "\n")
    models = [m for m in NAMES if m in rel.model.unique()]
    full = rel.pivot_table(index=["target", "h"], columns="model", values="rel")[models].reset_index()
    full.columns = ["target", "h"] + models
    mae = relmae.pivot_table(index=["target", "h"], columns="model", values="rel")[models].reset_index()
    crps = relcrps.pivot_table(index=["target", "h"], columns="model", values="rel").reset_index()
    regt = reg.pivot_table(index=["target", "regime"], columns="model", values="rel_rmse").reset_index()
    regt = regt[["target", "regime"] + [m for m in models if m in regt.columns]]
    dmt = dm.copy()
    dmt["sig"] = np.where(dmt.p_value < 0.05, np.where(dmt.dm_stat < 0, "better", "worse"), "")
    cov = dens.groupby(["model", "target"])[["cov80", "cov90"]].mean().reset_index()
    intro = Path(__file__).resolve().parents[2] / "experiments/macro_horse/REPORT_intro.md"
    text = intro.read_text() if intro.exists() else "# Macro horse race\n"
    text += "\n\n## Headline: relative RMSE vs AR(p) at h = 1, 4, 8\n\n" + headline
    text += "\n\nSPF and each model are scored on their common sample with AR (SPF: h<=5; core/headline PCE"
    text += " from 2007). Best fair Timestral = the no-future-information variant with the lowest geometric-mean"
    text += " relative RMSE over h=1..8 for that variable.\n"
    text += "\n### Same table excluding COVID target quarters (2020Q1-2021Q2)\n\n" + headline_ex + "\n"
    for k, p in figs.items():
        text += f"\n![{k}](figures/{p.name})\n"
    text += "\n## Relative RMSE vs AR, all horizons\n\n" + _md(full)
    text += "\n\n## Relative MAE vs AR\n\n" + _md(mae)
    text += "\n\n## Relative CRPS vs AR (quantile-grid CRPS; Gaussian models evaluated on the same grid)\n\n" + _md(crps)
    text += "\n\n## Interval coverage (mean over h=1..8; nominal 0.80 / 0.90)\n\n" + _md(cov)
    text += "\n\n## Regimes (target quarter), RMSE relative to AR, pooled h=1..8\n\n" + _md(regt)
    text += "\n\n## Diebold-Mariano tests (squared error, HLN small-sample correction; negative stat = challenger better)\n\n"
    text += _md(dmt[["challenger", "baseline", "target", "h", "rel_rmse", "dm_stat", "p_value", "n", "sig"]])
    (out / "REPORT.md").write_text(text + "\n")
