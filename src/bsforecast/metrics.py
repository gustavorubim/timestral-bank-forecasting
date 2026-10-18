"""Point, interval, directional and significance metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def add_errors(bt: pd.DataFrame, lo: float = 0.1, hi: float = 0.9) -> pd.DataFrame:
    df = bt[~bt["live"] & bt["actual"].notna() & bt["forecast"].notna()].copy()
    e = df["forecast"] - df["actual"]
    df["err"] = e
    df["ae"] = e.abs()
    df["se"] = e**2
    with np.errstate(all="ignore"):
        df["ape"] = 100 * (e.abs() / df["actual"].abs()).where(df["actual"].abs() > 1e-9)
        den = df["forecast"].abs() + df["actual"].abs()
        df["sape"] = 200 * (e.abs() / den).where(den > 1e-9)
        df["ase"] = (e.abs() / df["scale"]).where(df["scale"] > 1e-12)
    lo_c, hi_c = f"q{lo:g}", f"q{hi:g}"
    if lo_c in df and hi_c in df:
        df["covered"] = ((df["actual"] >= df[lo_c]) & (df["actual"] <= df[hi_c])).astype(float)
        df.loc[df[lo_c].isna() | df[hi_c].isna(), "covered"] = np.nan
    da = np.sign(df["forecast"] - df["y_origin"]) == np.sign(df["actual"] - df["y_origin"])
    df["dir_hit"] = da.astype(float)
    # A flat forecast (e.g. random walk) makes no directional call: excluded rather than scored as a miss.
    df.loc[np.isclose(df["forecast"], df["y_origin"]), "dir_hit"] = np.nan
    return df


def summarize(err: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = err.groupby(by)
    out = pd.DataFrame(
        {
            "MAE": g["ae"].mean(),
            "RMSE": np.sqrt(g["se"].mean()),
            "MAPE": g["ape"].median(),  # median APE: robust to near-zero quarters (e.g. provisions)
            "sMAPE": g["sape"].mean(),
            "MASE": g["ase"].mean(),
            "coverage80": g["covered"].mean() if "covered" in err else np.nan,
            "dir_acc": g["dir_hit"].mean(),
            "n": g.size(),
        }
    )
    return out.reset_index()


def relative_mase(err: pd.DataFrame, baseline: str, by: list[str] | None = None) -> pd.DataFrame:
    """Geometric mean across series of MASE(model)/MASE(baseline).

    MASE is averaged within (id, target, *by) cells first, so ``by=["h"]`` gives a skill curve.
    """
    by = by or []
    keys = ["id", "target"] + [b for b in by if b not in ("id", "target")]
    s = err.groupby(["model"] + keys)["ase"].mean().rename("mase").reset_index()
    base = s[s["model"] == baseline][keys + ["mase"]].rename(columns={"mase": "base"})
    s = s.merge(base, on=keys)
    s = s[(s["mase"] > 0) & (s["base"] > 0)]
    s["log_rel"] = np.log(s["mase"] / s["base"])
    r = s.groupby(["model"] + by)["log_rel"].mean().apply(np.exp).rename("rel_mase").reset_index()
    return r


def diebold_mariano(e1: np.ndarray, e2: np.ndarray, h: int, power: int = 2) -> tuple[float, float]:
    """DM test with Harvey-Leybourne-Newbold small-sample correction.

    Negative statistic => model 1 has lower loss. Returns (stat, two-sided p-value).
    """
    d = np.abs(e1) ** power - np.abs(e2) ** power
    d = d[~np.isnan(d)]
    n = len(d)
    if n < 4 or np.allclose(d, d[0]):
        return np.nan, np.nan
    dbar = d.mean()
    gam = [np.mean((d[k:] - dbar) * (d[: n - k] - dbar)) for k in range(min(h, n - 1))]
    var = (gam[0] + 2 * sum(gam[1:])) / n
    if var <= 0:
        var = gam[0] / n
    stat = dbar / np.sqrt(var)
    k = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    stat *= k
    p = 2 * stats.t.sf(np.abs(stat), df=n - 1)
    return float(stat), float(p)


def dm_table(err: pd.DataFrame, challenger: str, baseline: str) -> pd.DataFrame:
    a = err[err["model"] == challenger].set_index(["id", "target", "origin", "h"])["err"]
    b = err[err["model"] == baseline].set_index(["id", "target", "origin", "h"])["err"]
    j = pd.concat([a.rename("e1"), b.rename("e2")], axis=1).dropna().reset_index()
    rows = []
    for (i, t, h), g in j.groupby(["id", "target", "h"]):
        g = g.sort_values("origin")
        st, p = diebold_mariano(g["e1"].to_numpy(), g["e2"].to_numpy(), int(h))
        rows.append({"id": i, "target": t, "h": h, "dm_stat": st, "p_value": p, "n": len(g)})
    return pd.DataFrame(rows)


def win_rates(err: pd.DataFrame, challenger: str, baseline: str, by: list[str]) -> pd.DataFrame:
    a = err[err["model"] == challenger].set_index(["id", "target", "origin", "h"])["ae"]
    b = err[err["model"] == baseline].set_index(["id", "target", "origin", "h"])["ae"]
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna().reset_index()
    j["win"] = (j["a"] < j["b"]).astype(float) + 0.5 * (j["a"] == j["b"])
    return j.groupby(by)["win"].mean().rename("win_rate").reset_index()


def series_win_rates(err: pd.DataFrame, challenger: str, baseline: str) -> pd.DataFrame:
    """Per bank: share of target series where the challenger beats the baseline on each metric."""
    s = summarize(err[err["model"].isin([challenger, baseline])], ["model", "id", "target"])
    rows = []
    for metric in ["MAE", "RMSE", "MASE", "sMAPE", "dir_acc"]:
        p = s.pivot_table(index=["id", "target"], columns="model", values=metric, dropna=False)
        p = p.reindex(columns=[challenger, baseline])
        if p.isna().all().any():  # e.g. directional accuracy of a flat (naive) forecast is undefined
            continue
        better = p[challenger] > p[baseline] if metric == "dir_acc" else p[challenger] < p[baseline]
        w = better.groupby(level="id").mean()
        for i, v in w.items():
            rows.append({"id": i, "metric": metric, "win_rate": v})
    return pd.DataFrame(rows)


def identity_gaps(bt: pd.DataFrame, total: str, components: list[str], signs: list[float] | None = None):
    signs = signs or [1.0] * len(components)
    sub = bt[bt["target"].isin([total] + components)]
    p = sub.pivot_table(index=["model", "id", "origin", "h", "live"], columns="target", values="forecast")
    pa = sub.pivot_table(index=["model", "id", "origin", "h", "live"], columns="target", values="actual")
    comp = sum(s * p[c] for s, c in zip(signs, components, strict=True))
    comp_a = sum(s * pa[c] for s, c in zip(signs, components, strict=True))
    out = pd.DataFrame(
        {
            "total_fc": p[total],
            "sum_components_fc": comp,
            "gap_pct": 100 * (comp - p[total]) / p[total].abs(),
            "total_actual": pa[total],
            "gap_actual_pct": 100 * (comp_a - pa[total]) / pa[total].abs(),
        }
    ).reset_index()
    return out
