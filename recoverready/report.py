"""Generate the four deliverables as Markdown (renders nicely on GitHub):
   1. Backup policy   2. Restore test results   3. Recovery-time objectives (RPO/RTO)   4. Incident playbook
"""
from __future__ import annotations

import datetime
from pathlib import Path

from . import logs, status
from .backup import list_backups


def _table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)


def _hours(h) -> str:
    return f"{h:g} hour(s)"


def _contacts(cfg) -> str:
    return _table(["Role", "Name", "Phone"], [[c["role"], c["name"], c["phone"]] for c in cfg["contacts"]])


# --------------------------------------------------------------------------- policy
def policy_md(cfg, now=None) -> str:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    r = cfg["retention"]
    dests = cfg.destinations
    L = [f"# Backup Policy - {cfg['organization']}", "",
         f"_Owner: {cfg['owner']} - Version generated {now:%Y-%m-%d} - Review every 12 months or after any incident._", "",
         "## 1. Purpose",
         "To make sure the organisation can recover its important data after ransomware, theft, accidental deletion, "
         "hardware failure or disaster, within agreed time limits.", "",
         "## 2. Scope - what we protect", "",
         _table(["Priority", "Asset", "Owner"], [[a["priority"], a["name"], a["owner"]] for a in sorted(cfg["critical_assets"], key=lambda a: a["priority"])]),
         "", "Folders included in the automated backup:", ""]
    L += [f"- `{s}`" for s in cfg.sources]
    L += ["", "Excluded: " + ", ".join(f"`{e}`" for e in cfg["exclude"]), "",
          "## 3. Objectives", "",
          _table(["Objective", "Target", "Meaning"], [
              ["RPO (Recovery Point Objective)", _hours(cfg["rpo_hours"]), "The most data we accept losing. A backup must exist that is never older than this."],
              ["RTO (Recovery Time Objective)", _hours(cfg["rto_hours"]), "The longest we accept being without our data after an incident, measured from the decision to restore."],
          ]), "",
          "## 4. The 3-2-1 rule (plus offline)", "",
          "- **3 copies** of the data: the live data plus two backups.",
          "- **2 different kinds** of location (e.g. local disk and cloud/offsite).",
          "- **1 copy offsite or offline**, out of reach of ransomware that infects the main network.",
          "- **0 errors**: every backup is hash-verified, and restores are tested regularly.", "",
          "Configured destinations:", "",
          _table(["#", "Location", "Kind"], [[i + 1, f"`{d['path']}`", d["kind"]] for i, d in enumerate(dests)]), "",
          "## 5. Schedule and retention", "",
          f"- Backups run at least every **{_hours(cfg['rpo_hours'])}** (`recoverready backup`, scheduled with cron / Task Scheduler).",
          f"- Retention: keep the newest backup of each of the last **{r['daily']} days**, **{r['weekly']} weeks** and **{r['monthly']} months**.",
          "- Old backups are only deleted after a *new* backup has been written and copied successfully, and never when the ransomware guard has blocked a run.", "",
          "## 6. Protection of backups", "",
          "- Backup files are written read-only and are never modified after creation.",
          "- Every backup has a manifest with SHA-256 hashes of every file and of the archive itself.",
          "- The ransomware guard stops a backup if data looks freshly encrypted, so good backups are not overwritten or aged out by bad ones.",
          "- Backup storage uses separate credentials from everyday accounts; the offsite/offline copy is not permanently mounted on the main network.",
          "- Backups containing personal data are protected like the original data (encrypted disks/cloud storage, access limited to named people).", "",
          "## 7. Testing", "",
          f"- A **restore test** is performed at least every **{cfg['restore_test_every_days']} days** (`recoverready restore-test`), restoring the offsite copy into a scratch folder and checking every file.",
          "- Results and measured recovery time are recorded in the recovery report. A failed test is treated as an incident.",
          f"- Estimated recovery time = measured restore time + {cfg['rto_overhead_minutes']} minutes for detection, decision and setup. It must stay within the RTO.", "",
          "## 8. Roles", "", _contacts(cfg), "",
          "## 9. Incident response", "", "Follow `incident-playbook.md`.", "",
          "## 10. Alignment", "",
          "This policy is designed to support ISO/IEC 27001:2022 Annex A control 8.13 (Information backup) and the Recover function of the NIST Cybersecurity Framework 2.0."]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- playbook
