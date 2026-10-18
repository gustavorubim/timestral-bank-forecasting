import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synth_df():
    rng = np.random.default_rng(0)
    dates = pd.date_range("2005-03-31", periods=60, freq="QE")
    rows = []
    for i, bank in enumerate(["A", "B", "C"]):
        trend = np.linspace(100, 160, 60) * (1 + 0.2 * i)
        assets = trend + rng.normal(0, 2, 60).cumsum()
        loans = 0.6 * assets + rng.normal(0, 1, 60)
        other = assets - loans
        season = 5 * np.sin(np.arange(60) * np.pi / 2)
        income = 10 + season + rng.normal(0, 0.5, 60)
        macro = np.sin(np.arange(60) / 6)
        for t, d in enumerate(dates):
            rows.append(
                dict(
                    date=d,
                    bank=bank,
                    assets=assets[t],
                    loans=loans[t],
                    other=other[t],
                    income=income[t],
                    macro=macro[t],
                )
            )
    return pd.DataFrame(rows)


def pytest_addoption(parser):
    parser.addoption("--run-timestral", action="store_true", help="run tests that download Timestral weights")
