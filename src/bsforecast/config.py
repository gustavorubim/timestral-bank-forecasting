"""YAML configuration schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DataConfig:
    path: str
    date_col: str = "date"
    id_col: str = "id"
    targets: list[str] = field(default_factory=list)
    covariates: list[str] = field(default_factory=list)
    freq: str = "QE"
    min_date: str | None = None
    # Optional groups of targets (used for per-group metrics and plots).
    groups: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class BacktestConfig:
    horizon: int = 8
    n_origins: int = 12
    step: int = 1
    min_train: int = 24
    # Named windows of *origin* dates, e.g. covid: ["2019-06-30", "2020-06-30"].
    stress_windows: dict[str, list[str]] = field(default_factory=dict)
    live_forecast: bool = True


@dataclass
class ModelConfig:
    name: str
    type: str  # naive | seasonal_naive | auto_arima | timestral
    params: dict[str, Any] = field(default_factory=dict)
    # none | past | known_oracle   (known_oracle = realised future covariates, i.e. scenario-conditional)
    covariates: str = "none"


@dataclass
class EvalConfig:
    baseline: str = "arima"
    challenger: str = "timestral"
    mase_season: int = 1
    quantiles: list[float] = field(default_factory=lambda: [0.05, 0.1, 0.5, 0.9, 0.95])


@dataclass
class IdentityConfig:
    name: str
    total: str
    components: list[str]
    signs: list[float] | None = None


@dataclass
class PlotConfig:
    fan_series: list[str] = field(default_factory=list)
    fan_origins: list[str] = field(default_factory=list)
    stress_series: list[str] = field(default_factory=list)
    stress_origin: str | None = None
    # Optional "highlighted origins" analysis (e.g. rate-regime turning points).
    highlight_origins: list[str] = field(default_factory=list)
    highlight_series: list[str] = field(default_factory=list)
    highlight_models: list[str] = field(default_factory=list)
    spaghetti_series: list[str] = field(default_factory=list)
    spaghetti_models: list[str] = field(default_factory=list)
    # [model, reference] pairs for "how much does X help vs Y" bars.
    compare_pairs: list[list[str]] = field(default_factory=list)
    # {"columns": [...covariate names...], "maturities": [...years...]} to draw the curve at highlighted origins.
    yield_curve: dict = field(default_factory=dict)


@dataclass
class Config:
    name: str
    data: DataConfig
    backtest: BacktestConfig
    models: list[ModelConfig]
    evaluation: EvalConfig
    identities: list[IdentityConfig] = field(default_factory=list)
    plots: PlotConfig = field(default_factory=PlotConfig)
    output_dir: str = "reports"
    notes_file: str | None = None  # markdown prepended to REPORT.md (headline findings)

    @property
    def out(self) -> Path:
        return Path(self.output_dir)


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    models = []
    for m in raw.get("models", []):
        m = dict(m)
        name, typ = m.pop("name"), m.pop("type")
        cov = m.pop("covariates", "none")
        models.append(ModelConfig(name=name, type=typ, covariates=cov, params=m))
    return Config(
        name=raw.get("name", Path(path).stem),
        data=DataConfig(**raw["data"]),
        backtest=BacktestConfig(**raw.get("backtest", {})),
        models=models,
        evaluation=EvalConfig(**raw.get("evaluation", {})),
        identities=[IdentityConfig(**i) for i in raw.get("identities", [])],
        plots=PlotConfig(**raw.get("plots", {})),
        output_dir=raw.get("output_dir", f"reports/{raw.get('name', 'run')}"),
        notes_file=raw.get("notes_file"),
    )
