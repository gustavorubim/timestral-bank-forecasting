"""Fixed-parameter NY Fed DSGE (Model1002 ss104) rolling-origin forecasts for the macro horse race.

Run with the *nydsge-python* environment (never Econer's working tree), e.g.::

    cd /workspace/nydsge-horse && uv run python \
        /workspace/timestral-bank-forecasting/experiments/macro_horse/dsge_runner.py \
        --nydsge /workspace/nydsge-horse --out data/processed/macro_horse/dsge_forecasts.csv

Design (see reports/macro_horse/REPORT.md):
* Parameters: the DSGE.jl ss104 published-code defaults that nydsge's
  ``scripts/forecast_ss104_nyfed_params.py`` uses. No estimation at any origin.
* At each origin T the transformed observables are rebuilt from the 2026-10-06 FRED/public
  snapshot truncated at T (so the HP-filtered population trend only sees data up to T),
  Kalman-filtered/smoothed on 1959Q3..T, then forecast T+1..T+8 unconditionally.
* Regime path over the forecast window, two variants:
    - ``dsge``        (headline) freeze the regime in force at T. A forecaster at T could not know
                       the COVID-era regime schedule that ss104 installs from 2020Q1 on.
    - ``dsge_sched``  use ss104's dated regime schedule (ex-post knowledge of COVID regimes for
                       origins whose window crosses 2020Q1+; identical to ``dsge`` before 2018Q1).
* The report's headline ``dsge`` series = ``dsge`` for origins < 2020Q1 and ``dsge_sched`` from 2020Q1
  (freezing a one-quarter COVID shock-variance regime for 8 quarters gives absurd densities).
* Density: closed-form Gaussian. P_{T+h} = T P T' + R Q R' along the regime path from the final
  filtered covariance (parameter uncertainty excluded); Var(y) = Z P Z' + EE.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

TARGETS = {  # model observable -> (target name, scale to annualised percent)
    "obs_gdp": ("gdp", 4.0),
    "obs_corepce": ("corepce", 4.0),
    "obs_gdpdeflator": ("gdpdef", 4.0),
    "obs_nominalrate": ("ffr", 4.0),
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nydsge", type=Path, default=Path("/workspace/nydsge-horse"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--first", default="2005Q1")
    ap.add_argument("--last", default="2024Q2")
    ap.add_argument("--horizon", type=int, default=8)
    args = ap.parse_args()
    root = args.nydsge.resolve()
    if root == Path("/workspace/nydsge").resolve():
        raise SystemExit("Refusing to run inside Econer's working tree /workspace/nydsge.")
    sys.path.insert(0, str(root / "scripts"))
    from nydsge.kalman import (  # noqa: PLC0415
        kalman_log_likelihood,
        model_process_covariances,
        model_shock_covariance,
    )
    from nydsge.models import Model1002  # noqa: PLC0415
    from nydsge.regimes import regime_indices_from_dates  # noqa: PLC0415
    from nydsge.solve import compute_system  # noqa: PLC0415
    from ss104_local import FRED_SNAPSHOT, build_local_data  # noqa: PLC0415

    levels = pd.read_csv(FRED_SNAPSHOT)
    levels.index = pd.PeriodIndex(levels.date.str.replace("-Q", "Q"), freq="Q")
    rgdp_growth = 100 * np.log(levels.GDP / levels.GDPDEF).diff()

    rows = []
    h = args.horizon
    origins = pd.period_range(args.first, args.last, freq="Q")
    t0 = time.time()
    for k, origin in enumerate(origins):
        fstart = origin + 1
        model = Model1002(
            "ss104",
            settings={
                "data_vintage": "261006",
                "date_presample_start": "1959-Q3",
                "date_mainsample_start": "1960-Q1",
                "date_forecast_start": f"{fstart.year}-Q{fstart.quarter}",
            },
        )
        system = compute_system(model)
        data = build_local_data(model, end=f"{origin.year}-Q{origin.quarter}")
        data = data.loc[:origin]
        obs = data.loc[:, list(model.observables)].to_numpy(dtype=float)
        rdates = model.get_setting("regime_dates")
        idx = regime_indices_from_dates(rdates, data.index)
        presample = int((data.index < pd.Period("1960Q1", freq="Q")).sum())
        filt = kalman_log_likelihood(
            system,
            obs,
            regime_indices=idx,
            log_likelihood_start=presample,
            process_covariances=model_process_covariances(
                model, system, len(data), start_date=data.index[0]
            ),
        )
        s = np.asarray(filt.filtered_states[-1], dtype=float)
        p = np.asarray(filt.filtered_covariances[-1], dtype=float)
        pop_q = float(rgdp_growth.loc[origin] - data.loc[origin, "obs_gdp"])
        names = list(model.observables)
        fut = pd.period_range(fstart, periods=h, freq="Q")
        paths = {
            "dsge": np.full(h, idx[-1]),
            "dsge_sched": regime_indices_from_dates(rdates, fut),
        }
        for variant, path in paths.items():
            if variant == "dsge_sched" and np.array_equal(path, paths["dsge"]):
                pass  # identical; still written so both variants cover every origin
            systems = system.period_systems(path, h)
            st, pc = s.copy(), p.copy()
            for i, act in enumerate(systems):
                tr, ms = act.transition, act.measurement
                qq = model_shock_covariance(model, act, date=fut[i])
                st = tr.TTT @ st + tr.CCC
                pc = tr.TTT @ pc @ tr.TTT.T + tr.RRR @ qq @ tr.RRR.T
                y = ms.ZZ @ st + ms.DD
                vy = ms.ZZ @ pc @ ms.ZZ.T + ms.EE
                for obs_name, (tgt, sc) in TARGETS.items():
                    j = names.index(obs_name)
                    mean = y[j] + (pop_q if obs_name == "obs_gdp" else 0.0)
                    rows.append(
                        {
                            "model": variant,
                            "origin": str(origin),
                            "target": tgt,
                            "h": i + 1,
                            "mean": sc * mean,
                            "sd": sc * float(np.sqrt(max(vy[j, j], 0.0))),
                            "regime_T": int(idx[-1]),
                            "regime_h": int(path[i]),
                        }
                    )
        print(f"[{k + 1}/{len(origins)}] {origin} regime={idx[-1]} {time.time() - t0:.0f}s", flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.out, index=False)
    print("wrote", args.out, len(rows))


if __name__ == "__main__":
    main()
