"""Configuration: one JSON file describes what to protect, where copies go, and the targets (RPO/RTO)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import List

CONFIG_NAME = "recoverready.json"
KINDS = ("local", "offsite", "offline")

DEFAULT = {
    "organization": "Example Organisation",
    "owner": "IT / Security lead",
    "sources": ["./data"],
    "destinations": [
        {"path": "./backups/local", "kind": "local"},
        {"path": "./backups/offsite", "kind": "offsite"},
    ],
    "exclude": ["*.tmp", "*.swp", "node_modules", "__pycache__", ".git", "Thumbs.db"],
    "rpo_hours": 24,
    "rto_hours": 4,
    "rto_overhead_minutes": 60,
    "restore_test_every_days": 30,
    "retention": {"daily": 7, "weekly": 4, "monthly": 6},
    "ransomware_guard": {"enabled": True, "max_changed_percent": 30, "min_files": 20},
    "critical_assets": [
        {"name": "Customer and order records", "priority": 1, "owner": "Operations"},
        {"name": "Finance and accounting files", "priority": 1, "owner": "Finance"},
        {"name": "Shared documents", "priority": 2, "owner": "All staff"},
    ],
    "contacts": [
        {"role": "Incident lead", "name": "Your name", "phone": "+254 700 000 000"},
        {"role": "IT support / provider", "name": "Provider name", "phone": "+254 700 000 001"},
        {"role": "Management", "name": "Director name", "phone": "+254 700 000 002"},
    ],
}


class ConfigError(Exception):
    pass


class Config:
    def __init__(self, data: dict, base: Path):
        self.data = data
        self.base = Path(base).resolve()

    def _resolve(self, p: str) -> Path:
        path = Path(p).expanduser()
        return path if path.is_absolute() else (self.base / path).resolve()

    def __getitem__(self, key):
        return self.data[key]

    @property
    def sources(self) -> List[Path]:
        return [self._resolve(s) for s in self.data["sources"]]

    @property
    def destinations(self) -> List[dict]:
        out = []
        for d in self.data["destinations"]:
            d = {"path": d, "kind": "local"} if isinstance(d, str) else d
            out.append({"path": self._resolve(d["path"]), "kind": d.get("kind", "local")})
        return out

    @property
    def state_dir(self) -> Path:
        p = self.base / ".recoverready"
        p.mkdir(parents=True, exist_ok=True)
        return p


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def validate(cfg: Config) -> None:
    d = cfg.data
    if not d.get("sources"):
        raise ConfigError("'sources' must list at least one folder to protect")
    if not d.get("destinations"):
        raise ConfigError("'destinations' must list at least one backup location")
    for key in ("rpo_hours", "rto_hours", "restore_test_every_days"):
        if not isinstance(d.get(key), (int, float)) or d[key] <= 0:
            raise ConfigError(f"'{key}' must be a positive number")
    for k, v in d["retention"].items():
        if k not in ("daily", "weekly", "monthly") or not isinstance(v, int) or v < 0:
            raise ConfigError("'retention' needs non-negative whole numbers for daily/weekly/monthly")
    for dest in cfg.destinations:
        if dest["kind"] not in KINDS:
            raise ConfigError(f"destination kind must be one of {KINDS}, got '{dest['kind']}'")
        for src in cfg.sources:
            if dest["path"] == src or src in dest["path"].parents:
                raise ConfigError(f"destination {dest['path']} is inside source {src}: backups would back themselves up")


def load(path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file '{path}' not found. Create one with:  recoverready init")
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ConfigError(f"'{path}' is not valid JSON: {exc}") from exc
    cfg = Config(_merge(DEFAULT, user), path.parent)
    validate(cfg)
    return cfg


def write_default(path) -> None:
    path = Path(path)
    if path.exists():
        raise ConfigError(f"'{path}' already exists - not overwriting it")
    path.write_text(json.dumps(DEFAULT, indent=2) + "\n", encoding="utf-8")
