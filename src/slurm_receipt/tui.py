"""Interactive curses TUI with receipt aesthetic."""

import base64
import curses
import os
import subprocess
import sys
import random
from datetime import datetime, timedelta

from slurm_receipt.calc import CONVERSIONS, convert, get_mascot
from slurm_receipt.roast import generate_roasts


def _osc52_copy(text):
    """Copy to clipboard via OSC 52. Writes to /dev/tty to bypass curses."""
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    if os.environ.get("TMUX"):
        seq = f"\033Ptmux;\033\033]52;c;{encoded}\a\033\\"
    else:
        seq = f"\033]52;c;{encoded}\a"
    # Write directly to /dev/tty so the escape reaches the outer terminal
    # even when inside curses or tmux
    try:
        fd = os.open("/dev/tty", os.O_WRONLY | os.O_NOCTTY)
        os.write(fd, seq.encode("ascii"))
        os.close(fd)
    except OSError:
        sys.stdout.write(seq)
        sys.stdout.flush()


def _tmux_buffer_copy(text):
    """Copy to tmux paste buffer. User can paste with prefix+]."""
    try:
        p = subprocess.Popen(
            ["tmux", "load-buffer", "-"],
            stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        p.communicate(text.encode("utf-8"), timeout=3)
        return p.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _clipboard_copy(text):
    """Try multiple clipboard methods. Returns description of what worked."""
    # Try OSC 52 to /dev/tty (works over SSH if terminal supports it)
    try:
        _osc52_copy(text)
        # OSC 52 is fire-and-forget; we can't tell if it actually worked.
        # If in tmux, also load into tmux buffer as a reliable fallback.
        if os.environ.get("TMUX"):
            _tmux_buffer_copy(text)
            return "tmux buffer (prefix+])"
        return "clipboard (OSC 52)"
    except Exception:
        pass
    # Fallback: tmux paste buffer
    if os.environ.get("TMUX") and _tmux_buffer_copy(text):
        return "tmux buffer (prefix+])"
    # Fallback: xclip, xsel, wl-copy
    for cmd in [["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"],
                ["wl-copy"]]:
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL)
            p.communicate(text.encode("utf-8"), timeout=3)
            if p.returncode == 0:
                return "clipboard"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return ""


W = 52  # receipt inner width

def _ctr(text):
    return text.center(W)

def _right(label, value, dots=True):
    gap = W - len(label) - len(value)
    if dots and gap > 2:
        return label + " " + "." * (gap - 2) + " " + value
    return label + " " * max(gap, 1) + value

def _bar(filled, total, width=20):
    if total == 0:
        return "[" + " " * width + "]"
    pct = min(filled / total, 1.0)
    n = int(pct * width)
    return "[" + "#" * n + "." * (width - n) + "]"

def _fmt(n):
    if n >= 1_000_000:
        return f"{n:,.0f}"
    elif n >= 1000:
        return f"{n:,.0f}"
    elif n >= 10:
        return f"{n:,.1f}"
    elif n >= 1:
        return f"{n:.2f}"
    elif n >= 0.01:
        return f"{n:.3f}"
    else:
        return f"{n:.4f}"

def _fmt_time(sec):
    if sec < 60:
        return f"{sec}s"
    elif sec < 3600:
        return f"{sec // 60}m"
    else:
        return f"{int(sec // 3600)}h{int((sec % 3600) // 60)}m"


# ── Page builders ────────────────────────────────────────────────────

