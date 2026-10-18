"""Compute metrics, draw plots, write a markdown report."""

from __future__ import annotations

import json
from pathlib import Path

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
    if dm.empty:
        dm = pd.DataFrame(columns=["id", "target", "h", "dm_stat", "p_value", "n"])
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

    extra = _extra_sections(cfg, panel, bt, err, figs, base, models)

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
    lines += extra
    if cfg.notes_file and Path(cfg.notes_file).exists():
        lines[1:1] = ["", Path(cfg.notes_file).read_text().strip(), "", "---", "", "# Full tables"]
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


def _dm_all(err: pd.DataFrame, base: str, models: list[str]) -> pd.DataFrame:
    rows = []
    for m in models:
        if m == base:
            continue
        d = M.dm_table(err, m, base)
        if d.empty:
            continue
        d = d.assign(better=(d.dm_stat < 0) & (d.p_value < 0.05), worse=(d.dm_stat > 0) & (d.p_value < 0.05))
        for h, g in d.groupby("h"):
            rows.append({"model": m, "h": h, "better": g.better.mean(), "worse": g.worse.mean()})
    return pd.DataFrame(rows)


def _extra_sections(cfg: Config, panel: Panel, bt, err, figs: Path, base: str, models: list[str]) -> list[str]:
    pc = cfg.plots
    lines: list[str] = []
    dm_all = _dm_all(err, base, models)
    if not dm_all.empty:
        b = dm_all.pivot(index="h", columns="model", values="better")
        w = dm_all.pivot(index="h", columns="model", values="worse")
        lines += [
            "## Diebold-Mariano vs baseline, all models",
            f"Share of series significantly **better** than `{base}` at 5% (squared error):",
            "",
            _md(b.reset_index(), "{:.0%}"),
            "",
            "Share significantly **worse**:",
            "",
            _md(w.reset_index(), "{:.0%}"),
            "",
        ]
        (cfg.out / "tables").mkdir(exist_ok=True)
        dm_all.to_csv(cfg.out / "tables" / "dm_all_models.csv", index=False)
    cov = err.groupby(["model", "target"])["covered"].mean().unstack()
    lines += ["## 80% interval coverage by line", _md(cov.reset_index()), ""]
    rel_t = M.relative_mase(err, base, by=["target"]).pivot(index="target", columns="model", values="rel_mase")
    lines += [f"## Relative MASE vs `{base}` by line", _md(rel_t.reset_index()), ""]
    rel_th = M.relative_mase(err, base, by=["target", "h"])
    for t, g in rel_th.groupby("target") if rel_th["target"].nunique() <= 6 else []:
        lines += [
            f"### {t}: relative MASE by horizon",
            _md(g.pivot(index="h", columns="model", values="rel_mase").reset_index()),
            "",
        ]
    if pc.highlight_origins:
        ho = [pd.Timestamp(o) for o in pc.highlight_origins]
        eh = err[err.origin.isin(ho)]
        if not eh.empty:
            r = M.relative_mase(eh, base, by=["target"]).pivot(index="target", columns="model", values="rel_mase")
            lines += [
                "## Highlighted origins only: relative MASE",
                ", ".join(str(o.date()) for o in ho),
                "",
                _md(r.reset_index()),
                "",
            ]
            per = eh.groupby(["model", "origin", "target"])["ase"].mean().unstack("model").reset_index()
            per["origin"] = per["origin"].dt.date
            lines += ["### MASE per highlighted origin", _md(per), ""]
        hm = pc.highlight_models or models[:2]
        for t in pc.highlight_series:
            P.multi_origin_fans(bt, panel, t, ho, hm, figs / f"fans_{t}.png")
            lines.append(f"![](figures/fans_{t}.png)")
        lines.append("")
    for t in pc.spaghetti_series:
        P.spaghetti(bt, panel, t, pc.spaghetti_models or models[:2], figs / f"spaghetti_{t}.png")
        lines.append(f"![](figures/spaghetti_{t}.png)")
    for a, b in pc.compare_pairs:
        sub = err[err.model.isin([a, b])]
        tb = M.relative_mase(sub, b, by=["target", "id"])
        th = M.relative_mase(sub, b, by=["target", "h"])
        tb, th = tb[tb.model == a], th[th.model == a]
        P.help_bars(tb, th, f"How much does `{a}` help vs `{b}`?", figs / f"help_{a}_vs_{b}.png")
        tot = M.relative_mase(sub, b, by=["target"])
        tot = tot[tot.model == a][["target", "rel_mase"]]
        lines += [
            f"## How much does `{a}` help vs `{b}`? (relative MASE, <1 = helps)",
            _md(tot),
            "",
            f"![](figures/help_{a}_vs_{b}.png)",
            "",
        ]
    if pc.spaghetti_by_group:
        lines += _group_pages(cfg, panel, bt, err, figs, base, models)
    if pc.spaghetti_targets_grid:
        sm = pc.spaghetti_models or models[:3]
        for i in panel.ids:
            tag = str(i).replace("/", "_").replace(" ", "_")
            P.spaghetti_targets(bt, panel, i, panel.targets, sm, figs / f"spaghetti_targets_{tag}.png")
            lines += [f"## Spaghetti grid: {i} (rows = targets)", f"![](figures/spaghetti_targets_{tag}.png)", ""]
    if pc.id_heatmaps and len(panel.ids) > 1:
        lines += _id_heatmaps(err, figs, base, models, panel.ids)
    if pc.yield_curve:
        P.yield_curves(
            panel,
            pc.yield_curve["columns"],
            pc.yield_curve["maturities"],
            pc.highlight_origins,
            figs / "yield_curves.png",
        )
        lines += ["## Yield curve at highlighted origins", "![](figures/yield_curves.png)", ""]
    return lines


