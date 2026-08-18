"""Fetch and parse Slurm fair-share (priority) data via sshare/sacctmgr.

Scoping is deliberate: we only ever query the current user's own row
(``sshare -U -u $USER``) and their own account's direct members
(``sshare -A <account> -a``). We never run an unscoped ``sshare -a``,
which on a shared cluster dumps every lab's usage tree.
"""

import subprocess

FORMAT = "Account,User,RawShares,NormShares,RawUsage,EffectvUsage,FairShare"


def _run(cmd, timeout=15):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _to_float(s, default=0.0):
    s = s.strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _parse_row(line):
    """Parse one sshare -p line into a dict, or None for parent/summary rows."""
    fields = line.rstrip("\n").split("|")
    if len(fields) < 7:
        return None
    account, user, raw_shares, norm_shares, raw_usage, effectv_usage, fairshare = fields[:7]
    if not user.strip():
        return None
    return {
        "account": account.strip(),
        "user": user.strip(),
        "raw_shares": _to_float(raw_shares),
        "norm_shares": _to_float(norm_shares),
        "raw_usage": _to_float(raw_usage),
        "effectv_usage": _to_float(effectv_usage),
        "fairshare": _to_float(fairshare, default=None) if fairshare.strip() else None,
    }


def fetch_default_account(user):
    """Look up the user's default Slurm account via sacctmgr."""
    out = _run(["sacctmgr", "show", "user", user, "withassoc",
                "format=DefaultAccount", "-P", "-n"])
    if not out:
        return None
    for line in out.splitlines():
        acct = line.strip()
        if acct:
            return acct
    return None


def fetch_self(user):
    """Fetch the user's own fairshare row (all accounts they belong to)."""
    out = _run(["sshare", "-U", "-u", user, "-p", "--noheader", f"--format={FORMAT}"])
    if not out:
        return None
    rows = [r for r in (_parse_row(line) for line in out.splitlines()) if r]
    return rows


def fetch_leaderboard(account):
    """Fetch fairshare rows for every direct member of `account`."""
    if not account:
        return []
    out = _run(["sshare", "-A", account, "-a", "-p", "--noheader", f"--format={FORMAT}"])
    if not out:
        return []
    rows = []
    for line in out.splitlines():
        row = _parse_row(line)
        if row and row["account"] == account:
            rows.append(row)
    rows.sort(key=lambda r: r["effectv_usage"], reverse=True)
    return rows


def fetch_fairshare_data(user):
    """Fetch self + own-account leaderboard. Returns None if sshare/sacctmgr unavailable."""
    self_rows = fetch_self(user)
    if not self_rows:
        return None

    # Prefer the account matching sacctmgr's DefaultAccount if the user
    # belongs to more than one; otherwise just use the first row.
    default_acct = fetch_default_account(user)
    self_row = None
    if default_acct:
        self_row = next((r for r in self_rows if r["account"] == default_acct), None)
    if self_row is None:
        self_row = self_rows[0]

    leaderboard = fetch_leaderboard(self_row["account"])
    rank = None
    for i, r in enumerate(leaderboard, 1):
        if r["user"] == user:
            rank = i
            break

    return {
        "account": self_row["account"],
        "self": self_row,
        "leaderboard": leaderboard,
        "rank": rank,
    }


def generate_demo_fairshare(user="demo_user"):
    """Synthetic fairshare data for --demo mode (no sshare needed)."""
    import random
    labmates = ["labmate_a", "labmate_b", "labmate_c", "labmate_d"]
    names = [user] + labmates

    rows = []
    for n in names:
        usage = (random.randint(400_000, 2_500_000) if n == user
                  else random.randint(0, 900_000))
        rows.append({
            "account": "demolab",
            "user": n,
            "raw_shares": 1.0,
            "norm_shares": 1.0 / len(names),
            "raw_usage": float(usage),
            "effectv_usage": 0.0,
            "fairshare": None,
        })

    total_usage = sum(r["raw_usage"] for r in rows) or 1.0
    for r in rows:
        r["effectv_usage"] = r["raw_usage"] / total_usage
        # Rough stand-in: heavier relative usage -> lower fairshare score.
        r["fairshare"] = round(max(0.05, 1.0 - r["effectv_usage"]), 6)

    rows.sort(key=lambda r: r["effectv_usage"], reverse=True)
    self_row = next(r for r in rows if r["user"] == user)
    rank = next(i for i, r in enumerate(rows, 1) if r["user"] == user)

    return {"account": "demolab", "self": self_row, "leaderboard": rows, "rank": rank}
