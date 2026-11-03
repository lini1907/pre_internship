"""Download the Olist dataset, record a checksum manifest and read the raw CSV files."""

from __future__ import annotations

import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

import duckdb

from dqk import DATA_DIR

OLIST_URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"
OLIST_DIR = DATA_DIR / "raw" / "olist"
MANIFEST = DATA_DIR / "raw" / "MANIFEST.json"

# Raw table name -> source file. geolocation is not used (section 3.1).
OLIST_FILES: dict[str, str] = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "product_category_name_translation": "product_category_name_translation.csv",
}


class ChecksumError(RuntimeError):
    """The source files differ from the ones recorded in MANIFEST.json."""


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def download_olist(dest: Path = OLIST_DIR, url: str = OLIST_URL) -> Path:
    """Fetch and unzip the dataset. Does nothing if every needed file is present."""
    dest.mkdir(parents=True, exist_ok=True)
    if all((dest / f).exists() for f in OLIST_FILES.values()):
        return dest
    archive = dest.parent / "olist.zip"
    if not archive.exists():
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, archive)
    with zipfile.ZipFile(archive) as z:
        for name in OLIST_FILES.values():
            z.extract(name, dest)
    return dest


def _count_rows(path: Path) -> int:
    with duckdb.connect() as con:
        return con.execute(
            f"SELECT count(*) FROM read_csv('{path.as_posix()}', all_varchar=true)"
        ).fetchone()[0]


def build_manifest(src: Path = OLIST_DIR) -> dict:
    return {
        table: {"file": fname, "rows": _count_rows(src / fname), "sha256": sha256(src / fname)}
        for table, fname in OLIST_FILES.items()
    }


def write_manifest(src: Path = OLIST_DIR, out: Path = MANIFEST) -> dict:
    manifest = build_manifest(src)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def verify_manifest(src: Path = OLIST_DIR, manifest: Path = MANIFEST) -> None:
    """Raise ChecksumError if any source file changed since the manifest was written."""
    expected = json.loads(manifest.read_text(encoding="utf-8"))
    bad = [t for t, meta in expected.items() if sha256(src / meta["file"]) != meta["sha256"]]
    if bad:
        raise ChecksumError(f"Source data changed for: {', '.join(bad)}")


def ensure_olist(src: Path = OLIST_DIR, manifest: Path = MANIFEST) -> Path:
    """Download if needed, then write the manifest on first run or verify it afterwards."""
    download_olist(src)
    if manifest.exists():
        verify_manifest(src, manifest)
    else:
        write_manifest(src, manifest)
    return src
