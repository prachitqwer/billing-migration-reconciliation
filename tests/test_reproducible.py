"""The committed extract, results and mapping documents are exactly what the
scripts produce. If any of these fail, re-run the scripts and commit the output."""

from __future__ import annotations

import filecmp
import importlib.util
from pathlib import Path

from conftest import ROOT, read_csv


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_regenerates_identically(tmp_path):
    gen = _load_script("generate_legacy_extract")
    gen.main(tmp_path)
    for f in sorted((ROOT / "data" / "legacy_extract").glob("*.csv")):
        assert filecmp.cmp(f, tmp_path / f.name, shallow=False), f.name


def test_committed_results_are_current(runs):
    for run_id in ("profiling", "mock1", "mock2"):
        fresh = runs[run_id] if run_id == "profiling" else runs[run_id].folder
        committed = ROOT / "results" / run_id
        for name in sorted(p.name for p in committed.glob("*.csv")) + ["summary.json" if run_id != "profiling" else "profile_facts.json"]:
            assert filecmp.cmp(committed / name, fresh / name, shallow=False), f"results/{run_id}/{name} is stale"


def test_mapping_document_matches_its_csv(tmp_path, monkeypatch):
    build = _load_script("build_mapping_spec")
    spec = build._read(build.SPEC)
    assert build.build_markdown(spec) == (ROOT / "docs" / "03_source_to_target_mapping.md").read_text(encoding="utf-8")


def test_every_target_column_has_a_mapping(runs):
    spec = read_csv(ROOT / "config" / "mapping_spec.csv")
    mapped = {(r["target_table"], r["target_field"]) for r in spec}
    target = Path(runs["mock2"].folder).parent / "target" / "mock2"
    for table in ("customers", "subscriptions", "invoices", "credit_notes", "payments"):
        header = (target / f"{table}.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
        for column in header:
            assert (table, column) in mapped, f"{table}.{column} has no mapping row"
