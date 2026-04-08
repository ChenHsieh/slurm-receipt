# slurm-receipt

**See what your HPC compute really cost — in dollars, energy, and burgers.**

A zero-dependency terminal tool that reads your Slurm job history via `sacct`
and generates an interactive receipt showing compute charges, energy usage,
AWS cost equivalents, and fun real-world conversions. It also roasts you
about your failed jobs with data-backed commentary.

```
  ====================================================

                       _[==]_
                      |o    o|
                      |______|
                   The General Store
  ====================================================

    Customer:  you
    Period:    2026-03-25 -> 2026-04-07 20:24
    Days:      14

  ----------------------------------------------------
                     ORDER SUMMARY
  ----------------------------------------------------

    Jobs submitted .......................... 26,189
      Completed ............................ 26,085
      Failed ....................................57
      Cancelled .................................21
      Timed out ..................................3

    Success: [##########################..] 100%
```

## Install

```bash
# From PyPI (recommended)
pip install slurm-receipt

# Or with pipx (isolated install)
pipx install slurm-receipt

# Or from source
git clone https://github.com/chen-hsieh/slurm-receipt.git
cd slurm-receipt
pip install -e .
```

**Requirements:** Python 3.8+, access to `sacct` (any Slurm cluster), a
terminal with curses support. Zero external Python dependencies.

## Quick start

```bash
# Interactive receipt for the last 30 days
slurm-receipt

# Last 90 days
slurm-receipt --days 90

# Custom date range
slurm-receipt --start 2025-01-01 --end 2025-12-31

# Plain text output (no TUI)
slurm-receipt --snap

# Save to a specific file
slurm-receipt --snap-file my_receipt.txt

# Try it without a Slurm cluster (synthetic data)
slurm-receipt --demo

# Add UGA Bulldogs flavor to roasts
slurm-receipt --uga
```

## Examples

### Main receipt

The receipt shows your compute charges like a store receipt:

```
  ----------------------------------------------------
                    COMPUTE CHARGES
  ----------------------------------------------------

    CPU time ........................ 18,597 core-hrs
    Wall time ......................... 1,008 hrs
    Memory ........................ 176,483 GB-hrs

    Energy (CPU) ..................... 148.78 kWh
    Cooling overhead ......................... x1.3
    ------------------------------------------------
    TOTAL ENERGY ..................... 193.41 kWh
    CO2 emitted ...................... 77.37 kg

  ----------------------------------------------------
               AWS PRICE CHECK (on-demand)
  ----------------------------------------------------

    Compute (CPU) ........................ $929.87
    Memory ............................... $882.41
    ------------------------------------------------
    TOTAL ............................ $1,812.28

  ****************************************************
                    BUT ACTUALLY...
  ****************************************************

                    ~B~  276.3
                    burgers grilled

              "Enough to run a food truck for a day"

                 [1/37] (food)
```

### Activity report

Press `h` to see your submission patterns — weekly volume, day-of-week,
and time-of-day breakdowns:

```
                    WEEKLY BREAKDOWN
    ------------------------------------------------
       Mar 25-31  [####################] 25971 <-
       Apr 01-07  [#.....................]   218

                      DAY OF WEEK
    ------------------------------------------------
    Monday      [#####.............]    43
    Tuesday     [##################]    63 <-
    Wednesday   [##############....]    55
    Thursday    [#.................]     4
    Friday      [###########.......]    40
    Saturday    [############......] 25946 <-
    Sunday      [###...............]    25

                      TIME OF DAY
    ------------------------------------------------
      12am-4am  [....................]     0
       4am-8am  [....................]     0
      8am-12pm  [####................]  2593
      12pm-4pm  [####################] 10382
       4pm-8pm  [################....]  7786
      8pm-12am  [###########.........]  5428
```

### Performance review (roasts)

Press `r` to see data-driven roasts with a mini receipt showing the
referenced job info:

```
    25,963 jobs on 2026-03-28.
    That's one every 3s.
    Were you okay?

    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    | RELATED JOB INFO                              |
    |----------------------------------------------|
    |  Detail:  25,963 jobs on 2026-03-28          |
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

                        [1/6]
```

### Top jobs

Press `t` to see your hungriest jobs by CPU-hours, plus the failure
hall of shame:

