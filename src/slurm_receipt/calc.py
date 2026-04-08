"""Energy, cost, and fun-equivalent calculations."""

# Hardware power estimates (watts)
# CPU: per-CORE power draw under load. Server sockets are ~150-250W TDP
# spread across 16-64 cores, so per-core is ~5-10W. We use 8W as a
# blended average across typical HPC nodes (EPYC 7713 @ 225W/64c = 3.5W,
# Xeon Gold 6226R @ 150W/16c = 9.4W). This is conservative.
CPU_WATTS_PER_CORE = 8
GPU_TDP_W = {
    "a100": 400, "h100": 700, "l4": 72, "l40s": 350,
    "v100": 250, "v100s": 250, "p100": 250, "t4": 70,
}
PUE = 1.3
CO2_KG_PER_KWH = 0.4  # US Southeast grid

# Cloud pricing -- AWS on-demand (USD/hour, US regions, 2026)
AWS_CPU_HR = 0.05
AWS_GPU_HR = {"a100": 4.10, "h100": 8.00, "l4": 0.81, "l40s": 2.80, "v100": 3.06, "p100": 1.46, "t4": 0.53}
AWS_MEM_GB_HR = 0.005


# ── Pop-culture conversions ─────────────────────────────────────────
# Users cycle through these one at a time with < / >
# No emoji — pure ASCII for terminal compatibility.
# Each has an icon char for the receipt display.

