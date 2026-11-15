# Incident Playbook - Data Loss and Ransomware (Demo Shop Ltd)

> Print this page. If systems are down you will not be able to open it from the network.

**Targets:** lose no more than 24 hour(s) of data (RPO); be recovered within 4 hour(s) (RTO).

## Contacts

| Role | Name | Phone |
|---|---|---|
| Incident lead | Your name | +254 700 000 000 |
| IT support / provider | Provider name | +254 700 000 001 |
| Management | Director name | +254 700 000 002 |

## A. Ransomware (files encrypted, ransom note, or the backup guard says BLOCKED)

### First 15 minutes - contain
- [ ] **Do not pay and do not reply** to the attacker yet. Take a photo of the ransom note.
- [ ] Disconnect affected computers from the network and Wi-Fi (unplug the cable). **Do not shut down** if you can avoid it - memory can hold evidence.
- [ ] Disconnect or unmount the backup drives and cloud sync **now** so they cannot be encrypted too.
- [ ] Tell the incident lead. Write down the time, what was seen and who saw it.
- [ ] Change passwords for admin, email and cloud accounts **from a clean device** (not an infected one).

### First hour - assess
- [ ] Which computers, folders and accounts are affected? Is the damage still spreading?
- [ ] Run `recoverready status` and `recoverready verify` on a clean machine to find the **last good backup** (before the infection).
- [ ] Does it hold personal or customer data? If yes, start the notification clock (see Communication).

### Recover (decision point at 2 h - if not progressing, escalate to Management)
- [ ] Rebuild or wipe infected machines from trusted media. Do not restore onto a machine that is still infected.
- [ ] Restore into a **clean, isolated** folder first: `recoverready restore-test --archive <name> --dest <folder> --keep`
- [ ] Check the restored files open correctly; scan them with up-to-date antivirus.
- [ ] Restore the most important assets first (priority 1 in the policy), then the rest.
- [ ] Reconnect to the network only when everything is clean; monitor closely for a week.

### Communication
- [ ] Staff: short, factual message - what happened, what to do, what not to do.
- [ ] Customers/partners: if their data may be affected, tell them promptly and honestly.
- [ ] Regulators: personal-data breaches usually must be reported within **72 hours** of becoming aware (check your local law - e.g. Kenya Data Protection Act 2019, GDPR).
- [ ] Police / national CERT (e.g. KE-CIRT/CC in Kenya) and your insurer, if you have cover.

### Afterwards
- [ ] Find out how they got in (phishing? exposed remote access? unpatched software?) and close that door before reconnecting.
- [ ] Rotate **all** passwords and keys. Update this playbook with what you learned.

## B. Hardware failure (disk, laptop or server dies)

- [ ] Stop using the device; do not keep power-cycling a failing disk.
- [ ] Identify what was on it and when it was last backed up (`recoverready status`).
- [ ] Prepare replacement hardware, then restore: `recoverready restore-test --dest <folder> --keep`.
- [ ] Confirm the restored data is complete. Expected total time: under 4 hour(s).

## C. Theft or loss of a device

- [ ] Report to the incident lead immediately and to the police for an incident number.
- [ ] Lock or remotely wipe the device; reset passwords and revoke sessions for the user.
- [ ] Was the disk encrypted? If **not**, treat any personal data on it as breached (see Communication).
- [ ] Restore the user's files to a replacement device from backup.

## D. Accidental deletion or overwritten file

- [ ] Do not keep editing the folder. Note the file name, folder and approximate time.
- [ ] List backups (`recoverready verify`), pick one from before the mistake, restore it to a scratch folder and copy the file back.

## Decision log

| Time | What happened / decision | By |
|---|---|---|
|  |  |  |
|  |  |  |
|  |  |  |
