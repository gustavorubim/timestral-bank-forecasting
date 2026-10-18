import numpy as np
import pandas as pd
import pytest

from bsforecast.backtest import model_view, run_backtest
from bsforecast.config import BacktestConfig, Config, DataConfig, EvalConfig, ModelConfig, PlotConfig
from bsforecast.data.fred import fill_curve_gaps
from bsforecast.dataset import from_frame
from bsforecast.report import build_report


def test_fill_curve_gaps_interior_only():
    idx = pd.date_range("2000-03-31", periods=8, freq="QE")
    c = pd.DataFrame(
        {
            "y10": [4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7],
            "y30": [np.nan, 5.0, np.nan, np.nan, 5.6, 5.7, np.nan, 5.9],
        },
        index=idx,
    )
    f = fill_curve_gaps(c)
    assert np.isnan(f["y30"].iloc[0])  # leading gap: no extrapolation
    # interior gap: spread 0.9 -> 1.2 interpolated linearly, then added to the 10y
    assert np.isclose(f["y30"].iloc[2], 4.2 + 1.0) and np.isclose(f["y30"].iloc[3], 4.3 + 1.1)
    assert np.isclose(f["y30"].iloc[6], 4.6 + 1.2)


def test_model_view_subset(synth_df):
    synth_df["macro2"] = synth_df["macro"] * 2 + 1
    p = from_frame(
        synth_df,
        DataConfig(path="", date_col="date", id_col="bank", targets=["assets"], covariates=["macro", "macro2"]),
    )
    v = model_view(p, ["macro2"])
    assert v.covariates == ["macro2"] and v.x.shape[1] == 1 and np.allclose(v.x[:, 0], p.x[:, 1])
    assert model_view(p, None) is p
    with pytest.raises(KeyError):
        model_view(p, ["nope"])


def test_highlight_sections(tmp_path, synth_df):
    synth_df["macro2"] = np.cos(np.arange(len(synth_df)) / 5)
    cfg = Config(
        name="ts",
        data=DataConfig(
            path="", date_col="date", id_col="bank", targets=["assets", "income"], covariates=["macro", "macro2"]
        ),
        backtest=BacktestConfig(horizon=8, n_origins=6, min_train=20),
        models=[
            ModelConfig("naive", "naive"),
            ModelConfig(
                "arimax",
                "auto_arima",
                {"season_length": 4, "n_jobs": 1, "covariate_subset": ["macro"]},
                covariates="known_oracle",
            ),
        ],
        evaluation=EvalConfig(baseline="naive", challenger="arimax"),
        plots=PlotConfig(
            highlight_origins=["2016-06-30", "2017-03-31"],
            highlight_series=["income"],
            highlight_models=["naive", "arimax"],
            spaghetti_series=["assets"],
            spaghetti_models=["naive", "arimax"],
            compare_pairs=[["arimax", "naive"]],
            yield_curve={"columns": ["macro", "macro2"], "maturities": [1, 10]},
        ),
        output_dir=str(tmp_path / "out"),
    )
    panel = from_frame(synth_df, cfg.data)
    bt = run_backtest(cfg, panel)
    build_report(cfg, panel, bt)
    figs = cfg.out / "figures"
    for f in ["fans_income.png", "spaghetti_assets.png", "help_arimax_vs_naive.png", "yield_curves.png"]:
        assert (figs / f).exists(), f
    text = (cfg.out / "REPORT.md").read_text()
    assert "Highlighted origins only" in text and "How much does `arimax` help" in text