CONVERSIONS = [
    # ── Food & drink ──
    {
        "id": "burger", "icon": "~B~",
        "label": "burgers grilled",
        "kwh_per": 0.7,
        "tagline": "Enough to run a food truck for a day",
        "source": "Electric grill ~1400W x 30min",
        "category": "food",
    },
    {
        "id": "cake", "icon": "[#]",
        "label": "cakes baked",
        "kwh_per": 2.0,
        "tagline": "The Great HPC Bake Off",
        "source": "Oven at 350F for 1 hour",
        "category": "food",
    },
    {
        "id": "ramen", "icon": "(~)",
        "label": "pots of ramen boiled",
        "kwh_per": 0.15,
        "tagline": "The grad student energy unit",
        "source": "Electric kettle ~1500W x 6min",
        "category": "food",
    },
    {
        "id": "espresso", "icon": "c[]",
        "label": "espresso shots pulled",
        "kwh_per": 0.05,
        "tagline": "Fueled by coffee, funded by grants",
        "source": "Espresso machine ~1000W x 3min",
        "category": "food",
    },
    {
        "id": "toast", "icon": "/t\\",
        "label": "slices of toast",
        "kwh_per": 0.04,
        "tagline": "That's a lot of avocado toast",
        "source": "Toaster ~800W x 3min",
        "category": "food",
    },
    {
        "id": "pizza", "icon": "<V>",
        "label": "frozen pizzas baked",
        "kwh_per": 1.5,
        "tagline": "Friday night lab meeting, sorted",
        "source": "Oven at 425F for ~20min",
        "category": "food",
    },
    {
        "id": "popcorn", "icon": "*p*",
        "label": "bags of microwave popcorn",
        "kwh_per": 0.1,
        "tagline": "Just watching your jobs pop",
        "source": "Microwave 1000W x 3.5min",
        "category": "food",
    },
    {
        "id": "rice", "icon": ":::",
        "label": "rice cooker batches",
        "kwh_per": 0.3,
        "tagline": "The foundation of civilization and grad school",
        "source": "Rice cooker ~700W x 25min",
        "category": "food",
    },
    # ── Energy & fuel ──
    {
        "id": "gas", "icon": "[G]",
        "label": "gallons of gasoline",
        "kwh_per": 33.7,
        "tagline": "Hope you got good mileage",
        "source": "DOE: 1 gal = 33.7 kWh thermal",
        "category": "energy",
    },
    {
        "id": "phone", "icon": "[|]",
        "label": "phones fully charged",
        "kwh_per": 0.012,
        "tagline": "Your lab could start a phone-charging business",
        "source": "iPhone ~12Wh per full charge",
        "category": "energy",
    },
    {
        "id": "laptop", "icon": "[=]",
        "label": "laptop full charges",
        "kwh_per": 0.06,
        "tagline": "One for every student in the department",
        "source": "Laptop battery ~60Wh",
        "category": "energy",
    },
    {
        "id": "battery_aa", "icon": "+|-",
        "label": "AA batteries worth of energy",
        "kwh_per": 0.003,
        "tagline": "You'd need a very large TV remote",
        "source": "AA battery ~3Wh (1.5V x 2Ah)",
        "category": "energy",
    },
    {
        "id": "lightning", "icon": "/!/",
        "label": "lightning bolts",
        "kwh_per": 1400.0,
        "tagline": "Great Scott!",
        "source": "Avg lightning bolt ~1.4 GJ = ~1400 kWh",
        "category": "energy",
    },
    # ── Transport ──
    {
        "id": "tesla", "icon": "==>",
        "label": "Tesla miles driven",
        "kwh_per": 0.25,
        "tagline": "Your jobs went the distance",
        "source": "Model 3: 25 kWh/100 miles",
        "category": "transport",
    },
    {
        "id": "ebike", "icon": "o-o",
        "label": "e-bike miles ridden",
        "kwh_per": 0.02,
        "tagline": "Greener, but your jobs weren't",
        "source": "E-bike ~20Wh per mile",
        "category": "transport",
    },
    {
        "id": "flights", "icon": "->>",
        "label": "NYC-to-London flights (per seat)",
        "kwh_per": 2500.0,
        "tagline": "Business class turbulence",
        "source": "~3500 miles, ~715 kWh/seat-1000mi",
        "category": "transport",
    },
    # ── Household ──
    {
        "id": "laundry", "icon": "(@)",
        "label": "loads of laundry",
        "kwh_per": 2.5,
        "tagline": "At least your code is clean... right?",
        "source": "Washer + dryer cycle ~2.5 kWh",
        "category": "home",
    },
    {
        "id": "shower", "icon": "|.|",
        "label": "hot showers",
        "kwh_per": 4.0,
        "tagline": "Clean conscience not included",
        "source": "Electric heater, 10min shower",
        "category": "home",
    },
    {
        "id": "house", "icon": "/^\\",
        "label": "US homes powered for a day",
        "kwh_per": 30.0,
        "tagline": "You could have powered a small neighborhood",
        "source": "EIA: US avg ~30 kWh/day",
        "category": "home",
    },
    {
        "id": "fridge", "icon": "[F]",
        "label": "days of running a fridge",
        "kwh_per": 1.5,
        "tagline": "Keeping science cool since the 1930s",
        "source": "Avg fridge ~1.5 kWh/day",
        "category": "home",
    },
    {
        "id": "hairdryer", "icon": "~d>",
        "label": "hours of hair drying",
        "kwh_per": 1.8,
        "tagline": "Hot air: your cluster's second specialty",
        "source": "Hair dryer ~1800W",
        "category": "home",
    },
    {
        "id": "vacuum", "icon": "=o>",
        "label": "hours of vacuuming",
        "kwh_per": 1.4,
        "tagline": "Your jobs sucked up more than dust",
        "source": "Vacuum ~1400W",
        "category": "home",
    },
    # ── Entertainment ──
    {
        "id": "netflix", "icon": ">N>",
        "label": "hours of Netflix",
        "kwh_per": 0.08,
        "tagline": "Are you still running jobs?",
        "source": "IEA: ~80Wh per hour of streaming",
        "category": "entertainment",
    },
    {
        "id": "gaming", "icon": "[X]",
        "label": "hours of console gaming",
        "kwh_per": 0.15,
        "tagline": "Achievement unlocked: Cluster Abuse",
        "source": "PS5/Xbox ~150W",
        "category": "entertainment",
    },
    {
        "id": "vinyl", "icon": "(o)",
        "label": "vinyl records played (full album)",
        "kwh_per": 0.05,
        "tagline": "Your jobs have a nice warm analog quality",
        "source": "Turntable + amp ~50W, 1hr album",
        "category": "entertainment",
    },
    # ── Scale & science ──
    {
        "id": "iss", "icon": "-O-",
        "label": "ISS orbits powered",
        "kwh_per": 8400.0,
        "tagline": "Houston, we have a compute bill",
        "source": "ISS solar: 84kW, 1 orbit = 92min",
        "category": "scale",
    },
    {
        "id": "bitcoin", "icon": "{B}",
        "label": "Bitcoin transactions",
        "kwh_per": 700.0,
        "tagline": "At least your work produced science",
        "source": "Digiconomist: ~700 kWh/tx avg",
        "category": "scale",
    },
    {
        "id": "chatgpt", "icon": "?A?",
        "label": "ChatGPT queries",
        "kwh_per": 0.01,
        "tagline": "Your cluster could have answered a lot of questions",
        "source": "IEA estimate ~10Wh per query",
        "category": "scale",
    },
    {
        "id": "google", "icon": "?g?",
        "label": "Google searches",
        "kwh_per": 0.0003,
        "tagline": "Ctrl+F for your compute bill",
        "source": "Google: ~0.3Wh per search",
        "category": "scale",
    },
    {
        "id": "mri", "icon": "{M}",
        "label": "MRI brain scans",
        "kwh_per": 15.0,
        "tagline": "Scanning for intelligence in your sbatch scripts",
        "source": "MRI machine ~15 kWh per scan",
        "category": "scale",
    },
    # ── Memory-based ──
    {
        "id": "books", "icon": "|B|",
        "label": "novels stored in your allocated RAM",
        "mem_gb_per": 0.001,
        "tagline": "Your RAM held more than the Library of Alexandria",
        "source": "Avg novel ~500KB-1MB plain text",
        "category": "memory",
    },
    {
        "id": "photos", "icon": "[P]",
        "label": "smartphone photos in RAM",
        "mem_gb_per": 0.005,
        "tagline": "An Instagram feed nobody asked for",
        "source": "Avg phone photo ~5MB",
        "category": "memory",
    },
    {
        "id": "genomes", "icon": "~D~",
        "label": "human genomes in RAM",
        "mem_gb_per": 3.2,
        "tagline": "You held the blueprint of humanity... in swap",
        "source": "Human genome reference ~3.2GB",
        "category": "memory",
    },
    {
        "id": "wikipedia", "icon": "{W}",
        "label": "full Wikipedias in RAM",
        "mem_gb_per": 22.0,
        "tagline": "The sum of all human knowledge, allocated and unused",
        "source": "Wikipedia text dump ~22GB",
        "category": "memory",
    },
    # ── Environmental ──
    {
        "id": "trees", "icon": " T ",
        "label": "trees needed to offset (1 year)",
        "co2_per": 21.0,
        "tagline": "Start planting",
        "source": "EPA: 1 tree absorbs ~21 kg CO2/yr",
        "category": "environment",
    },
    {
        "id": "balloons", "icon": " o ",
        "label": "party balloons of CO2",
        "co2_per": 0.014,
        "tagline": "A very sad party",
        "source": "11in balloon holds ~14g gas",
        "category": "environment",
    },
    {
        "id": "soda", "icon": "|O|",
        "label": "cans of soda (dissolved CO2)",
        "co2_per": 0.006,
        "tagline": "Flat science",
        "source": "330ml soda contains ~6g CO2",
        "category": "environment",
    },
]