def build_receipt_page(user, days, stats, nrg, costs, conv_idx):
    """Build main receipt."""
    lines = []
    a = lines.append

    mascot = get_mascot(stats["total_cpu_hours"], user)

    # Show actual data range instead of query range
    first = stats.get("first_submit")
    last = stats.get("last_submit")
    if first and last:
        start_str = first.strftime("%Y-%m-%d")
        end_str = last.strftime("%Y-%m-%d %H:%M")
        actual_days = (last - first).days + 1
    else:
        start_str = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        actual_days = days

    a(("=" * W, "dim"))
    a(("", "normal"))
    for art_line in mascot["art"]:
        a((_ctr(art_line), "title"))
    a((_ctr(mascot["title"]), "heading"))
    a(("=" * W, "dim"))
    a(("", "normal"))
    a((f"  Customer:  {user}", "normal"))
    a((f"  Period:    {start_str} -> {end_str}", "normal"))
    a((f"  Days:      {actual_days}", "normal"))
    a(("", "normal"))

    # Order summary
    a(("-" * W, "dim"))
    a((_ctr("ORDER SUMMARY"), "heading"))
    a(("-" * W, "dim"))
    a(("", "normal"))

    total = stats["total_jobs"]
    a((_right("  Jobs submitted", f"{total:,}"), "normal"))
    a((_right("    Completed", f"{stats['completed']:,}"), "normal"))
    a((_right("    Failed", f"{stats['failed']:,}"),
       "highlight" if stats["failed"] > 0 else "normal"))
    if stats["cancelled"]:
        a((_right("    Cancelled", f"{stats['cancelled']:,}"), "dim"))
    if stats.get("timeout", 0):
        a((_right("    Timed out", f"{stats['timeout']:,}"), "dim"))
    a(("", "normal"))

    pct = (stats["completed"] / total * 100) if total else 0
    a((f"  Success: {_bar(stats['completed'], total, 28)} {pct:.0f}%", "bar"))
    a(("", "normal"))

    # Compute charges
    a(("-" * W, "dim"))
    a((_ctr("COMPUTE CHARGES"), "heading"))
    a(("-" * W, "dim"))
    a(("", "normal"))
    a((_right("  CPU time", f"{_fmt(stats['total_cpu_hours'])} core-hrs"), "normal"))
    if stats["total_gpu_hours"] > 0:
        a((_right("  GPU time", f"{_fmt(stats['total_gpu_hours'])} GPU-hrs"), "normal"))
        for gt, gh in sorted(stats["gpu_hours_by_type"].items()):
            a((_right(f"    {gt.upper()}", f"{_fmt(gh)} hrs"), "dim"))
    a((_right("  Wall time", f"{_fmt(stats['total_wall_hours'])} hrs"), "dim"))
    a((_right("  Memory", f"{_fmt(stats['total_mem_gb_hours'])} GB-hrs"), "dim"))
    a(("", "normal"))

    # Energy
    a((_right("  Energy (CPU)", f"{_fmt(nrg['cpu_kwh'])} kWh"), "normal"))
    if nrg["gpu_kwh"] > 0:
        a((_right("  Energy (GPU)", f"{_fmt(nrg['gpu_kwh'])} kWh"), "normal"))
    a((_right("  Cooling overhead", f"x{1.3}"), "dim"))
    a(("  " + "-" * (W - 4), "dim"))
    a((_right("  TOTAL ENERGY", f"{_fmt(nrg['total_kwh'])} kWh"), "highlight"))
    a((_right("  CO2 emitted", f"{_fmt(nrg['co2_kg'])} kg"), "normal"))
    a(("", "normal"))

    # AWS cost
    a(("-" * W, "dim"))
    a((_ctr("AWS PRICE CHECK (on-demand)"), "heading"))
    a(("-" * W, "dim"))
    a(("", "normal"))
    a((_right("  Compute (CPU)", f"${costs['cpu']:,.2f}"), "normal"))
    if costs["gpu"] > 0:
        a((_right("  Compute (GPU)", f"${costs['gpu']:,.2f}"), "normal"))
    a((_right("  Memory", f"${costs['mem']:,.2f}"), "dim"))
    a(("  " + "-" * (W - 4), "dim"))
    a((_right("  TOTAL", f"${costs['total']:,.2f}"), "highlight"))
    a(("", "normal"))

    # Fun conversion (single, rotatable)
    a(("*" * W, "dim"))
    a((_ctr("BUT ACTUALLY..."), "heading"))
    a(("*" * W, "dim"))
    a(("", "normal"))

    conv = CONVERSIONS[conv_idx % len(CONVERSIONS)]
    count = convert(nrg["total_kwh"], nrg["co2_kg"], stats["total_mem_gb_hours"], conv)

    a((_ctr(f"{conv['icon']}  {_fmt(count)}"), "conversion"))
    a((_ctr(conv["label"]), "conversion"))
    a(("", "normal"))
    a((_ctr(f'"{conv["tagline"]}"'), "roast"))
    a(("", "normal"))
    idx_display = conv_idx % len(CONVERSIONS) + 1
    cat = conv.get("category", "")
    a((_ctr(f"[{idx_display}/{len(CONVERSIONS)}] ({cat})"), "dim"))
    a(("", "normal"))

    # Footer
    a(("=" * W, "dim"))
    a((_ctr("THANK YOU FOR COMPUTING"), "title"))
    a((_ctr("Please come again."), "dim"))
    a((_ctr("No refunds on failed jobs."), "dim"))
    a(("=" * W, "dim"))

    return lines


