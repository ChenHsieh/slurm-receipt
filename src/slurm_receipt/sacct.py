"""Fetch and parse Slurm accounting data."""

import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta


def parse_tres(tres_str):
    """Parse AllocTRES string like 'billing=9,cpu=8,gres/gpu:a100=1,mem=64G'."""
    result = {"cpu": 0, "mem_gb": 0.0, "gpu_type": None, "gpu_count": 0}
    if not tres_str:
        return result
    for item in tres_str.split(","):
        if "=" not in item:
            continue
        key, val = item.split("=", 1)
        key, val = key.strip(), val.strip()
        if key == "cpu":
            try:
                result["cpu"] = int(val)
            except ValueError:
                pass
        elif key == "mem":
            try:
                if val.endswith("G"):
                    result["mem_gb"] = float(val[:-1])
                elif val.endswith("M"):
                    result["mem_gb"] = float(val[:-1]) / 1024
                elif val.endswith("T"):
                    result["mem_gb"] = float(val[:-1]) * 1024
                elif val.endswith("K"):
                    result["mem_gb"] = float(val[:-1]) / (1024 * 1024)
                else:
                    # Bare number = bytes
                    result["mem_gb"] = float(val) / (1024 ** 3)
            except ValueError:
                pass
        elif key.startswith("gres/gpu:"):
            result["gpu_type"] = key.split(":")[-1].lower()
            try:
                result["gpu_count"] = int(val)
            except ValueError:
                pass
        elif key == "gres/gpu" and result["gpu_count"] == 0:
            try:
                result["gpu_count"] = int(val)
            except ValueError:
                pass
    return result


def _safe_int(s, default=0):
    """Parse int, return default on failure."""
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


def _parse_line(fields):
    """Parse a single sacct output line (list of fields) into a job dict.

    Returns job dict or None if the line should be skipped.
    """
    if len(fields) < 8:
        return None
    job_id = fields[0]
    if not job_id or "." in job_id:  # skip substeps (safety net)
        return None

    tres = parse_tres(fields[4])
    elapsed = _safe_int(fields[5])
    # Handle negative elapsed (clock skew)
    if elapsed < 0:
        elapsed = 0
    state = fields[6].split(" ")[0] if fields[6] else ""
    submit_str = fields[7] if len(fields) > 7 else ""

    submit_dt = None
    if submit_str:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                submit_dt = datetime.strptime(submit_str, fmt)
                break
            except ValueError:
                continue

    return {
        "job_id": job_id,
        "name": fields[1].strip(),
        "partition": fields[2],
        "cpus": _safe_int(fields[3]),
        "mem_gb": tres["mem_gb"],
        "gpu_type": tres["gpu_type"],
        "gpu_count": tres["gpu_count"],
        "elapsed_sec": elapsed,
        "state": state,
        "submit_dt": submit_dt,
    }


def fetch_jobs(user, start_date, end_date):
    """Fetch job records from sacct. Returns list of job dicts.

    Uses -X (allocations only) to skip substeps and --state filter
    to skip PENDING/RUNNING jobs, which dramatically reduces output.
    """
    cmd = [
        "sacct",
        "-X",  # allocations only -- skip batch/extern substeps (big perf win)
        "--starttime", start_date,
        "--endtime", end_date,
        "-u", user,
        # No --state filter: let sacct return everything, we filter in Python.
        # Some Slurm versions don't support all state codes (e.g. SE).
        "--format=JobID,JobName%50,Partition,AllocCPUS,AllocTRES%80,ElapsedRaw,State,Submit",
        "-n", "--parsable2",
    ]
    try:
        # Stream parse: read line by line to avoid loading all output into memory
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except FileNotFoundError:
        print("Error: 'sacct' not found. Are you on a Slurm cluster?", file=sys.stderr)
        print("  Tip: use --demo to see a demo receipt without sacct.", file=sys.stderr)
        sys.exit(1)

    jobs = []
    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            fields = line.split("|")
            job = _parse_line(fields)
            if job:
                jobs.append(job)
    except Exception as e:
        print(f"Error parsing sacct output: {e}", file=sys.stderr)

    # Wait for process to finish (with timeout)
    try:
        _, stderr = proc.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        print("sacct timed out. Try a shorter --days range.", file=sys.stderr)
        sys.exit(1)

    if proc.returncode != 0:
        err = stderr.strip() if stderr else "unknown error"
        print(f"sacct error: {err}", file=sys.stderr)
        sys.exit(1)

    return jobs