def _group_pages(cfg: Config, panel: Panel, bt, err, figs: Path, base: str, models: list[str]) -> list[str]:
    """Spaghetti grid for every target + heatmaps + macro-helps bars, organised per target group."""
    pc = cfg.plots
    sp_models = pc.spaghetti_models or models[:3]
    order = [t for g in cfg.data.groups.values() for t in g] or panel.targets
    rel_t = M.relative_mase(err, base, by=["target"]).pivot(index="target", columns="model", values="rel_mase")
    rel_t = rel_t.reindex(order)[[m for m in models if m in rel_t.columns]]
    P.heatmap(
        rel_t,
        figs / "relmase_line_x_variant.png",
        f"Relative MASE vs {base} by line and variant (<1 blue = better)",
        center=1.0,
        fmt="{:.2f}",
        cmap="RdBu_r",
        span=0.6,
    )
    out = ["## Line x variant: relative MASE vs baseline", "![](figures/relmase_line_x_variant.png)", ""]
    for m in [x for x in models if x != base and "timestral" in x and x != "timestral"]:
        th = M.relative_mase(err[err.model.isin([m, base])], base, by=["target", "h"])
        pv = th[th.model == m].pivot(index="target", columns="h", values="rel_mase").reindex(order)
        P.heatmap(
            pv,
            figs / f"relmase_line_x_horizon_{m}.png",
            f"{m} / {base}: relative MASE by line and horizon",
            center=1.0,
            fmt="{:.2f}",
            cmap="RdBu_r",
            span=0.6,
        )
        out += [f"![](figures/relmase_line_x_horizon_{m}.png)"]
    helps = {}
    for a, b in pc.compare_pairs:
        r = M.relative_mase(err[err.model.isin([a, b])], b, by=["target"])
        helps[f"{a} vs {b}"] = r[r.model == a].set_index("target")["rel_mase"]
    if helps:
        hv = pd.DataFrame(helps).reindex(order)
        gmap = {t: g for g, ts in cfg.data.groups.items() for t in ts}
        P.helps_by_line(hv, gmap, figs / "macro_helps_by_line.png")
        out += [
            "",
            "## Does macro help? (relative MASE of covariate variant vs its no-covariate twin; <1 = helps)",
            "![](figures/macro_helps_by_line.png)",
            "",
            _md(hv.reset_index()),
            "",
        ]
    out += ["## Spaghetti pages by group", ""]
    for g, ts in cfg.data.groups.items():
        gdir = figs / g
        gdir.mkdir(parents=True, exist_ok=True)
        idx = [
            f"# {g}: all origins' 8-quarter median paths vs actual",
            "",
            f"Columns: {' | '.join(sp_models)}. Rows: banks. Colour = origin date; black = actual.",
            "",
            _md(rel_t.reindex(ts).reset_index()),
            "",
        ]
        for t in ts:
            if t not in panel.targets:
                continue
            P.spaghetti(bt, panel, t, sp_models, gdir / f"spaghetti_{t}.png", ids=pc.spaghetti_ids or None)
            idx += [f"## {t}", f"![](spaghetti_{t}.png)", ""]
        (gdir / "index.md").write_text("\n".join(idx))
        out.append(f"- [{g}](figures/{g}/index.md) ({len(ts)} lines)")
    return out + [""]


def _id_heatmaps(err: pd.DataFrame, figs: Path, base: str, models: list[str], ids: list[str]) -> list[str]:
    """Relative MASE heatmaps where the ids are the series of interest (id x variant, id x horizon)."""
    rel = M.relative_mase(err, base, by=["id"]).pivot(index="id", columns="model", values="rel_mase")
    rel = rel.reindex([i for i in ids if i in rel.index])[[m for m in models if m in rel.columns and m != base]]
    P.heatmap(
        rel,
        figs / "relmase_id_x_variant.png",
        f"Relative MASE vs {base} by series and variant (<1 = better)",
        center=1.0,
        fmt="{:.2f}",
        cmap="RdBu_r",
        span=0.6,
    )
    out = [
        f"## Relative MASE vs `{base}` by series",
        "![](figures/relmase_id_x_variant.png)",
        "",
        _md(rel.reset_index()),
        "",
    ]
    for m in [x for x in models if x != base]:
        rh = M.relative_mase(err[err.model.isin([m, base])], base, by=["id", "h"])
        pv = rh[rh.model == m].pivot(index="id", columns="h", values="rel_mase").reindex(rel.index)
        P.heatmap(
            pv,
            figs / f"relmase_id_x_horizon_{m}.png",
            f"{m} / {base}: relative MASE by series and horizon",
            center=1.0,
            fmt="{:.2f}",
            cmap="RdBu_r",
            span=0.6,
        )
        out += [f"![](figures/relmase_id_x_horizon_{m}.png)"]
    return out + [""]
