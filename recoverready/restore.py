"""Restore test: actually restore a backup into a scratch folder, check every file, and time it.
A backup you have never restored is a hope, not a backup."""
from __future__ import annotations

import datetime
import shutil
import tarfile
import tempfile
import time
from pathlib import Path

from . import logs
from .backup import list_backups, load_manifest
from .manifest import sha256_file


class UnsafeArchive(Exception):
    pass


def safe_extract(tf: tarfile.TarFile, dest: Path) -> int:
    """Extract regular files only; refuse anything that would land outside `dest` (path traversal)."""
    dest = Path(dest).resolve()
    n = 0
    for m in tf:
        if m.isdir():
            continue
        if not m.isreg():
            continue  # links, devices, etc. are never restored
        target = (dest / m.name).resolve()
        if dest not in target.parents:
            raise UnsafeArchive(f"archive member '{m.name}' tries to escape the restore folder")
        target.parent.mkdir(parents=True, exist_ok=True)
        src = tf.extractfile(m)
        with open(target, "wb") as out:
            shutil.copyfileobj(src, out, 1 << 20)
        n += 1
    return n


def pick_backup(cfg, destination_index=None, archive_name=None):
    dests = cfg.destinations
    # Default to the LAST destination: restoring from the offsite copy is the test that matters most.
    order = [destination_index] if destination_index is not None else list(range(len(dests) - 1, -1, -1))
    for i in order:
        for _s, arc, man in list_backups(dests[i]["path"]):
            if archive_name is None or arc.name == archive_name:
                return dests[i], arc, man
    return None, None, None


def restore_test(cfg, destination_index=None, archive_name=None, dest_dir=None, keep=False, now=None) -> dict:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    dest, arc, man = pick_backup(cfg, destination_index, archive_name)
    rec = {"date": now.strftime("%Y-%m-%d %H:%M:%S UTC"), "timestamp": now.timestamp()}
    if arc is None:
        rec.update({"passed": False, "problems": ["no backup found to test"], "files": 0, "bytes": 0})
        logs.append(cfg.state_dir / "restore-tests.jsonl", rec)
        return rec
    manifest = load_manifest(man)
    scratch = Path(dest_dir) if dest_dir else Path(tempfile.mkdtemp(prefix="recoverready-restore-"))
    scratch.mkdir(parents=True, exist_ok=True)
    problems = []
    t0 = time.time()
    try:
        if sha256_file(arc) != manifest["archive_sha256"]:
            problems.append("archive hash does not match the manifest")
        else:
            with tarfile.open(arc, "r:gz") as tf:
                safe_extract(tf, scratch)
            for name, meta in manifest["files"].items():
                p = scratch / name
                if not p.is_file():
                    problems.append(f"not restored: {name}")
                elif sha256_file(p) != meta["sha256"]:
                    problems.append(f"restored file is corrupt: {name}")
    except (tarfile.TarError, EOFError, OSError, UnsafeArchive) as exc:
        problems.append(f"restore failed: {exc}")
    secs = time.time() - t0
    if not keep and not dest_dir:
        shutil.rmtree(scratch, ignore_errors=True)

    measured_min = secs / 60.0
    est_min = measured_min + cfg["rto_overhead_minutes"]
    rto_min = cfg["rto_hours"] * 60
    rec.update({
        "passed": not problems, "problems": problems[:20], "archive": arc.name, "source": str(dest["path"]),
        "source_kind": dest["kind"], "files": manifest["file_count"], "bytes": manifest["total_bytes"],
        "restore_seconds": round(secs, 2),
        "restore_mb_per_s": round(manifest["total_bytes"] / 1e6 / secs, 1) if secs > 0 else None,
        "estimated_recovery_minutes": round(est_min, 1), "rto_target_minutes": rto_min,
        "meets_rto": (not problems) and est_min <= rto_min,
        "restored_to": str(scratch) if (keep or dest_dir) else None,
    })
    logs.append(cfg.state_dir / "restore-tests.jsonl", rec)
    return rec