# ── ASCII mascots / logos ────────────────────────────────────────────
# Compact (3-4 lines), varied, title is the only label (no duplication).
# Multiple options per tier; picked by hash of username for consistency.

MASCOT_TIERS = [
    # ── Tier 0: < 100 CPU-hours ──
    {
        "threshold": 100,
        "options": [
            {"art": [r" _|_", r"(o.o)", r" /|\\ "], "title": "The Lemonade Stand"},
            {"art": [r"  .", r" /|\\", r"/_|_\\"], "title": "The Paper Route"},
            {"art": [r" .--.", r"| oo |", r" '--'"], "title": "The Penny Jar"},
            {"art": [r"  ^", r" /o\\", r"/___\\"], "title": "The Side Hustle"},
        ],
    },
    # ── Tier 1: 100 - 1000 CPU-hours ──
    {
        "threshold": 1000,
        "options": [
            {"art": [r" .--[]--.", r" | o  o |", r" '------'"], "title": "The Corner Bodega"},
            {"art": [r"  _/\\_", r" |_.._|", r" |_||_|"], "title": "The Night Market Stall"},
            {"art": [r" [====]", r" | oo |", r" |____|"], "title": "The Vending Machine"},
            {"art": [r" .~~~~.", r" | oo |", r" '----'"], "title": "The Ramen Cart"},
        ],
    },
    # ── Tier 2: 1000 - 10000 CPU-hours ──
    {
        "threshold": 10000,
        "options": [
            {"art": [r" _[==]_", r"|o    o|", r"|______|"], "title": "The General Store"},
            {"art": [r"  /$$\\", r" | oo |", r" |____|"], "title": "The Pawn Shop"},
            {"art": [r" _/^^\\_", r"| o  o |", r"|=OPEN=|"], "title": "The Diner"},
            {"art": [r" .----.", r" |[oo]|", r" '===='"], "title": "The Jukebox Joint"},
        ],
    },
    # ── Tier 3: 10000 - 50000 CPU-hours ──
    {
        "threshold": 50000,
        "options": [
            {"art": [r" _/|  |\\_ ", r"|  o  o  |", r"|________|"], "title": "The Warehouse"},
            {"art": [r" |[]  []|", r" | o  o |", r" |=SALE=|"], "title": "The Outlet Mall"},
            {"art": [r" /|====|\\", r"| | oo | |", r"|_|____|_|"], "title": "The Department Store"},
            {"art": [r" __|  |__", r"|  [oo]  |", r"|________|"], "title": "The Wholesale Club"},
        ],
    },
    # ── Tier 4: 50000 - 200000 CPU-hours ──
    {
        "threshold": 200000,
        "options": [
            {"art": [r" _||====||_", r"| OPEN  24h |", r"|__________|"], "title": "The Mega Depot"},
            {"art": [r"  /||  ||\\", r" | [o][o] |", r" |________|"], "title": "The Industrial Complex"},
            {"art": [r" ==||[]||==", r" | o    o |", r" |________|"], "title": "The Power Plant"},
            {"art": [r"  _/====\\_", r" ||  <>  ||", r" ||______||"], "title": "The Data Cathedral"},
        ],
    },
    # ── Tier 5: > 200000 CPU-hours ──
    {
        "threshold": float("inf"),
        "options": [
            {"art": [r"  /\\  ||  /\\", r" |  [o  o]  |", r" |__________|"], "title": "The Compute Empire"},
            {"art": [r"  ==[||||]==", r"  | <oo> |", r"  |______|"], "title": "The Orbital Station"},
            {"art": [r"  //|====|\\\\", r" || [oo] ||", r" ||______||"], "title": "The National Lab"},
            {"art": [r"  _/\\/\\/\\_", r" | o      o |", r" |__________|"], "title": "The Supercomputer"},
        ],
    },
]


