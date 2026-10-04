"""ShiftLens CLI — run as: ../.venv/bin/python -m shiftlens.cli <cmd>

Subcommands (DESIGN.md):
  simulate          generate the deterministic dataset (data/)
  report [--date D] write per-worker daily reports (out/daily_reports/)
  monthly           compute monthly analytics (out/monthly.json)
  demo              simulate -> report -> monthly, print findings summary
  serve             FastAPI dashboard (imports shiftlens.dashboard lazily)

Data/output dirs default to ./data and ./out and can be overridden with
SHIFTLENS_DATA_DIR / SHIFTLENS_OUT_DIR (used by the smoke test).
"""
from __future__ import annotations

import argparse
import sys

from shiftlens import data_dir, out_dir


def _cmd_simulate(_args) -> int:
    from shiftlens.sensors import simulate
    info = simulate.run(data_dir())
    print(f"Simulated {info['days']} days x {info['workers']} workers "
          f"from {info['start']} (seed 42) -> {data_dir()}")
    return 0


def _cmd_report(args) -> int:
    from shiftlens.agent import report
    try:
        n = report.run(data_dir(), out_dir(), date=args.date)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    scope = args.date or "all dates"
    print(f"Wrote {n} daily reports ({scope}) -> {out_dir() / 'daily_reports'}")
    return 0


def _cmd_monthly(_args) -> int:
    from shiftlens.analytics import monthly
    try:
        result = monthly.run(data_dir(), out_dir())
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Monthly analytics for {result['period']} -> "
          f"{out_dir() / 'monthly.json'} "
          f"({len(result['correlations'])} correlations, "
          f"{len(result['findings'])} findings)")
    return 0


def _cmd_demo(_args) -> int:
    from shiftlens.agent import report
    from shiftlens.analytics import monthly
    from shiftlens.sensors import simulate

    info = simulate.run(data_dir())
    n_reports = report.run(data_dir(), out_dir())
    result = monthly.run(data_dir(), out_dir())

    print("=== ShiftLens demo ===")
    print(f"  simulate: {info['days']} days x {info['workers']} workers "
          f"from {info['start']} (seed 42)")
    print(f"  report:   {n_reports} daily reports -> "
          f"{out_dir() / 'daily_reports'}")
    print(f"  monthly:  {out_dir() / 'monthly.json'}")
    print()
    print("Correlations (all worker-days):")
    for c in result["correlations"]:
        print(f"  {c['x']:>12} <-> {c['y']:<11} r = {c['r']:+.2f} "
              f"(n={c['n']}) — {c['insight']}")
    print()
    print("Findings:")
    for i, f in enumerate(result["findings"], 1):
        print(f"  {i}. {f}")
    return 0


def _cmd_serve(_args) -> int:
    try:
        from shiftlens.dashboard import server  # lazy: optional component
    except ImportError as exc:
        print(f"error: dashboard unavailable ({exc})", file=sys.stderr)
        return 1
    server.main()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shiftlens", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("simulate", help="generate the deterministic dataset")

    p_report = sub.add_parser("report", help="write per-worker daily reports")
    p_report.add_argument("--date", metavar="YYYY-MM-DD", default=None,
                          help="only this date (default: all dates)")

    sub.add_parser("monthly", help="compute monthly analytics")
    sub.add_parser("demo", help="simulate -> report -> monthly, print findings")
    sub.add_parser("serve", help="serve the dashboard (FastAPI, port 8200+)")

    args = parser.parse_args(argv)
    handlers = {
        "simulate": _cmd_simulate,
        "report": _cmd_report,
        "monthly": _cmd_monthly,
        "demo": _cmd_demo,
        "serve": _cmd_serve,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
