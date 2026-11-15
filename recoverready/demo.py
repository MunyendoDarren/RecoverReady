"""Self-contained demo: fake company data -> backup -> simulated ransomware -> guard blocks -> restore test -> reports."""
from __future__ import annotations

import json
import os
import random
import shutil
from pathlib import Path

from . import report, restore, status
from .backup import create_backup, list_backups
from .config import DEFAULT, Config, _merge, validate


def _make_data(src: Path) -> None:
    rnd = random.Random(7)
    for folder, ext, n in (("customers", ".csv", 25), ("finance", ".txt", 15), ("documents", ".md", 25)):
        (src / folder).mkdir(parents=True, exist_ok=True)
        for i in range(n):
            lines = [f"{folder} record {i} line {j}: " + " ".join(rnd.choice(["alpha", "beta", "gamma", "delta", "invoice", "order", "client"]) for _ in range(12)) for j in range(400)]
            (src / folder / f"{folder}-{i:02d}{ext}").write_text("\n".join(lines))


def _simulate_ransomware(src: Path) -> None:
    for p in sorted(src.rglob("*"))[:200]:
        if p.is_file():
            p.write_bytes(os.urandom(max(p.stat().st_size, 8192)))
            p.rename(p.with_name(p.name + ".locked"))
    (src / "HOW_TO_DECRYPT_YOUR_FILES.txt").write_text("Your files are encrypted. (this is a harmless demo)")


def run_demo(out: Path) -> int:
    out = out.resolve()
    if out.exists():
        shutil.rmtree(out)
    src = out / "company-data"
    _make_data(src)
    data = _merge(DEFAULT, {"organization": "Demo Shop Ltd", "sources": [str(src)],
                            "destinations": [{"path": str(out / "backups" / "local"), "kind": "local"},
                                             {"path": str(out / "backups" / "offsite"), "kind": "offsite"}],
                            "rto_hours": 4})
    cfg = Config(data, out)
    validate(cfg)

    print("1) Creating a backup of the demo company data ...")
    r = create_backup(cfg)
    print(f"   {r['status'].upper()}: {r['files']} files -> {len(r['copies'])} locations")

    print("2) Restore test from the OFFSITE copy ...")
    t = restore.restore_test(cfg)
    print(f"   {'PASSED' if t['passed'] else 'FAILED'}: {t['files']} files restored and hash-checked in {t['restore_seconds']} s")

    print("3) Simulating a ransomware attack (files overwritten with random data and renamed .locked) ...")
    _simulate_ransomware(src)
    r2 = create_backup(cfg)
    print(f"   Backup result: {r2['status'].upper()}")
    for reason in r2.get("reasons", []):
        print(f"   - {reason}")
    print(f"   Good backups still available: {len(list_backups(cfg.destinations[1]['path']))} (nothing was overwritten or deleted)")

    print("4) Health status:")
    for c in status.evaluate(cfg)["checks"]:
        print(f"   [{c['level']:<4}] {c['name']}: {c['detail']}")

    print("5) Writing the deliverables ...")
    for p in report.write_all(cfg, out / "reports"):
        print(f"   {p}")
    (out / "recoverready.json").write_text(json.dumps(data, indent=2))
    return 0
