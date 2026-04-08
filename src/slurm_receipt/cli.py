"""CLI entry point for slurm-receipt."""

import argparse
import base64
import os
import sys
import time
import threading
import random
from datetime import datetime, timedelta

from slurm_receipt.sacct import fetch_jobs, compute_stats, generate_demo_jobs
from slurm_receipt.calc import energy, cloud_cost
from slurm_receipt.roast import generate_roasts
from slurm_receipt.tui import run_tui, render_snap


# ── Loading animation with live data preview ─────────────────────────

_SPINNER = ["|", "/", "-", "\\"]

# Fun facts shown during the sacct fetch (the slow part)
_FETCH_FACTS = [
    "The first Cray-1 (1976) had 8MB of RAM and cost $8M...",
    "The average HPC job spends 30% of its life in queue...",
    "'It works on my laptop' -- famous last words...",
    "Fun fact: sacct stores every job you've ever run...",
    "The scheduler sees all. The scheduler knows all...",
    "Somewhere, a sysadmin is reading your .err files...",
    "Did you know? 'seff' shows actual vs requested resources...",
    "Tip: shorter jobs get scheduled faster on Slurm...",
    "The first bug was an actual moth in a relay (1947)...",
    "60% of HPC jobs request 2x more memory than they use...",
    "sacct is basically your credit card statement...",
    "Each CPU core draws about 8 watts under load...",
    "An A100 GPU costs ~$15,000. You get to use it for free...",
    "The word 'queue' is just 'q' followed by 4 silent letters...",
    "Slurm was originally 'Simple Linux Utility for Resource Management'...",
    "Your .out files have been trying to tell you something...",
    "A lightning bolt has about 1,400 kWh of energy...",
    "The ISS uses 84 kW of solar power per orbit...",
    "Running 'squeue --me' 47 times won't make it go faster...",
    "NASA's Apollo computer had 74KB of memory. You requested 64GB...",
]


class _Loader:
    """Threaded spinner with live status updates and fun facts."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self._msg = ""
        self._detail = ""
        self._show_facts = False
        self._fact_interval = 3.0  # seconds between facts

    def _run(self):
        i = 0
        last_fact_time = time.time()
        fact_idx = random.randint(0, len(_FETCH_FACTS) - 1)
        current_fact = ""

        while not self._stop.is_set():
            frame = _SPINNER[i % 4]
            line = f"\r  {frame} {self._msg}"
            if self._detail:
                line += f"  ({self._detail})"
            # Pad to overwrite previous longer lines
            sys.stderr.write(f"{line:<72}")

            # Show rotating facts on a second line during fetch
            if self._show_facts:
                now = time.time()
                if now - last_fact_time > self._fact_interval:
                    fact_idx = (fact_idx + 1) % len(_FETCH_FACTS)
                    current_fact = _FETCH_FACTS[fact_idx]
                    last_fact_time = now
                if current_fact:
                    sys.stderr.write(f"\n    {current_fact:<68}\033[A")

            sys.stderr.flush()
            i += 1
            self._stop.wait(0.12)
        # Clear the lines
        if self._show_facts:
            sys.stderr.write(f"\r{' ':<72}\n{' ':<72}\r\033[A")
        else:
            sys.stderr.write(f"\r{' ':<72}\r")
        sys.stderr.flush()

    def start(self, msg, show_facts=False):
        self._msg = msg
        self._detail = ""
        self._show_facts = show_facts
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def detail(self, text):
        """Update the detail portion without changing the main message."""
        self._detail = text

    def stop(self, done_msg=None):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        if done_msg:
            sys.stderr.write(f"  + {done_msg}\n")
            sys.stderr.flush()


def _osc52_copy(text):
    """Copy to local clipboard via OSC 52. Handles tmux passthrough."""
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    # Check if inside tmux -- need to wrap in tmux passthrough
    if os.environ.get("TMUX"):
        # tmux requires DCS escape for passthrough to outer terminal
        sys.stdout.write(f"\033Ptmux;\033\033]52;c;{encoded}\a\033\\")
    else:
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
    parser.add_argument("--snap-file", type=str, default=None, metavar="PATH",
                        help="Save receipt to file")
    parser.add_argument("--no-copy", action="store_true",
                        help="Don't auto-copy to clipboard on snap")
    parser.add_argument("--uga", action="store_true",
                        help="Add UGA/Dawgs flavor to roasts")
    parser.add_argument("--demo", action="store_true",
                        help="Show demo receipt with synthetic data (no sacct needed)")

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
    loader = _Loader()

    # Phase 1: Fetch
    if args.demo:
        loader.start("Generating demo data...")
        jobs = generate_demo_jobs(days=days)
        user = user if user != "unknown" else "demo_user"
        loader.stop(f"Generated {len(jobs):,} demo jobs")
    else:
        loader.start(f"Fetching from sacct ({days} days)...", show_facts=True)
        jobs = fetch_jobs(user, start_date, end_date)

        if not jobs:
            loader.stop()
            sys.stderr.write("  No jobs found. The register is empty.\n\n")
            sys.exit(0)

        loader.stop(f"Found {len(jobs):,} jobs")

    # Phase 2: Compute
    loader.start("Crunching numbers...")
    stats = compute_stats(jobs)
    loader.detail(f"{stats['total_cpu_hours']:,.0f} core-hrs, {stats['failed']} failed")
    nrg = energy(stats)
    loader.detail(f"{nrg['total_kwh']:,.0f} kWh, {nrg['co2_kg']:,.0f} kg CO2")
    costs = cloud_cost(stats)
    loader.detail(f"${costs['total']:,.0f} on AWS")
    time.sleep(0.4)  # brief pause so user can read the last detail
    roasts = generate_roasts(stats, uga=args.uga)
    loader.stop("Receipt ready")

    # Phase 3: Output
    if args.snap or args.snap_file:
        text = render_snap(user, days, stats, nrg, costs, roasts)

        if args.snap_file:
            path = args.snap_file
        else:
            path = os.path.join(home_dir, f"slurm_receipt_{days}d.txt")
        with open(path, "w") as f:
            f.write(text)
        sys.stderr.write(f"  + Saved to {path}\n")

        if not args.no_copy:
            try:
                _osc52_copy(text)
                sys.stderr.write("  + Copied to clipboard (OSC 52)\n")
            except Exception:
                pass

        sys.stderr.write("\n")
        print(text)
        return

    # Phase 3b: TUI (run_tui will print save path on quit)
    sys.stderr.write("\n")
    run_tui(user, days, stats, nrg, costs, roasts)


if __name__ == "__main__":
    main()
