import datetime
import io
import json
import os
import random
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from recoverready import backup, indicators, report, restore, status, verify
from recoverready.config import DEFAULT, Config, ConfigError, _merge, validate
from recoverready.retention import select_keep

UTC = datetime.timezone.utc


def make_cfg(root: Path, files=40, **over):
    src = root / "data"
    src.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(1)
    for i in range(files):
        (src / f"doc{i:02d}.txt").write_text("\n".join(f"line {j} {rnd.random()}" for j in range(300)))
    (src / "sub").mkdir(exist_ok=True)
    (src / "sub" / "photo.jpg").write_bytes(os.urandom(20000))
    (src / "ignore.tmp").write_text("temp")
    data = _merge(DEFAULT, dict({"sources": [str(src)],
                                 "destinations": [{"path": str(root / "b" / "local"), "kind": "local"},
                                                  {"path": str(root / "b" / "off"), "kind": "offsite"}]}, **over))
    cfg = Config(data, root)
    validate(cfg)
    return cfg


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))


class TestBackupRoundTrip(Base):
    def test_backup_copies_verify_and_restore(self):
        cfg = make_cfg(self.tmp)
        r = backup.create_backup(cfg)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(len(r["copies"]), 2)
        self.assertEqual(r["files"], 41)  # 40 docs + 1 jpg; the .tmp file is excluded
        for d in cfg.destinations:
            self.assertEqual(len(backup.list_backups(d["path"])), 1)
        self.assertTrue(all(x["ok"] for x in verify.verify_all(cfg)))
        t = restore.restore_test(cfg)
        self.assertTrue(t["passed"], t["problems"])
        self.assertEqual(t["source_kind"], "offsite")  # tests the offsite copy by default

    def test_excludes_and_readonly(self):
        cfg = make_cfg(self.tmp)
        backup.create_backup(cfg)
        _s, arc, man = backup.list_backups(cfg.destinations[0]["path"])[0]
        self.assertNotIn("data/ignore.tmp", backup.load_manifest(man)["files"])
        self.assertFalse(os.access(arc, os.W_OK) and os.geteuid() != 0)


class TestTamperDetection(Base):
    def test_modified_archive_fails_verify_and_restore(self):
        cfg = make_cfg(self.tmp)
        backup.create_backup(cfg)
        _s, arc, _m = backup.list_backups(cfg.destinations[1]["path"])[0]
        os.chmod(arc, 0o644)
        data = bytearray(arc.read_bytes())
        data[len(data) // 2] ^= 0xFF
        arc.write_bytes(bytes(data))
        res = [r for r in verify.verify_all(cfg) if r["destination"].endswith("off")][0]
        self.assertFalse(res["ok"])
        self.assertFalse(restore.restore_test(cfg)["passed"])

    def test_missing_file_detected_by_deep_verify(self):
        cfg = make_cfg(self.tmp)
        backup.create_backup(cfg)
        _s, arc, man = backup.list_backups(cfg.destinations[0]["path"])[0]
        m = backup.load_manifest(man)
        m["files"]["data/ghost.txt"] = {"sha256": "0" * 64, "size": 1, "mtime": 0}
        res = verify.verify_archive(arc, m, deep=True)
        self.assertFalse(res["ok"])
        self.assertTrue(any("ghost" in p or "hash" in p for p in res["problems"]))


class TestRansomwareGuard(Base):
    def test_extension_and_note_block_without_deleting_good_backups(self):
        cfg = make_cfg(self.tmp)
        backup.create_backup(cfg)
        src = cfg.sources[0]
        (src / "doc00.txt.locked").write_text("x")
        (src / "HOW_TO_DECRYPT_FILES.txt").write_text("pay up")
        r = backup.create_backup(cfg, now=datetime.datetime.now(UTC) + datetime.timedelta(days=1))
        self.assertEqual(r["status"], "blocked")
        self.assertEqual(len(backup.list_backups(cfg.destinations[0]["path"])), 1)

    def test_in_place_encryption_detected_by_entropy(self):
        cfg = make_cfg(self.tmp, files=40)
        backup.create_backup(cfg)
        future = datetime.datetime.now(UTC).timestamp() + 500
        for p in sorted(cfg.sources[0].glob("doc*.txt"))[:25]:  # ~60% of files, no rename
            p.write_bytes(os.urandom(p.stat().st_size))
            os.utime(p, (future, future))
        res = indicators.assess(cfg, backup.latest_manifest(cfg)["files"])
        self.assertTrue(res["blocked"], res)
        self.assertTrue(any("look encrypted" in x for x in res["reasons"]))

    def test_normal_edits_do_not_trigger(self):
        cfg = make_cfg(self.tmp, files=40)
        backup.create_backup(cfg)
        future = datetime.datetime.now(UTC).timestamp() + 500
        for p in sorted(cfg.sources[0].glob("doc*.txt")):  # everything edited, but still plain text
            p.write_text(p.read_text() + "\nnew line")
            os.utime(p, (future, future))
        self.assertFalse(indicators.assess(cfg, backup.latest_manifest(cfg)["files"])["blocked"])

    def test_changed_compressed_files_are_ignored(self):
        cfg = make_cfg(self.tmp)
        backup.create_backup(cfg)
        photo = cfg.sources[0] / "sub" / "photo.jpg"
        photo.write_bytes(os.urandom(30000))
        os.utime(photo, (9999999999, 9999999999))
        self.assertFalse(indicators.assess(cfg, backup.latest_manifest(cfg)["files"])["blocked"])

    def test_force_overrides(self):
        cfg = make_cfg(self.tmp)
        backup.create_backup(cfg)
        (cfg.sources[0] / "a.locked").write_text("x")
        r = backup.create_backup(cfg, force=True, now=datetime.datetime.now(UTC) + datetime.timedelta(days=1))
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["forced"])


