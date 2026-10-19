"""Synthetic-data tests for the macro horse race helpers (no network, no model weights)."""

import numpy as np
import pandas as pd

from bsforecast import macro_horse as mh


def _ar1(n=400, phi=0.7, c=1.0, seed=0):
    rng = np.random.default_rng(seed)
    y = np.zeros(n)
    y[0] = c / (1 - phi)
    for t in range(1, n):
        y[t] = c + phi * y[t - 1] + rng.normal()
    return y


def test_ar_bic_recovers_ar1_and_forecast_converges():
    y = _ar1()
    p, b, sig = mh.ar_fit(y)
    assert p == 1
    assert abs(b[1] - 0.7) < 0.1 and abs(sig - 1) < 0.15
    mean, sd, _ = mh.ar_forecast(y, 40)
    assert abs(mean[-1] - 1 / 0.3) < 0.6  # converges to the unconditional mean
    assert np.all(np.diff(sd) >= 0) and abs(sd[-1] - 1 / np.sqrt(1 - 0.49)) < 0.25


def test_rw_forecast_flat_with_sqrt_h_bands():
    y = np.cumsum(np.random.default_rng(3).normal(size=50))
    y[:3] = np.nan
    m, s = mh.rw_forecast(y, 4)
    assert np.all(m == y[-1]) and np.allclose(s / s[0], np.sqrt([1, 2, 3, 4]))


def test_quantile_crps_matches_gaussian_closed_form():
    rng = np.random.default_rng(1)
    y = rng.normal(size=4000)
    q = np.tile(mh.norm.ppf(mh.QGRID), (len(y), 1))
    approx = mh.crps_quantiles(q, y).mean()
    exact = mh.crps_gaussian(0.0, 1.0, y).mean()
    assert abs(approx - exact) / exact < 0.12  # 19-quantile grid truncates the tails slightly


def test_regimes_by_target_quarter():
    r = mh.regime_of(pd.Series(["2019Q4", "2020Q1", "2021Q3", "2023Q3", "2026Q2"]))
    assert list(r) == ["pre_covid", "covid", "inflation_surge", "post_2023", "post_2023"]


def _fake_fc():
    rng = np.random.default_rng(2)
    rows = []
    for o in [str(p) for p in pd.period_range("2005Q1", "2010Q4", freq="Q")]:
        for h in range(1, 4):
            a = rng.normal()
            rows += [
                {"model": "ar", "origin": o, "target": "gdp", "h": h, "err": a * 2.0},
                {"model": "good", "origin": o, "target": "gdp", "h": h, "err": a * 1.0 + 0.01 * rng.normal()},
            ]
    return pd.DataFrame(rows)


def test_rel_table_and_dm_detect_better_model():
    fc = _fake_fc()
    rel = mh.rel_table(fc, "rmse")
    g = rel[rel.model == "good"].rel
    assert np.allclose(g, 0.5, atol=0.02)
    assert np.allclose(rel[rel.model == "ar"].rel, 1.0)
    dm = mh.dm_tests(fc, "good", "ar")
    assert (dm.dm_stat < 0).all() and (dm.p_value < 0.01).all()


def test_spf_alignment(tmp_path):
    raw = tmp_path / "raw" / "spf"
    raw.mkdir(parents=True)
    base = {"YEAR": [2010], "QUARTER": [1]}
    pd.DataFrame({**base, **{f"drgdp{k}": [float(k)] for k in range(2, 7)}}).to_csv(raw / "spf_growth_rgdp.csv")
    for stem, fn in (("CPI", "cpi"), ("COREPCE", "corepce"), ("PCE", "pce"), ("UNEMP", "unemp")):
        pd.DataFrame({**base, **{f"{stem}{k}": [float(k)] for k in range(1, 7)}}).to_csv(raw / f"spf_level_{fn}.csv")
    spf = mh.build_spf(tmp_path / "raw", tmp_path)
    g = spf[spf.target == "gdp"].set_index("h")["mean"]
    assert set(spf.origin) == {"2009Q4"}  # survey 2010Q1 -> origin = last full quarter 2009Q4
    assert abs(g[1] - 400 * np.log1p(2 / 400)) < 1e-9 and len(g) == 5  # column 2 = nowcast = h1
    assert spf[(spf.target == "unrate") & (spf.h == 5)]["mean"].iloc[0] == 6.0
