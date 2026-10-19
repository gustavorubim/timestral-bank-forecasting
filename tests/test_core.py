import numpy as np
import pandas as pd
import pytest

from bsforecast import metrics as M
from bsforecast.backtest import origin_indices, run_backtest
from bsforecast.config import (
    BacktestConfig,
    Config,
    DataConfig,
    EvalConfig,
    IdentityConfig,
    ModelConfig,
    PlotConfig,
    load_config,
)
from bsforecast.dataset import from_frame
from bsforecast.models import Batch, Naive, SeasonalNaive
from bsforecast.report import build_report


def _cfg(tmp_path, models):
    return Config(
        name="synth",
        data=DataConfig(
            path="",
            date_col="date",
            id_col="bank",
            targets=["assets", "loans", "other", "income"],
            covariates=["macro"],
            groups={"bs": ["assets", "loans", "other"], "inc": ["income"]},
        ),
        backtest=BacktestConfig(
            horizon=8, n_origins=6, min_train=20, stress_windows={"late": ["2017-01-01", "2018-12-31"]}
        ),
        models=models,
        evaluation=EvalConfig(baseline="naive", challenger="snaive"),
        identities=[IdentityConfig(name="assets", total="assets", components=["loans", "other"])],
        plots=PlotConfig(
            fan_series=["assets", "income"],
            fan_origins=["2016-06-30"],
            stress_series=["assets"],
            stress_origin="2016-06-30",
        ),
        output_dir=str(tmp_path / "out"),
    )


def test_panel_shape_and_gaps(synth_df):
    df = synth_df.drop(index=[5])  # drop one row -> becomes NaN, calendar stays regular
    p = from_frame(df, DataConfig(path="", date_col="date", id_col="bank", targets=["assets"], covariates=["macro"]))
    assert p.y.shape == (3, 1, 60) and p.x.shape == (3, 1, 60)
    assert np.isnan(p.y).sum() == 1


def test_single_series_without_id(synth_df):
    df = synth_df[synth_df.bank == "A"].drop(columns="bank")
    p = from_frame(df, DataConfig(path="", date_col="date", id_col="bank", targets=["assets", "income"]))
    assert p.ids == ["series"] and p.y.shape == (1, 2, 60)


def test_missing_column_raises(synth_df):
    with pytest.raises(KeyError):
        from_frame(synth_df, DataConfig(path="", date_col="date", id_col="bank", targets=["nope"]))


def test_origins_leave_full_horizon():
    idx = origin_indices(60, 8, 12, 1, 20)
    assert idx[-1] == 51 and len(idx) == 12 and idx == sorted(idx)


def test_naive_and_seasonal_shapes():
    y = np.arange(40, dtype=float).reshape(1, 1, 40)
    b = Batch(y=y, x_past=np.zeros((1, 0, 40)), x_future=np.zeros((1, 0, 8)), horizon=8)
    q = Naive(ModelConfig("n", "naive"), [0.1, 0.5, 0.9]).predict(b)
    assert q.shape == (1, 1, 8, 3) and np.allclose(q[..., 1], 39)
    s = SeasonalNaive(ModelConfig("s", "seasonal_naive", {"season_length": 4}), [0.5]).predict(b)
    assert np.allclose(s[0, 0, :, 0], [36, 37, 38, 39, 36, 37, 38, 39])


def test_dm_detects_better_model():
    rng = np.random.default_rng(1)
    e2 = rng.normal(0, 3, 200)
    e1 = rng.normal(0, 1, 200)
    stat, p = M.diebold_mariano(e1, e2, h=1)
    assert stat < 0 and p < 0.01
    stat, p = M.diebold_mariano(e2, e2 + 1e-12 * rng.normal(size=200), h=4)
    assert p > 0.05 or np.isnan(p)


def test_end_to_end_with_arima(tmp_path, synth_df):
    models = [
        ModelConfig("naive", "naive"),
        ModelConfig("snaive", "seasonal_naive", {"season_length": 4}),
        ModelConfig("arima", "auto_arima", {"season_length": 4, "n_jobs": 1}),
        ModelConfig("arimax", "auto_arima", {"season_length": 4, "n_jobs": 1}, covariates="known_oracle"),
    ]
    cfg = _cfg(tmp_path, models)
    panel = from_frame(synth_df, cfg.data)
    bt = run_backtest(cfg, panel)
    # 4 models x (6 origins + live) x 3 banks x 4 targets x 8 horizons
    assert len(bt) == 4 * 7 * 3 * 4 * 8
    assert bt.loc[~bt.live, "actual"].notna().all()
    assert (bt["q0.1"] <= bt["q0.9"] + 1e-9).all()
    s = build_report(cfg, panel, bt)
    err = M.add_errors(bt)
    # seasonal naive must beat naive on the seasonal income series
    inc = M.summarize(err[err.target == "income"], ["model"]).set_index("model")
    assert inc.loc["snaive", "MASE"] < inc.loc["naive", "MASE"]
    assert (cfg.out / "REPORT.md").exists()
    assert (cfg.out / "figures" / "winrate_heatmap_target_bank.png").exists()
    assert {r["model"] for r in s["rel_mase"]} == {m.name for m in models}


def test_identity_gap_zero_for_consistent_naive(tmp_path, synth_df):
    cfg = _cfg(tmp_path, [ModelConfig("naive", "naive")])
    bt = run_backtest(cfg, from_frame(synth_df, cfg.data))
    g = M.identity_gaps(bt, "assets", ["loans", "other"])
    assert np.allclose(g["gap_pct"], 0, atol=1e-8)  # naive carries components forward exactly


def test_metrics_values():
    bt = pd.DataFrame(
        {
            "live": False,
            "actual": [10.0, 10.0],
            "forecast": [11.0, 8.0],
            "y_origin": [9.0, 9.0],
            "scale": [1.0, 1.0],
            "q0.1": [9.0, 9.0],
            "q0.9": [12.0, 9.5],
            "model": "m",
            "id": "a",
            "target": "t",
            "origin": pd.Timestamp("2020-03-31"),
            "h": [1, 2],
        }
    )
    e = M.add_errors(bt)
    s = M.summarize(e, ["model"]).iloc[0]
    assert s.MAE == 1.5 and np.isclose(s.RMSE, np.sqrt(2.5)) and s.MASE == 1.5
    assert s.coverage80 == 0.5 and s.dir_acc == 0.5


def test_example_config_parses():
    cfg = load_config("experiments/y9c_top4/config.yaml")
    assert cfg.backtest.horizon == 8 and any(m.type == "timestral" for m in cfg.models)


@pytest.mark.skipif("not config.getoption('--run-timestral', default=False)")
def test_timestral_smoke():
    from bsforecast.models import TimestralModel

    y = np.cumsum(np.random.default_rng(0).normal(size=(2, 1, 60)), -1)
    b = Batch(y=y, x_past=np.zeros((2, 0, 60)), x_future=np.zeros((2, 0, 8)), horizon=8)
    q = TimestralModel(ModelConfig("t", "timestral"), [0.1, 0.5, 0.9]).predict(b)
    assert q.shape == (2, 1, 8, 3)
