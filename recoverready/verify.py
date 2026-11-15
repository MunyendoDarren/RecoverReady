"""Integrity checking: is the backup file the same one we wrote, and does it contain what the manifest says?"""
from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

from .backup import list_backups, load_manifest
from .manifest import sha256_file


def verify_archive(archive: Path, manifest: dict, deep: bool = True) -> dict:
    problems = []
    if sha256_file(archive) != manifest["archive_sha256"]:
        problems.append("archive hash does not match the manifest (file damaged or tampered with)")
    elif deep:
        try:
            seen = {}
            with tarfile.open(archive, "r:gz") as tf:
                for m in tf:
                    if not m.isreg():
                        continue
                    h = hashlib.sha256()
                    src = tf.extractfile(m)
                    for block in iter(lambda: src.read(1 << 20), b""):
                        h.update(block)
                    seen[m.name] = h.hexdigest()
            for name, meta in manifest["files"].items():
                if name not in seen:
                    problems.append(f"missing from archive: {name}")
                elif seen[name] != meta["sha256"]:
                    problems.append(f"content differs from manifest: {name}")
            for name in seen:
                if name not in manifest["files"]:
                    problems.append(f"unexpected file in archive: {name}")
        except (tarfile.TarError, EOFError, OSError) as exc:
            problems.append(f"archive cannot be read: {exc}")
    return {"archive": str(archive), "ok": not problems, "problems": problems[:20], "problem_count": len(problems)}


def verify_all(cfg, deep: bool = True, latest_only: bool = False):
    results = []
    for d in cfg.destinations:
        backups = list_backups(d["path"])
        if latest_only:
            backups = backups[:1]
        for _s, arc, man in backups:
            results.append(dict(verify_archive(arc, load_manifest(man), deep), destination=str(d["path"])))
    return results
