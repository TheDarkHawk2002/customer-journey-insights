from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(prog="journey-insights", description="Analyze a customer journey event CSV.")
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="validate events and write funnel/cohort reports")
    analyze.add_argument("--input", type=Path, required=True, help="source CSV (read only)")
    analyze.add_argument("--output-dir", type=Path, required=True, help="directory for generated reports")
    args = parser.parse_args()
    try:
        result = run(args.input, args.output_dir)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    summary = result["summary"]
    print(f"Accepted {summary['accepted_events']} events for {summary['unique_customers']} customers.")
    print(f"Completed orders: {summary['orders']} | revenue: €{summary['revenue_eur']}")
    print(f"Quality findings: {result['findings']} | reports: {result['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
