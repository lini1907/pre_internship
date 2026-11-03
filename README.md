# olist-dq-kpi

**From Pipeline to Evidence: Data Quality in E-commerce Analytics.**
An analytics pipeline on the [Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(Stage A) and a controlled experiment on how injected data errors distort business KPIs (Stage B).

Status: **week A1 done** — raw layer, profiling, frozen KPI spec, star schema.
Staging, mart, DQ checks and `run_pipeline.py` come in week A2.

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

## Commands (week A1)

| Command | Output |
|---|---|
| `python -m dqk.profiling` | downloads data if missing; `docs/profiling_report.md`, `docs/figures/*.png`, `results/stage_a/profiling.json` |
| `python -m dqk.config freeze` | `config/kpi_spec.lock` and `docs/kpi_spec.md` |
| `python -m dqk.config check` | exit 1 if `config/kpi_spec.yaml` or `sql/kpi/*.sql` changed since freeze |
| `python -m dqk.diagrams` | `docs/star_schema.png` |
| `pytest` | KPI tests on a hand-built mart, spec/lock and manifest tests |

## Layout

```
config/kpi_spec.yaml    15 KPIs, parameters and the 5 decisions fixed before Stage B
config/kpi_spec.lock    SHA-256 of the spec and every sql/kpi file
sql/kpi/                one query per KPI, returns (item, value, rank)
src/dqk/                io, db, tables, pipeline, kpis, config, profiling, diagrams
docs/                   profiling report, KPI spec, star schema
tests/
```

## License

Code: MIT. Data outputs derived from Olist: CC BY-NC-SA 4.0, as the source data.
