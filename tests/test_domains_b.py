"""Tests for the non-bank domain loaders (earnings, housing, retail) and shared-code additions."""

from __future__ import annotations

import numpy as np
import pandas as pd

from bsforecast.config import ModelConfig, PlotConfig
from bsforecast.data.earnings import _cal_q, quarterly_facts
from bsforecast.data.retail import calendar_features
from bsforecast.models import REGISTRY, AutoETSModel, Batch, build_model


def _fact(start, end, val, filed="2020-01-01", form="10-Q"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form}


def test_q4_derived_from_annual_minus_three_quarters():
    units = [
        _fact("2019-01-01", "2019-03-31", 10),
        _fact("2019-04-01", "2019-06-30", 20),
        _fact("2019-07-01", "2019-09-30", 30),
        _fact("2019-01-01", "2019-12-31", 100, form="10-K"),
        _fact("2019-01-01", "2019-06-30", 30),  # 6-month YTD fact must be ignored
    ]
    s = quarterly_facts(units)
    assert list(s.index.strftime("%Y-%m-%d")) == ["2019-03-31", "2019-06-30", "2019-09-30", "2019-12-31"]
    assert s.iloc[-1] == 40


def test_q4_not_derived_when_reported_and_restatement_wins():
    units = [
        _fact("2019-10-01", "2019-12-31", 41, filed="2020-02-01", form="10-K"),
        _fact("2019-10-01", "2019-12-31", 45, filed="2021-02-01", form="10-K"),
        _fact("2019-01-01", "2019-12-31", 100, form="10-K"),
    ]
    s = quarterly_facts(units)
    assert len(s) == 1 and s.iloc[0] == 45


def test_fiscal_quarter_maps_to_calendar_quarter_by_midpoint():
    ends = pd.Series(pd.to_datetime(["2024-01-28", "2024-09-28", "2024-06-30", "2024-04-30"]))
    got = _cal_q(ends).dt.strftime("%Y-%m-%d").tolist()
    assert got == ["2023-12-31", "2024-09-30", "2024-06-30", "2024-03-31"]


def test_calendar_features_weekends():
    f = calendar_features(pd.DatetimeIndex(["2024-02-29", "2024-06-30"]))
    assert f["n_days"].tolist() == [29, 30]
    assert f["n_weekend_days"].tolist() == [8, 10]
    assert np.allclose(f["month_sin"] ** 2 + f["month_cos"] ** 2, 1)


def test_auto_ets_registered_and_forecasts():
    assert REGISTRY["auto_ets"] is AutoETSModel
    m = build_model(
        ModelConfig(name="ets", type="auto_ets", covariates="known_oracle", params={"season_length": 4}),
        [0.1, 0.5, 0.9],
    )
    t = 40
    rng = np.random.default_rng(0)
    y = (100 + np.cumsum(rng.normal(0, 1, t)) + 5 * np.sin(np.arange(t) * np.pi / 2)).reshape(1, 1, t)
    q = m.predict(Batch(y=y, x_past=np.zeros((1, 1, t)), x_future=np.zeros((1, 1, 8)), horizon=8, freq="QE"))
    assert q.shape == (1, 1, 8, 3)
    assert np.all(q[..., 0] <= q[..., 1]) and np.all(q[..., 1] <= q[..., 2])


def test_plotconfig_spaghetti_ids_default_empty():
    assert PlotConfig().spaghetti_ids == []


def test_sec_user_agent_requires_env(monkeypatch):
    import pytest

    from bsforecast.data.earnings import sec_user_agent

    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(RuntimeError, match="contact email"):
        sec_user_agent()
    monkeypatch.setenv("SEC_USER_AGENT", "Test research test@example.com")
    assert sec_user_agent() == "Test research test@example.com"
