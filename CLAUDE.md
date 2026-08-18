# CLAUDE.md — slurm-receipt technical onboarding

> This file is for AI agents working on this codebase. Read this first.

## What this is

A zero-dependency Python CLI that reads Slurm job history (`sacct`) and renders
an interactive terminal receipt showing compute costs, energy usage, AWS price
equivalents, fun real-world conversions, and data-driven roasts about the user's
job patterns. Think "Spotify Wrapped" for HPC users.

**Entry point:** `slurm-receipt` CLI → `src/slurm_receipt/cli.py:main()`

## File map (7 files, all in `src/slurm_receipt/`)

| File | Lines | Role |
|------|-------|------|
| `cli.py` | Entry point. Argparse, pipeline (fetch jobs → fetch fair share → compute → output), threaded loading spinner with fun facts |
| `sacct.py` | Data layer. Calls `sacct -X --parsable2`, stream-parses output into job dicts, aggregates into stats dict. Also has `generate_demo_jobs()` for `--demo` mode |
| `fairshare.py` | Priority data layer. Calls `sshare`/`sacctmgr`, scoped to the user's own account only (never an unscoped `sshare -a`). Returns self row + own-account leaderboard. Has `generate_demo_fairshare()` for `--demo` mode |
| `calc.py` | Pure math. Energy (kWh from CPU/GPU TDP), AWS cost estimates, 37 fun conversions (food/energy/transport/etc.), ASCII mascot tiers (6 tiers by CPU-hours) |
| `roast.py` | Humor engine. ~25 roast triggers across failure rates, night owl patterns, cancellations, GPU usage, etc. Returns `[{"text": str, "context": dict_or_None}]` |
| `tui.py` | curses TUI. 7 pages (receipt/activity/monthly/roast/line/top/fairshare), keyboard+mouse navigation, clipboard copy (OSC52 → tmux buffer → xclip fallback), auto-save on entry |
| `__init__.py` | Just `__version__ = "0.1.0"` |

## Data flow

```
CLI args (--days, --user, --demo, --uga, --snap)
    │
    ▼
sacct.fetch_jobs()          ← subprocess.Popen, stream parse, -X flag
    │ returns: list[dict] with keys:
    │   job_id, name, partition, cpus, mem_gb, gpu_type,
    │   gpu_count, elapsed_sec, state, submit_dt
    ▼
sacct.compute_stats()       ← single-pass aggregation over all jobs
    │ returns: dict with ~30 keys including:
    │   total_jobs, completed, failed, cancelled, timeout
    │   total_cpu_hours, total_gpu_hours, gpu_hours_by_type
    │   total_mem_gb_hours, total_wall_hours, partitions
    │   top_jobs_cpu (top 10), fastest_fails (capped 500), slowest_fails (top 5)
    │   array_bursts, busiest_day, longest_job
    │   daily (date→count), daily_failed (date→count), daily_cpu_hours (date→float)
    │   monthly (month→{jobs,completed,...})
    │   submissions_by_hour, submissions_by_dow
    │   night_submissions, weekend_submissions, short_completed, single_core_jobs
    │   first_submit, last_submit (actual data date range)
    ▼
calc.energy(stats)          ← CPU_WATTS=8W/core, GPU TDP per type, PUE=1.3, CO2=0.4 kg/kWh
calc.cloud_cost(stats)      ← AWS on-demand 2026 pricing
roast.generate_roasts(stats, uga=False)
    │ returns: list of {"text": str, "context": {"job_id","name","detail"} or None}
    │ Selection: top 5 by priority (3=high,1=low) + optional 1 UGA + 1 closer
    ▼
OUTPUT: either render_snap() → stdout  OR  run_tui() → curses

fairshare.fetch_fairshare_data(user)   ← runs alongside the pipeline above, independent of sacct
    │ sacctmgr show user ... → default account
    │ sshare -U -u $USER              → self row only
    │ sshare -A <account> -a          → own-account members only (never unscoped `sshare -a`)
    │ returns: {"account": str, "self": row, "leaderboard": [row, ...], "rank": int}
    │   where row = {account, user, raw_shares, norm_shares, raw_usage,
    │                effectv_usage, fairshare}
    │ Returns None if sshare/sacctmgr unavailable -- the fairshare page/key is then hidden
```

## Key architecture decisions

### Roast system
- Each roast is a `{"text": str, "context": dict_or_None}` dict, not a plain string
- `context` powers the mini POS receipt panel shown below each roast in the TUI
- ~25 trigger conditions, most with multiple threshold tiers so even light users get roasts
- Priority 3 = must-show (>50% failure), priority 1 = filler (partition loyalty)
- Top 5 data-driven selected, then optionally +1 UGA (if `--uga`), then +1 closer
- TUI builds extra roasts via `generate_roasts()` x4 for rotation pool, deduped by text

### TUI rendering model
- All pages return `list[tuple[str, str]]` where tuple = `(text, attr_name)`
- `attr_name` is one of: title, heading, dim, highlight, normal, roast, conversion, bar
- Renderer centers content at width W=52 (receipt aesthetic), scrollable
- Mouse support: scroll wheel + status bar click detection via `_click_in()`
- State: `page`, `scroll`, `conv_idx`, `roast_idx`

### Clipboard chain (tui.py)
1. OSC 52 written to `/dev/tty` (bypasses curses, works over SSH)
2. `tmux load-buffer -` via subprocess (reliable in tmux, paste with prefix+])
3. xclip / xsel / wl-copy subprocess fallback
4. Returns description string of what worked, or `""` on total failure