def build_heatmap_page(stats, days, term_width=None):
    """Verbal activity report: weekly bars, day-of-week pattern, hour pattern."""
    lines = []
    a = lines.append
    daily = stats.get("daily", {})

    a(("=" * W, "dim"))
    a((_ctr("ACTIVITY REPORT"), "title"))
    a(("=" * W, "dim"))
    a(("", "normal"))

    if not daily:
        a((_ctr("No activity data available."), "dim"))
        return lines

    end = datetime.now()
    start = end - timedelta(days=min(days, 365))

    # ── Weekly breakdown with bars ───────────────────────────────────

    a((_ctr("WEEKLY BREAKDOWN"), "heading"))
    a(("  " + "-" * (W - 4), "dim"))

    # Bucket daily counts into weeks
    cur = start - timedelta(days=start.weekday())  # align to Monday
    weeks = []
    while cur <= end:
        week_end = cur + timedelta(days=6)
        count = 0
        for i in range(7):
            d = cur + timedelta(days=i)
            if start <= d <= end:
                count += daily.get(d.strftime("%Y-%m-%d"), 0)
        label = f"{cur.strftime('%b %d')}-{week_end.strftime('%d')}"
        weeks.append((label, count))
        cur += timedelta(days=7)

    max_week = max((c for _, c in weeks), default=1) or 1
    bar_w = 20
    for label, count in weeks:
        n = int(count / max_week * bar_w)
        bar = "#" * n + "." * (bar_w - n)
        peak = " <-" if count == max_week and count > 0 else ""
        a((f"  {label:>12}  [{bar}] {count:>5}{peak}", "bar"))

    a(("", "normal"))

    # ── Day-of-week pattern (aggregate) ──────────────────────────────

    a((_ctr("DAY OF WEEK"), "heading"))
    a(("  " + "-" * (W - 4), "dim"))

    by_dow = stats.get("submissions_by_dow", {})
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]
    max_dow = max(by_dow.values()) if by_dow else 1
    max_dow = max_dow or 1
    bar_w = 18

    for i, name in enumerate(day_names):
        count = by_dow.get(i, 0)
        n = int(count / max_dow * bar_w) if max_dow else 0
        bar = "#" * n + "." * (bar_w - n)
        peak = " <-" if count == max_dow and count > 0 else ""
        attr = "dim" if i >= 5 else "bar"
        a((f"  {name:<11} [{bar}] {count:>5}{peak}", attr))

    a(("", "normal"))

    # ── Hour-of-day pattern ──────────────────────────────────────────

    by_hour = stats.get("submissions_by_hour", {})
    if by_hour:
        a((_ctr("TIME OF DAY"), "heading"))
        a(("  " + "-" * (W - 4), "dim"))

        max_hr = max(by_hour.values()) if by_hour else 1
        max_hr = max_hr or 1

        # Compact: show 4-hour buckets
        buckets = [
            ("12am-4am",  range(0, 4)),
            (" 4am-8am",  range(4, 8)),
            (" 8am-12pm", range(8, 12)),
            ("12pm-4pm",  range(12, 16)),
            (" 4pm-8pm",  range(16, 20)),
            (" 8pm-12am", range(20, 24)),
        ]
        bucket_counts = []
        for label, hrs in buckets:
            c = sum(by_hour.get(h, 0) for h in hrs)
            bucket_counts.append((label, c))

        max_bucket = max(c for _, c in bucket_counts) or 1
        bar_w = 20
        for label, count in bucket_counts:
            n = int(count / max_bucket * bar_w)
            bar = "#" * n + "." * (bar_w - n)
            is_night = label.startswith("12am") or label.startswith(" 8pm")
            attr = "dim" if is_night else "bar"
            a((f"  {label:>10}  [{bar}] {count:>5}", attr))

        a(("", "normal"))

    # ── Summary stats ────────────────────────────────────────────────

    a(("-" * W, "dim"))
    a((_ctr("STATS"), "heading"))
    a(("-" * W, "dim"))

    total_days_in_range = (end - start).days + 1
    active_days = sum(1 for v in daily.values() if v > 0)
    streak = _longest_streak(daily, start, end)

    a((_right("  Active days", f"{active_days}/{total_days_in_range}"), "normal"))
    if streak > 1:
        a((_right("  Longest streak", f"{streak} days"), "highlight"))

    if daily:
        peak_day = max(daily.items(), key=lambda x: x[1])
        a((_right("  Peak day", f"{peak_day[0]} ({peak_day[1]:,})"), "highlight"))

        quietest = min(((k, v) for k, v in daily.items() if v > 0), key=lambda x: x[1])
        a((_right("  Quietest active day", f"{quietest[0]} ({quietest[1]})"), "dim"))

    total_submissions = sum(daily.values())
    if active_days > 0:
        avg = total_submissions / active_days
        a((_right("  Avg jobs/active day", f"{avg:.1f}"), "normal"))

    a(("", "normal"))
    return lines


def _longest_streak(daily, start, end):
    """Find longest consecutive days with at least 1 job."""
    cur = start
    streak = 0
    best = 0
    while cur <= end:
        key = cur.strftime("%Y-%m-%d")
        if daily.get(key, 0) > 0:
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
        cur += timedelta(days=1)
    return best


def build_monthly_page(stats):
    """Monthly breakdown page."""
    lines = []
    a = lines.append

    a(("=" * W, "dim"))
    a((_ctr("MONTHLY LEDGER"), "title"))
    a(("=" * W, "dim"))
    a(("", "normal"))

    monthly = stats.get("monthly", {})
    if not monthly:
        a((_ctr("No monthly data available."), "dim"))
        return lines

    a(("  Month     Jobs   OK   Fail   CPU-hrs", "heading"))
    a(("  " + "-" * (W - 4), "dim"))

    max_jobs = max((m["jobs"] for m in monthly.values()), default=1)

    for mk in sorted(monthly.keys()):
        m = monthly[mk]
        bar_w = 12
        bar_n = int(m["jobs"] / max_jobs * bar_w) if max_jobs else 0
        bar = "#" * bar_n + "." * (bar_w - bar_n)

        line = (
            f"  {mk}  {m['jobs']:>5} {m['completed']:>5} {m['failed']:>5}"
            f"  {_fmt(m['cpu_hours']):>8}"
        )
        a((line, "normal"))
        a((f"           [{bar}]", "bar"))

    a(("", "normal"))

    sorted_months = sorted(monthly.items(), key=lambda x: x[1]["jobs"], reverse=True)
    if sorted_months:
        peak = sorted_months[0]
        a(("-" * W, "dim"))
        a((f"  Peak month: {peak[0]} ({peak[1]['jobs']:,} jobs)", "highlight"))
        if peak[1]["failed"] > peak[1]["jobs"] * 0.3:
            a(("  ...and it was rough.", "roast"))
    a(("", "normal"))
    return lines


