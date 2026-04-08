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
            result["cpu"] = int(val)
        elif key == "mem":
            if val.endswith("G"):
                result["mem_gb"] = float(val[:-1])
            elif val.endswith("M"):
                result["mem_gb"] = float(val[:-1]) / 1024
            elif val.endswith("T"):
                result["mem_gb"] = float(val[:-1]) * 1024
        elif key.startswith("gres/gpu:"):
            result["gpu_type"] = key.split(":")[-1].lower()
            result["gpu_count"] = int(val)
        elif key == "gres/gpu" and result["gpu_count"] == 0:
            result["gpu_count"] = int(val)
    return result


def fetch_jobs(user, start_date, end_date):
    """Fetch job records from sacct. Returns list of job dicts."""
    cmd = [
        "sacct",
        "--starttime", start_date,
        "--endtime", end_date,
        "-u", user,
        "--format=JobID,JobName%50,Partition,AllocCPUS,AllocTRES%80,ElapsedRaw,State,Submit",
        "-n", "--parsable2",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"sacct error: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
    except FileNotFoundError:
        print("Error: 'sacct' not found. Are you on a Slurm cluster?", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("sacct timed out. Try a shorter --days range.", file=sys.stderr)
        sys.exit(1)

    jobs = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        fields = line.split("|")
        if len(fields) < 8:
            continue
        job_id = fields[0]
        if "." in job_id:  # skip substeps
            continue

        tres = parse_tres(fields[4])
        elapsed = int(fields[5]) if fields[5] else 0
        state = fields[6].split(" ")[0]
        submit_str = fields[7] if len(fields) > 7 else ""

        # Parse submit time for monthly bucketing
        submit_dt = None
        if submit_str:
            try:
                submit_dt = datetime.strptime(submit_str, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass

        jobs.append({
            "job_id": job_id,
            "name": fields[1].strip(),
            "partition": fields[2],
            "cpus": int(fields[3]) if fields[3] else 0,
            "mem_gb": tres["mem_gb"],
            "gpu_type": tres["gpu_type"],
            "gpu_count": tres["gpu_count"],
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
        "fastest_fails": [],       # jobs that failed in <10 seconds
        "slowest_fails": [],       # jobs that failed after long runtime
        "array_bursts": [],        # many jobs submitted in same minute
        "busiest_day": None,
        "longest_job": None,
        "monthly": defaultdict(lambda: {
            "jobs": 0, "completed": 0, "failed": 0,
            "cpu_hours": 0.0, "gpu_hours": 0.0, "wall_hours": 0.0,
        }),
    }

    # Track submissions per minute for array burst detection
    submissions_per_minute = defaultdict(int)
    submissions_per_day = defaultdict(int)

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
            s["fastest_fails"].append(j)
        if state == "FAILED" and j["elapsed_sec"] > 3600:
            s["slowest_fails"].append(j)

        if j["submit_dt"]:
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

    return s