### sacct performance
- `-X` flag = allocations only (skips batch/extern substeps, 50-75% less output)
- No `--state` filter (some Slurm versions reject unknown state codes like `SE`)
- Stream parse via `Popen` + line iteration (constant memory)
- `fastest_fails` capped at 500 entries during collection

### Demo mode
- `--demo` generates 200 synthetic bioinformatics jobs via `generate_demo_jobs()`
- No sacct needed — works on any machine with Python 3.8+

## Stats dict schema (output of compute_stats)

```python
{
    "total_jobs": int,
    "completed": int, "failed": int, "cancelled": int, "timeout": int, "other": int,
    "total_cpu_hours": float, "total_gpu_hours": float,
    "gpu_hours_by_type": {"a100": float, "l4": float, ...},
    "total_mem_gb_hours": float, "total_wall_hours": float,
    "partitions": {"batch": int, "gpu_p": int, ...},
    "top_jobs_cpu": [(name, cpu_hrs, job_id), ...],  # top 10
    "fastest_fails": [job_dict, ...],    # <10s failures, max 500
    "slowest_fails": [job_dict, ...],    # >1h failures, top 5
    "array_bursts": [(minute_key, count), ...],  # >10/min, top 5
    "busiest_day": {"date": "YYYY-MM-DD", "count": int} | None,
    "longest_job": job_dict | None,
    "short_completed": int,       # completed in <60s
    "single_core_jobs": int,      # cpus <= 1
    "night_submissions": int,     # 10pm-6am
    "weekend_submissions": int,   # Sat/Sun
    "submissions_by_hour": {0: int, 1: int, ..., 23: int},
    "submissions_by_dow": {0: int, ..., 6: int},  # 0=Mon
    "first_submit": datetime | None,
    "last_submit": datetime | None,
    "daily": {"YYYY-MM-DD": int, ...},
    "daily_failed": {"YYYY-MM-DD": int, ...},
    "daily_cpu_hours": {"YYYY-MM-DD": float, ...},
    "monthly": {"YYYY-MM": {"jobs":int, "completed":int, "failed":int, "cpu_hours":float, ...}, ...},
}
```

## Conversion system (calc.py)

37 conversions in `CONVERSIONS` list. Each is a dict:
```python
{"id": str, "icon": str(3-4 chars), "label": str, "tagline": str,
 "kwh_per": float | "co2_per": float | "mem_gb_per": float,
 "source": str, "category": str}
```
Categories: food, energy, transport, home, entertainment, scale, memory, environment.
`convert()` dispatches on which `*_per` key is present.

## Mascot system (calc.py)

`MASCOT_TIERS`: 6 tiers by CPU-hours threshold (100, 1K, 10K, 50K, 200K, inf).
Each tier has 4 ASCII art options. Picked by `hash(username) % len(options)` for
per-user consistency. Returns `{"art": [str, ...], "title": str}`.

## TUI pages

| Page | Builder | Key | Content |
|------|---------|-----|---------|
| receipt | `build_receipt_page()` | default | Mascot, order summary, compute charges, energy, AWS cost, rotatable conversion |
| activity | `build_heatmap_page()` | `h` | Weekly bars, day-of-week bars, time-of-day bars, stats (streak, peak, quietest) |
| monthly | `build_monthly_page()` | `m` | Per-month table with bars, peak month callout |
| roast | `build_roast_page()` | `r` | One roast at a time, mini POS panel for job context, rotatable with <> |
| line | `build_linechart_page()` | `l` | Daily trend line chart (block chars ▁▂▃▄▅▆▇█), 7-day moving avg, switchable layers (jobs/fails/cpu-hrs via tab) |
| top | `build_top_jobs_page()` | `t` | Top 10 CPU hogs, speedrun hall of shame (<10s fails), slow+painful fails |
| fairshare | `build_fairshare_page()` | `f` (hidden if no fairshare data) | FairShare score + bar, effective usage %, own-account leaderboard ranked by effective usage share |

## CLI flags

| Flag | Effect |
|------|--------|
| `--days N` | Look back N days (default 30) |
| `--user U` | Query different user's jobs |
| `--start/--end` | Explicit date range |
| `--snap` | Print plain text to stdout + save to ~/slurm_receipt_Nd.txt |
| `--snap-file PATH` | Save to specific path |
| `--no-copy` | Skip clipboard on --snap |
| `--uga` | Add UGA Bulldogs themed roasts |
| `--demo` | Synthetic data, no sacct needed |

## Known limitations / future work

- No caching — every run re-queries sacct (the `-X` flag helps but large ranges are still slow)
- Fair share leaderboard is scoped to the user's own Slurm account only, by design — never
  an unscoped `sshare -a`, which would dump every lab's usage on the cluster. A cluster-wide
  leaderboard was considered and deliberately not built for this reason.
- `fairshare.py`'s "RawUsage" is Slurm's internal decayed usage metric, not literal CPU-hours
  or seconds — the UI intentionally never labels it as a time unit, only shows it via the
  normalized `EffectvUsage` percentage, which is well-defined (share of account total).
- OSC 52 clipboard is fire-and-forget — can't confirm it worked
- Color 8 (gray/dim) requires 16-color terminal support
- No Windows support (curses, /dev/tty, sacct all absent)
- No test suite yet
- sacct `--parsable2` uses `|` delimiter — job names containing `|` would break parsing (rare but possible)
- `_fmt_time()` is duplicated in roast.py and tui.py with slightly different formats

## Build & publish

```bash
pip install build twine
python -m build          # creates dist/slurm_receipt-0.1.0-py3-none-any.whl
twine upload dist/*      # publish to PyPI
```

Build system: hatchling. Entry point: `slurm-receipt = "slurm_receipt.cli:main"`.
Wheel packages from `src/slurm_receipt/`. Zero runtime dependencies.
