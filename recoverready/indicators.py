"""Ransomware guard. If data looks freshly encrypted, DON'T let it overwrite or age out your good backups.

Heuristics (any one hard indicator blocks the run):
  1. new files with well-known ransomware extensions (.locked, .wncry, ...)
  2. ransom-note-looking file names
  3. a large share of existing files changed AND most of the changed ones look like random (encrypted) data
They are heuristics: they can be wrong in both directions, so a block can be overridden with --force.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from pathlib import Path

from .manifest import iter_files

SUSPICIOUS_EXT = {".locked", ".encrypted", ".crypt", ".crypted", ".cerber", ".locky", ".wncry", ".wnry",
                  ".lockbit", ".ryk", ".akira", ".djvu", ".zepto", ".odin", ".thor"}
NOTE_FRAGMENTS = ("decrypt", "ransom", "your_files", "your-files", "how_to_restore", "how_to_recover",
                  "recover_my", "restore_my", "files_encrypted", "encrypted_files")
NOTE_EXT = {".txt", ".html", ".hta"}
# Already-compressed formats are naturally high-entropy, so they say nothing about encryption.
COMPRESSED_EXT = {".zip", ".gz", ".bz2", ".xz", ".7z", ".rar", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp3",
                  ".mp4", ".mkv", ".avi", ".mov", ".pdf", ".docx", ".xlsx", ".pptx", ".jar", ".apk", ".heic"}
SAMPLE_BYTES = 65536
HIGH_ENTROPY = 7.5


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in Counter(data).values())


def looks_like_note(name: str) -> bool:
    low = name.lower()
    return Path(low).suffix in NOTE_EXT and any(f in low for f in NOTE_FRAGMENTS)


def assess(cfg, prev_files: dict) -> dict:
    guard = cfg["ransomware_guard"]
    result = {"blocked": False, "reasons": [], "checked": True,
              "stats": {"files": 0, "changed": 0, "changed_percent": 0.0, "high_entropy_ratio": 0.0}}
    if not guard.get("enabled", True):
        result["checked"] = False
        return result

    files = iter_files(cfg.sources, cfg["exclude"])
    result["stats"]["files"] = len(files)
    new_ext, notes, changed, sampled, high = [], [], 0, 0, 0
    comparable = 0
    for arc, path in files:
        ext = path.suffix.lower()
        prev = prev_files.get(arc)
        if prev is None and ext in SUSPICIOUS_EXT:
            new_ext.append(arc)
        if prev is None and looks_like_note(path.name):
            notes.append(arc)
        if prev is None:
            continue
        comparable += 1
        try:
            st = path.stat()
        except OSError:
            continue
        if st.st_size == prev["size"] and int(st.st_mtime) == prev["mtime"]:
            continue
        changed += 1
        if ext in COMPRESSED_EXT:
            continue
        try:
            with open(path, "rb") as f:
                sample = f.read(SAMPLE_BYTES)
        except OSError:
            continue
        if len(sample) >= 4096:
            sampled += 1
            if shannon_entropy(sample) >= HIGH_ENTROPY:
                high += 1

    pct = 100.0 * changed / comparable if comparable else 0.0
    ratio = high / sampled if sampled else 0.0
    result["stats"].update({"changed": changed, "changed_percent": round(pct, 1), "high_entropy_ratio": round(ratio, 2)})
    if new_ext:
        result["reasons"].append(f"{len(new_ext)} new file(s) with ransomware-style extensions (e.g. {new_ext[0]})")
    if notes:
        result["reasons"].append(f"{len(notes)} file(s) that look like ransom notes (e.g. {notes[0]})")
    if comparable >= guard["min_files"] and pct >= guard["max_changed_percent"] and sampled >= 5 and ratio >= 0.6:
        result["reasons"].append(
            f"{pct:.0f}% of files changed since the last backup and {ratio:.0%} of the changed files look encrypted (random data)")
    result["blocked"] = bool(result["reasons"])
    return result
