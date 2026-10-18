"""Static, mobile-friendly HTML site over every experiment report: ``python -m bsforecast site``.

Renders reports/<exp>/REPORT.md (findings are already prepended) plus the per-group spaghetti pages into
docs/<slug>/index.html, copies figures as downscaled JPEGs, and writes a landing page with a cross-domain summary.
Plain HTML/CSS, no build step, no extra dependencies.
"""

from __future__ import annotations

import html
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import metrics as M


@dataclass
class Exp:
    slug: str
    title: str
    domain: str
    config: str
    takeaway: str
    note: str = ""


EXPERIMENTS = [
    Exp("y9c_top4", "Top-4 banks: aggregate lines", "Banks", "configs/y9c_top4.yaml",
        "Timestral roughly ties AutoARIMA over 8 quarters; wins 1-3 quarters ahead, strongest on NII/NIM.",
        "FDIC call-report aggregation (Y-9C substitute)."),
    Exp("term_structure", "Banks: Treasury curve as known covariate", "Banks", "configs/term_structure.yaml",
        "Knowing the future yield curve halves interest-expense error (0.51 vs ARIMA)."),
    Exp("macro_panel", "Banks: 37 granular lines x 22-variable macro panel", "Banks", "configs/macro_panel.yaml",
        "Macro helps rate/credit lines (interest expense, provisions) but hurts balance-sheet volumes."),
    Exp("electricity", "Electricity demand + temperature (EIA-930)", "Energy", "experiments/electricity/config.yaml",
        "Plain Timestral beats MSTL by 23%; known temperature cuts error a further ~45% (0.41), gain grows with horizon."),
    Exp("inflation", "Inflation components", "Macro", "experiments/inflation/config.yaml",
        "Timestral beats ARIMA ~11% on core; a known oil path does most of the work (0.66 with macro, energy ~0.4)."),
    Exp("credit_losses", "Credit losses by loan type", "Credit", "experiments/credit_losses/config.yaml",
        "Timestral ~15% better than ARIMA (joint 0.81); known macro hurts (COVID: unemployment up, charge-offs down)."),
    Exp("treasury_curve", "Treasury yield curve", "Rates", "experiments/treasury_curve/config.yaml",
        "Timestral beats the random walk at the short end (0.94); a known fed funds path cuts error 61% (0.39)."),
    Exp("earnings", "Company earnings (SEC XBRL)", "Corporates", "experiments/earnings/config.yaml",
        "Timestral beats ARIMA by ~11% (best on net income/EPS); known macro hurts except cyclicals."),
    Exp("housing_fhfa", "Housing: FHFA metro HPI", "Housing", "experiments/housing/fhfa.yaml",
        "Timestral ~20% better than ARIMA at 8 quarters, with calibrated bands; macro adds little."),
    Exp("housing_zillow", "Housing: Zillow values + rents", "Housing", "experiments/housing/zillow.yaml",
        "Timestral 11-13% better than ETS over 24 months; rents gain more than values.", "AutoARIMA dropped."),
    Exp("retail_census", "Retail: Census sales by category", "Retail", "experiments/retail/census.yaml",
        "Timestral ~9% better than ETS; known macro 0.80, driven by gasoline (future pump price).",
        "AutoARIMA dropped."),
    Exp("retail_m5", "Retail: M5 Walmart store x dept", "Retail", "experiments/retail/m5.yaml",
        "See findings.", "AutoARIMA dropped."),
]  # fmt: skip

CSS = """
*{box-sizing:border-box}body{font:16px/1.5 -apple-system,system-ui,Segoe UI,Roboto,sans-serif;margin:0;color:#1b1f24;
background:#fafbfc}main{max-width:1100px;margin:auto;padding:16px}h1{font-size:1.6em}h2{margin-top:1.6em;border-bottom:1px
solid #ddd}h3{margin-top:1.2em}a{color:#0b62c4}nav{background:#0d1b2a;padding:10px 16px}nav a{color:#fff;margin-right:14px;
text-decoration:none;font-weight:600}.tbl{overflow-x:auto;margin:8px 0}table{border-collapse:collapse;font-size:.88em;
min-width:50%}td,th{border:1px solid #d0d7de;padding:4px 8px;text-align:right;white-space:nowrap}th{background:#eef1f4}
td:first-child,th:first-child{text-align:left}img{max-width:100%;height:auto;border:1px solid #e1e4e8;border-radius:4px;
background:#fff}.caveat{background:#fff8e1;border-left:4px solid #f0b400;padding:8px 14px;margin:12px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}.card{background:#fff;border:1px
solid #d0d7de;border-radius:8px;padding:12px}.card h3{margin:0 0 6px}.muted{color:#57606a;font-size:.9em}
code{background:#eef1f4;padding:1px 4px;border-radius:3px}
"""