def playbook_md(cfg) -> str:
    rto = cfg["rto_hours"]
    L = [f"# Incident Playbook - Data Loss and Ransomware ({cfg['organization']})", "",
         "> Print this page. If systems are down you will not be able to open it from the network.", "",
         f"**Targets:** lose no more than {_hours(cfg['rpo_hours'])} of data (RPO); be recovered within {_hours(rto)} (RTO).", "",
         "## Contacts", "", _contacts(cfg), "",
         "## A. Ransomware (files encrypted, ransom note, or the backup guard says BLOCKED)", "",
         "### First 15 minutes - contain",
         "- [ ] **Do not pay and do not reply** to the attacker yet. Take a photo of the ransom note.",
         "- [ ] Disconnect affected computers from the network and Wi-Fi (unplug the cable). **Do not shut down** if you can avoid it - memory can hold evidence.",
         "- [ ] Disconnect or unmount the backup drives and cloud sync **now** so they cannot be encrypted too.",
         "- [ ] Tell the incident lead. Write down the time, what was seen and who saw it.",
         "- [ ] Change passwords for admin, email and cloud accounts **from a clean device** (not an infected one).", "",
         "### First hour - assess",
         "- [ ] Which computers, folders and accounts are affected? Is the damage still spreading?",
         "- [ ] Run `recoverready status` and `recoverready verify` on a clean machine to find the **last good backup** (before the infection).",
         "- [ ] Does it hold personal or customer data? If yes, start the notification clock (see Communication).", "",
         f"### Recover (decision point at {rto / 2:g} h - if not progressing, escalate to {cfg['contacts'][-1]['role']})",
         "- [ ] Rebuild or wipe infected machines from trusted media. Do not restore onto a machine that is still infected.",
         "- [ ] Restore into a **clean, isolated** folder first: `recoverready restore-test --archive <name> --dest <folder> --keep`",
         "- [ ] Check the restored files open correctly; scan them with up-to-date antivirus.",
         "- [ ] Restore the most important assets first (priority 1 in the policy), then the rest.",
         "- [ ] Reconnect to the network only when everything is clean; monitor closely for a week.", "",
         "### Communication",
         "- [ ] Staff: short, factual message - what happened, what to do, what not to do.",
         "- [ ] Customers/partners: if their data may be affected, tell them promptly and honestly.",
         "- [ ] Regulators: personal-data breaches usually must be reported within **72 hours** of becoming aware (check your local law - e.g. Kenya Data Protection Act 2019, GDPR).",
         "- [ ] Police / national CERT (e.g. KE-CIRT/CC in Kenya) and your insurer, if you have cover.", "",
         "### Afterwards",
         "- [ ] Find out how they got in (phishing? exposed remote access? unpatched software?) and close that door before reconnecting.",
         "- [ ] Rotate **all** passwords and keys. Update this playbook with what you learned.", "",
         "## B. Hardware failure (disk, laptop or server dies)", "",
         "- [ ] Stop using the device; do not keep power-cycling a failing disk.",
         "- [ ] Identify what was on it and when it was last backed up (`recoverready status`).",
         "- [ ] Prepare replacement hardware, then restore: `recoverready restore-test --dest <folder> --keep`.",
         f"- [ ] Confirm the restored data is complete. Expected total time: under {_hours(rto)}.", "",
         "## C. Theft or loss of a device", "",
         "- [ ] Report to the incident lead immediately and to the police for an incident number.",
         "- [ ] Lock or remotely wipe the device; reset passwords and revoke sessions for the user.",
         "- [ ] Was the disk encrypted? If **not**, treat any personal data on it as breached (see Communication).",
         "- [ ] Restore the user's files to a replacement device from backup.", "",
         "## D. Accidental deletion or overwritten file", "",
         "- [ ] Do not keep editing the folder. Note the file name, folder and approximate time.",
         "- [ ] List backups (`recoverready verify`), pick one from before the mistake, restore it to a scratch folder and copy the file back.", "",
         "## Decision log", "",
         _table(["Time", "What happened / decision", "By"], [["", "", ""], ["", "", ""], ["", "", ""]]), ""]
    return "\n".join(L)


