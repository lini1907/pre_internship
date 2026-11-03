"""Load and validate the YAML configuration; freeze the KPI spec.

Usage:
    python -m dqk.config freeze   # write config/kpi_spec.lock and docs/kpi_spec.md
    python -m dqk.config check    # exit 1 if the spec changed since it was frozen
    python -m dqk.config docs     # regenerate docs/kpi_spec.md only
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

from dqk import CONFIG_DIR, DOCS_DIR, ROOT, SQL_DIR

KPI_SPEC = CONFIG_DIR / "kpi_spec.yaml"
KPI_LOCK = CONFIG_DIR / "kpi_spec.lock"

KpiType = Literal[
    "monetary", "count", "ratio", "rate", "duration", "score", "ranking", "series", "decision"
]


class AltDefinition(BaseModel):
    id: str
    sql: str
    population: str | None = None
    rule: str | None = None


class Kpi(BaseModel):
    id: str
    name: str
    type: KpiType
    sql: str
    population: str
    rule: str
    unit: str | None = None
    top_k: int | None = None
    alt_definitions: list[AltDefinition] = []

    @model_validator(mode="after")
    def _ranking_needs_top_k(self):
        if self.type == "ranking" and not self.top_k:
            raise ValueError(f"{self.id}: ranking KPI needs top_k")
        return self


class Decision(BaseModel):
    id: int
    topic: str
    choice: str


class KpiParams(BaseModel):
    window_start: date
    window_end: date
    min_reviews: int
    unknown_label: str


class KpiSpec(BaseModel):
    version: int
    params: KpiParams
    decisions: list[Decision]
    populations: dict[str, str]
    kpis: list[Kpi]

    @model_validator(mode="after")
    def _check(self):
        ids = [k.id for k in self.kpis]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate KPI id")
        for path in self.sql_files():
            if not (SQL_DIR / path).exists():
                raise ValueError(f"missing SQL file: sql/{path}")
        return self

    def sql_files(self) -> list[str]:
        files = [k.sql for k in self.kpis]
        files += [a.sql for k in self.kpis for a in k.alt_definitions]
        return files


def load_kpi_spec(path: Path = KPI_SPEC) -> KpiSpec:
    return KpiSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spec_hashes(spec_path: Path = KPI_SPEC) -> dict[str, str]:
    """SHA-256 of kpi_spec.yaml and of every file in sql/kpi/, keyed by repo path."""
    files = [spec_path, *sorted((SQL_DIR / "kpi").glob("*.sql"))]
    return {p.relative_to(ROOT).as_posix(): _sha256(p) for p in files}


def _combined(hashes: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def freeze(lock: Path = KPI_LOCK) -> dict:
    load_kpi_spec()  # refuse to freeze an invalid spec
    hashes = spec_hashes()
    payload = {
        "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "spec_hash": _combined(hashes),
        "files": hashes,
    }
    lock.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def check_lock(lock: Path = KPI_LOCK) -> list[str]:
    """Return the files whose hash differs from the lock (added, removed or changed)."""
    frozen = json.loads(lock.read_text(encoding="utf-8"))["files"]
    current = spec_hashes()
    return sorted(f for f in frozen.keys() | current.keys() if frozen.get(f) != current.get(f))


def render_kpi_doc(spec: KpiSpec) -> str:
    p = spec.params
    out = [
        "# KPI specification",
        "",
        "Generated from `config/kpi_spec.yaml` by `python -m dqk.config docs`. Do not edit.",
        "",
        f"Spec version {spec.version}. Window: purchase_ts in [{p.window_start}, {p.window_end}). "
        f"K15 minimum reviews: {p.min_reviews}. Unmatched label: `'{p.unknown_label}'`.",
        "",
        "## Decisions fixed before Stage B",
        "",
    ]
    out += [f"{d.id}. **{d.topic}.** {d.choice}" for d in spec.decisions]
    out += ["", "## Populations", ""]
    out += [f"- `{k}`: {v}" for k, v in spec.populations.items()]
    out += [
        "",
        "## KPIs",
        "",
        "| ID | Name | Type | Population | Rule | SQL |",
        "|---|---|---|---|---|---|",
    ]
    for k in spec.kpis:
        name = k.name + (f" (top {k.top_k})" if k.top_k else "")
        out.append(f"| {k.id} | {name} | {k.type} | {k.population} | {k.rule} | `sql/{k.sql}` |")
    alts = [(k.id, a) for k in spec.kpis for a in k.alt_definitions]
    if alts:
        out += ["", "## Alternative definitions (robustness only)", ""]
        out += [f"- **{a.id}** (for {kid}): {a.rule} — `sql/{a.sql}`" for kid, a in alts]
    out.append("")
    return "\n".join(out)


def write_kpi_doc() -> Path:
    path = DOCS_DIR / "kpi_spec.md"
    path.write_text(render_kpi_doc(load_kpi_spec()), encoding="utf-8")
    return path


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "check"
    if cmd == "freeze":
        payload = freeze()
        write_kpi_doc()
        print(f"Frozen {len(payload['files'])} files, spec_hash {payload['spec_hash'][:12]}")
    elif cmd == "docs":
        print(f"Wrote {write_kpi_doc()}")
    elif cmd == "check":
        changed = check_lock()
        if changed:
            print("KPI spec changed since freeze:\n  " + "\n  ".join(changed))
            return 1
        print("KPI spec matches lock")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
