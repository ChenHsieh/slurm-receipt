"""CLI entry point for slurm-receipt."""

import argparse
import base64
import os
import sys
from datetime import datetime, timedelta

from slurm_receipt.sacct import fetch_jobs, compute_stats
from slurm_receipt.calc import energy, cloud_cost
from slurm_receipt.roast import generate_roasts
from slurm_receipt.tui import run_tui, render_snap


# ── Simple loading feedback (no threads, no memory overhead) ─────────

def _step(msg):
    sys.stderr.write(f"  - {msg}\n")
    sys.stderr.flush()


def _done(msg):
    sys.stderr.write(f"  + {msg}\n")
    sys.stderr.flush()


def _osc52_copy(text):
    """Copy to local clipboard via OSC 52 (works over SSH)."""
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    sys.stdout.write(f"\033]52;c;{encoded}\a")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        prog="slurm-receipt",
        description="See what your HPC compute really cost.",
    )
    parser.add_argument("--days", type=int, default=30,
                        help="Days to look back (default: 30)")
    parser.add_argument("--user", type=str, default=None,
                        help="Slurm username (default: $USER)")
    parser.add_argument("--start", type=str, default=None,
                        help="Start date YYYY-MM-DD (overrides --days)")
    parser.add_argument("--end", type=str, default=None,
                        help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--snap", action="store_true",
                        help="Print receipt + copy to clipboard (no TUI)")
    parser.add_argument("--snap-file", type=str, default=None,
                        help="Save receipt to file")
    parser.add_argument("--no-copy", action="store_true",
                        help="Don't auto-copy to clipboard on snap")

    args = parser.parse_args()

    user = args.user or os.environ.get("USER", "unknown")
    home_dir = os.path.expanduser("~")

    end_date = args.end or datetime.now().strftime("%Y-%m-%d")
    if args.start:
        start_date = args.start
        d1 = datetime.strptime(start_date, "%Y-%m-%d")
        d2 = datetime.strptime(end_date, "%Y-%m-%d")
        days = (d2 - d1).days
    else:
        days = args.days
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    sys.stderr.write("\n")

    # Phase 1: Fetch
    _step(f"Fetching your order from sacct ({days} days)...")
    jobs = fetch_jobs(user, start_date, end_date)

    if not jobs:
        sys.stderr.write("  No jobs found. The register is empty.\n\n")
        sys.exit(0)

    _done(f"Found {len(jobs):,} jobs")

    # Phase 2: Compute
    _step("Crunching the numbers...")
    stats = compute_stats(jobs)
    nrg = energy(stats)
    costs = cloud_cost(stats)
    roasts = generate_roasts(stats)
    _done("Receipt ready")

    # Phase 3: Output
    if args.snap or args.snap_file:
        text = render_snap(user, days, stats, nrg, costs, roasts)

        # Save to file
        if args.snap_file:
            path = args.snap_file
        else:
            path = os.path.join(home_dir, f"slurm_receipt_{days}d.txt")
        with open(path, "w") as f:
            f.write(text)
        _done(f"Saved to {path}")

        # Copy to clipboard via OSC 52
        if not args.no_copy:
            try:
                _osc52_copy(text)
                _done("Copied to clipboard (OSC 52)")
            except Exception:
                pass

        # Also print to stdout
        sys.stderr.write("\n")
        print(text)
        return

    # Phase 3b: TUI
    _step("Printing receipt...")
    sys.stderr.write("\n")
    run_tui(user, days, stats, nrg, costs, roasts)


if __name__ == "__main__":
    main()
