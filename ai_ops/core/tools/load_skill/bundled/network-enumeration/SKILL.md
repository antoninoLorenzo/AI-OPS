---
name: network-enumeration
description: Use this skill when a task requires identifying hosts, open ports, or running services on a target network.
metadata: 
  requirements:
  - nmap
---

# Network Enumeration


## Operational Flow

```
Discover Live Hosts
        │
        ├─ no hosts found? ──────────────────────────┐
        │                                            ↓
        ↓                                   IDS/Firewall Evasion
   Map Open Ports                                    │
        │                                            │
        ├─ ports filtered? ──────────────────────────┘
        │
        ↓
  Identify Services and Versions
        │
        ├─ UDP service suspected? ──→  Scan UDP Services
        │
        └─ OS context needed? ──────→  OS Fingerprinting
```

---

## Discover Live Hosts

**Goal:** Build a confirmed live-host list before spending time on port scanning. Never skip this step, scanning a dead host wastes time and produces no signal.

**When you are given a CIDR range**, use host discovery to find which hosts are alive:
```bash
# Standard: uses ARP automatically on local Ethernet (most reliable on LAN)
nmap -sn -n <CIDR>

# ICMP blocked: broaden discovery probes
nmap -sn -n -PE -PP -PM <CIDR>

# TCP-based discovery when ICMP is fully blocked
nmap -sn -n -PS22,80,443 -PA80,443 <CIDR>
```

**When you are given a single IP**, confirm reachability before scanning:
```bash
# Quick reachability check
ping -c 3 <TARGET>

# Nmap host discovery on a single target
nmap -sn -n <TARGET>
```
If `ping` and `-sn` both return nothing, the host may still be alive but filtering probes.
Proceed to Map Open Ports with `-Pn` (treat as up) rather than concluding it is dead.
Only escalate to IDS/Firewall Evasion if the port scan also returns all `filtered`.

**If no hosts appear on a CIDR sweep:** the subnet may be using host-based firewalls that drop probes. Move to IDS/Firewall Evasion before concluding a host is dead.

---

## Map Open Ports

**Goal:** Identify which ports are open on confirmed live hosts.
Always pass `-Pn` here, you already know the host is up, so skip re-discovery.

```bash
# First pass: well-known ports, fast
nmap -sS -Pn -n -p 1-1024 <TARGET>

# Expanded: include high ports for non-standard services
nmap -sS -Pn -n -p 1-65535 <TARGET>

# Targeted: when you already suspect a service family
nmap -sS -Pn -n -p 80,443,8080,8443,8000 <TARGET>
```

Focus on `open` ports. `filtered` means a firewall is dropping packets, move to IDS/Firewall Evasion. `closed` means no service is listening but the host responded.

---

## Identify Services and Versions

**Goal:** Determine what software is listening on the open ports found above.
This is the step that turns port numbers into testable hypotheses.

```bash
# Version detection only — fastest, least intrusive
nmap -sS -sV -Pn -n -p <OPEN_PORTS> <TARGET>

# Aggressive version probing — slower, use when -sV is inconclusive
nmap -sS -sV --version-intensity 9 -Pn -n -p <OPEN_PORTS> <TARGET>
```

**Using NSE scripts selectively:** avoid running all scripts blindly with `-sC`, it is slow and noisy. Pick scripts by category or by name based on what you already know:

```bash
# Safe discovery scripts only (low noise, good general enrichment)
nmap -sS -sV --script=safe -Pn -n -p <OPEN_PORTS> <TARGET>

# Target a specific service you already identified
nmap -sS --script=http-title,http-headers -Pn -n -p 80,443 <TARGET>
nmap -sS --script=ssh-hostkey,ssh-auth-methods -Pn -n -p 22 <TARGET>
nmap -sS --script=ftp-anon,ftp-banner -Pn -n -p 21 <TARGET>
nmap -sS --script=smb-os-discovery,smb-security-mode -Pn -n -p 445 <TARGET>
```

Script categories ranked by noise level: `safe` → `discovery` → `version` → `auth` → `intrusive`. Stay in `safe` and `discovery` unless you have a specific reason to go further.

