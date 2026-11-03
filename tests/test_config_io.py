import json

import pytest

from dqk import config, io
from dqk.config import load_kpi_spec


def test_spec_has_15_kpis_and_5_decisions():
    spec = load_kpi_spec()
    assert [k.id for k in spec.kpis] == [f"K{i}" for i in range(1, 16)]
    assert [d.id for d in spec.decisions] == [1, 2, 3, 4, 5]


def test_lock_detects_change(tmp_path, monkeypatch):
    lock = tmp_path / "kpi_spec.lock"
    config.freeze(lock)
    assert config.check_lock(lock) == []
    # Simulate an edit to one KPI query without touching the real file.
    real = config._sha256
    monkeypatch.setattr(
        config, "_sha256", lambda p: "edited" if p.name == "k05_on_time_rate.sql" else real(p)
    )
    assert config.check_lock(lock) == ["sql/kpi/k05_on_time_rate.sql"]


def test_repo_lock_matches_current_spec():
    assert config.KPI_LOCK.exists(), "run: python -m dqk.config freeze"
    assert config.check_lock() == []


def test_manifest_roundtrip(tmp_path, monkeypatch):
    src = tmp_path / "olist"
    src.mkdir()
    files = {"t1": "a.csv", "t2": "b.csv"}
    for f in files.values():
        (src / f).write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    monkeypatch.setattr(io, "OLIST_FILES", files)
    manifest = tmp_path / "MANIFEST.json"
    m = io.write_manifest(src, manifest)
    assert m["t1"]["rows"] == 2
    assert json.loads(manifest.read_text())["t2"]["sha256"] == io.sha256(src / "b.csv")
    io.verify_manifest(src, manifest)
    (src / "a.csv").write_text("x,y\n9,9\n", encoding="utf-8")
    with pytest.raises(io.ChecksumError, match="t1"):
        io.verify_manifest(src, manifest)
