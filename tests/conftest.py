"""Shared fixtures: the profile and both mocks are run once per test session
into a temporary folder, so the tests never depend on stale files."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from migration import loader  # noqa: E402
from recon import engine  # noqa: E402


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Run:
    def __init__(self, folder: Path):
        self.folder = folder
        self.summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        self.checks = {r["check_id"]: r for r in read_csv(folder / "checks.csv")}
        self.fields = {f"{r['entity']}.{r['field']}": int(r["mismatches"]) for r in read_csv(folder / "l3_field_summary.csv")}
        self.bridge = {r["entity"]: {k: (int(v) if k != "entity" else v) for k, v in r.items()}
                       for r in read_csv(folder / "l1_bridge.csv")}

    def result(self, check_id: str) -> str:
        return self.checks[check_id]["result"]

    def failures(self, check_id: str) -> int:
        return int(self.checks[check_id]["failures"])


@pytest.fixture(scope="session")
def runs(tmp_path_factory) -> dict:
    base = tmp_path_factory.mktemp("runs")
    engine.profile(base / "profiling")
    out = {"profiling": base / "profiling"}
    for run_id in ("mock1", "mock2"):
        cfg = json.loads((ROOT / "config" / f"{run_id}.json").read_text(encoding="utf-8"))
        target = base / "target" / run_id
        loader.run(cfg["migration_build"], target)
        engine.reconcile(cfg, target, base / run_id)
        out[run_id] = Run(base / run_id)
    return out


@pytest.fixture(scope="session")
def mock1(runs) -> Run:
    return runs["mock1"]


@pytest.fixture(scope="session")
def mock2(runs) -> Run:
    return runs["mock2"]


@pytest.fixture(scope="session")
def profile_facts(runs) -> dict:
    return json.loads((runs["profiling"] / "profile_facts.json").read_text(encoding="utf-8"))
