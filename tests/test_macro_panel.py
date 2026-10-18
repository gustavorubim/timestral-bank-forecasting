import numpy as np
import pandas as pd

from bsforecast.backtest import run_backtest
from bsforecast.config import BacktestConfig, Config, DataConfig, EvalConfig, ModelConfig, PlotConfig
from bsforecast.data.granular import CHECKS, LINES, check_identities
from bsforecast.dataset import from_frame
from bsforecast.report import build_report


def test_line_map_is_unique_and_checks_reference_lines():
    names = [n for g in LINES.values() for n in g]
    assert len(names) == len(set(names)) == 37
    for _, total, comps, signs in CHECKS:
        assert total in names and all(c in names for c in comps) and len(comps) == len(signs)


def test_check_identities_flags_gap():
    df = pd.DataFrame({"bank": ["A", "A"], "date": pd.to_datetime(["2020-03-31", "2020-06-30"])})
    for n in [n for g in LINES.values() for n in g]:
        df[n] = 1.0
    df["deposits"], df["dep_dom"], df["dep_for"] = 10.0, 6.0, 4.0
    df["dep_ib"], df["dep_nib"] = 7.0, [3.0, 2.0]  # second quarter is 10% short
    r = check_identities(df).set_index("check")
    assert r.loc["deposits = domestic + foreign", "max_abs_gap_pct"] == 0
    assert np.isclose(r.loc["deposits = int.-bearing + nonint.-bearing", "max_abs_gap_pct"], 10)


def test_group_pages(tmp_path, synth_df):
    cfg = Config(
        name="mp",
        data=DataConfig(
            path="",
            date_col="date",
            id_col="bank",
            targets=["assets", "loans", "income"],
            covariates=["macro"],
            groups={"bs": ["assets", "loans"], "inc": ["income"]},
        ),
        backtest=BacktestConfig(horizon=8, n_origins=5, min_train=20, live_forecast=False),
        models=[ModelConfig("naive", "naive"), ModelConfig("snaive", "seasonal_naive", {"season_length": 4})],
        evaluation=EvalConfig(baseline="naive", challenger="snaive"),
        plots=PlotConfig(
            spaghetti_models=["naive", "snaive"], spaghetti_by_group=True, compare_pairs=[["snaive", "naive"]]
        ),
        output_dir=str(tmp_path / "out"),
    )
    panel = from_frame(synth_df, cfg.data)
    build_report(cfg, panel, run_backtest(cfg, panel))
    f = cfg.out / "figures"
    assert (f / "bs" / "spaghetti_loans.png").exists() and (f / "inc" / "index.md").exists()
    assert (f / "relmase_line_x_variant.png").exists() and (f / "macro_helps_by_line.png").exists()
