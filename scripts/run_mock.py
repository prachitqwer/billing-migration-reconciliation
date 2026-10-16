"""Run a mock cutover end to end: loader build -> load files -> reconciliation.

    python scripts/run_mock.py mock1
    python scripts/run_mock.py mock2
    python scripts/run_mock.py --profile        # data quality profiling only

Load files go to target/<run>/ (not committed, they are rebuilt in seconds).
Results go to results/<run>/.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from migration import loader  # noqa: E402
from recon import engine, workbook  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", nargs="?", choices=["mock1", "mock2"])
    ap.add_argument("--profile", action="store_true", help="run the data quality profile of the legacy extract")
    ap.add_argument("--keep-db", action="store_true", help="keep the SQLite working database in target/<run>/")
    args = ap.parse_args()

    if args.profile:
        facts = engine.profile(ROOT / "results" / "profiling")
        print(f"profiled {facts['total_rows']} legacy rows; failing rules: "
              + ", ".join(f"{k}={v}" for k, v in facts["dq"].items() if v))
        return 0
    if not args.run:
        ap.error("give a run (mock1 or mock2) or --profile")

    cfg = json.loads((ROOT / "config" / f"{args.run}.json").read_text(encoding="utf-8"))
    target = ROOT / "target" / args.run
    counts = loader.run(cfg["migration_build"], target)
    print(f"loader build {cfg['migration_build']}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))

    out = ROOT / "results" / args.run
    db = target / "recon.db" if args.keep_db else None
    summary = engine.reconcile(cfg, target, out, db)
    workbook.build(out, summary)
    print(f"{cfg['label']}: {summary['checks_passed']} of {summary['checks_total']} checks passed; "
          f"failed: {', '.join(summary['checks_failed']) or 'none'}; "
          f"no data: {', '.join(summary['checks_no_data']) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
