"""Forecasters with a common batch interface.

Every model gets a batch of series cut at a forecast origin and returns quantile
forecasts for the *whole* horizon in one call (direct multi-horizon, no chaining of
one-step forecasts by the harness). For Timestral, an 8-quarter horizon fits inside a
single 32-step output patch, so the model emits all 8 steps in one forward pass.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm

from .config import ModelConfig


@dataclass
class Batch:
    """Series cut at one origin. y: (B, V, T) context; x_past: (B, C, T); x_future: (B, C, H)."""

    y: np.ndarray
    x_past: np.ndarray
    x_future: np.ndarray
    horizon: int
    freq: str = "QE"
    cov_names: list[str] | None = None


class Forecaster:
    multivariate = False  # if True, receives all targets of an id jointly (V > 1)

    def __init__(self, cfg: ModelConfig, quantiles: list[float]):
        self.cfg = cfg
        self.quantiles = np.asarray(quantiles)

    def predict(self, batch: Batch) -> np.ndarray:
        """Return quantiles (B, V, H, Q)."""
        raise NotImplementedError


def _last_valid(y: np.ndarray) -> np.ndarray:
    s = pd.DataFrame(y.reshape(-1, y.shape[-1])).ffill(axis=1).to_numpy()[:, -1]
    return s.reshape(y.shape[:-1])


def _naive_sigma(y: np.ndarray, lag: int) -> np.ndarray:
    d = y[..., lag:] - y[..., :-lag]
    return np.nanstd(d, axis=-1)


class Naive(Forecaster):
    def predict(self, batch):
        last = _last_valid(batch.y)
        sig = _naive_sigma(batch.y, 1)
        h = np.arange(1, batch.horizon + 1)
        z = norm.ppf(self.quantiles)
        return last[..., None, None] + sig[..., None, None] * np.sqrt(h)[:, None] * z


class SeasonalNaive(Forecaster):
    def predict(self, batch):
        m = int(self.cfg.params.get("season_length", 4))
        y = pd.DataFrame(batch.y.reshape(-1, batch.y.shape[-1])).ffill(axis=1).to_numpy()
        y = y.reshape(batch.y.shape)
        h = np.arange(batch.horizon)
        base = y[..., -m:][..., h % m]
        sig = _naive_sigma(batch.y, m)
        k = np.floor(h / m) + 1
        z = norm.ppf(self.quantiles)
        return base[..., None] + sig[..., None, None] * np.sqrt(k)[:, None] * z


def _full_rank_columns(x: np.ndarray, tol: float = 1e-8) -> list[int]:
    """Greedy column selection so the exogenous matrix (with intercept) has full column rank."""
    keep: list[int] = []
    base = np.ones((x.shape[0], 1))
    for c in range(x.shape[1]):
        if np.nanstd(x[:, c]) < tol:
            continue
        cand = np.column_stack([base, x[:, keep + [c]]])
        if np.linalg.matrix_rank(cand, tol=tol * np.abs(cand).max()) == cand.shape[1]:
            keep.append(c)
    return keep


def Naive_():
    from statsforecast.models import Naive as SFNaive

    return SFNaive()


class AutoARIMAModel(Forecaster):
    """statsforecast AutoARIMA; with ``covariates: known_oracle`` it is an ARIMAX."""

    def predict(self, batch):
        from statsforecast import StatsForecast
        from statsforecast.models import AutoARIMA

        b, v, t = batch.y.shape
        qs = self.quantiles
        levels = sorted({int(round(abs(1 - 2 * q) * 100)) for q in qs if abs(q - 0.5) > 1e-9})
        dates = pd.date_range("2000-03-31", periods=t + batch.horizon, freq=batch.freq)
        use_x = self.cfg.covariates == "known_oracle" and batch.x_past.shape[1] > 0
        cols = list(range(batch.x_past.shape[1]))
        subset = self.cfg.params.get("covariate_subset")
        if use_x and subset and batch.cov_names:
            cols = [batch.cov_names.index(c) for c in subset]
        rows, xrows = [], []
        for i in range(b):
            for j in range(v):
                s = pd.Series(batch.y[i, j], index=dates[:t])
                first = s.first_valid_index()
                if first is None:
                    continue
                s = s.loc[first:].ffill()
                df = pd.DataFrame({"unique_id": f"{i}|{j}", "ds": s.index, "y": s.to_numpy()})
                if use_x:
                    xp = pd.DataFrame(batch.x_past[i][cols].T, index=dates[:t]).loc[first:].ffill().bfill()
                    xf = pd.DataFrame(batch.x_future[i][cols].T, index=dates[t:]).ffill()
                    xf = xf.fillna(xp.iloc[-1])
                    keep = _full_rank_columns(xp.to_numpy())
                    xp, xf = xp.iloc[:, keep], xf.iloc[:, keep]
                    xp.columns = xf.columns = range(len(keep))
                    for c in range(xp.shape[1]):
                        df[f"x{c}"] = xp[c].to_numpy()
                    xr = pd.DataFrame({"unique_id": f"{i}|{j}", "ds": dates[t:]})
                    for c in range(xf.shape[1]):
                        xr[f"x{c}"] = xf[c].to_numpy()
                    xrows.append(xr)
                rows.append(df)
        df = pd.concat(rows, ignore_index=True)
        m = int(self.cfg.params.get("season_length", 4))
        sf = StatsForecast(
            models=[AutoARIMA(season_length=m, alias="m")],
            freq=batch.freq,
            n_jobs=int(self.cfg.params.get("n_jobs", min(8, os.cpu_count() or 1))),
            # A failed ARIMAX fit (e.g. singular xreg) falls back to a plain AutoARIMA-free naive.
            fallback_model=Naive_() if use_x else None,
        )
        kw = {"X_df": pd.concat(xrows, ignore_index=True)} if use_x else {}
        fc = sf.forecast(df=df, h=batch.horizon, level=levels, **kw)
        if "unique_id" not in fc.columns:
            fc = fc.reset_index()
        out = np.full((b, v, batch.horizon, len(qs)), np.nan)
        for uid, g in fc.groupby("unique_id"):
            i, j = map(int, str(uid).split("|"))
            g = g.sort_values("ds")
            for k, q in enumerate(qs):
                if abs(q - 0.5) < 1e-9:
                    col = "m"
                else:
                    lvl = int(round(abs(1 - 2 * q) * 100))
                    col = f"m-{'lo' if q < 0.5 else 'hi'}-{lvl}"
                out[i, j, :, k] = g[col].to_numpy()
        return out


class TimestralModel(Forecaster):
    _cache: dict[str, object] = {}

    def __init__(self, cfg, quantiles):
        super().__init__(cfg, quantiles)
        self.multivariate = bool(cfg.params.get("multivariate", False))

    def _model(self):
        import torch
        from timestral import TimestralForecaster

        mid = self.cfg.params.get("model_id", "mistralai/Timestral-209M")
        if mid not in self._cache:
            torch.set_num_threads(int(self.cfg.params.get("threads", min(8, os.cpu_count() or 1))))
            self._cache[mid] = TimestralForecaster.from_pretrained(mid, device="cpu")
        return self._cache[mid]

    def predict(self, batch):
        m = self._model()
        kw = {}
        if self.cfg.covariates == "past" and batch.x_past.shape[1]:
            kw["past_covariates"] = batch.x_past
        elif self.cfg.covariates == "known_oracle" and batch.x_past.shape[1]:
            kw["known_covariates"] = np.concatenate([batch.x_past, batch.x_future], axis=-1)
        bs = int(self.cfg.params.get("batch_size", 64))
        outs = []
        for s in range(0, batch.y.shape[0], bs):
            sl = slice(s, s + bs)
            kws = {k: v[sl] for k, v in kw.items()}
            f = m.forecast(
                batch.y[sl],
                prediction_length=batch.horizon,
                clip_nonnegative=bool(self.cfg.params.get("clip_nonnegative", True)),
                **kws,
            )
            outs.append(f.quantiles.cpu().numpy())
        q = np.concatenate(outs, axis=0)  # (B, V, H, 21)
        knots = np.asarray(m.config.quantile_knots)
        idx = [int(np.argmin(np.abs(knots - x))) for x in self.quantiles]
        return q[..., idx]


REGISTRY = {
    "naive": Naive,
    "seasonal_naive": SeasonalNaive,
    "auto_arima": AutoARIMAModel,
    "timestral": TimestralModel,
}


def build_model(cfg: ModelConfig, quantiles: list[float]) -> Forecaster:
    if cfg.type not in REGISTRY:
        raise ValueError(f"unknown model type {cfg.type!r}; choose from {sorted(REGISTRY)}")
    return REGISTRY[cfg.type](cfg, quantiles)
