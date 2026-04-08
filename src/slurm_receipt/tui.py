"""Interactive curses TUI with receipt aesthetic."""

import base64
import curses
import os
import random
from datetime import datetime, timedelta

from slurm_receipt.calc import CONVERSIONS, convert, get_mascot


def _osc52_copy(text):
    """Copy text to the user's local clipboard via OSC 52 escape sequence.

    This works over SSH -- the terminal interprets the escape and copies
    to its own clipboard. Supported by: iTerm2, kitty, alacritty,
    Windows Terminal, foot, WezTerm, tmux (with set -g set-clipboard on).
    Silently does nothing on unsupported terminals.
    """
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    # OSC 52 ; c ; <base64> ST
    sys.stdout.write(f"\033]52;c;{encoded}\a")
    sys.stdout.flush()


# Need sys for _osc52_copy
import sys


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


def build_receipt_page(user, days, stats, nrg, costs, conv_idx):
    """Build main receipt as list of (line_string, attr_name) tuples."""
    lines = []
    a = lines.append

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    start_str = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    mascot = get_mascot(stats["total_cpu_hours"], user)

    # ── Mascot header ──
    a(("=" * W, "dim"))
    a(("", "normal"))
    for art_line in mascot["art"]:
        a((_ctr(art_line), "title"))
    a((_ctr(mascot["title"]), "heading"))
    a(("=" * W, "dim"))
    a(("", "normal"))
    a((f"  Customer:  {user}", "normal"))
    a((f"  Period:    {start_str} -> {now_str}", "normal"))
    a((f"  Days:      {days}", "normal"))
    a(("", "normal"))

    # ── Order summary ──
    a(("-" * W, "dim"))
    a((_ctr("ORDER SUMMARY"), "heading"))
    a(("-" * W, "dim"))
    a(("", "normal"))

    total = stats["total_jobs"]
    a((_right("  Jobs submitted", f"{total:,}"), "normal"))
    a((_right("    Completed", f"{stats['completed']:,}"), "normal"))
    fail_attr = "highlight" if stats["failed"] > 0 else "normal"
    a((_right("    Failed", f"{stats['failed']:,}"), fail_attr))
    if stats["cancelled"]:
        a((_right("    Cancelled", f"{stats['cancelled']:,}"), "dim"))
    if stats.get("timeout", 0):
        a((_right("    Timed out", f"{stats['timeout']:,}"), "dim"))
    a(("", "normal"))

    pct = (stats["completed"] / total * 100) if total else 0
    bar = _bar(stats["completed"], total, 28)
    a((f"  Success: {bar} {pct:.0f}%", "bar"))
    a(("", "normal"))

    # ── Compute charges ──
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

    # ── Energy ──
    a((_right("  Energy (CPU)", f"{_fmt(nrg['cpu_kwh'])} kWh"), "normal"))
    if nrg["gpu_kwh"] > 0:
        a((_right("  Energy (GPU)", f"{_fmt(nrg['gpu_kwh'])} kWh"), "normal"))
    a((_right("  Cooling overhead", f"x{1.3}"), "dim"))
    a(("  " + "-" * (W - 4), "dim"))
    a((_right("  TOTAL ENERGY", f"{_fmt(nrg['total_kwh'])} kWh"), "highlight"))
    a((_right("  CO2 emitted", f"{_fmt(nrg['co2_kg'])} kg"), "normal"))
    a(("", "normal"))

    # ── Cloud costs ──
    a(("-" * W, "dim"))
    a((_ctr("CLOUD PRICE CHECK"), "heading"))
    a((_ctr("(if you had to pay on-demand)"), "dim"))
    a(("-" * W, "dim"))
    a(("", "normal"))
    for p in ("aws", "gcp"):
        c = costs[p]
        a((_right(f"  {p.upper()} total", f"${c['total']:,.2f}"), "highlight"))
    a(("", "normal"))

    # ── Fun conversion (single, rotatable) ──
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
    a((_ctr(f"[{idx_display}/{len(CONVERSIONS)}] ({cat})  < / > to browse"), "dim"))
    a(("", "normal"))

    # ── Footer ──
    a(("=" * W, "dim"))
    a((_ctr("THANK YOU FOR COMPUTING"), "title"))
    a((_ctr("Please come again."), "dim"))
    a((_ctr("No refunds on failed jobs."), "dim"))
    a(("=" * W, "dim"))
    a(("", "normal"))
    a((_ctr("[r]oast [m]onthly [t]op jobs [s]nap [q]uit"), "dim"))

    return lines


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
        a(("", "normal"))
        a((_ctr("[b]ack"), "dim"))
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

    # Monthly summary insights
    sorted_months = sorted(monthly.items(), key=lambda x: x[1]["jobs"], reverse=True)
    if sorted_months:
        peak = sorted_months[0]
        a(("-" * W, "dim"))
        a((f"  Peak month: {peak[0]} ({peak[1]['jobs']:,} jobs)", "highlight"))
        if peak[1]["failed"] > peak[1]["jobs"] * 0.3:
            a(("  ...and it was rough.", "roast"))
    a(("", "normal"))

    a(("-" * W, "dim"))
    a((_ctr("[b]ack to receipt"), "dim"))
    return lines