def _inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", s)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)


def md_to_html(md: str, img: callable) -> str:
    """Minimal markdown: headings, pipe tables, images, bullet lists, paragraphs."""
    out, lines, i = [], md.splitlines(), 0
    para: list[str] = []

    def flush():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        ln = lines[i].rstrip()
        m_img = re.fullmatch(r"!\[[^\]]*\]\(([^)]+)\)", ln.strip())
        if m_img:
            flush()
            src = img(m_img.group(1))
            if src:
                out.append(f'<p><a href="{src}"><img loading="lazy" src="{src}" alt=""></a></p>')
        elif ln.startswith("#"):
            flush()
            n = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{min(n + 1, 4)}>{_inline(ln[n:].strip())}</h{min(n + 1, 4)}>")
        elif ln.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            i -= 1
            if rows:
                head = "".join(f"<th>{_inline(c)}</th>" for c in rows[0])
                body = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
                out.append(f'<div class="tbl"><table><tr>{head}</tr>{body}</table></div>')
        elif re.match(r"^\s*[-*] ", ln):
            flush()
            items = []
            while i < len(lines) and (re.match(r"^\s*[-*] ", lines[i]) or (lines[i].startswith("  ") and items)):
                t = lines[i].strip()
                if re.match(r"^[-*] ", t):
                    items.append(t[2:])
                else:
                    items[-1] += " " + t
                i += 1
            i -= 1
            out.append("<ul>" + "".join(f"<li>{_inline(t)}</li>" for t in items) + "</ul>")
        elif not ln.strip():
            flush()
        else:
            para.append(ln.strip())
        i += 1
    flush()
    return "\n".join(out)


def _page(title: str, body: str, root: str = "") -> str:
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style></head>'
        f'<body><nav><a href="{root}index.html">Timestral experiments</a></nav><main>{body}</main></body></html>'
    )


class ImageStore:
    """Copies report PNGs into docs/ as downscaled JPEGs (keeps the site small)."""

    def __init__(self, docs: Path, max_w: int = 1800, quality: int = 80):
        self.docs, self.max_w, self.quality = docs, max_w, quality

    def put(self, src: Path, dest_rel: str) -> str | None:
        from PIL import Image

        if not src.exists():
            return None
        dest = (self.docs / dest_rel).with_suffix(".jpg")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
            im = Image.open(src).convert("RGB")
            if im.width > self.max_w:
                im = im.resize((self.max_w, int(im.height * self.max_w / im.width)), Image.LANCZOS)
            im.save(dest, "JPEG", quality=self.quality, optimize=True)
        return str(dest.relative_to(self.docs))


def _summary_row(e: Exp, root: Path) -> dict | None:
    from .config import load_config

    cfg = load_config(root / e.config)
    bt_path = root / cfg.output_dir / "backtest.parquet"
    if not bt_path.exists():
        return None
    base = cfg.evaluation.baseline
    bt = pd.read_parquet(bt_path)
    err = M.add_errors(bt)
    rel = M.relative_mase(err, base).set_index("model")["rel_mase"]
    plain = rel.get("timestral", float("nan"))
    known = rel[[m for m in rel.index if "timestral" in m and "known" in m]]
    best_known = (known.idxmin(), known.min()) if len(known) else ("", float("nan"))
    cov = M.summarize(err, ["model"]).set_index("model")["coverage80"]
    return {
        "slug": e.slug,
        "Experiment": e.title,
        "Domain": e.domain,
        "Baseline": base,
        "H": int(bt.h.max()),
        "Timestral (no inputs)": plain,
        "Best known-covariate variant": best_known[0],
        "Timestral + known": best_known[1],
        "Best model": rel.idxmin(),
        "cov_plain": cov.get("timestral", float("nan")),
        "Takeaway": e.takeaway,
        "Note": e.note,
    }


