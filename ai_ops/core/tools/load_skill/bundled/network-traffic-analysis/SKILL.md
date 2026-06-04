---
name: network-traffic-analysis
description: Capture and analyze network traffic to extract credentials, session tokens, flags, or other sensitive data in transit. Load when the objective involves intercepting traffic between hosts or observing network communications.
metadata:
  requirements:
  - tcpdump
  - tshark
  - python3
---

# Network Traffic Analysis

The general process is always: **capture traffic to a file → analyze the file**.
Never stream raw packet output to the terminal, it will flood context immediately.

Two capture modes exist depending on your position relative to the traffic:

- **Passive**: you are already in the traffic path (traffic is destined to you, or it is broadcast on the segment). Use `tcpdump` to capture.
- **Active (MITM)**: traffic flows between two other hosts and you need to insert yourself into the path. Requires concurrent redirection + capture; use a Python script.


## Understand the Network Layout

Identify: your interface name, your IP, the local subnet, and the gateway IP. These are needed for all subsequent steps.
```bash
# identify interfaces and addresses
ip -br addr show

# identify gateway and local subnets
ip route show
```

## Discover What Is on the Wire

Run a short broad capture to understand what traffic exists before committing to a targeted approach. Limit by packet count to avoid large files.

```bash
tcpdump -i eth0 -w /tmp/discovery.pcap -nn -c 200 -G 15 -W 1 2>/dev/null
```

To analyze the capture suppress per-packet output, show only summaries:

```bash
# which protocols are present?
tshark -r /tmp/discovery.pcap -q -z io,phs 2>/dev/null | grep -v "^$" | head -30

# which hosts are talking to each other and how much?
tshark -r /tmp/discovery.pcap -q -z conv,ip 2>/dev/null | grep -v "^$" | head -20
```

From this output determine:
- What protocols are in use (TCP, UDP, ICMP, ARP, HTTP, etc.)
- Which pairs of hosts are communicating
- Whether you are already in the traffic path or not

**Decide which capture mode to use:**

If the traffic you need to observe is already reaching your interface (it is destined to you, or it is broadcast), passive capture is sufficient.

If the traffic flows between two other hosts and you need to intercept it, you must insert yourself into the path. How you insert yourself depends on the network topology: identify where the hosts are relative to you (same L2 segment, different subnet, DNS-dependent, etc.) and choose the appropriate redirection technique accordingly.

If the discovery capture is empty, re-examine the task description, the hosts may not be communicating, or the interface or subnet may be wrong. Try setting `tcpdump` interface to another interface or any interface (`-i any`).


## Passive Capture

Capture with a targeted BPF filter to limit file size and noise:

```bash
# traffic involving a specific host
tcpdump -i eth0 -w /tmp/capture.pcap -nn "host 192.168.1.10" -c 500 -G 20 -W 1 2>/dev/null

# specific protocol only
tcpdump -i eth0 -w /tmp/capture.pcap -nn "udp and host 192.168.1.10" -c 500 -G 20 -W 1 2>/dev/null

# traffic between two specific hosts
tcpdump -i eth0 -w /tmp/capture.pcap -nn "host 192.168.1.10 and host 192.168.1.1" -c 500 -G 20 -W 1 2>/dev/null
```

BPF filter primitives: `host`, `net`, `port`, `tcp`, `udp`, `arp`, `icmp`.
Combine with `and`, `or`, `not`.

## MITM Capture

When traffic flows between two other hosts, you need to redirect it through your machine while forwarding it so the hosts stay connected, and capture it in transit. The appropriate redirection technique depends on the network topology. Determine this from the layout and from the task description, then implement accordingly.

For whichever technique you use, the capture pattern is the same: run redirection and capture concurrently in a single script using `scapy`, write to a pcap file, stop automatically after a fixed duration. 
This is necessary because the terminal is non-interactive, so backgrounded processes cannot be managed across separate commands reliably.

Here is an example of how to write packets to a `.pcap` file using `AsyncSniffer` and `PcapWriter` in `scapy`:
```python
import functools
from scapy.sendrecv import AsyncSniffer
from scapy.utils import PcapWriter

def write_packet(packet, writer):
    writer.write(packet)

writer = PcapWriter("capture.pcap", append=False, sync=True)

sniffer = AsyncSniffer(
    iface="...",
    filter=f"...",
    prn=functools.partial(write_packet, writer=writer),
    store=False
)

sniffer.start()
# ...
sniffer.stop()
writer.close()
```

Verify the capture has content before analyzing:

```bash
tshark -r /tmp/mitm_capture.pcap -q -z io,phs 2>/dev/null | grep -v "^$" | head -20
```

If the capture is empty or only shows ARP traffic, the redirection did not succeed.
Check that both IPs are reachable and that the correct gateway was identified.


## Analyze the Capture

The analysis step is identical regardless of how the capture was obtained.

### Identify protocol and conversation structure first

```bash
# protocol breakdown
tshark -r /tmp/capture.pcap -q -z io,phs 2>/dev/null | grep -v "^$" | head -30

# IP conversations
tshark -r /tmp/capture.pcap -q -z conv,ip 2>/dev/null | grep -v "^$" | head -20

# UDP conversations (if UDP is present)
tshark -r /tmp/capture.pcap -q -z conv,udp 2>/dev/null | grep -v "^$" | head -20
```

### Extract payload content

Match the extraction command to the protocol identified above:

```bash
# UDP payload as text
tshark -r /tmp/capture.pcap -Y "udp" -T fields -e ip.src -e ip.dst -e data.text 2>/dev/null | grep -v "^$" | head -30

# TCP payload
tshark -r /tmp/capture.pcap -Y "tcp" -T fields -e ip.src -e ip.dst -e tcp.payload 2>/dev/null | grep -v "^$" | head -30

# HTTP — POST bodies and auth headers
tshark -r /tmp/capture.pcap \
  -Y "http.request.method == POST or http.authorization" \
  -T fields -e ip.src -e http.host -e http.file_data -e http.authorization \
  2>/dev/null | grep -v "^$" | head -20

# FTP credentials
tshark -r /tmp/capture.pcap \
  -Y "ftp.request.command == USER or ftp.request.command == PASS" \
  -T fields -e ip.src -e ftp.request.command -e ftp.request.arg \
  2>/dev/null | head -10

# DNS queries
tshark -r /tmp/capture.pcap -Y "dns.flags.response == 0" \
  -T fields -e ip.src -e dns.qry.name \
  2>/dev/null | sort -u | head -20
```

### Broad sweep when protocol is unknown or above filters return nothing

```bash
tshark -r /tmp/capture.pcap \
  -T fields -e data.text \
  2>/dev/null | grep -v "^$" | head -40
```

If you have a **whiteboard** and found the target data, record it:
```
name: traffic_finding
description: Found <data type> in <protocol> traffic between <src> and <dst>.
content: tshark command that extracted it, raw value
```
