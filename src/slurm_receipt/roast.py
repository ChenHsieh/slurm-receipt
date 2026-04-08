"""Context-aware roasts based on user's actual job history.

Every data-driven roast references the specific job/event that triggered it.
Selection: collect candidates with priority, pick top 4 + 1 thematic + 1 closer.
"""

import random


def _fmt_time(sec):
    if sec < 60:
        return f"{sec}s"
    elif sec < 3600:
        return f"{sec // 60}m {sec % 60}s"
    else:
        h = sec // 3600
        m = (sec % 3600) // 60
        return f"{h}h {m}m"


def _short(name, maxlen=24):
    return (name[:maxlen-2] + "..") if len(name) > maxlen else name


def generate_roasts(stats):
    """Generate a curated list of roasts. Returns max 7 strings."""
    candidates = []  # (text, priority)

    total = stats["total_jobs"]
    failed = stats["failed"]
    cancelled = stats["cancelled"]
    completed = stats["completed"]

    # ── Failure rate ─────────────────────────────────────────────────

    if total > 0:
        fail_pct = failed / total * 100
        if fail_pct > 50:
            candidates.append((
                f"  {fail_pct:.0f}% of your jobs failed. At this\n"
                f"  point the cluster is just your personal\n"
                f"  debugger.", 3))
        elif fail_pct > 30:
            candidates.append((
                f"  {fail_pct:.0f}% failure rate. You're not running\n"
                f"  experiments, you're running a lottery.", 3))
        elif fail_pct > 15:
            candidates.append((
                f"  {failed:,} failed jobs ({fail_pct:.0f}%). Not a\n"
                f"  bug, a lifestyle.", 2))
        elif fail_pct > 5:
            candidates.append((
                f"  Only {fail_pct:.0f}% failures. Suspiciously\n"
                f"  competent.", 2))
        elif failed == 0 and total > 100:
            candidates.append((
                "  Zero failed jobs? Either you're a wizard\n"
                "  or you're not pushing hard enough.", 3))

    # ── Instant failures (with job names) ────────────────────────────

    fast_fails = stats.get("fastest_fails", [])
    if len(fast_fails) > 5:
        # Find the most repeated instant-fail job name
        names = {}
        for j in fast_fails:
            names[j["name"]] = names.get(j["name"], 0) + 1
        top_name, top_count = max(names.items(), key=lambda x: x[1])
        candidates.append((
            f"  {len(fast_fails)} jobs died in under 10 seconds.\n"
            f"  Worst offender: '{_short(top_name)}'\n"
            f"  failed {top_count}x before it could even\n"
            f"  print hello.", 3))

    # ── Slow painful failures (with job names) ───────────────────────

    slow_fails = stats.get("slowest_fails", [])
    if slow_fails:
        worst = slow_fails[0]
        t = _fmt_time(worst["elapsed_sec"])
        n = _short(worst["name"])
        candidates.append((random.choice([
            f"  '{n}' ran for {t} and then\n"
            f"  failed. That job had a whole character\n"
            f"  arc.",
            f"  '{n}' burned {t} of compute\n"
            f"  before dying. It knew things. It saw\n"
            f"  things. It failed anyway.",
            f"  '{n}' ran {t}, then FAILED.\n"
            f"  Like reading a 500-page novel where\n"
            f"  the last page is ripped out.",
        ]), 3))

    # ── Array job spam ───────────────────────────────────────────────

    bursts = stats.get("array_bursts", [])
    if bursts:
        worst = bursts[0]
        candidates.append((random.choice([
            f"  {worst[1]} jobs in one minute ({worst[0]}).\n"
            f"  The scheduler felt that.",
            f"  {worst[1]} submissions in 60 seconds on\n"
            f"  {worst[0]}. That's not a pipeline,\n"
            f"  that's a DDoS.",
        ]), 3))

    # ── Busiest day ──────────────────────────────────────────────────

    busiest = stats.get("busiest_day")
    if busiest and busiest["count"] > 200:
        candidates.append((
            f"  {busiest['count']:,} jobs on {busiest['date']}.\n"
            f"  That's one every {86400 // max(busiest['count'], 1)}s.\n"
            f"  Were you okay?", 3))

        try:
            from datetime import datetime
            day = datetime.strptime(busiest["date"], "%Y-%m-%d")
            if day.weekday() >= 5:
                candidates.append((
                    f"  Peak day was a {day.strftime('%A')}.\n"
                    f"  Work-life balance has left the chat.", 3))
        except (ValueError, ImportError):
            pass

    # ── Wall time roasts ─────────────────────────────────────────────

    wall = stats["total_wall_hours"]
    longest = stats.get("longest_job")

    if wall > 10000:
        candidates.append((
            f"  {wall:,.0f} wall-hours total. That's\n"
            f"  {wall / 8760:.1f} years of continuous compute.\n"
            f"  Somewhere a clock is weeping.", 2))
    elif wall > 1000:
        candidates.append((
            f"  {wall:,.0f} wall-hours. That's {wall / 24:.0f} days\n"
            f"  of non-stop computation. Your jobs\n"
            f"  never sleep.", 2))

    if longest and longest["elapsed_sec"] > 172800:
        days_r = longest["elapsed_sec"] / 86400
        n = _short(longest["name"])
        candidates.append((random.choice([
            f"  '{n}' ran for {days_r:.1f} days.\n"
            f"  It saw weekends. It outlived some\n"
            f"  of your relationships.",
            f"  '{n}': {days_r:.1f} days. That job\n"
            f"  could have hiked the Appalachian Trail\n"
            f"  in less time. Well, part of it.",
        ]), 2))

    # ── Space mission comparisons ────────────────────────────────────

    if wall > 500:
        candidates.append((random.choice([
            f"  {wall:,.0f} wall-hours. Apollo 11 took\n"
            f"  195 hours round-trip to the moon.\n"
            f"  You've gone {wall / 195:.1f}x further... in CPU time.",
            f"  Your total wall time could have covered\n"
            f"  {wall / 4:.0f} ISS orbits (92 min each).\n"
            f"  Houston, we have a compute bill.",
            f"  Voyager 1 has been running for 48 years.\n"
            f"  Your cluster time is {wall / (48*8760) * 100:.2f}%\n"
            f"  of that. Getting there.",
        ]), 2))

    # ── Scavenge partition ───────────────────────────────────────────

    scav = stats["partitions"].get("scavenge_p", 0)
    if scav > total * 0.5 and total > 50:
        candidates.append((
            f"  {scav:,} scavenge jobs -- living off the\n"
            f"  spare cycles of labs with funding.\n"
            f"  Resourceful.", 2))

    # ── GPU usage (with type) ────────────────────────────────────────

    gpu_hrs = stats["total_gpu_hours"]
    if gpu_hrs > 100:
        types = ", ".join(t.upper() for t in stats["gpu_hours_by_type"])
        candidates.append((
            f"  {gpu_hrs:.0f} GPU-hours on {types}.\n"
            f"  That silicon could have been training\n"
            f"  the next ChatGPT. Instead: your jobs.", 2))
    elif 0 < gpu_hrs < 1:
        candidates.append((
            f"  {gpu_hrs:.2f} GPU-hours. You reserved a GPU\n"
            f"  and barely whispered at it.", 3))

    # ── Volume ───────────────────────────────────────────────────────

    if total > 30000:
        candidates.append((
            f"  {total:,} jobs. You're a significant\n"
            f"  fraction of this cluster's purpose.", 2))

    # ── Timeouts (with job name) ─────────────────────────────────────

    if stats.get("timeout", 0) > 5:
        candidates.append((
            f"  {stats['timeout']} jobs timed out. They didn't\n"
            f"  fail -- they ran out of hope.", 2))

    # ── Success rate ─────────────────────────────────────────────────

    if total > 100 and completed / total > 0.95:
        candidates.append((
            f"  {completed / total * 100:.1f}% success rate.\n"
            f"  The cluster would give you a loyalty\n"
            f"  card if it could.", 1))

    # ── SELECT TOP 4 DATA-DRIVEN ─────────────────────────────────────

    random.shuffle(candidates)
    candidates.sort(key=lambda x: x[1], reverse=True)
    roasts = [text for text, _ in candidates[:4]]

    # ── ADD 1 THEMATIC ROAST ─────────────────────────────────────────
    # Mix of: UGA/football, global culture, space, wall time metaphors

    thematic = [
        # UGA / Georgia / football
        "  Your failed jobs have more fumbles than\n"
        "  a bad day at Sanford Stadium.",

        "  Between the Hedges they cheer touchdowns.\n"
        "  Between the nodes you cheer COMPLETED.",

        "  Uga the Bulldog naps in an air-conditioned\n"
        "  doghouse. Your jobs nap in scavenge_p.\n"
        "  Same energy.",

        "  Your jobs run harder than a 4th-quarter\n"
        "  Dawgs drive. But with more timeouts.",

        "  Even the SEC has a mercy rule.\n"
        "  The Slurm scheduler does not.",

        "  Georgia didn't win back-to-back natties\n"
        "  by submitting broken scripts. Just saying.",

        "  On Saturdays we wear red.\n"
        "  On weekdays we wear out the cluster.",

        # Global culture / food
        "  Your compute bill could buy nasi lemak\n"
        "  for the entire NUS campus.",

        "  That's enough energy to cook jollof rice\n"
        "  for a Lagos wedding. The debate over\n"
        "  whose recipe is better continues.",

        "  In Japan they have a word for this:\n"
        "  'karoshi' -- death by overwork.\n"
        "  Your cluster is unionizing.",

        "  Your wall time exceeds the brewing time\n"
        "  of a proper Chinese pu-erh tea by\n"
        "  several orders of magnitude.",

        "  Italian nonnas would say your pipeline\n"
        "  needs more patience and less --mem=500G.",

        "  Like a Brazilian churrascaria: the compute\n"
        "  keeps coming until you flip the card to\n"
        "  red. You never flipped.",

        "  Your job queue is longer than the line\n"
        "  for Tim Hortons on a Monday morning.",

        "  This much compute in Seoul would earn you\n"
        "  a PC bang loyalty card. Platinum tier.",

        # Space missions
        "  The Hubble Space Telescope's flight\n"
        "  computer runs at 25 MHz. Your jobs\n"
        "  had more FLOPS and less to show for it.",

        "  NASA's entire Apollo guidance computer\n"
        "  had 74KB of memory. You requested 64GB\n"
        "  for a Python script. Times change.",

        "  The Mars rover Perseverance does science\n"
        "  on 2GB of RAM. You allocated 256GB.\n"
        "  Who's the real explorer here?",

        # Wall time
        "  Your total wall time exceeds the runtime\n"
        "  of every Lord of the Rings extended\n"
        "  edition back to back. Twice.",

        "  If your jobs were a TV series, they'd\n"
        "  have more episodes than The Simpsons.",
    ]
    roasts.append(random.choice(thematic))

    # ── ADD 1 CAREER ROAST ───────────────────────────────────────────

    career = [
        "  Undergrad energy: requesting 64 cores\n"
        "  for a single-threaded script.",

        "  Intern vibes: 'What do you mean conda\n"
        "  activate doesn't work in sbatch?'",

        "  First-year grad energy: submitting the\n"
        "  same broken script 47 times hoping\n"
        "  something changes.",

        "  New grad vibes: --mem=500G because\n"
        "  'what if it needs it?' It used 400MB.",

        "  Fifth-year mood: your sbatch scripts\n"
        "  have more error handling than your thesis.",

        "  Senior grad move: checking squeue every\n"
        "  90 seconds while pretending to write.",

        "  Postdoc energy: optimizing queue wait\n"
        "  while your contract ticks down.",

        "  Postdoc move: fixing 17 hardcoded paths\n"
        "  in someone else's pipeline before it\n"
        "  even starts.",

        "  PI energy: 'Just run it on the cluster.'\n"
        "  No further instructions provided.",

        "  PI mood: your students submitted 30,000\n"
        "  jobs and you found out from this receipt.",
    ]
    roasts.append(random.choice(career))

    # ── ADD 1 CLOSER ─────────────────────────────────────────────────

    closers = [
        "  \"It was the best of jobs, it was the\n"
        "  worst of jobs.\" -- A Tale of Two Clusters",

        "  \"I have not failed. I've just found\n"
        "  10,000 SBATCH configs that won't work.\"",

        "  Netflix asks 'Are you still watching?'\n"
        "  Slurm asks 'Are you still submitting?'",

        "  Spotify Wrapped shows your music taste.\n"
        "  Slurm Receipt shows your compute sins.",

        "  If your failed jobs were a playlist,\n"
        "  it would be 'Exit Code Blues'.",

        "  Like a Costco receipt, but instead of\n"
        "  bulk paper towels it's bulk core-hours.",

        "  The real carbon footprint was the jobs\n"
        "  we failed along the way.",

        "  sacct never forgets. sacct never forgives.",

        "  Somewhere, a sysadmin just felt a chill\n"
        "  and doesn't know why.",

        "  Your .err files could fill a novella.",

        "  In the candlelit halls of /scratch,\n"
        "  your data awaits the 30-day purge.",

        "  A journey of a thousand core-hours\n"
        "  begins with a single sbatch.",

        "  But hey -- you showed up. You submitted.\n"
        "  You fought the scheduler and sometimes\n"
        "  won. That counts.",

        "  One day you'll look back at this receipt\n"
        "  and laugh. Today is not that day.",

        "  Go Dawgs.",
    ]
    roasts.append(random.choice(closers))

    return roasts
