"""Grandfather-father-son style retention: keep the newest backup of each recent day, week and month."""
from __future__ import annotations

import datetime
import re
from typing import Iterable, Optional, Set

STAMP_RE = re.compile(r"^backup-(\d{8}-\d{6})\.tar\.gz$")
FMT = "%Y%m%d-%H%M%S"


def stamp_of(name: str) -> Optional[datetime.datetime]:
    m = STAMP_RE.match(name)
    return datetime.datetime.strptime(m.group(1), FMT) if m else None


def select_keep(stamps: Iterable[datetime.datetime], daily: int, weekly: int, monthly: int) -> Set[datetime.datetime]:
    ordered = sorted(stamps, reverse=True)
    keep = set(ordered[:1])  # never delete the newest backup, whatever the settings

    def bucket(keyfn, limit):
        seen = []
        for s in ordered:
            k = keyfn(s)
            if k not in seen:
                seen.append(k)
                if len(seen) <= limit:
                    keep.add(s)

    bucket(lambda s: s.date(), daily)
    bucket(lambda s: s.isocalendar()[:2], weekly)
    bucket(lambda s: (s.year, s.month), monthly)
    return keep
