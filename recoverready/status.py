"""Health check: are we actually meeting the targets we wrote down?"""
from __future__ import annotations

import datetime

from . import logs
from .backup import list_backups


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def evaluate(cfg, now=None) -> dict:
    now = now or _now()
    checks = []

    def add(level, name, detail):
        checks.append({"level": level, "name": name, "detail": detail})

    dests = cfg.destinations
    # 1. RPO: how old is the newest good backup in the primary location?
    newest = None
    for d in dests:
        b = list_backups(d["path"])
        if b:
            s = b[0][0].replace(tzinfo=datetime.timezone.utc)
            newest = max(newest, s) if newest else s
    rpo = cfg["rpo_hours"]
    if newest is None:
        add("FAIL", "Recovery point (RPO)", "No backups exist yet.")
        age_h = None
    else:
        age_h = (now - newest).total_seconds() / 3600
        lvl = "OK" if age_h <= rpo else "FAIL"
        add(lvl, "Recovery point (RPO)", f"Newest backup is {age_h:.1f} h old; target is {rpo} h.")

    # 2. 3-2-1 rule
    kinds = {d["kind"] for d in dests}
    copies = 1 + len(dests)
    ok321 = copies >= 3 and len(kinds) >= 2 and bool(kinds & {"offsite", "offline"})
    add("OK" if ok321 else "WARN", "3-2-1 rule",
        f"{copies} copies across {sorted(kinds)}." + ("" if ok321 else " Need 3 copies, 2 kinds of location, 1 offsite/offline."))
    if "offline" not in kinds:
        add("WARN", "Ransomware resilience", "No 'offline' copy. Ransomware that reaches your network can often reach connected backups too.")

    # 3. each destination reachable & has a backup
    for d in dests:
        b = list_backups(d["path"])
        add("OK" if b else "WARN", f"Destination {d['path']}", f"{len(b)} backup(s) ({d['kind']})." if b else "Empty or unreachable.")

    # 4. restore tests
    tests = logs.read(cfg.state_dir / "restore-tests.jsonl")
    every = cfg["restore_test_every_days"]
    if not tests:
        add("FAIL", "Restore testing", "No restore test has ever been run. Run: recoverready restore-test")
    else:
        last = tests[-1]
        age_d = (now.timestamp() - last["timestamp"]) / 86400
        if not last["passed"]:
            add("FAIL", "Restore testing", f"Last restore test FAILED ({last['date']}): {'; '.join(last['problems'][:2])}")
        elif age_d > every:
            add("WARN", "Restore testing", f"Last passing test was {age_d:.0f} days ago; policy is every {every} days.")
        else:
            add("OK", "Restore testing", f"Last test passed {age_d:.0f} day(s) ago.")
        if last["passed"]:
            add("OK" if last["meets_rto"] else "FAIL", "Recovery time (RTO)",
                f"Estimated full recovery {last['estimated_recovery_minutes']} min vs target {last['rto_target_minutes']} min.")

    # 5. blocked backups recently
    recent = logs.read(cfg.state_dir / "backups.jsonl")[-5:]
    if any(r["status"] == "blocked" for r in recent):
        add("FAIL", "Ransomware guard", "A recent backup was BLOCKED because data looked encrypted. Treat as an incident until cleared.")
    worst = "FAIL" if any(c["level"] == "FAIL" for c in checks) else "WARN" if any(c["level"] == "WARN" for c in checks) else "OK"
    return {"overall": worst, "checks": checks, "newest_backup_age_hours": age_h}