```
                 TOP 10 HUNGRIEST JOBS
  ====================================================

    #   Job Name                  CPU-hrs
    ------------------------------------------------
     1.  genera_717hap1              9,216
     2.  genera_717hap2              8,832
     3.  build_diamond_nr              768
     4.  syn_ks                         36
     ...
```

## Interactive controls

| Key | Action |
|-----|--------|
| `<` / `>` | Rotate through 37 fun conversions |
| `r` | Performance review (roasts) |
| `m` | Monthly ledger |
| `h` | Activity report (weekly/daily/hourly) |
| `t` | Top jobs + failure hall of shame |
| `s` | Save receipt to `~/slurm_receipt_30d.txt` + copy to clipboard |
| `j`/`k` or arrows | Scroll |
| `PgUp`/`PgDn` | Scroll fast |
| `b` | Back to main receipt |
| `q` | Quit (prints save location) |

Mouse scroll and status bar clicks also work in supported terminals.

## What it calculates

| Metric | Method | Source |
|--------|--------|--------|
| CPU energy | core-hours x 8W per core / 1000 | Blended avg across HPC nodes |
| GPU energy | GPU-hours x GPU TDP / 1000 | A100=400W, H100=700W, L4=72W, etc. |
| Cooling overhead | Total energy x 1.3 PUE | Industry standard data center PUE |
| CO2 emissions | kWh x 0.4 kg/kWh | US Southeast electricity grid |
| AWS cost | On-demand list prices, US regions | 2026 pricing |

## Fun conversions (37)

Rotate through with `<`/`>`:

- **Food:** burgers, cakes, ramen, espresso, toast, pizza, popcorn, rice
- **Energy:** phone charges, laptop charges, AA batteries, lightning bolts
- **Transport:** Tesla miles, e-bike miles, transatlantic flights
- **Household:** laundry loads, showers, houses powered, fridge days
- **Entertainment:** Netflix hours, gaming hours, vinyl albums
- **Scale:** ISS orbits, Bitcoin transactions, ChatGPT queries, MRI scans
- **Memory:** novels in RAM, photos, human genomes, full Wikipedias
- **Environment:** trees to offset, CO2 balloons, soda cans

## Roast categories

All roasts reference your actual data with a mini receipt panel:

- Failure rate analysis (any % triggers something)
- Instant failures (<10s) with job name
- Slow painful failures (hours then FAILED) with job name
- Array job burst detection
- Night owl patterns (10pm–6am submissions)
- Weekend warrior detection
- Peak submission hour commentary
- Short job inefficiency (<60s completed)
- Single-core job usage
- Memory usage patterns
- Partition loyalty/diversity
- Cancellation habits
- Top CPU hog identification
- Day-of-week patterns (Monday panic, Friday submit-and-pray)

## Mascot tiers

Your shop mascot changes based on total CPU-hours:

| CPU-hours | Examples |
|-----------|----------|
| < 100 | The Lemonade Stand, The Penny Jar |
| 100 – 1K | The Corner Bodega, The Ramen Cart |
| 1K – 10K | The General Store, The Diner |
| 10K – 50K | The Warehouse, The Department Store |
| 50K – 200K | The Mega Depot, The Data Cathedral |
| > 200K | The Compute Empire, The Supercomputer |

## CLI reference

```
usage: slurm-receipt [-h] [--days DAYS] [--user USER] [--start START]
                     [--end END] [--snap] [--snap-file PATH]
                     [--no-copy] [--uga] [--demo]

See what your HPC compute really cost.

options:
  --days DAYS      Days to look back (default: 30)
  --user USER      Slurm username (default: $USER)
  --start START    Start date YYYY-MM-DD (overrides --days)
  --end END        End date YYYY-MM-DD (default: today)
  --snap           Print receipt + save to ~/slurm_receipt_Nd.txt (no TUI)
  --snap-file PATH Save receipt to file
  --no-copy        Don't auto-copy to clipboard on snap
  --uga            Add UGA Bulldogs flavor to roasts
  --demo           Demo with synthetic data (no sacct needed)
```

## Clipboard

The `s` key saves the receipt and tries to copy to clipboard:

1. **OSC 52** — works over SSH if your terminal supports it (writes to `/dev/tty`)
2. **tmux buffer** — `tmux load-buffer` (paste with `prefix + ]`)
3. **xclip / xsel / wl-copy** — local clipboard fallback

On quit, the auto-saved receipt location is printed:
```
  Receipt saved to: /home/you/slurm_receipt_30d.txt
```

## License

MIT
