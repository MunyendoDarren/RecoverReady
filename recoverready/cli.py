from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, report, restore, status, verify
from .backup import create_backup
from .config import CONFIG_NAME, ConfigError, load, write_default

TAGS = {"OK": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]"}


def cmd_init(args, _cfg=None) -> int:
    write_default(args.config)
    print(f"Created {args.config}. Edit the sources, destinations, RPO/RTO and contacts, then run:\n  recoverready backup")
    return 0


def cmd_backup(args, cfg) -> int:
    r = create_backup(cfg, force=args.force)
    if r["status"] == "blocked":
        print("BLOCKED - possible ransomware activity detected:")
        for reason in r["reasons"]:
            print(f"  - {reason}")
        print(f"\n{r['message']}\nIf you are sure this is a false alarm, re-run with --force.")
        return 3
    if r["status"] == "error":
        print(f"ERROR: {r['message']}")
        return 1
    print(f"Backup {r['archive']}: {r['files']} files, {r['bytes'] / 1e6:.2f} MB -> {len(r['copies'])} location(s)")
    for p in r["problems"]:
        print(f"  WARNING: copy failed: {p}")
    for s in r["skipped"][:5]:
        print(f"  skipped: {s}")
    return 4 if r["status"] == "partial" else 0


def cmd_verify(args, cfg) -> int:
    results = verify.verify_all(cfg, deep=not args.quick, latest_only=args.latest)
    if not results:
        print("No backups found.")
        return 1
    bad = 0
    for r in results:
        print(f"{'[ OK ]' if r['ok'] else '[FAIL]'} {r['archive']}")
        for p in r["problems"][:3]:
            print(f"        {p}")
        bad += 0 if r["ok"] else 1
    return 1 if bad else 0


def cmd_restore_test(args, cfg) -> int:
    r = restore.restore_test(cfg, args.destination, args.archive, args.dest, args.keep)
    if not r["passed"]:
        print("RESTORE TEST FAILED")
        for p in r["problems"]:
            print(f"  - {p}")
        return 1
    print(f"RESTORE TEST PASSED: {r['files']} files ({r['bytes'] / 1e6:.2f} MB) from the {r['source_kind']} copy in {r['restore_seconds']} s")
    print(f"Estimated full recovery: {r['estimated_recovery_minutes']} min (target {r['rto_target_minutes']} min) -> "
          f"{'meets RTO' if r['meets_rto'] else 'MISSES RTO'}")
    if r["restored_to"]:
        print(f"Restored files kept in: {r['restored_to']}")
    return 0 if r["meets_rto"] else 2


def cmd_status(args, cfg) -> int:
    ev = status.evaluate(cfg)
    for c in ev["checks"]:
        print(f"{TAGS[c['level']]} {c['name']}: {c['detail']}")
    return {"OK": 0, "WARN": 0, "FAIL": 1}[ev["overall"]]


def cmd_report(args, cfg) -> int:
    for p in report.write_all(cfg, args.out):
        print(f"Wrote {p}")
    return 0


def cmd_demo(args, _cfg=None) -> int:
    from .demo import run_demo
    return run_demo(Path(args.out))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="recoverready", description="Backups you can actually restore - with the policy, tests and playbook to prove it.")
    p.add_argument("--version", action="version", version=f"RecoverReady {__version__}")
    p.add_argument("-c", "--config", default=CONFIG_NAME, help=f"config file (default: {CONFIG_NAME})")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create a starter config file").set_defaults(fn=cmd_init, needs_cfg=False)
    b = sub.add_parser("backup", help="create a verified backup and copy it to every destination")
    b.add_argument("--force", action="store_true", help="back up even if the ransomware guard objects")
    b.set_defaults(fn=cmd_backup)
    v = sub.add_parser("verify", help="check backups against their hashes")
    v.add_argument("--quick", action="store_true", help="only check archive hashes, not every file inside")
    v.add_argument("--latest", action="store_true", help="only the newest backup in each location")
    v.set_defaults(fn=cmd_verify)
    r = sub.add_parser("restore-test", help="restore a backup to a scratch folder, verify every file, time it")
    r.add_argument("--destination", type=int, help="index (0-based) of the destination to restore from; default: the last (offsite)")
    r.add_argument("--archive", help="specific backup file name")
    r.add_argument("--dest", help="restore into this folder (kept) instead of a temp folder")
    r.add_argument("--keep", action="store_true", help="keep the restored files")
    r.set_defaults(fn=cmd_restore_test)
    sub.add_parser("status", help="are we meeting our RPO/RTO and the 3-2-1 rule?").set_defaults(fn=cmd_status)
    rp = sub.add_parser("report", help="write backup policy, incident playbook and recovery report")
    rp.add_argument("--out", default="reports")
    rp.set_defaults(fn=cmd_report)
    d = sub.add_parser("demo", help="run a complete safe demo with fake data (includes a simulated ransomware attack)")
    d.add_argument("--out", default="demo-output")
    d.set_defaults(fn=cmd_demo, needs_cfg=False)

    args = p.parse_args(argv)
    try:
        cfg = load(args.config) if getattr(args, "needs_cfg", True) else None
        return args.fn(args, cfg)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