def build_roast_page(roasts, roast_idx):
    """Roast page -- shows one roast at a time with mini job receipt."""
    lines = []
    a = lines.append

    a(("=" * W, "dim"))
    a((_ctr("YOUR PERFORMANCE REVIEW"), "title"))
    a((_ctr("(the cluster has thoughts)"), "dim"))
    a(("=" * W, "dim"))
    a(("", "normal"))
    a(("", "normal"))

    if roasts:
        idx = roast_idx % len(roasts)
        roast = roasts[idx]
        # Support both old str format and new dict format
        if isinstance(roast, dict):
            text = roast["text"]
            ctx = roast.get("context")
        else:
            text = roast
            ctx = None

        for rline in text.split("\n"):
            a((rline, "roast"))

        a(("", "normal"))

        # Mini POS receipt panel for job context
        if ctx:
            a(("  " + "~" * (W - 4), "dim"))
            a(("  | RELATED JOB INFO" + " " * (W - 23) + " |", "dim"))
            a(("  |" + "-" * (W - 6) + "|", "dim"))
            if ctx.get("job_id"):
                jid = ctx["job_id"]
                a((f"  |  Job ID:  {jid:<{W-18}}|", "dim"))
            if ctx.get("name"):
                nm = ctx["name"]
                a((f"  |  Name:    {nm:<{W-18}}|", "dim"))
            if ctx.get("detail"):
                dt = ctx["detail"]
                a((f"  |  Detail:  {dt:<{W-18}}|", "dim"))
            a(("  " + "~" * (W - 4), "dim"))

        a(("", "normal"))
        a((_ctr(f"[{idx + 1}/{len(roasts)}]"), "dim"))
    else:
        a((_ctr("Nothing to roast. Suspiciously clean."), "dim"))

    a(("", "normal"))
    return lines


BLOCKS = " ▁▂▃▄▅▆▇█"  # 9 levels: 0 = empty, 8 = full


def _moving_avg(values, window=7):
    """Compute simple moving average, returning same-length list (None-padded at start)."""
    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(None)
        else:
            result.append(sum(values[i - window + 1:i + 1]) / window)
    return result


def _sparkline(values, width, max_val):
    """Render a list of values as a sparkline string using block characters."""
    if max_val <= 0:
        return " " * width
    chars = []
    for v in values:
        if v is None:
            chars.append(" ")
        else:
            level = int(min(v / max_val, 1.0) * 8)
            chars.append(BLOCKS[level])
    return "".join(chars)


# Line chart overlay layers
LINE_LAYERS = [
    {"key": "daily", "label": "Jobs submitted", "unit": "jobs"},
    {"key": "daily_failed", "label": "Failed jobs", "unit": "fails"},
    {"key": "daily_cpu_hours", "label": "CPU hours", "unit": "cpu-hrs"},
]