class TestRetention(unittest.TestCase):
    def test_keeps_recent_days_weeks_months_and_never_the_newest_deleted(self):
        base = datetime.datetime(2026, 11, 14, 2, 0)
        stamps = [base - datetime.timedelta(days=i) for i in range(120)]
        keep = select_keep(stamps, 7, 4, 3)
        self.assertIn(stamps[0], keep)
        self.assertTrue(all(stamps[i] in keep for i in range(7)))
        self.assertLess(len(keep), 20)
        self.assertGreater(len(keep), 7)

    def test_multiple_per_day_keeps_newest_of_day(self):
        a = datetime.datetime(2026, 1, 1, 1)
        b = datetime.datetime(2026, 1, 1, 23)
        self.assertEqual(select_keep([a, b], 1, 0, 0), {b})

    def test_apply_retention_prunes_old_files(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        cfg = make_cfg(tmp, retention={"daily": 2, "weekly": 0, "monthly": 0})
        t0 = datetime.datetime(2026, 3, 1, 3, 0, tzinfo=UTC)
        for i in range(4):
            backup.create_backup(cfg, now=t0 + datetime.timedelta(days=i))
        self.assertEqual(len(backup.list_backups(cfg.destinations[0]["path"])), 2)


class TestSafeExtract(Base):
    def test_path_traversal_rejected(self):
        evil = self.tmp / "evil.tar.gz"
        with tarfile.open(evil, "w:gz") as tf:
            ti = tarfile.TarInfo("../../escaped.txt")
            ti.size = 3
            tf.addfile(ti, io.BytesIO(b"bad"))
        with tarfile.open(evil) as tf:
            with self.assertRaises(restore.UnsafeArchive):
                restore.safe_extract(tf, self.tmp / "out")
        self.assertFalse((self.tmp.parent / "escaped.txt").exists())


class TestConfig(Base):
    def test_destination_inside_source_rejected(self):
        src = self.tmp / "data"
        src.mkdir()
        cfg = Config(_merge(DEFAULT, {"sources": [str(src)], "destinations": [str(src / "backups")]}), self.tmp)
        with self.assertRaises(ConfigError):
            validate(cfg)

    def test_bad_numbers_rejected(self):
        cfg = Config(_merge(DEFAULT, {"rpo_hours": 0}), self.tmp)
        with self.assertRaises(ConfigError):
            validate(cfg)


class TestStatusAndReports(Base):
    def test_status_flags_missing_restore_test_then_passes(self):
        cfg = make_cfg(self.tmp)
        self.assertEqual(status.evaluate(cfg)["overall"], "FAIL")  # no backups yet
        backup.create_backup(cfg)
        ev = status.evaluate(cfg)
        self.assertTrue(any(c["name"] == "Restore testing" and c["level"] == "FAIL" for c in ev["checks"]))
        restore.restore_test(cfg)
        ev = status.evaluate(cfg)
        self.assertEqual([c for c in ev["checks"] if c["name"] == "Restore testing"][0]["level"], "OK")

    def test_old_backup_misses_rpo(self):
        cfg = make_cfg(self.tmp)
        backup.create_backup(cfg, now=datetime.datetime.now(UTC) - datetime.timedelta(days=3))
        ev = status.evaluate(cfg)
        self.assertEqual([c for c in ev["checks"] if c["name"].startswith("Recovery point")][0]["level"], "FAIL")

    def test_reports_contain_the_four_deliverables(self):
        cfg = make_cfg(self.tmp)
        backup.create_backup(cfg)
        restore.restore_test(cfg)
        paths = report.write_all(cfg, self.tmp / "reports")
        text = {p.name: p.read_text() for p in paths}
        self.assertIn("RPO", text["backup-policy.md"])
        self.assertIn("RTO", text["backup-policy.md"])
        self.assertIn("Ransomware", text["incident-playbook.md"])
        self.assertIn("Restore test results", text["recovery-report.md"])
        self.assertIn("PASS", text["recovery-report.md"])


if __name__ == "__main__":
    unittest.main()
