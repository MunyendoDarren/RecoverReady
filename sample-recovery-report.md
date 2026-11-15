# Recovery Report - Demo Shop Ltd

_Generated 2026-11-14 20:07 UTC_

## Overall: **NOT MEETING TARGETS**

| Status | Check | Detail |
|---|---|---|
| OK | Recovery point (RPO) | Newest backup is 0.0 h old; target is 24 h. |
| OK | 3-2-1 rule | 3 copies across ['local', 'offsite']. |
| WARN | Ransomware resilience | No 'offline' copy. Ransomware that reaches your network can often reach connected backups too. |
| OK | Destination /tmp/rr_demo/backups/local | 1 backup(s) (local). |
| OK | Destination /tmp/rr_demo/backups/offsite | 1 backup(s) (offsite). |
| OK | Restore testing | Last test passed 0 day(s) ago. |
| OK | Recovery time (RTO) | Estimated full recovery 60.0 min vs target 240 min. |
| FAIL | Ransomware guard | A recent backup was BLOCKED because data looked encrypted. Treat as an incident until cleared. |

## Recovery objectives: target vs actual

| Objective | Target | Actual | Result |
|---|---|---|---|
| RPO (max data loss) | 24 hour(s) | newest backup 0.0 h old | met |
| RTO (max downtime) | 4 hour(s) | 60.0 min (restore 0.02 s + 60 min overhead) | met |

## Restore test results (latest 10)

| Date | Backup | From | Files | Size (MB) | Restore time (s) | Est. recovery (min) | Result |
|---|---|---|---|---|---|---|---|
| 2026-11-14 20:07:34 UTC | backup-20261114-200733.tar.gz | offsite | 65 | 2.71 | 0.02 | 60.0 | PASS |

## Backup history (latest 10)

| Date | Result | Files | Size (MB) | Notes |
|---|---|---|---|---|
| 2026-11-14 20:07:34 UTC | BLOCKED | - | 0.0 | 65 new file(s) with ransomware-style extensions (e.g. company-data/customers/customers-00.csv.locked); 1 file(s) that look like ransom notes |
| 2026-11-14 20:07:33 UTC | OK | 65 | 2.71 |  |

## Stored backups

| Location | Kind | Backup | Size (MB) |
|---|---|---|---|
| `/tmp/rr_demo/backups/local` | local | backup-20261114-200733.tar.gz | 0.30 |
| `/tmp/rr_demo/backups/offsite` | offsite | backup-20261114-200733.tar.gz | 0.30 |

## Actions needed

- [ ] **Ransomware resilience** - No 'offline' copy. Ransomware that reaches your network can often reach connected backups too.
- [ ] **Ransomware guard** - A recent backup was BLOCKED because data looked encrypted. Treat as an incident until cleared.