def generate_demo_jobs(days=30, count=200):
    """Generate synthetic job data for demo/testing without sacct."""
    import random
    jobs = []
    now = datetime.now()

    job_names = [
        "alignment_star", "variant_calling", "fastqc_check",
        "assembly_v2", "trimmomatic_run", "salmon_quant",
        "deseq2_analysis", "kallisto_idx", "samtools_sort",
        "picard_markdup", "gatk_haplotype", "bcftools_filter",
        "diamond_blastx", "busco_assess", "multiqc_report",
        "rnaseq_pipeline", "chipseq_peaks", "bwa_mem_align",
        "featurecounts", "stringtie_assemble",
    ]
    partitions = ["batch", "batch", "batch", "gpu_p", "highmem_p"]
    gpu_types = [None, None, None, None, "a100", "l4"]
    states_weights = ["COMPLETED"] * 7 + ["FAILED"] * 2 + ["CANCELLED"]

    for i in range(count):
        submit_dt = now - timedelta(
            days=random.randint(0, days - 1),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        state = random.choice(states_weights)
        part = random.choice(partitions)
        gpu = random.choice(gpu_types) if part == "gpu_p" else None
        elapsed = random.randint(5, 86400)
        if state == "FAILED" and random.random() < 0.3:
            elapsed = random.randint(1, 8)  # instant fail

        jobs.append({
            "job_id": str(100000 + i),
            "name": random.choice(job_names),
            "partition": part,
            "cpus": random.choice([1, 4, 8, 16]),
            "mem_gb": random.choice([4.0, 8.0, 16.0, 32.0, 64.0]),
            "gpu_type": gpu,
            "gpu_count": 1 if gpu else 0,
            "elapsed_sec": elapsed,
            "state": state,
            "submit_dt": submit_dt,
        })
    return jobs


def compute_stats(jobs):
    """Aggregate statistics from job list."""
    s = {
        "total_jobs": len(jobs),
        "completed": 0,
        "failed": 0,
        "cancelled": 0,
        "timeout": 0,
        "other": 0,
        "total_cpu_hours": 0.0,
        "total_gpu_hours": 0.0,
        "gpu_hours_by_type": defaultdict(float),
        "total_mem_gb_hours": 0.0,
        "total_wall_hours": 0.0,
        "partitions": defaultdict(int),
        "top_jobs_cpu": [],
        # Roast-worthy metrics
        "fastest_fails": [],       # jobs that failed in <10 seconds (capped)
        "slowest_fails": [],       # jobs that failed after long runtime
        "array_bursts": [],        # many jobs submitted in same minute
        "busiest_day": None,
        "longest_job": None,
        "short_completed": 0,      # completed in <60 seconds
        "single_core_jobs": 0,     # jobs with cpus=1
        "night_submissions": 0,    # submitted 10pm-6am
        "weekend_submissions": 0,  # submitted Sat/Sun
        "submissions_by_hour": defaultdict(int),  # hour -> count
        "submissions_by_dow": defaultdict(int),    # weekday (0=Mon) -> count
        "first_submit": None,    # earliest submit datetime
        "last_submit": None,     # latest submit datetime
        "monthly": defaultdict(lambda: {
            "jobs": 0, "completed": 0, "failed": 0,
            "cpu_hours": 0.0, "gpu_hours": 0.0, "wall_hours": 0.0,
        }),
    }

    if not jobs:
        return s

    # Track submissions per minute for array burst detection
    submissions_per_minute = defaultdict(int)
    submissions_per_day = defaultdict(int)

    # Cap fastest_fails to avoid unbounded growth
    MAX_FAST_FAILS = 500

    for j in jobs:
        state = j["state"]
        if state == "COMPLETED":
            s["completed"] += 1
        elif state == "FAILED":
            s["failed"] += 1
        elif state.startswith("CANCEL"):
            s["cancelled"] += 1
        elif state == "TIMEOUT":
            s["timeout"] += 1
        else:
            s["other"] += 1

        hours = j["elapsed_sec"] / 3600.0
        cpu_hours = j["cpus"] * hours
        gpu_hours = j["gpu_count"] * hours

        s["total_cpu_hours"] += cpu_hours
        s["total_gpu_hours"] += gpu_hours
        s["total_mem_gb_hours"] += j["mem_gb"] * hours
        s["total_wall_hours"] += hours

        if j["gpu_type"] and gpu_hours > 0:
            s["gpu_hours_by_type"][j["gpu_type"]] += gpu_hours
        if j["partition"]:
            s["partitions"][j["partition"]] += 1

        s["top_jobs_cpu"].append((j["name"], cpu_hours, j["job_id"]))

        # Roast metrics
        if state == "FAILED" and j["elapsed_sec"] < 10:
            if len(s["fastest_fails"]) < MAX_FAST_FAILS:
                s["fastest_fails"].append(j)
        if state == "FAILED" and j["elapsed_sec"] > 3600:
            s["slowest_fails"].append(j)
        if state == "COMPLETED" and j["elapsed_sec"] < 60:
            s["short_completed"] += 1
        if j["cpus"] <= 1:
            s["single_core_jobs"] += 1

        if j["submit_dt"]:
            hr = j["submit_dt"].hour
            dow = j["submit_dt"].weekday()
            s["submissions_by_hour"][hr] += 1
            s["submissions_by_dow"][dow] += 1
            if hr >= 22 or hr < 6:
                s["night_submissions"] += 1
            if dow >= 5:
                s["weekend_submissions"] += 1
            # Track actual date range
            if s["first_submit"] is None or j["submit_dt"] < s["first_submit"]:
                s["first_submit"] = j["submit_dt"]
            if s["last_submit"] is None or j["submit_dt"] > s["last_submit"]:
                s["last_submit"] = j["submit_dt"]
            minute_key = j["submit_dt"].strftime("%Y-%m-%d %H:%M")
            submissions_per_minute[minute_key] += 1
            day_key = j["submit_dt"].strftime("%Y-%m-%d")
            submissions_per_day[day_key] += 1

            # Monthly bucketing
            month_key = j["submit_dt"].strftime("%Y-%m")
            m = s["monthly"][month_key]
            m["jobs"] += 1
            m["cpu_hours"] += cpu_hours
            m["gpu_hours"] += gpu_hours
            m["wall_hours"] += hours
            if state == "COMPLETED":
                m["completed"] += 1
            elif state == "FAILED":
                m["failed"] += 1

        # Track longest job
        if s["longest_job"] is None or j["elapsed_sec"] > s["longest_job"]["elapsed_sec"]:
            s["longest_job"] = j

    # Top CPU consumers
    s["top_jobs_cpu"].sort(key=lambda x: x[1], reverse=True)
    s["top_jobs_cpu"] = s["top_jobs_cpu"][:10]

    # Slowest fails sorted by runtime
    s["slowest_fails"].sort(key=lambda x: x["elapsed_sec"], reverse=True)
    s["slowest_fails"] = s["slowest_fails"][:5]

    # Array bursts: minutes with >10 submissions
    s["array_bursts"] = sorted(
        [(k, v) for k, v in submissions_per_minute.items() if v > 10],
        key=lambda x: x[1], reverse=True,
    )[:5]

    # Busiest day
    if submissions_per_day:
        busiest = max(submissions_per_day.items(), key=lambda x: x[1])
        s["busiest_day"] = {"date": busiest[0], "count": busiest[1]}

    # Daily activity for heatmap
    s["daily"] = dict(submissions_per_day)

    # Convert defaultdicts for cleanliness
    s["gpu_hours_by_type"] = dict(s["gpu_hours_by_type"])
    s["partitions"] = dict(s["partitions"])
    s["monthly"] = dict(s["monthly"])
    s["submissions_by_hour"] = dict(s["submissions_by_hour"])
    s["submissions_by_dow"] = dict(s["submissions_by_dow"])

    return s
