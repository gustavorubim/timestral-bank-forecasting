"""Rolling-origin backtest with direct H-step forecasts from every origin."""

from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd

from .config import Config
from .dataset import Panel
from .models import Batch, build_model

log = logging.getLogger(__name__)


def origin_indices(n_time: int, horizon: int, n_origins: int, step: int, min_train: int) -> list[int]:
    """Indices of the last observed period at each origin; every origin has a full horizon of actuals."""
    last = n_time - 1 - horizon
    idx = [last - k * step for k in range(n_origins)]
    idx = sorted(i for i in idx if i + 1 >= min_train)
    if not idx:
        raise ValueError("no valid origins: reduce n_origins/min_train or provide more history")
    return idx


def _batch(panel: Panel, o: int, horizon: int, multivariate: bool, freq: str) -> Batch:
    t_end = o + 1
    y = panel.y[:, :, :t_end]
    xp = panel.x[:, :, :t_end]
    xf = panel.x[:, :, t_end : t_end + horizon]
    if xf.shape[-1] < horizon:  # live origin: no realised covariates -> hold last value
        pad = np.repeat(xp[:, :, -1:], horizon - xf.shape[-1], axis=-1)
        xf = np.concatenate([xf, pad], axis=-1)
    if multivariate:
        return Batch(y=y, x_past=xp, x_future=xf, horizon=horizon, freq=freq, cov_names=panel.covariates)
    n_id, n_tg, _ = y.shape
    return Batch(
        y=y.reshape(n_id * n_tg, 1, t_end),
        x_past=np.repeat(xp, n_tg, axis=0),
        x_future=np.repeat(xf, n_tg, axis=0),
        horizon=horizon,
        freq=freq,
        cov_names=panel.covariates,
    )


def mase_scale(y: np.ndarray, m: int) -> np.ndarray:
    d = np.abs(y[..., m:] - y[..., :-m])
    with np.errstate(all="ignore"):
        return np.nanmean(d, axis=-1)


def run_backtest(cfg: Config, panel: Panel) -> pd.DataFrame:
    h = cfg.backtest.horizon
    qs = cfg.evaluation.quantiles
    origins = origin_indices(len(panel.dates), h, cfg.backtest.n_origins, cfg.backtest.step, cfg.backtest.min_train)
    if cfg.backtest.live_forecast:
        origins = origins + [len(panel.dates) - 1]
    n_id, n_tg, n_t = panel.y.shape
    future_dates = pd.date_range(panel.dates[-1], periods=h + 1, freq=cfg.data.freq)[1:]
    all_dates = panel.dates.append(future_dates)
    frames = []
    for mc in cfg.models:
        model = build_model(mc, qs)
        t0 = time.time()
        for o in origins:
            b = _batch(panel, o, h, model.multivariate, cfg.data.freq)
            q = model.predict(b).reshape(n_id, n_tg, h, len(qs))
            ctx = panel.y[:, :, : o + 1]
            last = pd.DataFrame(ctx.reshape(-1, o + 1)).ffill(axis=1).to_numpy()[:, -1].reshape(n_id, n_tg)
            scale = mase_scale(ctx, cfg.evaluation.mase_season)
            act = np.full((n_id, n_tg, h), np.nan)
            seg = panel.y[:, :, o + 1 : o + 1 + h]
            act[:, :, : seg.shape[-1]] = seg
            ii, jj, kk = np.meshgrid(np.arange(n_id), np.arange(n_tg), np.arange(h), indexing="ij")
            df = pd.DataFrame(
                {
                    "model": mc.name,
                    "id": np.asarray(panel.ids)[ii.ravel()],
                    "target": np.asarray(panel.targets)[jj.ravel()],
                    "origin": panel.dates[o],
                    "h": kk.ravel() + 1,
                    "date": all_dates[o + 1 + kk.ravel()],
                    "actual": act.ravel(),
                    "y_origin": last[ii.ravel(), jj.ravel()],
                    "scale": scale[ii.ravel(), jj.ravel()],
                    "live": o == n_t - 1,
                }
            )
            for k, qq in enumerate(qs):
                df[f"q{qq:g}"] = q[..., k].ravel()
            frames.append(df)
        log.info("model %s: %d origins in %.1fs", mc.name, len(origins), time.time() - t0)
    out = pd.concat(frames, ignore_index=True)
    out["forecast"] = out["q0.5"]
    return out
