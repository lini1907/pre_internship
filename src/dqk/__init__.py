"""Data quality and KPI reliability on the Olist e-commerce dataset."""

from pathlib import Path

__version__ = "0.1.0"

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
SQL_DIR = ROOT / "sql"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
RESULTS_DIR = ROOT / "results"
