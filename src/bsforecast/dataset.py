"""Load any CSV/parquet panel into a dense (id, target, time) cube."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DataConfig


@dataclass
class Panel:
    dates: pd.DatetimeIndex
    ids: list[str]
    targets: list[str]
    covariates: list[str]
    y: np.ndarray  # (n_ids, n_targets, T)
    x: np.ndarray  # (n_ids, n_cov, T)

    @property
    def n_series(self) -> int:
        return len(self.ids) * len(self.targets)

    def series_keys(self) -> list[tuple[str, str]]:
        return [(i, t) for i in self.ids for t in self.targets]


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    return pd.read_csv(path)


def from_frame(df: pd.DataFrame, cfg: DataConfig) -> Panel:
    df = df.copy()
    if cfg.id_col not in df.columns:  # single-series dataset
        df[cfg.id_col] = "series"
    df[cfg.date_col] = pd.to_datetime(df[cfg.date_col])
    if cfg.min_date:
        df = df[df[cfg.date_col] >= pd.Timestamp(cfg.min_date)]
    targets = cfg.targets or [c for c in df.select_dtypes("number").columns if c not in cfg.covariates]
    missing = [c for c in targets + cfg.covariates if c not in df.columns]
    if missing:
        raise KeyError(f"columns not found in dataset: {missing}")
    obs = pd.DatetimeIndex(sorted(df[cfg.date_col].unique()))
    # Regular calendar so gaps become NaN (both model families accept / handle NaN).
    dates = pd.date_range(obs.min(), obs.max(), freq=cfg.freq) if cfg.freq else obs
    if not obs.isin(dates).all():  # e.g. dates not on period ends: snap them
        df[cfg.date_col] = df[cfg.date_col].dt.to_period(dates.freqstr[0]).dt.end_time.dt.normalize()
    ids = sorted(df[cfg.id_col].astype(str).unique())
    df[cfg.id_col] = df[cfg.id_col].astype(str)
    idx = pd.MultiIndex.from_product([ids, dates], names=[cfg.id_col, cfg.date_col])
    wide = df.set_index([cfg.id_col, cfg.date_col])[targets + cfg.covariates]
    wide = wide[~wide.index.duplicated(keep="last")].reindex(idx)
    t = len(dates)
    y = wide[targets].to_numpy(float).reshape(len(ids), t, len(targets)).transpose(0, 2, 1)
    if cfg.covariates:
        x = wide[cfg.covariates].to_numpy(float).reshape(len(ids), t, len(cfg.covariates)).transpose(0, 2, 1)
    else:
        x = np.zeros((len(ids), 0, t))
    return Panel(dates=dates, ids=ids, targets=list(targets), covariates=list(cfg.covariates), y=y, x=x)


def load_panel(cfg: DataConfig) -> Panel:
    return from_frame(read_table(cfg.path), cfg)
