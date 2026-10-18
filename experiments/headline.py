"""Print headline numbers for a domain report: python experiments/headline.py reports/<domain>"""

import sys
from pathlib import Path

import pandas as pd

from bsforecast import metrics as M

d = Path(sys.argv[1])
t = d / "tables"
bt = pd.read_parquet(d / "backtest.parquet")
err = M.add_errors(bt)
err = err[~err.live]
base = pd.read_csv(t / "relative_mase.csv").query("rel_mase == 1.0").model.iloc[0]
H = int(err.h.max())
hs = sorted({1, max(1, H // 4), max(1, H // 2), H})
rel = M.relative_mase(err, base).set_index("model")["rel_mase"]
rh = M.relative_mase(err, base, by=["h"]).pivot(index="model", columns="h", values="rel_mase")[hs]
ov = pd.read_csv(t / "overall.csv").set_index("model")
tab = rh.assign(overall=rel, coverage80=ov["coverage80"], MASE=ov["MASE"]).sort_values("overall")
pd.set_option("display.width", 200)
print(f"baseline={base}  H={H}")
print(tab.round(3).to_string())
dm = pd.read_csv(t / "dm_all_models.csv")
print("\nDM share better/worse at 5% (h in", hs, ")")
print(dm[dm.h.isin(hs)].pivot(index="model", columns="h", values=["better", "worse"]).round(2).to_string())
print("\nrel MASE by id:")
ri = M.relative_mase(err, base, by=["id"]).pivot(index="id", columns="model", values="rel_mase")
print(ri.round(2).to_string())
if err.target.nunique() > 1:
    print("\nrel MASE by target:")
    rt = M.relative_mase(err, base, by=["target"]).pivot(index="target", columns="model", values="rel_mase")
    print(rt.round(2).to_string())
print("\nby slice MASE:")
print(pd.read_csv(t / "by_slice.csv").pivot(index="model", columns="slice", values="MASE").round(3).to_string())