def build_roast_page(roasts):
    """Roast / performance review page."""
    lines = []
    a = lines.append

    a(("=" * W, "dim"))
    a((_ctr("YOUR PERFORMANCE REVIEW"), "title"))
    a((_ctr("(the cluster has thoughts)"), "dim"))
    a(("=" * W, "dim"))
    a(("", "normal"))

    for roast in roasts:
        for rline in roast.split("\n"):
            a((rline, "roast"))
        a(("", "normal"))

    a(("-" * W, "dim"))
    a((_ctr("[b]ack to receipt"), "dim"))
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

    # Fastest fails
    fast = stats.get("fastest_fails", [])
    if fast:
        a(("-" * W, "dim"))
        a((_ctr("SPEEDRUN HALL OF SHAME"), "heading"))
        a((_ctr(f"{len(fast)} jobs failed in under 10 seconds"), "dim"))
        a(("-" * W, "dim"))
        a(("", "normal"))
        shown = {}
        for j in fast[:20]:
            n = j["name"]
            shown[n] = shown.get(n, 0) + 1
        for n, c in sorted(shown.items(), key=lambda x: -x[1])[:5]:
            short = (n[:30] + "..") if len(n) > 32 else n
            a((f"    {short:<32s} x{c}", "highlight"))
        a(("", "normal"))

    # Slow painful deaths
    slow = stats.get("slowest_fails", [])
    if slow:
        a(("-" * W, "dim"))
        a((_ctr("SLOW AND PAINFUL"), "heading"))
        a((_ctr("(jobs that ran forever, then failed)"), "dim"))
        a(("-" * W, "dim"))
        for j in slow[:5]:
            short = (j["name"][:26] + "..") if len(j["name"]) > 28 else j["name"]
            a((f"    {short:<28s} ran {_fmt_time(j['elapsed_sec']):>8}", "highlight"))
        a(("", "normal"))

    a(("-" * W, "dim"))
    a((_ctr("[b]ack to receipt"), "dim"))
    return lines


def render_snap(user, days, stats, nrg, costs, roasts, conv_idx=0):
    """Plain-text receipt for copy-paste or screenshot sharing."""
    pages = build_receipt_page(user, days, stats, nrg, costs, conv_idx)
    out = []
    for text, _ in pages:
        if "[r]oast" in text and "[m]onthly" in text:
            continue
        if "< / > to browse" in text:
            continue
        out.append(text)

    # Append one random roast
    if roasts:
        out.append("")
        out.append("-" * W)
        out.append(_ctr("P.S. from the cluster:"))
        out.append("-" * W)
        roast = random.choice(roasts)
        for line in roast.split("\n"):
            out.append(line)
        out.append("")

    out.append("=" * W)
    out.append(_ctr("Generated by slurm-receipt"))
    out.append(_ctr("pip install slurm-receipt"))
    out.append("=" * W)
    return "\n".join(out)


def run_tui(user, days, stats, nrg, costs, roasts):
    """Launch interactive curses TUI."""
    curses.wrapper(_tui_main, user, days, stats, nrg, costs, roasts)


