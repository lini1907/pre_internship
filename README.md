# olist-dq-kpi

**From Pipeline to Evidence: Data Quality in E-commerce Analytics.**
An analytics pipeline on the [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(Stage A) and a controlled experiment on how injected data errors distort business KPIs (Stage B).

Status: **week A2 done** — staging, mart, 15 KPIs, 20 DQ checks, `run_pipeline.py`,
exports for the dashboard, Stage A tests. Stage B (error injection) starts in week B1.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
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

About 10 seconds once the data is downloaded. Output:

- `warehouse/olist.duckdb` — schemas `raw`, `staging`, `mart`, `results`
- `results/stage_a/dq_results.csv`, `kpis_clean.csv`, `run_meta.json` (git commit, KPI spec hash, library versions)
- `exports/*.parquet`, `exports/*.csv` — mart tables, KPIs and DQ results for the dashboard (`docs/dashboard.md`)
- `docs/dq_catalogue.md` — check catalogue with the clean baseline

Exit code 1 if a check fails on the mart (`--allow-fail` to continue).

## Other commands

| Command | Output |
|---|---|
| `python -m dqk.profiling` | `docs/profiling_report.md`, `docs/figures/*.png`, `results/stage_a/profiling.json` |
| `python -m dqk.config freeze` | `config/kpi_spec.lock` and `docs/kpi_spec.md` |
| `python -m dqk.config check` | exit 1 if `config/kpi_spec.yaml` or `sql/kpi/*.sql` changed since freeze |
| `python -m dqk.dq docs` | `docs/dq_catalogue.md` |
| `python -m dqk.powerbi` | `powerbi/Olist.pbip` — 5-page Power BI dashboard on `exports/` (`docs/dashboard.md`) |
| `python -m dqk.diagrams` | `docs/star_schema.png` |
| `pytest` | all tests; `pytest -m "not slow"` skips the reconciliation on real data |

## Layout

```
run_pipeline.py         Stage A in one command
config/kpi_spec.yaml    15 KPIs, parameters and the 5 decisions fixed before Stage B
config/kpi_spec.lock    SHA-256 of the spec and every sql/kpi file
config/dq_checks.yaml   20 checks: dimension, layers, warn/fail thresholds, reference row counts
config/category_translation_extra.csv   two category translations missing from the source
sql/staging/            one query per source table (casts, renames, one row per key)
sql/mart/               star schema: fact_orders, fact_order_items, dim_*
sql/kpi/                one query per KPI, returns (item, value, rank)
sql/dq/                 one query per check, returns (n_failed, n_total); {{table}} placeholders per layer
src/dqk/                io, db, tables, pipeline, kpis, dq, export, config, profiling, diagrams
docs/                   profiling report, KPI spec, DQ catalogue, cleaning log, dashboard spec, star schema
tests/                  KPI, DQ (planted errors), staging/mart rules, reconciliation against raw
```

## License

Code: MIT. Data outputs derived from Olist: CC BY-NC-SA 4.0, as the source data.
