"""Context-aware roasts based on user's actual job history.

Every data-driven roast references the specific job/event that triggered it.
Each roast carries optional job context for the mini-receipt panel.
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


def generate_roasts(stats, uga=False):
    """Generate a curated list of roasts.

    Returns list of dicts:
      {"text": str, "context": dict or None}
    where context = {"job_id", "name", "detail"} for job-specific roasts.
    """
    candidates = []  # (roast_dict, priority)

    total = stats["total_jobs"]
    failed = stats["failed"]
    cancelled = stats["cancelled"]
    completed = stats["completed"]

    # ── Failure rate ─────────────────────────────────────────────────

    if total > 0:
        fail_pct = failed / total * 100
        if fail_pct > 50:
            candidates.append((
                {"text":
                    f"  {fail_pct:.0f}% of your jobs failed. At this\n"
                    f"  point the cluster is just your personal\n"
                    f"  debugger.",
                 "context": {"detail": f"{failed:,}/{total:,} jobs FAILED"}},
                3))
        elif fail_pct > 30:
            candidates.append((
                {"text":
                    f"  {fail_pct:.0f}% failure rate. You're not running\n"
                    f"  experiments, you're running a lottery.",
                 "context": {"detail": f"{failed:,}/{total:,} jobs FAILED ({fail_pct:.0f}%)"}},
                3))
        elif fail_pct > 15:
            candidates.append((
                {"text":
                    f"  {failed:,} failed jobs ({fail_pct:.0f}%). Not a\n"
                    f"  bug, a lifestyle.",
                 "context": {"detail": f"{failed:,} FAILED out of {total:,}"}},
                2))
        elif fail_pct > 5:
            candidates.append((
                {"text":
                    f"  Only {fail_pct:.0f}% failures. Suspiciously\n"
                    f"  competent.",
                 "context": {"detail": f"{fail_pct:.0f}% failure rate"}},
                2))
        elif fail_pct > 0 and fail_pct <= 5:
            candidates.append((
                {"text":
                    f"  {failed} failed out of {total:,}. Barely a\n"
                    f"  scratch. The cluster respects you.",
                 "context": {"detail": f"{failed} FAILED / {total:,} total"}},
                1))
        elif failed == 0 and total > 10:
            candidates.append((
                {"text":
                    "  Zero failed jobs? Either you're a wizard\n"
                    "  or you're not pushing hard enough.",
                 "context": {"detail": f"0 FAILED / {total:,} total"}},
                3))

    # ── Instant failures (with job names) ────────────────────────────

    fast_fails = stats.get("fastest_fails", [])
    if len(fast_fails) > 5:
        names = {}
        for j in fast_fails:
            names[j["name"]] = names.get(j["name"], 0) + 1
        top_name, top_count = max(names.items(), key=lambda x: x[1])
        worst_j = next(j for j in fast_fails if j["name"] == top_name)
        candidates.append((
            {"text":
                f"  {len(fast_fails)} jobs died in under 10 seconds.\n"
                f"  Worst offender: '{_short(top_name)}'\n"
                f"  failed {top_count}x before it could even\n"
                f"  print hello.",
             "context": {
                 "job_id": worst_j.get("job_id", ""),
                 "name": _short(top_name, 30),
                 "detail": f"FAILED in <10s x{top_count}"}},
            3))
    elif len(fast_fails) > 0:
        j = fast_fails[0]
        candidates.append((
            {"text":
                f"  '{_short(j['name'])}' failed in under\n"
                f"  10 seconds. It didn't even try.",
             "context": {
                 "job_id": j.get("job_id", ""),
                 "name": _short(j["name"], 30),
                 "detail": f"FAILED in <10s"}},
            2))

    # ── Slow painful failures (with job names) ───────────────────────

    slow_fails = stats.get("slowest_fails", [])
    if slow_fails:
        worst = slow_fails[0]
        t = _fmt_time(worst["elapsed_sec"])
        n = _short(worst["name"])
        candidates.append((
            {"text": random.choice([
                f"  '{n}' ran for {t} and then\n"
                f"  failed. That job had a whole character\n"
                f"  arc.",
                f"  '{n}' burned {t} of compute\n"
                f"  before dying. It knew things. It saw\n"
                f"  things. It failed anyway.",
                f"  '{n}' ran {t}, then FAILED.\n"
                f"  Like reading a 500-page novel where\n"
                f"  the last page is ripped out.",
             ]),
             "context": {
                 "job_id": worst.get("job_id", ""),
                 "name": _short(worst["name"], 30),
                 "detail": f"Ran {t} -> FAILED"}},
            3))

    # ── Array job spam ───────────────────────────────────────────────

    bursts = stats.get("array_bursts", [])
    if bursts:
        worst = bursts[0]
        candidates.append((
            {"text": random.choice([
                f"  {worst[1]} jobs in one minute ({worst[0]}).\n"
                f"  The scheduler felt that.",
                f"  {worst[1]} submissions in 60 seconds on\n"
                f"  {worst[0]}. That's not a pipeline,\n"
                f"  that's a DDoS.",
             ]),
             "context": {"detail": f"{worst[1]} jobs at {worst[0]}"}},
            3))

    # ── Busiest day ──────────────────────────────────────────────────

    busiest = stats.get("busiest_day")
    if busiest and busiest["count"] > 200:
        candidates.append((
            {"text":
                f"  {busiest['count']:,} jobs on {busiest['date']}.\n"
                f"  That's one every {86400 // max(busiest['count'], 1)}s.\n"
                f"  Were you okay?",
             "context": {"detail": f"{busiest['count']:,} jobs on {busiest['date']}"}},
            3))
    elif busiest and busiest["count"] > 30:
        candidates.append((
            {"text":
                f"  {busiest['count']} jobs on {busiest['date']}.\n"
                f"  That was a busy day. The scheduler\n"
                f"  remembers.",
             "context": {"detail": f"{busiest['count']} jobs on {busiest['date']}"}},
            2))

    if busiest:
        try:
            from datetime import datetime
            day = datetime.strptime(busiest["date"], "%Y-%m-%d")
            if day.weekday() >= 5:
                candidates.append((
                    {"text":
                        f"  Peak day was a {day.strftime('%A')}.\n"
                        f"  Work-life balance has left the chat.",
                     "context": {"detail": f"{busiest['date']} ({day.strftime('%A')})"}},
                    3))
        except (ValueError, ImportError):
            pass

    # ── Wall time roasts ─────────────────────────────────────────────

    wall = stats["total_wall_hours"]
    longest = stats.get("longest_job")

    if wall > 10000:
        candidates.append((
            {"text":
                f"  {wall:,.0f} wall-hours total. That's\n"
                f"  {wall / 8760:.1f} years of continuous compute.\n"
                f"  Somewhere a clock is weeping.",
             "context": {"detail": f"{wall:,.0f} wall-hours total"}},
            2))
    elif wall > 1000:
        candidates.append((
            {"text":
                f"  {wall:,.0f} wall-hours. That's {wall / 24:.0f} days\n"
                f"  of non-stop computation. Your jobs\n"
                f"  never sleep.",
             "context": {"detail": f"{wall:,.0f} wall-hours = {wall / 24:.0f} days"}},
            2))
    elif wall > 100:
        candidates.append((
            {"text":
                f"  {wall:,.0f} wall-hours. That's {wall / 24:.1f} full\n"
                f"  days of compute. Not bad for someone\n"
                f"  who 'just ran a quick test'.",
             "context": {"detail": f"{wall:,.0f} wall-hours"}},
            1))
    elif wall > 1:
        candidates.append((
            {"text":
                f"  {wall:.1f} wall-hours total. You've barely\n"
                f"  warmed up the silicon. The cluster\n"
                f"  expected more of you.",
             "context": {"detail": f"{wall:.1f} wall-hours total"}},
            1))

    if longest and longest["elapsed_sec"] > 172800:
        days_r = longest["elapsed_sec"] / 86400
        n = _short(longest["name"])
        candidates.append((
            {"text": random.choice([
                f"  '{n}' ran for {days_r:.1f} days.\n"
                f"  It saw weekends. It outlived some\n"
                f"  of your relationships.",
                f"  '{n}': {days_r:.1f} days. That job\n"
                f"  could have hiked the Appalachian Trail\n"
                f"  in less time. Well, part of it.",
             ]),
             "context": {
                 "job_id": longest.get("job_id", ""),
                 "name": _short(longest["name"], 30),
                 "detail": f"Ran {days_r:.1f} days"}},
            2))
    elif longest and longest["elapsed_sec"] > 28800:
        hrs_r = longest["elapsed_sec"] / 3600
        n = _short(longest["name"])
        candidates.append((
            {"text":
                f"  '{n}' ran for {hrs_r:.1f} hours.\n"
                f"  That's a full work shift. Hope it\n"
                f"  was productive.",
             "context": {
                 "job_id": longest.get("job_id", ""),
                 "name": _short(longest["name"], 30),
                 "detail": f"Ran {hrs_r:.1f} hours"}},
            1))

    # ── Cancellation roasts ──────────────────────────────────────────

    if cancelled > 0 and total > 0:
        cancel_pct = cancelled / total * 100
        if cancel_pct > 30:
            candidates.append((
                {"text":
                    f"  {cancelled:,} cancelled jobs ({cancel_pct:.0f}%).\n"
                    f"  You submitted them just to feel\n"
                    f"  something.",
                 "context": {"detail": f"{cancelled:,} CANCELLED ({cancel_pct:.0f}%)"}},
                3))
        elif cancelled > 10:
            candidates.append((
                {"text":
                    f"  {cancelled} jobs cancelled. That's not\n"
                    f"  indecision, that's iterative design.",
                 "context": {"detail": f"{cancelled} CANCELLED"}},
                2))
        elif cancelled > 0:
            candidates.append((
                {"text":
                    f"  {cancelled} cancelled job{'s' if cancelled > 1 else ''}.\n"
                    f"  We've all been there. Ctrl+C is\n"
                    f"  an underrated debugging tool.",
                 "context": {"detail": f"{cancelled} CANCELLED"}},
                1))

    # ── Night owl / weekend warrior ──────────────────────────────────

    night = stats.get("night_submissions", 0)
    weekend = stats.get("weekend_submissions", 0)

    if night > 0 and total > 0:
        night_pct = night / total * 100
        if night_pct > 40:
            candidates.append((
                {"text":
                    f"  {night_pct:.0f}% of your jobs were submitted\n"
                    f"  between 10pm and 6am. The cluster\n"
                    f"  is not a coping mechanism.",
                 "context": {"detail": f"{night} jobs submitted 10pm-6am"}},
                3))
        elif night_pct > 15:
            candidates.append((
                {"text":
                    f"  {night} jobs submitted after midnight.\n"
                    f"  Nothing good happens on a cluster\n"
                    f"  after midnight.",
                 "context": {"detail": f"{night} late-night submissions"}},
                2))
        elif night > 0:
            candidates.append((
                {"text":
                    f"  {night} late-night submission{'s' if night > 1 else ''}.\n"
                    f"  Burning the midnight compute.",
                 "context": {"detail": f"{night} jobs submitted 10pm-6am"}},
                1))

    if weekend > 0 and total > 0:
        wknd_pct = weekend / total * 100
        if wknd_pct > 30:
            candidates.append((
                {"text":
                    f"  {wknd_pct:.0f}% of your jobs ran on weekends.\n"
                    f"  The scheduler doesn't get overtime pay\n"
                    f"  but it's starting to resent you.",
                 "context": {"detail": f"{weekend} weekend submissions"}},
                2))

    # ── Peak submission hour ─────────────────────────────────────────

    by_hour = stats.get("submissions_by_hour", {})
    if by_hour:
        peak_hr = max(by_hour, key=by_hour.get)
        peak_count = by_hour[peak_hr]
        if peak_hr >= 22 or peak_hr < 5:
            candidates.append((
                {"text":
                    f"  Your peak submission hour: {peak_hr}:00.\n"
                    f"  Most people are sleeping. You're\n"
                    f"  submitting batch jobs. Respect.",
                 "context": {"detail": f"{peak_count} jobs at {peak_hr}:00"}},
                2))
        elif peak_hr >= 11 and peak_hr <= 13:
            candidates.append((
                {"text":
                    f"  Peak submissions at {peak_hr}:00.\n"
                    f"  Lunch break? More like launch break.",
                 "context": {"detail": f"{peak_count} jobs at {peak_hr}:00"}},
                1))

    # ── Short completed jobs ─────────────────────────────────────────

    short_ok = stats.get("short_completed", 0)
    if short_ok > 20 and total > 0:
        short_pct = short_ok / total * 100
        candidates.append((
            {"text":
                f"  {short_ok} jobs finished in under 60 seconds.\n"
                f"  That's {short_pct:.0f}% of your jobs. The queue\n"
                f"  wait was longer than the actual work.",
             "context": {"detail": f"{short_ok} completed in <60s"}},
            2))
    elif short_ok > 5:
        candidates.append((
            {"text":
                f"  {short_ok} jobs done in under a minute.\n"
                f"  Could've run those on a laptop, but\n"
                f"  where's the fun in that?",
             "context": {"detail": f"{short_ok} completed in <60s"}},
            1))

    # ── Single-core jobs ─────────────────────────────────────────────

    single = stats.get("single_core_jobs", 0)
    if single > 0 and total > 0:
        single_pct = single / total * 100
        if single_pct > 80 and total > 10:
            candidates.append((
                {"text":
                    f"  {single_pct:.0f}% of your jobs used a single\n"
                    f"  core. The other cores are filing\n"
                    f"  for unemployment.",
                 "context": {"detail": f"{single}/{total:,} single-core jobs"}},
                2))

    # ── Memory usage ─────────────────────────────────────────────────

    mem_gb_hrs = stats["total_mem_gb_hours"]
    if mem_gb_hrs > 0 and wall > 0.01:
        avg_mem = mem_gb_hrs / wall  # avg GB per wall-hour
        if avg_mem > 100:
            candidates.append((
                {"text":
                    f"  Averaging {avg_mem:.0f} GB per job-hour.\n"
                    f"  Are you loading the entire internet\n"
                    f"  into RAM?",
                 "context": {"detail": f"Avg {avg_mem:.0f} GB/hr memory"}},
                2))
        elif avg_mem > 32:
            candidates.append((
                {"text":
                    f"  {avg_mem:.0f} GB average memory usage.\n"
                    f"  Your jobs eat RAM like a Chrome tab\n"
                    f"  eats swap space.",
                 "context": {"detail": f"Avg {avg_mem:.0f} GB/hr memory"}},
                1))

    # ── Partition diversity ──────────────────────────────────────────

    parts = stats["partitions"]
    if len(parts) == 1:
        only_part = list(parts.keys())[0]
        candidates.append((
            {"text":
                f"  All {total:,} jobs on {only_part}.\n"
                f"  There are other partitions, you know.\n"
                f"  The cluster has range.",
             "context": {"detail": f"All jobs on {only_part}"}},
            1))
    elif len(parts) >= 4:
        candidates.append((
            {"text":
                f"  Jobs spread across {len(parts)} partitions.\n"
                f"  You're a true partition connoisseur.\n"
                f"  Explorer badge earned.",
             "context": {"detail": f"{len(parts)} different partitions used"}},
            1))

    # ── Scavenge partition ───────────────────────────────────────────

    scav = parts.get("scavenge_p", 0)
    if scav > total * 0.5 and total > 50:
        candidates.append((
            {"text":
                f"  {scav:,} scavenge jobs -- living off the\n"
                f"  spare cycles of labs with funding.\n"
                f"  Resourceful.",
             "context": {"detail": f"{scav:,} jobs on scavenge_p"}},
            2))
    elif scav > 0:
        candidates.append((
            {"text":
                f"  {scav} scavenge job{'s' if scav > 1 else ''}. Free\n"
                f"  compute at the risk of getting yeeted.\n"
                f"  Fortune favors the bold.",
             "context": {"detail": f"{scav} jobs on scavenge_p"}},
            1))

    # ── GPU usage (with type) ────────────────────────────────────────

    gpu_hrs = stats["total_gpu_hours"]
    if gpu_hrs > 100:
        types = ", ".join(t.upper() for t in stats["gpu_hours_by_type"])
        candidates.append((
            {"text":
                f"  {gpu_hrs:.0f} GPU-hours on {types}.\n"
                f"  That silicon could have been training\n"
                f"  the next ChatGPT. Instead: your jobs.",
             "context": {"detail": f"{gpu_hrs:.0f} GPU-hrs on {types}"}},
            2))
    elif 0 < gpu_hrs < 1:
        candidates.append((
            {"text":
                f"  {gpu_hrs:.2f} GPU-hours. You reserved a GPU\n"
                f"  and barely whispered at it.",
             "context": {"detail": f"{gpu_hrs:.2f} GPU-hours total"}},
            3))
    elif 1 <= gpu_hrs <= 100:
        types = ", ".join(t.upper() for t in stats["gpu_hours_by_type"])
        candidates.append((
            {"text":
                f"  {gpu_hrs:.1f} GPU-hours on {types}.\n"
                f"  A modest GPU appetite. The A100s\n"
                f"  barely noticed you.",
             "context": {"detail": f"{gpu_hrs:.1f} GPU-hrs on {types}"}},
            1))

    # ── No GPU usage ─────────────────────────────────────────────────

    if gpu_hrs == 0 and total > 50:
        candidates.append((
            {"text":
                f"  {total:,} jobs and zero GPU time. Either\n"
                f"  you're CPU-loyal or you haven't\n"
                f"  discovered the GPU queue yet.",
             "context": {"detail": "0 GPU-hours"}},
            1))

    # ── Volume ───────────────────────────────────────────────────────

    if total > 30000:
        candidates.append((
            {"text":
                f"  {total:,} jobs. You're a significant\n"
                f"  fraction of this cluster's purpose.",
             "context": {"detail": f"{total:,} total jobs submitted"}},
            2))
    elif total > 1000:
        candidates.append((
            {"text":
                f"  {total:,} jobs. That's not a workload,\n"
                f"  that's a relationship.",
             "context": {"detail": f"{total:,} total jobs submitted"}},
            1))
    elif total > 100:
        candidates.append((
            {"text":
                f"  {total} jobs this period. Steady and\n"
                f"  reliable. The cluster's favorite\n"
                f"  regular.",
             "context": {"detail": f"{total} total jobs submitted"}},
            1))
    elif total <= 10:
        candidates.append((
            {"text":
                f"  {total} jobs total? That's it? The\n"
                f"  cluster booted up for this?",
             "context": {"detail": f"{total} total jobs submitted"}},
            2))

    # ── Timeouts ─────────────────────────────────────────────────────

    timeout = stats.get("timeout", 0)
    if timeout > 5:
        candidates.append((
            {"text":
                f"  {timeout} jobs timed out. They didn't\n"
                f"  fail -- they ran out of hope.",
             "context": {"detail": f"{timeout} TIMEOUT"}},
            2))
    elif timeout > 0:
        candidates.append((
            {"text":
                f"  {timeout} job{'s' if timeout > 1 else ''} hit the\n"
                f"  wall-time limit. So close, yet so\n"
                f"  --time=too-short.",
             "context": {"detail": f"{timeout} TIMEOUT"}},
            2))

    # ── Success rate ─────────────────────────────────────────────────

    if total > 10 and completed / total > 0.95:
        candidates.append((
            {"text":
                f"  {completed / total * 100:.1f}% success rate.\n"
                f"  The cluster would give you a loyalty\n"
                f"  card if it could.",
             "context": {"detail": f"{completed / total * 100:.1f}% success rate"}},
            1))

    # ── Top job CPU hog ──────────────────────────────────────────────

    top_jobs = stats.get("top_jobs_cpu", [])
    if top_jobs:
        top_name, top_cpu, top_id = top_jobs[0]
        if top_cpu > 100:
            candidates.append((
                {"text":
                    f"  '{_short(top_name)}' alone used\n"
                    f"  {top_cpu:,.0f} core-hours. That one job\n"
                    f"  is carrying your entire compute bill.",
                 "context": {
                     "job_id": top_id,
                     "name": _short(top_name, 30),
                     "detail": f"{top_cpu:,.0f} core-hours"}},
                2))

    # ── Day-of-week pattern ──────────────────────────────────────────

    by_dow = stats.get("submissions_by_dow", {})
    if by_dow:
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"]
        busiest_dow = max(by_dow, key=by_dow.get)
        if busiest_dow == 0:  # Monday
            candidates.append((
                {"text":
                    f"  Peak day: Monday. You hit the ground\n"
                    f"  running. Or panicking. Hard to tell.",
                 "context": {"detail": f"{by_dow[busiest_dow]} jobs on Mondays"}},
                1))
        elif busiest_dow == 4:  # Friday
            candidates.append((
                {"text":
                    f"  Peak day: Friday. Submit and pray\n"
                    f"  over the weekend. Classic move.",
                 "context": {"detail": f"{by_dow[busiest_dow]} jobs on Fridays"}},
                2))

    # ── SELECT TOP 5 DATA-DRIVEN ─────────────────────────────────────

    random.shuffle(candidates)
    candidates.sort(key=lambda x: x[1], reverse=True)
    roasts = [roast for roast, _ in candidates[:5]]

    # ── ADD 1 UGA THEMATIC (only if uga=True) ────────────────────────

    if uga:
        thematic = [
            {"text":
                "  Your failed jobs have more fumbles than\n"
                "  a bad day at Sanford Stadium.",
             "context": None},
            {"text":
                "  Between the Hedges they cheer touchdowns.\n"
                "  Between the nodes you cheer COMPLETED.",
             "context": None},
            {"text":
                "  Uga the Bulldog naps in an air-conditioned\n"
                "  doghouse. Your jobs nap in scavenge_p.\n"
                "  Same energy.",
             "context": None},
            {"text":
                "  Even the SEC has a mercy rule.\n"
                "  The Slurm scheduler does not.",
             "context": None},
            {"text":
                "  On Saturdays we wear red.\n"
                "  On weekdays we wear out the cluster.",
             "context": None},
        ]
        roasts.append(random.choice(thematic))

    # ── ADD 1 CLOSER ─────────────────────────────────────────────────

    closers = [
        {"text":
            "  \"It was the best of jobs, it was the\n"
            "  worst of jobs.\" -- A Tale of Two Clusters",
         "context": None},
        {"text":
            "  \"I have not failed. I've just found\n"
            "  10,000 SBATCH configs that won't work.\"",
         "context": None},
        {"text":
            "  sacct never forgets. sacct never forgives.",
         "context": None},
        {"text":
            "  But hey -- you showed up. You submitted.\n"
            "  You fought the scheduler and sometimes\n"
            "  won. That counts.",
         "context": None},
        {"text":
            "  One day you'll look back at this receipt\n"
            "  and laugh. Today is not that day.",
         "context": None},
        {"text":
            "  Somewhere, a sysadmin just felt a chill\n"
            "  and doesn't know why.",
         "context": None},
    ]
    roasts.append(random.choice(closers))

    return roasts
