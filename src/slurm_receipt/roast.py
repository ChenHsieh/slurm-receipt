"""Context-aware roasts based on user's actual job history.

Selection logic:
  1. Collect ALL applicable roasts as (text, priority) candidates.
     priority: 3 = data-specific & surprising, 2 = situational, 1 = generic.
  2. Sort by priority (highest first), break ties randomly.
  3. Pick top 4 data-driven roasts.
  4. Add 1 career-stage roast + 1 closing quote = 6 max.
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


def generate_roasts(stats):
    """Generate a curated list of roasts. Returns max 6 strings."""
    candidates = []  # (text, priority)

    total = stats["total_jobs"]
    failed = stats["failed"]
    cancelled = stats["cancelled"]
    completed = stats["completed"]

    # ── Failure rate (priority 3 -- always interesting) ──────────────

    if total > 0:
        fail_pct = failed / total * 100
        if fail_pct > 50:
            candidates.append((random.choice([
                f"  {fail_pct:.0f}% of your jobs failed. At this point\n"
                f"  the cluster is your personal debugger.",
                f"  {fail_pct:.0f}% failure rate. That's not trial and\n"
                f"  error, that's just error.",
                f"  More than half your jobs failed.\n"
                f"  The scheduler is starting to take it\n"
                f"  personally.",
            ]), 3))
        elif fail_pct > 30:
            candidates.append((random.choice([
                f"  {fail_pct:.0f}% failure rate. You're not running\n"
                f"  experiments, you're running a lottery.",
                f"  Nearly 1 in 3 jobs failed. Like ordering\n"
                f"  at a restaurant where the kitchen is on\n"
                f"  fire.",
            ]), 3))
        elif fail_pct > 15:
            candidates.append((random.choice([
                f"  {failed:,} failed jobs. That's not a bug,\n"
                f"  that's a lifestyle.",
                f"  {fail_pct:.0f}% failure rate -- within the\n"
                f"  acceptable range for chaos engineering.",
            ]), 2))
        elif fail_pct > 5:
            candidates.append((
                f"  Only {fail_pct:.0f}% failures. Suspiciously\n"
                f"  competent for someone on this cluster.", 2))
        elif failed == 0 and total > 100:
            candidates.append((
                "  Zero failed jobs? Either you're a wizard\n"
                "  or you're not trying hard enough.", 3))

    # ── Instant failures (priority 3 -- very specific) ───────────────

    fast_fails = stats.get("fastest_fails", [])
    if len(fast_fails) > 50:
        candidates.append((random.choice([
            f"  {len(fast_fails)} jobs failed in under 10 seconds.\n"
            f"  That's not computing, that's speed-dating\n"
            f"  the scheduler.",
            f"  {len(fast_fails)} sub-10-second failures.\n"
            f"  Even a microwave gives you 30.",
        ]), 3))
    elif len(fast_fails) > 5:
        candidates.append((
            f"  {len(fast_fails)} jobs died within 10 seconds.\n"
            f"  Have you considered testing locally first?", 3))

    # ── Slow painful failures (priority 3) ───────────────────────────

    slow_fails = stats.get("slowest_fails", [])
    if slow_fails:
        worst = slow_fails[0]
        t = _fmt_time(worst["elapsed_sec"])
        candidates.append((random.choice([
            f"  Your longest failure ran for {t} before\n"
            f"  giving up. A metaphor, perhaps.",
            f"  One job ran {t} and still failed.\n"
            f"  That's not a job, that's a relationship.",
            f"  {t} of compute, ending in FAILED.\n"
            f"  Like watching a cake rise and then\n"
            f"  collapse in the oven.",
        ]), 3))

    # ── Array job spam (priority 3 -- very specific) ─────────────────

    bursts = stats.get("array_bursts", [])
    if bursts:
        worst = bursts[0]
        candidates.append((random.choice([
            f"  You submitted {worst[1]} jobs in one minute\n"
            f"  on {worst[0]}. The scheduler felt that.",
            f"  {worst[1]} jobs in 60 seconds.\n"
            f"  That's not a submission, that's a DDoS.",
            f"  {worst[1]} simultaneous jobs.\n"
            f"  Your labmates' queue priority sends\n"
            f"  its regards.",
        ]), 3))

    # ── Busiest day (priority 2-3) ───────────────────────────────────

    busiest = stats.get("busiest_day")
    if busiest and busiest["count"] > 500:
        pri = 3
        candidates.append((random.choice([
            f"  {busiest['count']:,} jobs on {busiest['date']}.\n"
            f"  Were you okay that day? Blink twice\n"
            f"  if you need help.",
            f"  {busiest['count']:,} submissions in one day.\n"
            f"  That's one every {86400 // busiest['count']}s.\n"
            f"  Relentless.",
        ]), pri))

        # Weekend bonus
        try:
            from datetime import datetime
            day = datetime.strptime(busiest["date"], "%Y-%m-%d")
            if day.weekday() >= 5:
                candidates.append((random.choice([
                    f"  Your busiest day was a {day.strftime('%A')}.\n"
                    f"  Work-life balance has left the chat.",
                    f"  Peak submissions on a {day.strftime('%A')}.\n"
                    f"  Your advisor would be proud. Your\n"
                    f"  therapist would not.",
                ]), 3))
        except (ValueError, ImportError):
            pass

    elif busiest and busiest["count"] > 100:
        candidates.append((
            f"  {busiest['count']:,} jobs on {busiest['date']}.\n"
            f"  Deadline energy.", 2))

    # ── Scavenge partition (priority 2) ──────────────────────────────

    scav = stats["partitions"].get("scavenge_p", 0)
    if scav > total * 0.5 and total > 50:
        candidates.append((random.choice([
            f"  {scav:,} scavenge jobs -- basically\n"
            f"  dumpster-diving for compute. Respect.",
            f"  Over half your jobs are scavenge.\n"
            f"  You're the seagull of this cluster --\n"
            f"  opportunistic and effective.",
        ]), 2))

    # ── GPU usage (priority 2) ───────────────────────────────────────

    gpu_hrs = stats["total_gpu_hours"]
    if gpu_hrs > 100:
        candidates.append((random.choice([
            f"  {gpu_hrs:.0f} GPU-hours. That silicon could\n"
            f"  have been mining crypto, but instead\n"
            f"  it served science. Noble.",
            f"  {gpu_hrs:.0f} GPU-hours on A100s. Some labs\n"
            f"  would trade a grad student for that.",
        ]), 2))
    elif 0 < gpu_hrs < 1:
        candidates.append((
            f"  {gpu_hrs:.2f} GPU-hours total. You reserved a\n"
            f"  GPU and barely whispered at it.", 3))

    # ── Volume (priority 2) ──────────────────────────────────────────

    if total > 30000:
        candidates.append((random.choice([
            f"  {total:,} jobs. You personally are a\n"
            f"  significant fraction of this cluster's\n"
            f"  reason to exist.",
            f"  {total:,} submissions. The electricity\n"
            f"  bill has your name on it in spirit.",
        ]), 2))
    elif total > 5000:
        candidates.append((
            f"  {total:,} jobs. The cluster considers\n"
            f"  you a regular.", 2))

    # ── Longest job (priority 2) ─────────────────────────────────────

    longest = stats.get("longest_job")
    if longest and longest["elapsed_sec"] > 172800:
        days_r = longest["elapsed_sec"] / 86400
        candidates.append((random.choice([
            f"  Your longest job ran for {days_r:.1f} days.\n"
            f"  It saw weekends. It changed.",
            f"  {days_r:.1f} days for a single job. That's\n"
            f"  longer than some relationships.",
        ]), 2))

    # ── Timeouts (priority 2) ────────────────────────────────────────

    if stats.get("timeout", 0) > 5:
        candidates.append((random.choice([
            f"  {stats['timeout']} jobs timed out. They didn't\n"
            f"  fail -- they ran out of hope.",
            f"  {stats['timeout']} TIMEOUT exits. Each one a\n"
            f"  cliffhanger with no sequel.",
        ]), 2))

    # ── Cancelled (priority 1) ───────────────────────────────────────

    if cancelled > 20:
        candidates.append((
            f"  {cancelled} cancelled jobs. Changed your\n"
            f"  mind, or changed your parameters?", 1))

    # ── Success (priority 1 -- wholesome) ────────────────────────────

    if total > 100 and completed / total > 0.95:
        candidates.append((
            f"  {completed / total * 100:.1f}% success rate though.\n"
            f"  The cluster would give you a loyalty\n"
            f"  card if it could.", 1))

    # ── SELECT TOP 4 DATA-DRIVEN ROASTS ─────────────────────────────

    # Shuffle to break ties randomly, then sort by priority desc
    random.shuffle(candidates)
    candidates.sort(key=lambda x: x[1], reverse=True)

    roasts = [text for text, _ in candidates[:4]]

    # ── ADD 1 CAREER-STAGE ROAST ─────────────────────────────────────

    career = [
        # Undergrad
        "  Undergrad energy: requesting 64 cores\n"
        "  for a script that's single-threaded.",

        "  Intern vibes: 'What do you mean conda\n"
        "  activate doesn't work in sbatch?'",

        # Junior grad
        "  First-year grad energy: submitting the\n"
        "  same broken script 47 times hoping the\n"
        "  cluster figures it out.",

        "  Year-one move: copying your advisor's\n"
        "  sbatch script from 2019 and wondering\n"
        "  why nothing works.",

        "  New grad vibes: --mem=500G because\n"
        "  'what if it needs it?' It used 400MB.",

        # Senior grad
        "  Fifth-year mood: your sbatch scripts have\n"
        "  more error handling than your thesis.",

        "  Dissertation-stage energy: submitting jobs\n"
        "  at 2 AM and calling it productivity.",

        "  Senior grad move: checking squeue every\n"
        "  90 seconds while pretending to write.",

        "  Senior grad mood: your tmux sessions have\n"
        "  tmux sessions. Turtles all the way down.",

        # Postdoc
        "  Postdoc energy: optimizing sbatch headers\n"
        "  to shave 2 minutes off queue wait while\n"
        "  your contract ticks down.",

        "  Postdoc move: running someone else's\n"
        "  pipeline and fixing 17 hardcoded paths\n"
        "  before it even starts.",

        "  Postdoc mood: you've memorized the GPU\n"
        "  node names and know which ones run hot.",

        # PI
        "  PI energy: 'Can you just run it on the\n"
        "  cluster?' without specifying what 'it'\n"
        "  is or which cluster.",

        "  PI vibes: checking this receipt and\n"
        "  wondering where the grant money went.",

        "  PI mood: your students submitted 30,000\n"
        "  jobs and you found out from this receipt.",
    ]
    roasts.append(random.choice(career))

    # ── ADD 1 CLOSING QUOTE ──────────────────────────────────────────

    closers = [
        # Accessible literature / pop culture
        "  \"It was the best of jobs, it was the\n"
        "  worst of jobs.\" -- A Tale of Two Clusters",

        "  \"I have not failed. I've just found\n"
        "  10,000 SBATCH configs that won't work.\"\n"
        "  -- You, probably",

        "  \"One does not simply walk into a compute\n"
        "  node.\" -- Boromir, HPC orientation",

        "  Netflix asks 'Are you still watching?'\n"
        "  Slurm asks 'Are you still submitting?'",

        "  Spotify Wrapped shows your music taste.\n"
        "  Slurm Receipt shows your compute sins.",

        "  \"Call me Ishmael. I submitted a job three\n"
        "  days ago and it's still pending.\"",

        "  \"Do not go gentle into that good night.\n"
        "  Rage, rage against the dying of the job.\"",

        "  \"So we beat on, jobs against the queue,\n"
        "  borne back ceaselessly into PENDING.\"",

        "  If your failed jobs were a playlist,\n"
        "  it would be called 'Exit Code Blues'.",

        "  Like a Costco receipt, but instead of\n"
        "  bulk paper towels it's bulk core-hours.",

        "  The real carbon footprint was the jobs\n"
        "  we failed along the way.",

        "  Some people count sheep to fall asleep.\n"
        "  You count pending jobs.",

        # Sysadmin / HPC culture
        "  sacct never forgets. sacct never forgives.\n"
        "  sacct is always watching.",

        "  Somewhere, a sysadmin just felt a chill\n"
        "  and doesn't know why.",

        "  Your .err files could fill a novella.\n"
        "  A tragic one.",

        "  Your dissertation acknowledgements should\n"
        "  include the Slurm scheduler.",

        # Dark academia
        "  In the candlelit halls of /scratch,\n"
        "  your data awaits the 30-day purge\n"
        "  like a manuscript awaits the flames.",

        "  The cluster hums its electric requiem\n"
        "  for your forgotten jobs.",

        "  There is a poetry to a well-crafted\n"
        "  sbatch script. Yours is free verse.",

        # Proverbs (widely known)
        "  A journey of a thousand core-hours\n"
        "  begins with a single sbatch.",

        "  Fall seven times, stand up eight.\n"
        "  Submit nine, fail seven.",

        # Wholesome surprise (1 in ~25 chance it's this one)
        "  But hey -- you showed up. You submitted.\n"
        "  You fought the scheduler and sometimes\n"
        "  won. That counts for something.",

        "  Behind every successful pipeline is a\n"
        "  graveyard of test runs nobody talks about.",

        "  One day you'll look back at this receipt\n"
        "  and laugh. Today is not that day.",
    ]
    roasts.append(random.choice(closers))

    return roasts