def get_mascot(cpu_hours, username=""):
    """Pick mascot tier based on CPU-hours, variant by username hash."""
    for tier in MASCOT_TIERS:
        if cpu_hours < tier["threshold"]:
            idx = hash(username) % len(tier["options"])
            return tier["options"][idx]
    # fallback to last tier
    last = MASCOT_TIERS[-1]
    idx = hash(username) % len(last["options"])
    return last["options"][idx]


def energy(stats):
    """Compute energy in kWh from stats."""
    cpu_kwh = stats["total_cpu_hours"] * CPU_WATTS_PER_CORE / 1000
    gpu_kwh = sum(
        hrs * GPU_TDP_W.get(gt, 300) / 1000
        for gt, hrs in stats["gpu_hours_by_type"].items()
    )
    typed = sum(stats["gpu_hours_by_type"].values())
    if stats["total_gpu_hours"] > typed:
        gpu_kwh += (stats["total_gpu_hours"] - typed) * 300 / 1000
    total = (cpu_kwh + gpu_kwh) * PUE
    return {
        "cpu_kwh": cpu_kwh,
        "gpu_kwh": gpu_kwh,
        "total_kwh": total,
        "co2_kg": total * CO2_KG_PER_KWH,
    }


def cloud_cost(stats):
    """Estimate AWS on-demand equivalent cost."""
    cpu = stats["total_cpu_hours"] * AWS_CPU_HR
    gpu = sum(
        hrs * AWS_GPU_HR.get(gt, 3.0)
        for gt, hrs in stats["gpu_hours_by_type"].items()
    )
    mem = stats["total_mem_gb_hours"] * AWS_MEM_GB_HR
    return {"cpu": cpu, "gpu": gpu, "mem": mem, "total": cpu + gpu + mem}


def convert(kwh, co2_kg, mem_gb_hours, conv):
    """Apply a single conversion. Returns count."""
    if "kwh_per" in conv:
        return kwh / conv["kwh_per"] if conv["kwh_per"] else 0
    elif "co2_per" in conv:
        return co2_kg / conv["co2_per"] if conv["co2_per"] else 0
    elif "mem_gb_per" in conv:
        return mem_gb_hours / conv["mem_gb_per"] if conv["mem_gb_per"] else 0
    return 0