def _tui_main(stdscr, user, days, stats, nrg, costs, roasts):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()

    # Enable mouse support
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    # Some terminals need this escape to enable mouse tracking
    print("\033[?1003h", end="", flush=True)

    curses.init_pair(1, curses.COLOR_YELLOW, -1)   # title
    curses.init_pair(2, curses.COLOR_CYAN, -1)     # heading
    curses.init_pair(3, 8, -1)                      # dim
    curses.init_pair(4, curses.COLOR_GREEN, -1)    # highlight
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)  # roast
    curses.init_pair(6, curses.COLOR_WHITE, -1)    # conversion
    curses.init_pair(7, curses.COLOR_BLUE, -1)     # bar

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
    page = "receipt"
    scroll = 0
    home_dir = os.path.expanduser("~")

    # Status bar button regions for mouse click detection
    # (label, action, page_filter)
    RECEIPT_BUTTONS = [
        ("r:roast", "roast", "receipt"),
        ("m:monthly", "monthly", "receipt"),
        ("t:top", "top", "receipt"),
        ("s:snap", "snap", "receipt"),
        ("<:prev", "prev", "receipt"),
        (">:next", "next", "receipt"),
    ]

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        if page == "receipt":
            content = build_receipt_page(user, days, stats, nrg, costs, conv_idx)
        elif page == "monthly":
            content = build_monthly_page(stats)
        elif page == "roast":
            content = build_roast_page(roasts)
        elif page == "top":
            content = build_top_jobs_page(stats)
        else:
            content = build_receipt_page(user, days, stats, nrg, costs, conv_idx)

        max_scroll = max(0, len(content) - h + 2)
        scroll = max(0, min(scroll, max_scroll))

        for i, (text, attr_name) in enumerate(content[scroll:]):
            row = i
            if row >= h - 1:
                break
            attr = ATTRS.get(attr_name, curses.A_NORMAL)
            pad_left = max(0, (w - W) // 2)
            try:
                stdscr.addnstr(row, pad_left, text[:w - pad_left - 1], w - pad_left - 1, attr)
            except curses.error:
                pass

        # Status bar with scroll indicator
        scroll_pct = ""
        if max_scroll > 0:
            pct = int(scroll / max_scroll * 100)
            scroll_pct = f" [{pct}%]"

        if page == "receipt":
            status = f" q:quit | arrows:scroll/rotate | r m t s{scroll_pct} "
        else:
            status = f" q:quit | b:back | arrows:scroll{scroll_pct} "
        try:
            stdscr.addnstr(h - 1, 0, status.ljust(w)[:w-1], w - 1, curses.A_REVERSE)
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()

        # ── Mouse events ──
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                # Scroll wheel
                if bstate & curses.BUTTON4_PRESSED:  # scroll up
                    scroll = max(0, scroll - 3)
                elif bstate & 0x200000:  # BUTTON5_PRESSED / scroll down
                    scroll = min(max_scroll, scroll + 3)
                # Click on status bar
                elif my == h - 1 and (bstate & curses.BUTTON1_CLICKED
                                      or bstate & curses.BUTTON1_PRESSED):
                    bar_text = status.lower()
                    if page == "receipt":
                        # Detect which button was clicked by x position
                        for label, action, _ in RECEIPT_BUTTONS:
                            pos = bar_text.find(label[0])
                            if pos >= 0 and pos - 2 <= mx <= pos + len(label) + 2:
                                if action == "roast":
                                    page = "roast"; scroll = 0
                                elif action == "monthly":
                                    page = "monthly"; scroll = 0
                                elif action == "top":
                                    page = "top"; scroll = 0
                                elif action == "snap":
                                    key = ord("s")  # fall through to snap handler
                                elif action == "prev":
                                    conv_idx = (conv_idx - 1) % len(CONVERSIONS)
                                elif action == "next":
                                    conv_idx = (conv_idx + 1) % len(CONVERSIONS)
                                break
                    elif "b:back" in bar_text:
                        pos = bar_text.find("b")
                        if pos >= 0 and pos - 2 <= mx <= pos + 8:
                            page = "receipt"; scroll = 0
            except curses.error:
                pass
            if key == curses.KEY_MOUSE:
                continue

        # ── Keyboard events ──
        if key == ord("q") or key == ord("Q"):
            break
        elif key == ord("r") and page == "receipt":
            page = "roast"; scroll = 0
        elif key == ord("m") and page == "receipt":
            page = "monthly"; scroll = 0
        elif key == ord("t") and page == "receipt":
            page = "top"; scroll = 0
        elif key == ord("s") and page == "receipt":
            snap = render_snap(user, days, stats, nrg, costs, roasts, conv_idx)
            snap_path = os.path.join(home_dir, f"slurm_receipt_{days}d.txt")
            with open(snap_path, "w") as f:
                f.write(snap)
            # Copy to clipboard via OSC 52 (works over SSH)
            try:
                _osc52_copy(snap)
                msg = f" Saved + copied to clipboard! {snap_path} "
            except Exception:
                msg = f" Saved: {snap_path} "
            try:
                row_mid = h // 2
                col_mid = max(0, (w - len(msg)) // 2)
                stdscr.addnstr(row_mid, col_mid, msg, w - 1, curses.A_REVERSE | curses.A_BOLD)
                stdscr.refresh()
                curses.napms(1800)
            except curses.error:
                pass
            continue
        elif key == ord("b") and page != "receipt":
            page = "receipt"; scroll = 0
        elif key in (curses.KEY_RIGHT, ord(">"), ord(".")):
            conv_idx = (conv_idx + 1) % len(CONVERSIONS)
        elif key in (curses.KEY_LEFT, ord("<"), ord(",")):
            conv_idx = (conv_idx - 1) % len(CONVERSIONS)
        elif key in (curses.KEY_DOWN, ord("j")):
            scroll += 1
        elif key in (curses.KEY_UP, ord("k")):
            scroll = max(0, scroll - 1)
        elif key == curses.KEY_NPAGE:
            scroll += h // 2
        elif key == curses.KEY_PPAGE:
            scroll = max(0, scroll - h // 2)

    # Disable mouse tracking on exit
    print("\033[?1003l", end="", flush=True)