def build_linechart_page(stats, days, layer_idx=0):
    """ASCII line chart of daily activity with switchable overlay layers."""
    lines = []
    a = lines.append

    layer = LINE_LAYERS[layer_idx % len(LINE_LAYERS)]
    daily_data = stats.get(layer["key"], {})

    a(("=" * W, "dim"))
    a((_ctr("TREND LINE"), "title"))
    a(("=" * W, "dim"))
    a(("", "normal"))

    # Layer selector
    parts = []
    for i, ly in enumerate(LINE_LAYERS):
        if i == layer_idx % len(LINE_LAYERS):
            parts.append(f"[{ly['label']}]")
        else:
            parts.append(f" {ly['label']} ")
    a((_ctr("  ".join(parts)), "heading"))
    a((_ctr("tab to switch layer"), "dim"))
    a(("", "normal"))

    if not stats.get("daily", {}):
        a((_ctr("No activity data available."), "dim"))
        return lines

    # Build date range
    end = datetime.now()
    start = end - timedelta(days=min(days, 365))

    # Collect values for each day in range
    date_list = []
    values = []
    cur = start
    while cur <= end:
        key = cur.strftime("%Y-%m-%d")
        date_list.append(cur)
        values.append(daily_data.get(key, 0))
        cur += timedelta(days=1)

    if not values:
        a((_ctr("No data in range."), "dim"))
        return lines

    max_val = max(values) if values else 1
    max_val = max_val or 1
    avg = _moving_avg(values, window=7)
    max_avg = max((v for v in avg if v is not None), default=1) or 1
    # Use the same scale for both raw and moving average
    scale_max = max(max_val, max_avg)

    # ── Vertical chart (rows = value levels, cols = days) ────────
    # Show a chart that's W-8 columns wide; if more days, bucket them
    chart_w = W - 8  # leave room for y-axis labels
    n_days = len(values)

    if n_days <= chart_w:
        # One column per day
        plot_vals = values
        plot_avg = avg
        plot_dates = date_list
    else:
        # Bucket days into chart_w bins
        bucket_size = n_days / chart_w
        plot_vals = []
        plot_avg = []
        plot_dates = []
        for i in range(chart_w):
            lo = int(i * bucket_size)
            hi = int((i + 1) * bucket_size)
            bucket = values[lo:hi]
            plot_vals.append(sum(bucket) / len(bucket) if bucket else 0)
            avg_bucket = [v for v in avg[lo:hi] if v is not None]
            plot_avg.append(sum(avg_bucket) / len(avg_bucket) if avg_bucket else None)
            plot_dates.append(date_list[lo])

    # ── Row-based vertical chart ─────────────────────────────────
    chart_h = 10  # number of rows
    a(("-" * W, "dim"))

    # Y-axis labels at top, middle, bottom
    for row in range(chart_h, 0, -1):
        threshold = (row / chart_h) * scale_max
        row_chars = []
        for i, v in enumerate(plot_vals):
            val_level = v / scale_max * chart_h if scale_max else 0
            if val_level >= row:
                row_chars.append("█")
            elif val_level >= row - 0.5:
                row_chars.append("▄")
            else:
                # Check if moving average crosses this row
                ma = plot_avg[i] if i < len(plot_avg) else None
                if ma is not None:
                    ma_level = ma / scale_max * chart_h
                    if abs(ma_level - row + 0.5) < 0.6:
                        row_chars.append("─")
                    else:
                        row_chars.append(" ")
                else:
                    row_chars.append(" ")

        bar_str = "".join(row_chars)
        if row == chart_h:
            label = f"{_fmt(scale_max):>5}"
        elif row == chart_h // 2:
            label = f"{_fmt(scale_max / 2):>5}"
        elif row == 1:
            label = "    0"
        else:
            label = "     "
        a((f"{label} │{bar_str}", "bar"))

    # X-axis
    x_axis = "─" * len(plot_vals)
    a((f"      └{x_axis}", "dim"))

    # Date markers on x-axis
    if plot_dates:
        # Place month markers
        last_month = None
        month_labels = []
        for i, d in enumerate(plot_dates):
            m = d.strftime("%b")
            if m != last_month:
                month_labels.append((i, m))
                last_month = m
        # Render month labels (avoid overlap)
        label_row = list(" " * len(plot_dates))
        for pos, lbl in month_labels:
            if pos + len(lbl) <= len(label_row):
                for ci, ch in enumerate(lbl):
                    label_row[pos + ci] = ch
        a((f"       {''.join(label_row)}", "dim"))

    a(("", "normal"))

    # ── Sparkline (compact single-row view) ──────────────────────
    a((_ctr("SPARKLINE"), "heading"))
    a(("  " + "-" * (W - 4), "dim"))

    spark = _sparkline(plot_vals, len(plot_vals), scale_max)
    a((f"  raw: {spark}", "bar"))

    avg_spark = _sparkline(plot_avg, len(plot_avg), scale_max)
    a((f"  7d~: {avg_spark}", "highlight"))

    a(("", "normal"))

    # ── Summary stats ────────────────────────────────────────────
    a(("-" * W, "dim"))
    a((_ctr("TREND STATS"), "heading"))
    a(("-" * W, "dim"))

    total = sum(values)
    active_days = sum(1 for v in values if v > 0)
    peak_val = max(values) if values else 0
    peak_idx = values.index(peak_val) if peak_val > 0 else 0
    peak_date = date_list[peak_idx].strftime("%Y-%m-%d") if date_list else "N/A"

    a((_right(f"  Total {layer['unit']}", f"{_fmt(total)}"), "normal"))
    a((_right("  Active days", f"{active_days}/{len(values)}"), "normal"))
    a((_right("  Peak", f"{_fmt(peak_val)} on {peak_date}"), "highlight"))

    if active_days > 0:
        avg_active = total / active_days
        a((_right(f"  Avg/active day", f"{_fmt(avg_active)} {layer['unit']}"), "normal"))

    # Trend direction: compare first half avg to second half avg
    mid = len(values) // 2
    if mid > 0:
        first_half = sum(values[:mid]) / mid
        second_half = sum(values[mid:]) / max(len(values) - mid, 1)
        if first_half > 0:
            change_pct = ((second_half - first_half) / first_half) * 100
            if change_pct > 10:
                a((_right("  Trend", f"↑ +{change_pct:.0f}%"), "highlight"))
            elif change_pct < -10:
                a((_right("  Trend", f"↓ {change_pct:.0f}%"), "dim"))
            else:
                a((_right("  Trend", "→ stable"), "normal"))

    a(("", "normal"))
    a((_ctr("█ raw data   ─ 7-day avg"), "dim"))
    a(("", "normal"))

    return lines

