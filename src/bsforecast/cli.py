"""Command line interface.

python -m bsforecast fetch-y9c-top4          # build the top-4 BHC + macro panel
python -m bsforecast run --config configs/y9c_top4.yaml
python -m bsforecast report --config configs/y9c_top4.yaml   # re-plot from saved backtest
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from .backtest import run_backtest
from .config import load_config
from .dataset import load_panel
from .report import build_report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="bsforecast")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch-y9c-top4", help="download top-4 BHC data (FDIC fallback) + FRED macro")
    f.add_argument("--raw-dir", default="data/raw")
    f.add_argument("--out-dir", default="data/processed")
    g = sub.add_parser("fetch-macro-panel", help="granular top-4 BHC lines + CCAR-style macro panel")
    g.add_argument("--raw-dir", default="data/raw")
    g.add_argument("--out-dir", default="data/processed")
    for name in ("run", "report"):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True)
        p.add_argument("--models", nargs="*", help="subset of model names to run")
        p.add_argument("--shard", help="write backtest_<shard>.parquet (parallel runs); report merges all shards")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.cmd == "fetch-y9c-top4":
        from .data.build import build

        panel = build(Path(args.raw_dir), Path(args.out_dir))
        print(panel.groupby("bank")["date"].agg(["min", "max", "count"]))
        return

    if args.cmd == "fetch-macro-panel":
        from .data.granular import build_macro_panel

        panel = build_macro_panel(Path(args.raw_dir), Path(args.out_dir))
        print(panel.groupby("bank")["date"].agg(["min", "max", "count"]))
        return

    cfg = load_config(args.config)
    if args.models:
        cfg.models = [m for m in cfg.models if m.name in args.models]
    panel = load_panel(cfg.data)
    cfg.out.mkdir(parents=True, exist_ok=True)
    bt_path = cfg.out / "backtest.parquet"
    if args.cmd == "run":
        bt = run_backtest(cfg, panel)
        if args.shard:
            bt.to_parquet(cfg.out / f"backtest_{args.shard}.parquet", index=False)
            print(f"shard written: {cfg.out / f'backtest_{args.shard}.parquet'}")
            return
        if bt_path.exists() and args.models:  # merge partial re-runs
            old = pd.read_parquet(bt_path)
            bt = pd.concat([old[~old.model.isin(args.models)], bt], ignore_index=True)
        bt.to_parquet(bt_path, index=False)
    shards = sorted(cfg.out.glob("backtest_*.parquet"))
    if shards:  # merge parallel shards into the canonical backtest file
        parts = [pd.read_parquet(p) for p in shards]
        if bt_path.exists():
            old = pd.read_parquet(bt_path)
            new_models = set().union(*(set(p.model.unique()) for p in parts))
            parts.insert(0, old[~old.model.isin(new_models)])
        pd.concat(parts, ignore_index=True).to_parquet(bt_path, index=False)
        for p in shards:
            p.unlink()
    bt = pd.read_parquet(bt_path)
    if args.cmd == "report" and args.models:
        cfg.models = load_config(args.config).models
    s = build_report(cfg, panel, bt)
    for r in sorted(s["rel_mase"], key=lambda r: r["rel_mase"]):
        print(f"{r['model']:>22s}  rel MASE vs baseline = {r['rel_mase']:.3f}")
    print(f"report: {cfg.out / 'REPORT.md'}")


if __name__ == "__main__":
    main()
