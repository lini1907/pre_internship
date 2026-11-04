"""The generated Power BI project is internally consistent: every field a visual uses
exists in the model, and every file is UTF-8 without BOM (Power BI rejects a BOM)."""

import json

from dqk import powerbi


def _fields(node):
    if isinstance(node, dict):
        for kind in ("Column", "Measure"):
            if kind in node and "Property" in node[kind]:
                yield kind, node[kind]["Expression"]["SourceRef"]["Entity"], node[kind]["Property"]
        for v in node.values():
            yield from _fields(v)
    elif isinstance(node, list):
        for v in node:
            yield from _fields(v)


def test_project_files_and_references(tmp_path):
    pbip = powerbi.write_project(tmp_path, tmp_path / "exports")
    assert pbip.exists()
    model = tmp_path / "Olist.SemanticModel" / "definition"
    assert {p.stem for p in (model / "tables").glob("*.tmdl")} == set(powerbi.COLUMNS)

    columns = {(t, c) for t, cols in powerbi.COLUMNS.items() for c, _, _ in cols}
    measures = {(t, m) for t, ms in powerbi.MEASURES.items() for m, _, _ in ms}
    visuals = list((tmp_path / "Olist.Report").rglob("visual.json"))
    assert len(visuals) == sum(len(v) for _, _, v in powerbi.pages())
    for path in visuals:
        for kind, table, name in _fields(json.loads(path.read_text("utf-8"))):
            assert (table, name) in (columns if kind == "Column" else measures), (path, name)

    pages = json.loads((tmp_path / "Olist.Report/definition/pages/pages.json").read_text("utf-8"))
    assert len(pages["pageOrder"]) == 5

    for p in tmp_path.rglob("*"):
        if p.is_file():
            assert not p.read_bytes().startswith(b"\xef\xbb\xbf"), p


def test_m_lists_use_braces(tmp_path):
    powerbi.write_project(tmp_path, tmp_path / "exports")
    text = (tmp_path / "Olist.SemanticModel/definition/tables/dim_seller.tmdl").read_text("utf-8")
    assert 'Table.SelectColumns(Source, {"seller_id", "state"})' in text
