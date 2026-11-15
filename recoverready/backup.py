"""Create a backup: one compressed archive + a manifest of SHA-256 hashes, copied to every destination."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import socket
import tarfile
import time
from pathlib import Path

from . import __version__, indicators, logs
from .manifest import iter_files, sha256_file
from .retention import STAMP_RE, FMT, select_keep, stamp_of


class _HashingReader:
    def __init__(self, f):
        self.f, self.h, self.n = f, hashlib.sha256(), 0

    def read(self, n=-1):
        b = self.f.read(n)
        self.h.update(b)
        self.n += len(b)
        return b


def manifest_path_for(archive: Path) -> Path:
    return archive.with_name(archive.name[:-len(".tar.gz")] + ".manifest.json")


def list_backups(dest: Path):
    """[(stamp, archive_path, manifest_path)] newest first, only complete pairs."""
    out = []
    if not dest.is_dir():
        return out
    for p in dest.iterdir():
        s = stamp_of(p.name)
        if s and manifest_path_for(p).exists():
            out.append((s, p, manifest_path_for(p)))
    return sorted(out, reverse=True)


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_manifest(cfg):
    for dest in cfg.destinations:
        b = list_backups(dest["path"])
        if b:
            return load_manifest(b[0][2])
    return None


def _chmod_ro(*paths):
    for p in paths:
        try:
            os.chmod(p, 0o444)
        except OSError:
            pass


def _delete(path: Path):
    try:
        os.chmod(path, 0o644)
        path.unlink()
    except OSError:
        pass


def apply_retention(dest: Path, cfg) -> list:
    r = cfg["retention"]
    backups = list_backups(dest)
    keep = select_keep([b[0] for b in backups], r["daily"], r["weekly"], r["monthly"])
    removed = []
    for s, arc, man in backups:
        if s not in keep:
            _delete(arc)
            _delete(man)
            removed.append(arc.name)
    return removed


def create_backup(cfg, force: bool = False, now=None) -> dict:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    state = cfg.state_dir / "backups.jsonl"
    t0 = time.time()
    prev = latest_manifest(cfg)
    check = indicators.assess(cfg, prev["files"] if prev else {})

    def finish(rec):
        rec.update({"date": now.strftime("%Y-%m-%d %H:%M:%S UTC"), "timestamp": now.timestamp(),
                    "duration_seconds": round(time.time() - t0, 2), "ransomware_check": check})
        logs.append(state, rec)
        return rec

    if check["blocked"] and not force:
        return finish({"status": "blocked", "reasons": check["reasons"],
                       "message": "Backup NOT written and NO old backups were deleted. Investigate before continuing."})

    dests = cfg.destinations
    primary = dests[0]["path"]
    try:
        primary.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return finish({"status": "error", "message": f"Cannot create primary destination {primary}: {exc}"})

    stamp = now.strftime(FMT)
    name = f"backup-{stamp}.tar.gz"
    partial = primary / (name + ".partial")
    files, skipped, total = {}, [], 0
    try:
        with tarfile.open(partial, "w:gz") as tf:
            for arc, path in iter_files(cfg.sources, cfg["exclude"]):
                try:
                    f = open(path, "rb")
                except OSError as exc:
                    skipped.append(f"{arc}: {exc.strerror or exc}")
                    continue
                with f:
                    ti = tf.gettarinfo(arcname=arc, fileobj=f)
                    ti.uid = ti.gid = 0
                    ti.uname = ti.gname = ""
                    reader = _HashingReader(f)
                    tf.addfile(ti, reader)
                    files[arc] = {"sha256": reader.h.hexdigest(), "size": ti.size, "mtime": int(ti.mtime)}
                    total += ti.size
    except Exception as exc:  # file vanished/shrank mid-backup, disk full, ...
        _delete(partial)
        return finish({"status": "error", "message": f"Backup failed and was discarded: {exc}. Safe to re-run."})

    archive = primary / name
    os.replace(partial, archive)
    man = {"version": 1, "tool": f"recoverready {__version__}", "created": now.isoformat(),
           "host": socket.gethostname(), "archive": name, "archive_sha256": sha256_file(archive),
           "archive_bytes": archive.stat().st_size, "file_count": len(files), "total_bytes": total,
           "files": files, "skipped": skipped}
    mpath = manifest_path_for(archive)
    mpath.write_text(json.dumps(man, indent=1), encoding="utf-8")
    _chmod_ro(archive, mpath)

    copies, problems = [str(primary)], []
    for d in dests[1:]:
        dp = d["path"]
        try:
            dp.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archive, dp / name)
            shutil.copy2(mpath, dp / mpath.name)
            if sha256_file(dp / name) != man["archive_sha256"]:
                raise OSError("copy does not match the original (hash mismatch)")
            _chmod_ro(dp / name, dp / mpath.name)
            copies.append(str(dp))
        except OSError as exc:
            problems.append(f"{dp}: {exc}")
            _delete(dp / name)
            _delete(dp / mpath.name)

    removed = {}
    for d in dests:
        if str(d["path"]) in copies:
            removed[str(d["path"])] = apply_retention(d["path"], cfg)

    rec = {"status": "partial" if problems else "ok", "archive": name, "files": len(files), "bytes": total,
           "archive_bytes": man["archive_bytes"], "copies": copies, "problems": problems, "skipped": skipped,
           "pruned": removed, "forced": bool(check["blocked"] and force)}
    return finish(rec)
