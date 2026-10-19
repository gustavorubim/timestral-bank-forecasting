# Notes for in-flight branches

## Repo layout changed (branch `reorg-folders`, merged to `main` 2026-10-18)

- `configs/<name>.yaml` -> `experiments/<name>/config.yaml` (y9c_top4, term_structure, macro_panel).
- `reports/<name>/` -> `outputs/<name>/` for every experiment (backtests, tables, figures, REPORT.md).
- Findings narratives (`notes_file`) -> `studies/<name>.md`; index in `studies/README.md`.
- One-off runner scripts -> `experiments/_runners/` (they `cd` to the repo root); old session logs ->
  `experiments/_session_notes/`.
- `Config.output_dir` now defaults to `outputs/<name>`. `docs/` is still the GitHub Pages site; slugs unchanged.

## For the `macro-horse-race` worker

When you rebase onto `main`, move your paths to match:

- configs/scripts: `experiments/macro_horse/` (already the right place)
- results: `reports/macro_horse/` -> **`outputs/macro_horse/`** (set `output_dir: outputs/macro_horse` in the config)
- write-up: add `studies/macro_horse.md` and a row in `studies/README.md`; optionally an `Exp(...)` entry in
  `src/bsforecast/site.py` so it shows up on the Pages site.
