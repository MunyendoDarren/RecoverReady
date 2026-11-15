from __future__ import annotations

import fnmatch
import hashlib
import os
from pathlib import Path
from typing import List, Tuple


def sha256_file(path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def is_excluded(rel_parts, patterns) -> bool:
    rel = "/".join(rel_parts)
    return any(fnmatch.fnmatch(p, pat) for p in rel_parts for pat in patterns) or \
        any(fnmatch.fnmatch(rel, pat) for pat in patterns)


def _labels(sources: List[Path]) -> List[str]:
    labels, used = [], set()
    for s in sources:
        base = s.name or "root"
        label, n = base, 2
        while label in used:
            label, n = f"{base}-{n}", n + 1
        used.add(label)
        labels.append(label)
    return labels


def iter_files(sources: List[Path], excludes) -> List[Tuple[str, Path]]:
    """Return (name-inside-archive, real path). Symlinks are skipped, never followed."""
    out = []
    for label, src in zip(_labels(sources), sources):
        if src.is_file():
            out.append((label, src))
            continue
        if not src.is_dir():
            continue
        for root, dirs, files in os.walk(src, followlinks=False):
            rel_root = Path(root).relative_to(src).parts
            dirs[:] = sorted(d for d in dirs if not is_excluded(rel_root + (d,), excludes))
            for name in sorted(files):
                if is_excluded(rel_root + (name,), excludes):
                    continue
                p = Path(root) / name
                if p.is_symlink():
                    continue
                out.append(("/".join((label,) + rel_root + (name,)), p))
    return out