def build_fairshare_page(fs_data, user):
    """Fair-share / priority standing page, with a lab leaderboard and an
    optional anonymized cluster-wide percentile.

    Scoped deliberately to the user's own Slurm account -- see fairshare.py.
    The cluster percentile (fs_data["cluster"]) is opt-in via --cluster-rank
    and never carries any other user's name or usage, only the caller's own
    rank among everyone.
    """
    lines = []
    a = lines.append

    a(("=" * W, "dim"))
    a((_ctr("FAIR SHARE"), "title"))
    a((_ctr("where you stand in the priority queue"), "dim"))
    a(("=" * W, "dim"))
    a(("", "normal"))

    if not fs_data:
        a((_ctr("Fair share data isn't available here."), "dim"))
        a((_ctr("(sshare/sacctmgr not found, or this isn't a Slurm cluster)"), "dim"))
        a(("", "normal"))
        return lines

    self_row = fs_data["self"]
    account = fs_data["account"]
    board = fs_data["leaderboard"]
    rank = fs_data.get("rank")
    fs = self_row.get("fairshare")
    eff = self_row.get("effectv_usage", 0.0)

    a((f"  Account:  {account}", "normal"))
    if rank and board:
        a((f"  Rank:     #{rank} of {len(board)} in {account}", "normal"))
    a(("", "normal"))

    a(("-" * W, "dim"))
    a((_ctr("PRIORITY SCORE"), "heading"))
    a(("-" * W, "dim"))
    a(("", "normal"))

    if fs is not None:
        a((_ctr(f"FairShare: {fs:.4f}"), "conversion"))
        bar_n = int(min(max(fs, 0.0), 1.0) * 30)
        a((_ctr("[" + "#" * bar_n + "." * (30 - bar_n) + "]"), "bar"))
        a(("", "normal"))
        if fs < 0.2:
            a((_ctr("Low priority: you've used more than your"), "roast"))
            a((_ctr("share, so others get scheduled ahead of you."), "roast"))
        elif fs < 0.5:
            a((_ctr("Middling priority: you've used roughly"), "roast"))
            a((_ctr("your fair share, give or take."), "roast"))
        else:
            a((_ctr("High priority: you've used less than your"), "roast"))
            a((_ctr("share, so you jump the queue when it matters."), "roast"))
        a(("", "normal"))
        a((_ctr("1.0 = you've barely used your account's time"), "dim"))
        a((_ctr("0.0 = you've used far more than your share"), "dim"))
    else:
        a((_ctr("No fairshare score yet -- no usage on record."), "dim"))
    a(("", "normal"))

    a((_right("  Effective usage", f"{eff * 100:.1f}% of {account}"), "normal"))
    a(("", "normal"))

    if board:
        a(("-" * W, "dim"))
        a((_ctr(f"{account.upper()} LEADERBOARD"), "heading"))
        a((_ctr("each member's share of the account's usage"), "dim"))
        a(("-" * W, "dim"))
        a(("", "normal"))

        max_eff = max((r["effectv_usage"] for r in board), default=0) or 1
        for i, r in enumerate(board, 1):
            is_self = r["user"] == user
            n = int(r["effectv_usage"] / max_eff * 18) if max_eff else 0
            bar = "#" * n + "." * (18 - n)
            marker = " <-" if is_self else ""
            pct = r["effectv_usage"] * 100
            label = f"  {i:>2}. {r['user']:<12s} [{bar}] {pct:>5.1f}%{marker}"
            a((label, "highlight" if is_self else "normal"))
        a(("", "normal"))

        if rank == 1 and len(board) > 1 and eff > 0.5:
            a((_ctr(f"You're carrying {eff * 100:.0f}% of {account}'s"), "roast"))
            a((_ctr("compute usage. Your labmates say thanks."), "roast"))
        elif rank == 1 and len(board) > 1:
            a((_ctr(f"#1 in {account}. Wear it with pride."), "roast"))
        elif len(board) == 1:
            a((_ctr("You're the only member of this account."), "dim"))
            a((_ctr("Undisputed champion by default."), "dim"))
        a(("", "normal"))

    cluster = fs_data.get("cluster")
    if cluster:
        pct = min(max(cluster["percentile"], 0.0), 100.0)
        n_users = cluster["total_users"]
        top_pct = max(100.0 - pct, 0.1)

        a(("-" * W, "dim"))
        a((_ctr("CLUSTER STANDING"), "heading"))
        a((_ctr("anonymized -- no other user's data is shown"), "dim"))
        a(("-" * W, "dim"))
        a(("", "normal"))
        a((_ctr(f"Top {top_pct:.0f}% of {n_users:,} users cluster-wide"), "conversion"))
        bar_n = int(pct / 100 * 30)
        a((_ctr("[" + "#" * bar_n + "." * (30 - bar_n) + "]"), "bar"))
        a(("", "normal"))
        a((_ctr(f"You've used more compute than {pct:.0f}% of"), "dim"))
        a((_ctr(f"the {n_users:,} users active on this cluster."), "dim"))
        a(("", "normal"))

    return lines


def build_top_jobs_page(stats):
    """Top jobs and failure hall of shame."""
    lines = []
    a = lines.append

    a(("=" * W, "dim"))
    a((_ctr("TOP 10 HUNGRIEST JOBS"), "title"))
    a(("=" * W, "dim"))
    a(("", "normal"))
    a(("  #   Job Name                  CPU-hrs", "heading"))
    a(("  " + "-" * (W - 4), "dim"))

    for i, (name, cpu_hrs, jid) in enumerate(stats["top_jobs_cpu"][:10], 1):
        short = (name[:26] + "..") if len(name) > 28 else name
        a((f"  {i:>2}.  {short:<28s} {_fmt(cpu_hrs):>8}", "normal"))

    a(("", "normal"))

    fast = stats.get("fastest_fails", [])
    if fast:
        a(("-" * W, "dim"))
        a((_ctr("SPEEDRUN HALL OF SHAME"), "heading"))
        a((_ctr(f"{len(fast)} jobs failed in under 10 seconds"), "dim"))
        a(("-" * W, "dim"))
        a(("", "normal"))
        shown = {}
        for j in fast[:20]:
            shown[j["name"]] = shown.get(j["name"], 0) + 1
        for n, c in sorted(shown.items(), key=lambda x: -x[1])[:5]:
            short = (n[:30] + "..") if len(n) > 32 else n
            a((f"    {short:<32s} x{c}", "highlight"))
        a(("", "normal"))

    slow = stats.get("slowest_fails", [])
    if slow:
        a(("-" * W, "dim"))
        a((_ctr("SLOW AND PAINFUL"), "heading"))
        a(("-" * W, "dim"))
        for j in slow[:5]:
            short = (j["name"][:26] + "..") if len(j["name"]) > 28 else j["name"]
            a((f"    {short:<28s} ran {_fmt_time(j['elapsed_sec']):>8}", "highlight"))
        a(("", "normal"))

    return lines


