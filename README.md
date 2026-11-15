# 🛟 RecoverReady

**Backups you can actually restore, plus the paperwork to prove it.**

Ransomware, theft or a dead disk can destroy an organisation's data overnight. Most small organisations *have* backups but have never tested a restore, never written down how fast they must recover, and have no plan for the first panicked hour. RecoverReady is a dependency-free Python CLI that does the whole job and produces the four deliverables a real recovery programme needs:

| Deliverable | How RecoverReady produces it |
|---|---|
| **Backup policy** | `recoverready report` → `backup-policy.md` (scope, 3-2-1 rule, schedule, retention, roles, ISO 27001 A.8.13 / NIST CSF alignment) |
| **Restore test results** | `recoverready restore-test` restores the *offsite* copy to a scratch folder, hash-checks every file and times it → logged and shown in `recovery-report.md` |
| **Recovery-time objectives** | RPO/RTO targets in your config, measured against reality (`status` and the report show *target vs actual*) |
| **Incident playbook** | `incident-playbook.md`: printable checklists for ransomware, hardware failure, device theft and accidental deletion, filled with your contacts and targets |

## What makes it more than a copy script

- **Ransomware guard:** before every backup it looks for ransomware extensions, ransom-note names, and a mass change of files that now look like random (encrypted) data. If it smells an attack it **blocks the backup and deletes nothing**, so good backups can't be overwritten or aged out by encrypted ones.
- **Tamper-evident:** every backup has a SHA-256 manifest for every file and for the archive; `verify` catches damage or tampering. Backups are written read-only.
- **3-2-1 aware:** copies go to every destination and are hash-checked after copying. `status` warns if you don't meet 3 copies / 2 kinds of location / 1 offsite, and warns when there's no *offline* copy.
- **Safe restores:** extraction refuses path-traversal and never restores links or devices.
- **Honest RTO:** estimated recovery = measured restore time + configurable overhead (detection, decisions, setup), compared with your RTO target.
- **Retention that can't hurt you:** keeps the newest backup of each recent day/week/month, never deletes the newest, never prunes after a blocked or failed run.
- **Zero dependencies**: Python 3.8+ standard library only.

## Try it in 30 seconds (safe, fake data)

```bash
git clone https://github.com/MunyendoDarren/recoverready.git
cd recoverready
python -m recoverready demo --out demo-output
```

The demo creates a fake company's files, backs them up, restore-tests the offsite copy, **simulates a ransomware attack**, shows the guard blocking the next backup, then writes the reports into `demo-output/reports/`.

## Use it for real

```bash
pip install -e .                         # optional: gives you the `recoverready` command
recoverready init                        # writes recoverready.json, edit it
recoverready backup                      # verified backup → every destination
recoverready verify                      # hash-check all backups (--quick, --latest)
recoverready restore-test                # restore the offsite copy to a temp folder and time it
recoverready status                      # are we meeting RPO / RTO / 3-2-1?
recoverready report --out reports        # policy + playbook + recovery report (Markdown)
```

Exit codes make it scriptable: `backup` returns `0` ok, `3` blocked by ransomware guard, `4` partial (a copy failed), `1` error; `restore-test` returns `1` on failure and `2` if it works but misses the RTO.

**Schedule it** (cron, daily at 02:00, plus a monthly restore test):

```cron
0 2 * * *  cd /srv/backup-config && recoverready backup  || mail -s "BACKUP PROBLEM" it@example.com < /dev/null
0 4 1 * *  cd /srv/backup-config && recoverready restore-test
```
On Windows use Task Scheduler with the same commands.

## Configuration (`recoverready.json`)

```jsonc
{
  "organization": "Demo Shop Ltd",
  "sources": ["/srv/shared", "/home/accounts/documents"],
  "destinations": [
    {"path": "/mnt/nas/backups", "kind": "local"},
    {"path": "/mnt/cloud-sync/backups", "kind": "offsite"},
    {"path": "/media/usb-rotating", "kind": "offline"}   // plug in, back up, unplug
  ],
  "rpo_hours": 24,            // most data you accept losing
  "rto_hours": 4,             // longest you accept being down
  "rto_overhead_minutes": 60, // detection + decision + setup, added to measured restore time
  "restore_test_every_days": 30,
  "retention": {"daily": 7, "weekly": 4, "monthly": 6},
  "ransomware_guard": {"enabled": true, "max_changed_percent": 30, "min_files": 20},
  "critical_assets": [{"name": "Customer records", "priority": 1, "owner": "Operations"}],
  "contacts": [{"role": "Incident lead", "name": "…", "phone": "…"}]
}
```
See `examples/recoverready.example.json`. Relative paths are resolved from the config file's folder; destinations inside a source are rejected.

## Project layout

```
recoverready/
├── cli.py          # init / backup / verify / restore-test / status / report / demo
├── backup.py       # archive + hashing in one pass, multi-destination copy, retention
├── indicators.py   # ransomware guard heuristics
├── verify.py       # archive + per-file integrity checks
├── restore.py      # safe extraction, timed restore test, RTO estimate
├── status.py       # RPO / RTO / 3-2-1 / test-freshness health checks
├── retention.py    # day / week / month retention selection
├── report.py       # policy, playbook, recovery report generators
├── config.py  manifest.py  logs.py  demo.py
tests/              # 18 tests: round trip, tamper, ransomware, retention, path traversal, reports
```

`python -m unittest discover -s tests -v`

## Honest limitations

- The ransomware guard is **heuristic**. Malware that preserves file timestamps, encrypts slowly, or renames nothing can evade it, and legitimate bulk changes of random-looking data can trigger it (`--force` overrides). It is a safety net, not antivirus.
- Archives are **not encrypted**. Keep backup storage on encrypted disks/cloud buckets (encryption at rest) or add GPG/age yourself (see roadmap).
- Manifests aren't signed: someone with write access to both archive *and* manifest could forge a pair. Keep one copy **offline/immutable** (the policy and `status` push you towards this).
- If a file shrinks mid-backup the run aborts cleanly (nothing is kept) and should be re-run.
- Estimated RTO is a model. Do a real full-scale restore drill at least once a year.

## Roadmap

- [ ] Built-in encryption (age/AES-GCM) with key-escrow instructions
- [ ] Signed manifests (Ed25519) and immutable object-store destinations (S3 Object Lock)
- [ ] Incremental / deduplicated backups
- [ ] Email / webhook alerts on failure, blocked backups, and overdue restore tests
- [ ] HTML/PDF versions of the reports
- [ ] Database dump helpers (MySQL/PostgreSQL) before archiving

## License

MIT, see [LICENSE](LICENSE).
