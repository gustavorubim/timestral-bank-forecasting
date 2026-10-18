"""Compute metrics, draw plots, write a markdown report."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import metrics as M
from . import plots as P
from .config import Config
from .dataset import Panel


def _md(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else floatfmt.format(v))
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in d.astype(str).itertuples(index=False):
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _group_of(cfg: Config) -> dict[str, str]:
    g = {}
    for name, ts in cfg.data.groups.items():
        for t in ts:
            g[t] = name
    return g


def build_report(cfg: Config, panel: Panel, bt: pd.DataFrame) -> dict:
    out = cfg.out
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    base, chal = cfg.evaluation.baseline, cfg.evaluation.challenger
    models = [m.name for m in cfg.models]
    err = M.add_errors(bt)
    gmap = _group_of(cfg)
    err["group"] = err["target"].map(gmap).fillna("other")
    stress = cfg.backtest.stress_windows
    err["slice"] = "normal"
    for name, (a, b) in stress.items():
        err.loc[(err["origin"] >= a) & (err["origin"] <= b), "slice"] = name

    overall = M.summarize(err, ["model"]).sort_values("MASE")
    by_h = pd.concat(
        [M.summarize(err, ["model", "h"]).assign(group="all")]
        + [M.summarize(g, ["model", "h"]).assign(group=k) for k, g in err.groupby("group")]
    )
    by_bank = M.summarize(err, ["model", "id"])
    by_slice = M.summarize(err, ["model", "slice"])
    by_target = M.summarize(err, ["model", "target"])
    rel = M.relative_mase(err, base)
    rel_bank = M.relative_mase(err, base, by=["id"])
    rel_bank = (
        err.groupby(["model", "id", "target"])["ase"]
        .mean()
        .rename("mase")
        .reset_index()
        .pipe(
            lambda s: s.merge(
                s[s.model == base][["id", "target", "mase"]].rename(columns={"mase": "b"}),
                on=["id", "target"],
            )
        )
        .query("mase > 0 and b > 0")
        .assign(lr=lambda s: np.log(s.mase / s.b))
        .groupby(["model", "id"])["lr"]
        .mean()
        .apply(np.exp)
        .rename("rel_mase")
        .reset_index()
    )
    dm = M.dm_table(err, chal, base)
    dm_sum = (
        dm.assign(
            better=(dm.dm_stat < 0) & (dm.p_value < 0.05),
            worse=(dm.dm_stat > 0) & (dm.p_value < 0.05),
        )
        .groupby("h")[["better", "worse"]]
        .mean()
        .reset_index()
    )
    wr = M.win_rates(err, chal, base, ["id", "target"])
    wr_h = M.win_rates(err, chal, base, ["id", "h"])
    swr = M.series_win_rates(err, chal, base)

    # ---- plots
    groups = {"all": None, **{k: None for k in cfg.data.groups}}
    P.error_by_horizon(by_h, figs / "error_by_horizon_mase.png", "MASE", groups)
    P.error_by_horizon(by_h, figs / "error_by_horizon_smape.png", "sMAPE", groups)
    P.coverage_plot(by_h, figs / "coverage_by_horizon.png")
    P.heatmap(
        wr.pivot(index="target", columns="id", values="win_rate"),
        figs / "winrate_heatmap_target_bank.png",
        f"{chal} win rate vs {base} (share of origin x horizon with lower |error|)",
    )
    P.heatmap(
        wr_h.pivot(index="id", columns="h", values="win_rate"),
        figs / "winrate_heatmap_bank_horizon.png",
        f"{chal} win rate vs {base} by horizon",
    )
    P.heatmap(
        swr.pivot(index="id", columns="metric", values="win_rate"),
        figs / "winrate_heatmap_bank_metric.png",
        f"Share of series where {chal} beats {base}",
    )
    P.rel_mase_bars(rel, rel_bank, base, figs / "relative_mase.png")
    rel_h = M.relative_mase(err, base, by=["h"])
    rel_bank_h = M.relative_mase(err, base, by=["id", "h"])
    rel_tgt_h = M.relative_mase(err[err.model.isin([chal, base])], base, by=["target", "h"])
    rel_tgt_h = rel_tgt_h[rel_tgt_h.model == chal]
    P.skill_curves(rel_h, rel_bank_h, wr_h, dm_sum, chal, base, figs / "skill_vs_horizon.png")
    order = [t for t in panel.targets if t in set(rel_tgt_h.target)]
    P.heatmap(
        rel_tgt_h.pivot(index="target", columns="h", values="rel_mase").loc[order],
        figs / "relmase_heatmap_line_horizon.png",
        f"{chal} / {base} relative MASE by line and horizon (<1 blue = {chal} better)",
        center=1.0,
        fmt="{:.2f}",
        cmap="RdBu_r",
    )
    P.origin_timeline(
        err,
        [m for m in models if m in (chal, base, "timestral_cov", "arimax_oracle", "naive")],
        figs / "error_by_origin.png",
        stress,
    )
    fan_models = [m for m in [chal, base] if m in models]
    stress_models = [m for m in [chal, base, "timestral_cov_oracle", "arimax_oracle"] if m in models]
    for o in cfg.plots.fan_origins:
        tag = pd.Timestamp(o).strftime("%Y%m%d")
        P.fan_grid(
            bt,
            panel,
            cfg.plots.fan_series,
            o,
            fan_models,
            figs / f"fan_{tag}.png",
            f"8-quarter one-shot forecasts from {o} (80% bands)",
        )
    live_o = panel.dates[-1]
    P.fan_grid(
        bt,
        panel,
        cfg.plots.fan_series,
        live_o,
        fan_models,
        figs / "fan_live.png",
        f"Live 8-quarter forecast from {live_o.date()}",
    )
    if cfg.plots.stress_origin:
        P.fan_grid(
            bt,
            panel,
            cfg.plots.stress_series,
            cfg.plots.stress_origin,
            stress_models,
            figs / "covid_stress_fans.png",
            f"COVID stress: forecasts from {cfg.plots.stress_origin} (oracle = realised macro path)",
        )
    id_tables = []
    for ident in cfg.identities:
        gaps = M.identity_gaps(bt, ident.total, ident.components, ident.signs)
        P.identity_plot(gaps, figs / f"identity_{ident.name}.png", ident.name)
        gl = gaps[~gaps.live].assign(excess=lambda d: (d.gap_pct - d.gap_actual_pct).abs())
        t = (
            gl.groupby("model")
            .agg(
                median_abs_gap_pct=("gap_pct", lambda s: s.abs().median()),
                median_abs_actual_gap_pct=("gap_actual_pct", lambda s: s.abs().median()),
                median_excess_vs_actual_pp=("excess", "median"),
            )
            .reset_index()
        )
        t.insert(0, "identity", ident.name)
        id_tables.append(t)

    # ---- tables
    tables = out / "tables"
    tables.mkdir(exist_ok=True)
    for name, df in {
        "overall": overall,
        "by_horizon": by_h,
        "by_bank": by_bank,
        "by_slice": by_slice,
        "by_target": by_target,
        "relative_mase": rel,
        "relative_mase_by_bank": rel_bank,
        "dm_tests": dm,
        "dm_summary": dm_sum,
        "win_rates_target_bank": wr,
        "win_rates_series_metric": swr,
    }.items():
        df.to_csv(tables / f"{name}.csv", index=False)

    hz = by_h[by_h.group == "all"].pivot(index="h", columns="model", values="MASE")[models].reset_index()
    bank_tbl = rel_bank.pivot(index="id", columns="model", values="rel_mase").reset_index()
    slice_tbl = by_slice.pivot(index="model", columns="slice", values="MASE").reset_index()
    swr_tbl = swr.pivot(index="id", columns="metric", values="win_rate").reset_index()
    origins = sorted(bt.loc[~bt.live, "origin"].unique())
    lines = [
        f"# Backtest report: {cfg.name}",
        "",
        f"- Series: {len(panel.ids)} ids x {len(panel.targets)} targets = {panel.n_series}",
        f"- Data: {panel.dates[0].date()} to {panel.dates[-1].date()} ({len(panel.dates)} periods)",
        f"- Rolling origins: {len(origins)} ({pd.Timestamp(origins[0]).date()} .. {pd.Timestamp(origins[-1]).date()}), "
        f"one-shot direct horizon h=1..{cfg.backtest.horizon}",
        f"- Challenger `{chal}` vs baseline `{base}`. MASE scale = in-sample naive (lag {cfg.evaluation.mase_season}).",
        "",
        "## Overall",
        _md(overall),
        "",
        "## MASE by horizon (all series)",
        _md(hz),
        "",
        "![](figures/error_by_horizon_mase.png)",
        "",
        "## Skill vs horizon",
        "![](figures/skill_vs_horizon.png)",
        "",
        _md(rel_h.pivot(index="h", columns="model", values="rel_mase").reset_index()),
        "",
        "![](figures/relmase_heatmap_line_horizon.png)",
        "",
        "![](figures/error_by_origin.png)",
        "",
        "## Relative MASE vs baseline (geometric mean; <1 = better than baseline)",
        _md(rel.sort_values("rel_mase")),
        "",
        "### By bank",
        _md(bank_tbl),
        "",
        "![](figures/relative_mase.png)",
        "",
        "## Win rates (share of series where challenger beats baseline)",
        _md(swr_tbl, "{:.0%}"),
        "",
        "![](figures/winrate_heatmap_target_bank.png)",
        "",
        "## Diebold-Mariano (squared error, HLN-corrected, per series and horizon)",
        "Share of bank x target series where the challenger is significantly better / worse at 5%:",
        "",
        _md(dm_sum, "{:.0%}"),
        "",
        "## Stress slices (MASE)",
        _md(slice_tbl),
        "",
        "![](figures/covid_stress_fans.png)",
        "",
        "## Interval coverage (80%)",
        "![](figures/coverage_by_horizon.png)",
        "",
        "## Balance-sheet identity consistency",
        _md(pd.concat(id_tables)) if id_tables else "(none configured)",
        "",
    ]
    lines += [f"![](figures/identity_{i.name}.png)" for i in cfg.identities]
    lines += ["", "## Forecast fans", ""]
    lines += [f"![](figures/fan_{pd.Timestamp(o).strftime('%Y%m%d')}.png)" for o in cfg.plots.fan_origins]
    lines += ["![](figures/fan_live.png)", ""]
    (out / "REPORT.md").write_text("\n".join(lines))
    summary = {
        "overall": overall.to_dict("records"),
        "rel_mase": rel.to_dict("records"),
        "mase_by_h": hz.to_dict("records"),
        "rel_mase_by_h": rel_h.to_dict("records"),
        "rel_mase_by_bank_h": rel_bank_h.to_dict("records"),
        "rel_mase_by_bank": bank_tbl.to_dict("records"),
        "dm_summary": dm_sum.to_dict("records"),
        "series_win_rates": swr_tbl.to_dict("records"),
        "slices": slice_tbl.to_dict("records"),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    return summary