def render_snap(user, days, stats, nrg, costs, roasts, conv_idx=0, fs_data=None):
    """Plain-text receipt for sharing."""
    pages = build_receipt_page(user, days, stats, nrg, costs, conv_idx)
    out = [text for text, _ in pages]

    if fs_data:
        out.append("")
        fs_pages = build_fairshare_page(fs_data, user)
        out.extend(text for text, _ in fs_pages)

    if roasts:
        out.append("")
        out.append("-" * W)
        out.append(_ctr("P.S. from the cluster:"))
        out.append("-" * W)
        roast = random.choice(roasts)
        text = roast["text"] if isinstance(roast, dict) else roast
        for line in text.split("\n"):
            out.append(line)
        out.append("")

    out.append("=" * W)
    out.append(_ctr("Generated by slurm-receipt"))
    out.append(_ctr("pip install slurm-receipt"))
    out.append("=" * W)
    return "\n".join(out)


# ── TUI main loop ───────────────────────────────────────────────────

def run_tui(user, days, stats, nrg, costs, roasts, fs_data=None):
    """Launch interactive curses TUI."""
    snap_path = os.path.join(os.path.expanduser("~"), f"slurm_receipt_{days}d.txt")

    # Auto-save on entry (graceful if home is not writable)
    try:
        snap = render_snap(user, days, stats, nrg, costs, roasts, fs_data=fs_data)
        with open(snap_path, "w") as f:
            f.write(snap)
    except OSError:
        snap_path = None  # can't write, skip save

    curses.wrapper(_tui_main, user, days, stats, nrg, costs, roasts, snap_path, fs_data)

    # After TUI exits, print where the receipt was saved
    if snap_path:
        sys.stderr.write(f"\n  Receipt saved to: {snap_path}\n\n")
    else:
        sys.stderr.write("\n")