def summary_chart(rows: pd.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    d = rows.iloc[::-1]
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(9, 0.48 * len(d) + 1.6))
    ax.axvline(1, color="k", lw=1)
    ax.scatter(d["Timestral (no inputs)"], y, s=60, color="tab:blue", label="Timestral, no covariates", zorder=3)
    ax.scatter(
        d["Timestral + known"],
        y,
        s=60,
        marker="D",
        color="tab:purple",
        label="Timestral + best known-future covariates",
        zorder=3,
    )
    for yy, a, b in zip(y, d["Timestral (no inputs)"], d["Timestral + known"], strict=True):
        if np.isfinite(a) and np.isfinite(b):
            ax.plot([a, b], [yy, yy], color="grey", lw=1, zorder=2)
    ax.set_yticks(y, [f"{t}  (vs {b})" for t, b in zip(d["Experiment"], d["Baseline"], strict=True)], fontsize=8)
    ax.set_xlabel("Relative MASE vs the experiment's baseline (<1 = Timestral better)")
    ax.set_title("Timestral-209M zero-shot across domains (one-shot multi-step)", fontsize=11)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2, frameon=False)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def _f(x) -> str:
    return "-" if pd.isna(x) else f"{x:.3f}"


def build_site(root: Path = Path("."), docs: Path = Path("docs")) -> dict:
    from .config import load_config

    root, docs = Path(root), Path(docs)
    docs.mkdir(parents=True, exist_ok=True)
    (docs / ".nojekyll").write_text("")
    store = ImageStore(docs)
    rows, built = [], []
    for e in EXPERIMENTS:
        cfg = load_config(root / e.config)
        rep = root / cfg.output_dir
        if not (rep / "REPORT.md").exists():
            continue
        r = _summary_row(e, root)
        if r:
            rows.append(r)
        used: set[str] = set()

        def img(rel: str, base: Path = rep, e=e, used=used) -> str | None:
            src = (base / rel).resolve()
            used.add(str(src))
            rr = base.resolve()
            out = store.put(src, f"{e.slug}/img/{src.relative_to(rr) if src.is_relative_to(rr) else src.name}")
            return out[len(e.slug) + 1 :] if out else None

        parts = [f"<h1>{html.escape(e.title)}</h1>"]
        if e.note:
            parts.append(f'<div class="caveat">{_inline(e.note)}</div>')
        if r:
            parts.append(
                f'<p class="muted">Baseline <code>{r["Baseline"]}</code>, horizon {r["H"]} steps. '
                f"Relative MASE: Timestral {_f(r['Timestral (no inputs)'])}, best known-covariate variant "
                f"<code>{r['Best known-covariate variant'] or '-'}</code> {_f(r['Timestral + known'])}.</p>"
            )
        if e.slug.startswith("housing"):
            live = root / "reports/housing/figures/live_tampa.png"
            src = store.put(live, f"{e.slug}/img/live_tampa.png")
            if src:
                parts.append("<h2>Live Tampa forecast (latest data, macro held flat)</h2>")
                parts.append(
                    f'<p><a href="{src[len(e.slug) + 1 :]}"><img src="{src[len(e.slug) + 1 :]}" alt=""></a></p>'
                )
        parts.append(md_to_html((rep / "REPORT.md").read_text(), img))
        for idx in sorted((rep / "figures").glob("*/index.md")):
            gdir = idx.parent
            parts.append(f"<h2>Spaghetti grids: {html.escape(gdir.name)}</h2>")
            parts.append(
                md_to_html(
                    idx.read_text().split("\n", 1)[-1], lambda rel, g=gdir, r0=rep: img(str((g / rel).relative_to(r0)))
                )
            )
        extra = sorted(p for p in (rep / "figures").rglob("*.png") if str(p.resolve()) not in used)
        if extra:
            parts.append("<h2>Other plots</h2>")
            for p in extra:
                s = img(str(p.relative_to(rep)))
                if s:
                    parts.append(
                        f'<h3>{html.escape(p.stem)}</h3><p><a href="{s}"><img loading="lazy" src="{s}" alt=""></a></p>'
                    )
        (docs / e.slug).mkdir(parents=True, exist_ok=True)
        (docs / e.slug / "index.html").write_text(_page(e.title, "\n".join(parts), root="../"))
        built.append(e.slug)

    tab = pd.DataFrame(rows)
    chart = docs / "summary_relmase.png"
    if len(tab):
        summary_chart(tab, chart)
        shutil.copy(chart, root / "reports" / "summary_relmase.png")
        tab.drop(columns=["slug"]).to_csv(docs / "summary.csv", index=False)
    trs = "".join(
        f'<tr><td><a href="{r.slug}/index.html">{html.escape(r.Experiment)}</a></td><td>{r.Domain}</td>'
        f"<td>{r.Baseline}</td><td>{r.H}</td><td>{_f(r['Timestral (no inputs)'])}</td><td>{_f(r['Timestral + known'])}"
        f'<br><span class="muted">{r["Best known-covariate variant"]}</span></td>'
        f'<td style="text-align:left;white-space:normal">{html.escape(r.Takeaway)}</td></tr>'
        for _, r in tab.iterrows()
    )
    caveats = """<div class="caveat"><strong>Caveats.</strong><ul>
<li><strong>Known-future covariates are scenario tests:</strong> models were given the <em>realised</em> path of the
covariates (rates, macro, weather, prices) over the forecast window. That measures how well a model follows a given
scenario, not real-time accuracy.</li>
<li><strong>AutoARIMA dropped</strong> where seasonal ARIMA was too slow on the shared machine: Zillow, Census retail,
M5 (and electricity uses MSTL). Those experiments use AutoETS / seasonal naive / MSTL as the baseline, so relative
MASE is not comparable 1:1 across rows.</li>
<li><strong>Banks:</strong> FR Y-9C downloads are CAPTCHA-blocked, so bank data are FDIC call reports of each holding
company's bank subsidiaries (nonbank subsidiaries missing; totals run low, especially for Citi and BofA).</li>
<li><strong>Timestral-209M weights license</strong> (Modified MIT): free use only for companies under $20M/month
revenue; larger companies need a commercial license from Mistral. Code is Apache-2.0.</li>
<li>Relative MASE = geometric mean over series of model MASE / baseline MASE; &lt;1 means better than the baseline.</li>
</ul></div>"""
    body = f"""<h1>Timestral-209M forecasting experiments</h1>
<p>Zero-shot <a href="https://huggingface.co/mistralai/Timestral-209M">Timestral-209M</a> vs classical baselines,
one-shot multi-step forecasts from many rolling origins, across {len(built)} experiments. Code:
<a href="https://github.com/gustavorubim/timestral-bank-forecasting">github.com/gustavorubim/timestral-bank-forecasting</a>.</p>
{caveats}
<h2>Cross-domain summary</h2>
<p><a href="summary_relmase.png"><img src="summary_relmase.png" alt="summary chart"></a></p>
<div class="tbl"><table><tr><th>Experiment</th><th>Domain</th><th>Baseline</th><th>H</th><th>Timestral, no inputs</th>
<th>Timestral + best known</th><th>Takeaway</th></tr>{trs}</table></div>
<p class="muted">Data: <a href="summary.csv">summary.csv</a>. Each page: findings, headline tables, spaghetti grids
(every origin's median path, colour = origin date, black = actual), error by horizon, heatmaps, coverage, DM tests.</p>
<h2>Experiments</h2><div class="cards">{"".join(f'<div class="card"><h3><a href="{s}/index.html">{html.escape(e.title)}</a></h3><div class="muted">{e.domain}</div></div>' for e in EXPERIMENTS for s in [e.slug] if s in built)}</div>
"""
    (docs / "index.html").write_text(_page("Timestral-209M experiments", body))
    size = sum(p.stat().st_size for p in docs.rglob("*") if p.is_file())
    return {"pages": built, "rows": tab, "size_mb": size / 1e6, "chart": chart}