The `VERSION` column and any script output are the primary artifacts from this step. Record the service name and version string — these drive every subsequent decision.

---

## Scan UDP Services

**Goal:** Discover services that only listen on UDP. Nmap's default TCP scan misses these entirely. The most common UDP services in pentest contexts: SNMP (161), DNS (53), TFTP (69), NTP (123), DHCP (67/68).

```bash
# Targeted UDP scan — requires root; much slower than TCP
nmap -sU -Pn -n -p 161,53,69,123,500 <TARGET>

# With version detection on a specific suspected service
nmap -sU -sV -Pn -n -p 161 <TARGET>
```

Limit `-p` to ports you actually suspect, a full UDP sweep is extremely slow.

If a UDP port shows `open|filtered` (no response received), probe it manually with the service's own client to confirm. For SNMP: `snmpwalk -v2c -c public <TARGET>`, a valid response confirms the port is open.

---

## IDS/Firewall Evasion

**Goal:** Get scan results when a firewall or IDS is blocking or distorting responses. Use this when host discovery returns nothing on a subnet you know is populated, or when port scanning returns mostly `filtered` results.

**Fragment packets**: split probes so signature-based IDS cannot match them:
```bash
nmap -sS -f -Pn -n -p <PORTS> <TARGET>
nmap -sS -ff -Pn -n -p <PORTS> <TARGET>        # 16-byte fragments
nmap -sS --mtu 24 -Pn -n -p <PORTS> <TARGET>
```

**Slow the scan down**: many IDS systems use rate thresholds:
```bash
nmap -sS -T1 -Pn -n -p <PORTS> <TARGET>        # very slow; evades rate-based detection
nmap -sS -T2 -Pn -n -p <PORTS> <TARGET>        # restrained
```
Default is `-T3`. Never use `-T5` when evasion matters — it is maximally noisy.

**Use decoys**: inject fake source IPs so your real IP is one of many:
```bash
nmap -sS -D RND:10 -Pn -n -p <PORTS> <TARGET>
nmap -sS -D <DECOY1>,<DECOY2>,ME -Pn -n -p <PORTS> <TARGET>
```
`ME` places your real IP at a known position in the decoy list. Omit it to place randomly.

**Spoof source port**: some firewalls permit traffic from well-known source ports:
```bash
nmap -sS --source-port 53 -Pn -n -p <PORTS> <TARGET>
nmap -sS --source-port 80 -Pn -n -p <PORTS> <TARGET>
```

**Use alternative scan types**: when SYN scan (`-sS`) is blocked:
```bash
nmap -sA -Pn -n -p <PORTS> <TARGET>    # ACK scan: reveals unfiltered vs. filtered, not open/closed
nmap -sF -Pn -n -p <PORTS> <TARGET>    # FIN scan: evades some stateless ACLs
nmap -sN -Pn -n -p <PORTS> <TARGET>    # NULL scan: no flags set
nmap -sX -Pn -n -p <PORTS> <TARGET>    # Xmas scan: FIN+PSH+URG set
```
ACK scan does not reveal open vs. closed, it reveals which ports the firewall passes through.
Use it to find traversable ports, then probe those with a regular scan.

**Pad packets and vary TTL:**
```bash
nmap -sS --data-length 25 -Pn -n -p <PORTS> <TARGET>
nmap -sS --ttl 64 -Pn -n -p <PORTS> <TARGET>
```

**Decision ladder:** start with `-T1 -f`. If still filtered, add `-D RND:5`. If ACK scan shows `unfiltered` on a port where SYN shows `filtered`, the firewall is stateful, try `--source-port 53` to exploit a permit rule. Escalate one step at a time.

---

## OS Fingerprinting

**Goal:** Determine the operating system of the target. Run this only after you have open port results, OS fingerprinting needs at least one open and one closed port to produce a reliable guess.

```bash
nmap -sS -O -Pn -n -p <OPEN_PORTS> <TARGET>
```

If the result says "too many fingerprints match" or confidence is below 90%, treat the output as noise and do not act on it.