def _tui_main(stdscr, user, days, stats, nrg, costs, roasts, snap_path, fs_data=None):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()

    # Mouse: click + scroll only (no motion tracking -- avoids flicker)
    curses.mousemask(
        curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED
        | curses.BUTTON4_PRESSED | 0x200000
    )

    curses.init_pair(1, curses.COLOR_YELLOW, -1)
    curses.init_pair(2, curses.COLOR_CYAN, -1)
    curses.init_pair(3, 8, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)
    curses.init_pair(6, curses.COLOR_WHITE, -1)
    curses.init_pair(7, curses.COLOR_BLUE, -1)

    ATTRS = {
        "title":      curses.color_pair(1) | curses.A_BOLD,
        "heading":    curses.color_pair(2) | curses.A_BOLD,
        "dim":        curses.color_pair(3),
        "highlight":  curses.color_pair(4) | curses.A_BOLD,
        "normal":     curses.A_NORMAL,
        "roast":      curses.color_pair(5),
        "conversion": curses.color_pair(6) | curses.A_BOLD,
        "bar":        curses.color_pair(7),
    }

    conv_idx = 0
    roast_idx = 0
    layer_idx = 0
    page = "receipt"
    scroll = 0
    home_dir = os.path.expanduser("~")

    # Build roast pool for rotation
    all_roasts = list(roasts)
    for _ in range(4):
        for r in generate_roasts(stats):
            # Deduplicate by text
            r_text = r["text"] if isinstance(r, dict) else r
            existing = [
                (x["text"] if isinstance(x, dict) else x)
                for x in all_roasts
            ]
            if r_text not in existing:
                all_roasts.append(r)

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        # Build current page
        if page == "receipt":
            content = build_receipt_page(user, days, stats, nrg, costs, conv_idx)
        elif page == "heatmap":
            content = build_heatmap_page(stats, days)
        elif page == "line":
            content = build_linechart_page(stats, days, layer_idx)
        elif page == "monthly":
            content = build_monthly_page(stats)
        elif page == "roast":
            content = build_roast_page(all_roasts, roast_idx)
        elif page == "top":
            content = build_top_jobs_page(stats)
        elif page == "fairshare":
            content = build_fairshare_page(fs_data, user)
        else:
            content = build_receipt_page(user, days, stats, nrg, costs, conv_idx)

        max_scroll = max(0, len(content) - h + 2)
        scroll = max(0, min(scroll, max_scroll))

        # Render content
        for i, (text, attr_name) in enumerate(content[scroll:]):
            if i >= h - 1:
                break
            attr = ATTRS.get(attr_name, curses.A_NORMAL)
            pad_left = max(0, (w - W) // 2)
            display = text[:w - pad_left - 1].ljust(W)[:w - pad_left - 1]
            try:
                stdscr.addnstr(i, pad_left, display, w - pad_left - 1, attr)
            except curses.error:
                pass

        # Status bar
        scroll_pct = f" {int(scroll / max_scroll * 100)}%%" if max_scroll > 0 else ""
        if page == "receipt":
            fshare_key = " [f]airshare" if fs_data else ""
            status = f" [r]oast [m]onthly [h]eatmap [l]ine [t]op{fshare_key} [s]nap [<>]rotate{scroll_pct} [q]uit "
        elif page == "roast":
            status = f" [<>]rotate [b]ack [q]uit "
        elif page == "line":
            status = f" [tab]layer [b]ack [q]uit{scroll_pct} "
        else:
            status = f" [b]ack [q]uit{scroll_pct} "
        try:
            stdscr.addnstr(h - 1, 0, status.ljust(w)[:w-1], w - 1, curses.A_REVERSE)
        except curses.error:
            pass

        stdscr.noutrefresh()
        curses.doupdate()
        key = stdscr.getch()

        # Mouse
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & curses.BUTTON4_PRESSED:
                    scroll = max(0, scroll - 3)
                elif bstate & 0x200000:
                    scroll = min(max_scroll, scroll + 3)
                elif my == h - 1 and (bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED)):
                    if page == "receipt":
                        if _click_in(status, "[r]oast", mx):
                            page = "roast"; scroll = 0
                        elif _click_in(status, "[m]onthly", mx):
                            page = "monthly"; scroll = 0
                        elif _click_in(status, "[h]eatmap", mx):
                            page = "heatmap"; scroll = 0
                        elif _click_in(status, "[l]ine", mx):
                            page = "line"; scroll = 0
                        elif _click_in(status, "[t]op", mx):
                            page = "top"; scroll = 0
                        elif fs_data and _click_in(status, "[f]airshare", mx):
                            page = "fairshare"; scroll = 0
                        elif _click_in(status, "[s]nap", mx):
                            key = ord("s")
                        elif _click_in(status, "[<>]rotate", mx):
                            conv_idx = (conv_idx + 1) % len(CONVERSIONS)
                    elif page == "roast":
                        if _click_in(status, "[<>]rotate", mx):
                            roast_idx = (roast_idx + 1) % len(all_roasts)
                        elif _click_in(status, "[b]ack", mx):
                            page = "receipt"; scroll = 0
                    elif page == "line":
                        if _click_in(status, "[tab]layer", mx):
                            layer_idx = (layer_idx + 1) % len(LINE_LAYERS)
                        elif _click_in(status, "[b]ack", mx):
                            page = "receipt"; scroll = 0
                    else:
                        if _click_in(status, "[b]ack", mx):
                            page = "receipt"; scroll = 0
            except curses.error:
                pass
            if key == curses.KEY_MOUSE:
                continue

        # Keyboard
        if key in (ord("q"), ord("Q")):
            break
        elif key == ord("r") and page == "receipt":
            page = "roast"; scroll = 0
        elif key == ord("m") and page == "receipt":
            page = "monthly"; scroll = 0
        elif key == ord("h") and page == "receipt":
            page = "heatmap"; scroll = 0
        elif key == ord("l") and page == "receipt":
            page = "line"; scroll = 0
        elif key == ord("\t") and page == "line":
            layer_idx = (layer_idx + 1) % len(LINE_LAYERS)
        elif key == ord("t") and page == "receipt":
            page = "top"; scroll = 0
        elif key == ord("f") and page == "receipt" and fs_data:
            page = "fairshare"; scroll = 0
        elif key == ord("s") and page == "receipt":
            snap = render_snap(user, days, stats, nrg, costs, all_roasts, conv_idx, fs_data=fs_data)
            saved = False
            if snap_path:
                try:
                    with open(snap_path, "w") as f:
                        f.write(snap)
                    saved = True
                except OSError:
                    pass
            clip_method = _clipboard_copy(snap)
            if saved and clip_method:
                msg = f" Saved + copied ({clip_method})! "
            elif saved:
                msg = f" Saved: ~/{os.path.basename(snap_path)} "
            elif clip_method:
                msg = f" Copied ({clip_method})! "
            else:
                msg = " Could not save or copy. "
            try:
                stdscr.addnstr(h // 2, max(0, (w - len(msg)) // 2),
                               msg, w - 1, curses.A_REVERSE | curses.A_BOLD)
                stdscr.refresh()
                curses.napms(1800)
            except curses.error:
                pass
            continue
        elif key == ord("b") and page != "receipt":
            page = "receipt"; scroll = 0
        elif key in (curses.KEY_RIGHT, ord(">"), ord(".")):
            if page == "receipt":
                conv_idx = (conv_idx + 1) % len(CONVERSIONS)
            elif page == "roast":
                roast_idx = (roast_idx + 1) % len(all_roasts)
        elif key in (curses.KEY_LEFT, ord("<"), ord(",")):
            if page == "receipt":
                conv_idx = (conv_idx - 1) % len(CONVERSIONS)
            elif page == "roast":
                roast_idx = (roast_idx - 1) % len(all_roasts)
        elif key in (curses.KEY_DOWN, ord("j")):
            scroll += 1
        elif key in (curses.KEY_UP, ord("k")):
            scroll = max(0, scroll - 1)
        elif key == curses.KEY_NPAGE:
            scroll += h // 2
        elif key == curses.KEY_PPAGE:
            scroll = max(0, scroll - h // 2)


def _click_in(bar_text, label, mx):
    """Check if mouse x position hits a status bar label."""
    pos = bar_text.find(label)
    return pos >= 0 and pos <= mx <= pos + len(label)
