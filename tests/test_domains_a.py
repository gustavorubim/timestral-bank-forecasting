import numpy as np
import pandas as pd

from bsforecast.backtest import _batch, run_backtest
from bsforecast.config import BacktestConfig, Config, DataConfig, EvalConfig, ModelConfig, PlotConfig, load_config
from bsforecast.dataset import from_frame
from bsforecast.models import build_model
from bsforecast.report import build_report


def _cfg(tmp_path, **plots):
    return Config(
        name="da",
        data=DataConfig(path="", date_col="date", id_col="bank", targets=["assets", "income"], covariates=["macro"]),
        backtest=BacktestConfig(horizon=6, n_origins=4, min_train=20, live_forecast=False, max_context=30),
        models=[
            ModelConfig("naive", "naive"),
            ModelConfig("snaive", "seasonal_naive", {"season_length": 4}),
            ModelConfig("ets", "auto_ets", {"season_length": 4, "n_jobs": 1}),
        ],
        evaluation=EvalConfig(baseline="naive", challenger="ets"),
        plots=PlotConfig(spaghetti_models=["naive", "ets"], **plots),
        output_dir=str(tmp_path / "out"),
    )


def test_max_context_truncates(synth_df, tmp_path):
    cfg = _cfg(tmp_path)
    panel = from_frame(synth_df, cfg.data)
    b = _batch(panel, 50, 6, False, "QE", max_context=30)
    assert b.y.shape == (6, 1, 30) and b.x_past.shape[-1] == 30 and b.x_future.shape[-1] == 6
    assert np.allclose(b.y[0, 0], panel.y[0, 0, 21:51])
    assert _batch(panel, 50, 6, False, "QE").y.shape[-1] == 51  # default unchanged


def test_ets_and_mstl_shapes(synth_df, tmp_path):
    cfg = _cfg(tmp_path)
    panel = from_frame(synth_df, cfg.data)
    b = _batch(panel, 40, 6, False, "QE")
    for typ, params in [("auto_ets", {"season_length": 4}), ("mstl", {"season_lengths": [4]})]:
        q = build_model(ModelConfig(typ, typ, {**params, "n_jobs": 1}), [0.1, 0.5, 0.9]).predict(b)
        assert q.shape == (6, 1, 6, 3) and np.isfinite(q).all()
        assert (q[..., 0] <= q[..., 1] + 1e-9).all() and (q[..., 1] <= q[..., 2] + 1e-9).all()


def test_targets_grid_and_id_heatmaps(synth_df, tmp_path):
    cfg = _cfg(tmp_path, spaghetti_targets_grid=True, id_heatmaps=True)
    panel = from_frame(synth_df, cfg.data)
    build_report(cfg, panel, run_backtest(cfg, panel))
    f = cfg.out / "figures"
    assert (f / "spaghetti_targets_A.png").exists() and (f / "relmase_id_x_variant.png").exists()
    assert (f / "relmase_id_x_horizon_ets.png").exists()


def test_domain_configs_parse():
    for d in ["electricity", "inflation", "credit_losses", "treasury_curve"]:
        cfg = load_config(f"experiments/{d}/config.yaml")
        names = [m.name for m in cfg.models]
        assert cfg.evaluation.baseline in names and cfg.evaluation.challenger in names
        for a, b in cfg.plots.compare_pairs:
            assert a in names and b in names
        for m in cfg.models:
            assert set(m.params.get("covariate_subset", [])) <= set(cfg.data.covariates)


def test_electricity_daily_load_flags_short_days(tmp_path):
    from bsforecast.data.electricity import daily_load

    rows = []
    for d, hours in [("2024-01-01", 24), ("2024-01-02", 10)]:
        for _h in range(hours):
            rows.append({"Balancing Authority": "FPL", "Data Date": d, "Demand (MW)": "1,000"})
    p = tmp_path / "x.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    out = daily_load([p]).set_index("date")["gwh"]
    assert np.isclose(out.loc["2024-01-01"], 24.0) and np.isnan(out.loc["2024-01-02"])
