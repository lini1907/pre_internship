"""Data contracts for the raw layer (code plan v1.1, M3).

    python -m dqk.contracts          # validate data/olist against contracts/*.yaml

validate_contract(raw, contract) reports, per raw table of a contract:
  missing_column   a declared column is absent (error if required, else warning)
  extra_column     a column the contract does not declare (warning)
  unparseable      share of non-empty values that do not cast to the declared logicalType
                   above slaProperties.max_unparseable_share (error)
  missing_table    the table is absent (error)
run_pipeline.py stops before staging when any error is found (unless --no-contracts).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from dqk import ROOT
from dqk.tables import Tables

CONTRACTS_DIR = ROOT / "contracts"
DUCK_TYPES = {
    "integer": "BIGINT",
    "number": "DOUBLE",
    "timestamp": "TIMESTAMP",
    "date": "DATE",
    "boolean": "BOOLEAN",
}


@dataclass(frozen=True)
class Violation:
    contract: str
    table: str
    column: str | None
    kind: str
    severity: str
    detail: str

    def __str__(self) -> str:
        col = f".{self.column}" if self.column else ""
        return f"[{self.severity}] {self.contract}: {self.table}{col} {self.kind} - {self.detail}"


def load_contracts(folder: Path = CONTRACTS_DIR) -> list[dict]:
    return [
        yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.yaml"))
    ]


def _max_bad(contract: dict) -> float:
    for p in contract.get("slaProperties", []):
        if p.get("property") == "max_unparseable_share":
            return float(p["value"])
    return 0.0


def unparseable_share(values: pd.Series, logical_type: str) -> float:
    """Share of non-empty values that TRY_CAST cannot turn into the declared type."""
    duck = DUCK_TYPES.get(logical_type)
    if duck is None:
        return 0.0
    df = pd.DataFrame({"v": values.astype("string")})
    con = duckdb.connect()
    con.register("t", df)
    n, bad = con.execute(
        f"SELECT count(*) FILTER (WHERE v IS NOT NULL AND trim(v) <> ''), "
        f"count(*) FILTER (WHERE v IS NOT NULL AND trim(v) <> '' "
        f"AND TRY_CAST(v AS {duck}) IS NULL) FROM t"
    ).fetchone()
    con.close()
    return bad / n if n else 0.0


def validate_contract(raw: Tables, contract: dict) -> list[Violation]:
    out: list[Violation] = []
    cid = contract["id"]
    max_bad = _max_bad(contract)
    for obj in contract["schema"]:
        table = obj["name"]
        if table not in raw.names():
            out.append(Violation(cid, table, None, "missing_table", "error", "table not loaded"))
            continue
        df = raw[table]
        declared = [p["name"] for p in obj["properties"]]
        for p in obj["properties"]:
            col = p["name"]
            if col not in df.columns:
                sev = "error" if p.get("required") else "warning"
                out.append(Violation(cid, table, col, "missing_column", sev, "column absent"))
                continue
            share = unparseable_share(df[col], p.get("logicalType", "string"))
            if share > max_bad:
                out.append(
                    Violation(
                        cid, table, col, "unparseable", "error",
                        f"{share:.2%} of values are not {p['logicalType']} "
                        f"(max {max_bad:.2%})",
                    )
                )
        for col in df.columns:
            if col not in declared:
                out.append(
                    Violation(cid, table, col, "extra_column", "warning", "not in the contract")
                )
    return out


def validate_all(raw: Tables, contracts: list[dict] | None = None) -> list[Violation]:
    contracts = load_contracts() if contracts is None else contracts
    return [v for c in contracts for v in validate_contract(raw, c)]


class ContractError(RuntimeError):
    pass


def enforce(raw: Tables, contracts: list[dict] | None = None, echo=print) -> list[Violation]:
    """Validate and raise ContractError on any error-level violation."""
    vs = validate_all(raw, contracts)
    for v in vs:
        echo(str(v))
    errors = [v for v in vs if v.severity == "error"]
    if errors:
        raise ContractError(f"{len(errors)} contract violation(s): " + "; ".join(map(str, errors)))
    return vs


if __name__ == "__main__":
    from dqk.io import OLIST_DIR
    from dqk.pipeline import load_raw

    try:
        vs = enforce(load_raw(OLIST_DIR))
    except ContractError as e:
        print(e)
        sys.exit(1)
    print(f"contracts OK ({len(load_contracts())} contracts, {len(vs)} warning(s))")
