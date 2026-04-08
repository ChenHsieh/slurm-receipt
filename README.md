# slurm-receipt

**See what your HPC compute really cost -- in dollars, energy, and burgers.**

A terminal tool that reads your Slurm job history and generates an interactive
receipt with compute usage, cloud cost equivalents, and fun real-world
conversions you can rotate through. It also roasts you about your failed jobs.

```
  _______________
 |  ___________  |
 | |  SLURM's  | |
 | |  GENERAL  | |
 | |   STORE   | |
 | | >[O]  [O] | |
 | |    ====   | |
 | |___________| |
 |_____[  ]______|
  || |      | ||
  || '------' ||
```

## Install

```bash
# With pipx (recommended -- isolated install, works anywhere)
pipx install slurm-receipt

# Or with pip
pip install slurm-receipt

# Or just clone and run
git clone https://github.com/YOUR_USER/slurm-receipt.git
cd slurm-receipt
pip install -e .
```

## Usage

```bash
# Interactive receipt (last 30 days)
slurm-receipt

# Last year
slurm-receipt --days 365

# Print plain text (for copy-paste / screenshot sharing)
slurm-receipt --snap --days 365

# Save to file for sharing
slurm-receipt --snap-file my_receipt.txt --days 365

# Custom date range
slurm-receipt --start 2025-01-01 --end 2025-12-31

# Check a labmate (if sacct permits)
slurm-receipt --user labmate
```

## Interactive mode

The TUI is keyboard-driven:

| Key | Action |
|-----|--------|
| `<` / `>` | Rotate through fun conversions |
| `r` | View your performance roast |
| `m` | Monthly breakdown |
| `t` | Top jobs + failure hall of shame |
| `s` | Snap -- save plain text to /tmp |
| `j` / `k` | Scroll up/down |
| `q` | Quit |

## What you see

**Order summary** -- jobs submitted, completed, failed, with a success rate bar.

**Compute charges** -- CPU core-hours, GPU-hours (by type), memory, wall time.

**Energy & CO2** -- estimated kWh and kg CO2 based on hardware TDP with PUE overhead.

**Cloud price check** -- what this would cost on AWS and GCP at on-demand rates.

**Fun conversions** (35+ and growing) -- rotate through one at a time:
- Food: burgers, cakes, ramen, espresso, toast, pizza, popcorn, rice
- Energy: phone charges, laptop charges, AA batteries, lightning bolts
- Transport: Tesla miles, e-bike miles, transatlantic flights
- Home: laundry loads, showers, houses powered, fridge days, vacuuming
- Entertainment: Netflix hours, gaming hours, vinyl albums
- Scale: ISS orbits, Bitcoin transactions, ChatGPT queries, Google searches, MRI scans
- Memory: novels in RAM, photos, human genomes, full Wikipedias
- Environment: trees to offset, CO2 balloons, cans of soda

**Roasts** -- context-aware commentary about your job history:
- Failure rate analysis
- "Speedrun failures" (jobs that died in <10 seconds)
- "Slow painful deaths" (jobs that ran for hours then failed)
- Array job spam detection
- Scavenge partition habits
- Dark academia closing quotes

**Monthly ledger** -- jobs and CPU-hours per month with ASCII bar chart.

**Top jobs** -- your hungriest jobs by CPU-hours, plus the failure hall of shame.

## Mascot

The shop mascot changes based on your compute usage:

| CPU-hours | Mascot | Shop name |
|-----------|--------|-----------|
| < 100 | Lil' Batch | Corner Compute Shop |
| 100 - 5K | Receipt Printer | Slurm's Compute Kitchen |
| 5K - 50K | General Store | Slurm's General Store |
| > 50K | Mega Depot | Slurm Mega Compute Depot |

## Sharing

The `--snap` output is designed to look good when:
- Copy-pasted into Slack/Discord (use a code block)
- Screenshotted from your terminal
- Saved as a .txt file and shared

No HTML, no browser, no dependencies beyond Python 3.8+ and `sacct`.

## How estimates work

| Component | Method |
|-----------|--------|
| CPU energy | core-hours x 150W TDP / 1000 |
| GPU energy | GPU-hours x GPU-specific TDP / 1000 |
| Overhead | x 1.3 PUE (cooling, networking) |
| CO2 | kWh x 0.4 kg/kWh (US Southeast grid) |
| AWS cost | On-demand list prices, US regions |
| GCP cost | On-demand list prices, US regions |

## Requirements

- Python 3.8+
- Access to `sacct` (any Slurm cluster)
- A terminal that supports curses (for interactive mode)
- Zero external dependencies

## License

MIT