# --------------------------------------------------------------------------- recovery report
def recovery_report_md(cfg, now=None) -> str:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    ev = status.evaluate(cfg, now)
    tests = logs.read(cfg.state_dir / "restore-tests.jsonl")
    runs = logs.read(cfg.state_dir / "backups.jsonl")
    badge = {"OK": "PASS", "WARN": "NEEDS ATTENTION", "FAIL": "NOT MEETING TARGETS"}[ev["overall"]]
    L = [f"# Recovery Report - {cfg['organization']}", "", f"_Generated {now:%Y-%m-%d %H:%M UTC}_", "",
         f"## Overall: **{badge}**", "",
         _table(["Status", "Check", "Detail"], [[c["level"], c["name"], c["detail"]] for c in ev["checks"]]), "",
         "## Recovery objectives: target vs actual", ""]
    age = ev["newest_backup_age_hours"]
    last_ok = next((t for t in reversed(tests) if t["passed"]), None)
    rows = [["RPO (max data loss)", _hours(cfg["rpo_hours"]), "no backups" if age is None else f"newest backup {age:.1f} h old",
             "-" if age is None else ("met" if age <= cfg["rpo_hours"] else "MISSED")]]
    if last_ok:
        rows.append(["RTO (max downtime)", _hours(cfg["rto_hours"]),
                     f"{last_ok['estimated_recovery_minutes']} min (restore {last_ok['restore_seconds']} s + {cfg['rto_overhead_minutes']} min overhead)",
                     "met" if last_ok["meets_rto"] else "MISSED"])
    else:
        rows.append(["RTO (max downtime)", _hours(cfg["rto_hours"]), "never measured", "UNKNOWN"])
    L += [_table(["Objective", "Target", "Actual", "Result"], rows), "",
          "## Restore test results (latest 10)", ""]
    if tests:
        L.append(_table(["Date", "Backup", "From", "Files", "Size (MB)", "Restore time (s)", "Est. recovery (min)", "Result"],
                        [[t["date"], t.get("archive", "-"), t.get("source_kind", "-"), t["files"], round(t["bytes"] / 1e6, 2),
                          t.get("restore_seconds", "-"), t.get("estimated_recovery_minutes", "-"), "PASS" if t["passed"] else "FAIL: " + "; ".join(t["problems"][:1])]
                         for t in tests[-10:][::-1]]))
    else:
        L.append("_No restore tests recorded yet._")
    L += ["", "## Backup history (latest 10)", ""]
    if runs:
        L.append(_table(["Date", "Result", "Files", "Size (MB)", "Notes"],
                        [[r["date"], r["status"].upper(), r.get("files", "-"), round(r.get("bytes", 0) / 1e6, 2),
                          "; ".join(r.get("reasons", []) + r.get("problems", []) + ([r["message"]] if r.get("message") and r["status"] == "error" else []))[:140]]
                         for r in runs[-10:][::-1]]))
    else:
        L.append("_No backups recorded yet._")
    L += ["", "## Stored backups", ""]
    rows = []
    for d in cfg.destinations:
        for s, arc, _m in list_backups(d["path"])[:5]:
            rows.append([f"`{d['path']}`", d["kind"], arc.name, f"{arc.stat().st_size / 1e6:.2f}"])
    L.append(_table(["Location", "Kind", "Backup", "Size (MB)"], rows) if rows else "_None._")
    todo = [c for c in ev["checks"] if c["level"] in ("FAIL", "WARN")]
    L += ["", "## Actions needed", ""]
    L += [f"- [ ] **{c['name']}** - {c['detail']}" for c in todo] if todo else ["- Nothing outstanding. Keep testing."]
    return "\n".join(L) + "\n"


def write_all(cfg, out_dir) -> list:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = {"backup-policy.md": policy_md(cfg), "incident-playbook.md": playbook_md(cfg), "recovery-report.md": recovery_report_md(cfg)}
    paths = []
    for name, text in files.items():
        p = out / name
        p.write_text(text, encoding="utf-8")
        paths.append(p)
    return paths
