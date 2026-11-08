# olist-dq-kpi

**From Pipeline to Evidence: Data Quality in E-commerce Analytics.**
An analytics pipeline on the [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(Stage A) and a controlled experiment on how injected data errors distort business KPIs (Stage B).

Status: **Stage A and Stage B done (tag `v1.0-paper`)** — pipeline, 15 KPIs, 20 DQ checks and
dashboard (Stage A); error injection E1–E6, main and robustness grids, Online Retail II replication,
RQ1–RQ3 statistics, tables and figures (Stage B). Every table and figure of the paper is rebuilt by
`python -m dqk.analysis.make_all`.

![Dashboard, page 5: data quality](docs/figures/dashboard_5_data_quality.png)

## Setup

Requires Python 3.12 and internet access to kaggle.com on the first run.

```bash
git clone https://github.com/lini1907/-internship-.git olist-dq-kpi && cd olist-dq-kpi
python -m venv .venv
.venv\Scripts\activate              # Windows cmd / PowerShell
# source .venv/Scripts/activate     # Windows Git Bash
# source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt     # a few minutes: duckdb, pyarrow, pandas, scipy, matplotlib
pip install -e .
```

The dataset is public; no Kaggle API key is needed. It is downloaded on first use into
`data/raw/olist/`, and `data/raw/MANIFEST.json` records row counts and SHA-256 of each file.
Later runs stop with `ChecksumError` if the source files change.

## Run

```bash
python run_pipeline.py                       # download if missing -> raw -> DQ raw -> staging
                                             # -> DQ staging -> mart -> DQ mart -> KPI -> export
python run_pipeline.py --skip-download --no-export
```

The first run takes about 1.5 minutes including the download; later runs about 10 seconds
(measured on a laptop, 2026-11-08). Output:

- `warehouse/olist.duckdb` — schemas `raw`, `staging`, `mart`, `results`
- `results/stage_a/dq_results.csv`, `kpis_clean.csv`, `run_meta.json` (git commit, KPI spec hash, library versions)
- `exports/*.parquet`, `exports/*.csv` — mart tables, KPIs and DQ results for the dashboard (`docs/dashboard.md`)
- `docs/dq_catalogue.md` — check catalogue with the clean baseline

Exit code 1 if a check fails on the mart (`--allow-fail` to continue).

## Stage B: experiment

```bash
python run_experiment.py --grid config/grid_main.yaml --workers 8 --resume        # 65 cells x 200 seeds
python run_experiment.py --grid config/grid_robustness.yaml --workers 8 --resume  # 6 scenarios
python -m dqk.retail.adapter                                                      # Online Retail II mart
python run_experiment.py --grid config/grid_retail.yaml --workers 3 --resume      # 30 cells x 200 seeds
python -m dqk.analysis.make_all                                                   # all tables and figures
```

Each grid writes `results/runs/<grid>/<cell>.{kpi,dq,runs}.parquet` and `_meta.json` (git commit,
KPI spec hash, library versions). `--resume` skips finished cells; a pilot is
`--cell <cell_id> --seeds 5`. Measured wall time on a 12-thread laptop with 8 GB RAM: main grid
96 min (10 workers), robustness 2 h (10 workers), Online Retail II 67 min
(3 workers: each worker holds the 770k-line retail mart, 10 workers ran out of memory).
`make_all` takes a few minutes (`--n-boot 200` for a quick check) and writes:

- `results/tables/summary.md` — every result with its table; `paper_tables.md` — tables P1–P2 for the paper
- `results/tables/t*.csv` main grid, `r*.csv` robustness, `x*.csv` Online Retail II, `p*.csv` paper summary
- `results/figures/fig1`–`fig7` (PNG, 300 dpi, each with the CSV it is drawn from)

**Online Retail II** (UCI, CC BY 4.0) is loaded into the same mart schema as Olist (one invoice =
one delivered order, line revenue in `price`, StockCode in place of category, Country in place of
state), so the frozen KPI queries, DQ checks and injectors run unchanged. Which KPIs and checks apply,
and why the others do not: `src/dqk/retail/kpi_map.yaml`; cleaning rules with row counts:
`docs/retail_adapter.md`.

## Check that your build matches

A clean clone, set up as above, was tested on 2026-11-08: `python run_pipeline.py` exits 0,
`pytest` gives 60 passed, `python -m dqk.config check` prints "KPI spec matches lock", and
`results/stage_a/kpis_clean.csv` and `dq_results.csv` equal the reference build to 1e-9.
Quick check of your own build: mart DQ = 19 pass, 1 warn (C03), 0 fail; K1 GMV =
13,181,027.13 BRL; K2 delivered orders = 96,211 (more values in `docs/dashboard.md`).

## Dashboard

```bash
python -m dqk.powerbi          # writes powerbi/Olist.pbip with ExportsFolder = your exports folder
```

Open `powerbi/Olist.pbip` in Power BI Desktop (free) and press **Refresh**. Always run
`python -m dqk.powerbi` after cloning: the committed project points at the author's folder.
Screenshots of the five pages are in `docs/figures/dashboard_*.png` (PDF: `docs/figures/dashboard.pdf`).

## Other commands

| Command | Output |
|---|---|
| `python -m dqk.profiling` | `docs/profiling_report.md`, `docs/figures/*.png`, `results/stage_a/profiling.json` |
| `python -m dqk.config freeze` | `config/kpi_spec.lock` and `docs/kpi_spec.md` |
| `python -m dqk.config check` | exit 1 if `config/kpi_spec.yaml` or `sql/kpi/*.sql` changed since freeze |
| `python -m dqk.dq docs` | `docs/dq_catalogue.md` |
| `python -m dqk.powerbi` | `powerbi/Olist.pbip` — 5-page Power BI dashboard on `exports/` (`docs/dashboard.md`) |
| `python -m dqk.diagrams` | `docs/star_schema.png` |
| `python -m dqk.retail.adapter` | `warehouse/retail.duckdb`, `docs/retail_adapter.md` (downloads the UCI file on first run) |
| `python -m dqk.analysis.make_all` | `results/tables/*`, `results/figures/*` |
| `pytest` | all tests; `pytest -m "not slow"` skips the reconciliation on real data |

## Layout

```
run_pipeline.py         Stage A in one command
run_experiment.py       Stage B: run a grid of error-injection cells
config/grid_*.yaml      main grid, robustness scenarios, Online Retail II grid
config/kpi_spec.yaml    15 KPIs, parameters and the 5 decisions fixed before Stage B
config/kpi_spec.lock    SHA-256 of the spec and every sql/kpi file
config/dq_checks.yaml   20 checks: dimension, layers, warn/fail thresholds, reference row counts
config/category_translation_extra.csv   two category translations missing from the source
sql/staging/            one query per source table (casts, renames, one row per key)
sql/mart/               star schema: fact_orders, fact_order_items, dim_*
sql/kpi/                one query per KPI, returns (item, value, rank)
sql/dq/                 one query per check, returns (n_failed, n_total); {{table}} placeholders per layer
sql/retail/             Online Retail II staging and mart in the Olist schema
src/dqk/                io, db, tables, pipeline, kpis, dq, export, config, profiling, diagrams
src/dqk/inject/         E1-E6 injectors, unit sampling (MCAR / MAR / MNAR, nested rates)
src/dqk/experiment/     grid expansion, runner (parallel, resume), distortion and detection measures
src/dqk/analysis/       statistics (Friedman, Spearman + cluster bootstrap, Wilson), figures, make_all
src/dqk/retail/         Online Retail II adapter and kpi_map.yaml
docs/                   profiling report, KPI spec, DQ catalogue, cleaning log, dashboard spec, star schema
tests/                  KPI, DQ (planted errors), staging/mart rules, reconciliation against raw,
                        sampling, injectors, measures, Online Retail II adapter
```

## License

Code: MIT. Data outputs derived from Olist: CC BY-NC-SA 4.0, as the source data. Outputs derived
from Online Retail II (Chen, 2012, UCI Machine Learning Repository): CC BY 4.0.
