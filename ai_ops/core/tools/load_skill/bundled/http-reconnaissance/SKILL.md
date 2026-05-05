---
name: http-reconnaissance
description: Perform initial HTTP/HTTPS reconnaissance on a target to identify the web stack, exposed endpoints, security headers, and surface-level misconfigurations. Load at the start of any web-facing task before running exploitation tools.
metadata:
  requirements:
    - curl
    - ffuf
    - grep
    - openssl
---

Start with a baseline request against the root path. This confirms the host is responding
and gives you the raw material for fingerprinting.

```bash
curl -sk -D /tmp/headers.txt -o /tmp/body.html --max-time 10 "$TARGET_URL/"
```

If `headers.txt` is empty, the host is not responding. Verify with `nmap -sV -p <port> <host>`
before continuing.

## Fingerprinting

Read `headers.txt` for technology signals: `Server` and `X-Powered-By` give the web server
and language directly. Cookie names are reliable framework indicators —
`PHPSESSID` = PHP, `JSESSIONID` = Java, `csrftoken`/`sessionid` = Django,
`laravel_session` = Laravel, `rack.session` = Ruby. Note any missing security headers
(`Content-Security-Policy`, `X-Frame-Options`, `Strict-Transport-Security`,
`X-Content-Type-Options`) and any `Location` redirect that leaks internal path structure.

Then read the body:

```bash
# CMS, generator tags, framework comments
grep -iE '(generator|wp-content|drupal|joomla|powered by|framework)' /tmp/body.html | head -20

# JS/CSS asset paths — version strings often appear in filenames
grep -oE 'src="[^"]*\.js[^"]*"' /tmp/body.html | head -20

# Request a non-existent path and read the error page — server and framework often self-identify
curl -sk -o /tmp/error.html "$TARGET_URL/doesnotexist_$(date +%s)" && grep -iE '(apache|nginx|iis|php|python|java|ruby|exception|stack trace)' /tmp/error.html | head -10
```

The identified technology determines which file extensions are worth fuzzing later:

| Stack | Extensions to target |
|---|---|
| PHP | `.php`, `.php5`, `.phtml`, `.bak`, `.php.bak` |
| Java / JSP | `.jsp`, `.jspx`, `.do`, `.action` |
| ASP.NET | `.asp`, `.aspx`, `.ashx`, `.asmx`, `.config` |
| Python | `.py`, `.cfg`, `.env` |
| Any | `.bak`, `.old`, `.orig`, `.txt`, `.zip`, `~`, `.swp` |

## Known Paths

Fetch paths the application may expose intentionally or accidentally. These often reveal
structure before any fuzzing is needed.

```bash
for path in robots.txt sitemap.xml sitemap_index.xml .well-known/security.txt crossdomain.xml; do
  status=$(curl -sk -o /tmp/$(basename $path) -w "%{http_code}" "$TARGET_URL/$path")
  [ "$status" = "200" ] && echo "[+] $path" && cat /tmp/$(basename $path)
done
```

Extract any paths from `robots.txt` and sitemap — use them as a supplementary wordlist:

```bash
grep -oE '(/[^ \n]*)' /tmp/robots.txt /tmp/sitemap.xml 2>/dev/null | sort -u > /tmp/known_paths.txt
```

## Wildcard Calibration

This step is mandatory before running ffuf. Many servers return a 200 or redirect for every
path — running ffuf without calibration produces hundreds of false positives.

Request two random paths and compare the responses:

```bash
R1=$(curl -sk -o /tmp/wc1.html -w "%{http_code} %{size_download}" "$TARGET_URL/$(head -c8 /dev/urandom | md5sum | head -c8)"); R2=$(curl -sk -o /tmp/wc2.html -w "%{http_code} %{size_download}" "$TARGET_URL/$(head -c8 /dev/urandom | md5sum | head -c8)"); echo "Sample 1: $R1"; echo "Sample 2: $R2"
```

Choose the ffuf filter based on what you see:

| Both responses | Filter to use |
|---|---|
| `404`, any size | No filter needed — use `-mc 200,201,301,302,307,401,403` |
| `200`, same size | `-fs <that_size>` |
| `200`, similar but not identical size | `-fw $(wc -w < /tmp/wc1.html)` |
| `302` to the same destination | `-fc 302` and inspect the redirect target separately |

## Directory Fuzzing

Run a fast first pass with `common.txt`. This calibrates signal density before committing
to a larger list.

```bash
ffuf -u "$TARGET_URL/FUZZ" \
     -w /usr/share/seclists/Discovery/Web-Content/common.txt \
     -mc 200,201,204,301,302,307,401,403 \
     -t 40 -o /tmp/ffuf_pass1.json -of json -s
```

Parse the results:

```bash
python3 -c "import json; [print(f\"{r['status']}  {r['length']:>8}  {r['url']}\") for r in json.load(open('/tmp/ffuf_pass1.json')).get('results',[])]" | sort
```

If the app shows signs of depth (login panels, API routes, admin paths in Pass 1), follow
up with a broader list. Add the calibrated filter from above.

```bash
ffuf -u "$TARGET_URL/FUZZ" \
     -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt \
     -mc 200,201,204,301,302,307,401,403 \
     -t 40 -o /tmp/ffuf_pass2.json -of json -s
```

For recursion into discovered directories (doubles request count — use with intent):

```bash
ffuf -u "$TARGET_URL/FUZZ" \
     -w /usr/share/seclists/Discovery/Web-Content/common.txt \
     -mc 200,301,302,401,403 \
     -recursion -recursion-depth 2 -t 20 -o /tmp/ffuf_recursive.json -of json -s
```

## Extension Fuzzing

Run this only after fingerprinting identifies the stack. Backup and swap files are
consistently high-value — they can expose source code of files that are otherwise served
compiled or behind access controls.

```bash
ffuf -u "$TARGET_URL/FUZZ" \
     -w /usr/share/seclists/Discovery/Web-Content/raft-medium-words.txt \
     -e .php,.bak,.old,.txt,.zip,.config,.env,.swp \
     -mc 200,201,301,302,401,403 \
     -t 40 -o /tmp/ffuf_ext.json -of json -s
```

## Virtual Host Enumeration

Only relevant when the target has a known hostname rather than a bare IP. First measure
the baseline response size for an unknown `Host` header, then fuzz:

```bash
baseline=$(curl -sk -o /dev/null -w "%{size_download}" -H "Host: nonexistent-$(date +%s).<DOMAIN>" "$TARGET_URL/")
ffuf -u "$TARGET_URL/" \
     -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt \
     -H "Host: FUZZ.<DOMAIN>" \
     -mc 200,201,301,302,401,403 -fs $baseline \
     -t 40 -o /tmp/ffuf_vhost.json -of json -s
```

## TLS Certificate Check

HTTPS targets only. SAN entries frequently reveal internal hostnames and additional
vhosts not visible from the main application.

```bash
_h=$(echo $TARGET_URL | sed 's|https\?://||' | cut -d: -f1 | cut -d/ -f1); _p=$(echo $TARGET_URL | grep -oP ':\K[0-9]+' || echo 443); echo | openssl s_client -connect $_h:$_p -servername $_h 2>/dev/null | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
```

A subject matching the issuer means self-signed. SAN DNS entries are candidate vhosts —
add them to Virtual Host Enumeration. An expired `notAfter` signals a neglected or
abandoned service.

## What to Carry Forward

At this point you should know the technology stack, which paths exist and their status
codes, whether backup or config files are exposed, and any additional hostnames from TLS
SANs. Record all of this — the stack determines which exploitation techniques apply,
the path list feeds directly into parameter and vulnerability probing, and any 401/403 paths
are candidates for authentication bypass.

## Common Failure Modes

| Symptom | Likely cause | Action |
|---|---|---|
| `headers.txt` empty | Host down or port filtered | `nmap -sV -p <port> <host>` |
| ffuf wordlist not found | Wrong path | `ls /usr/share/seclists/Discovery/Web-Content/`; fallback: `/usr/share/wordlists/dirb/common.txt` |
| ffuf returns hundreds of same-size hits | Wildcard catch-all | Re-run calibration; add `-fs <size>` |
| Hits vary by a few bytes | Dynamic wildcard | Switch to `-fw` or `-fr "<stable_phrase_from_error_page>"` |
| `openssl s_client` hangs | Port is plain HTTP | Skip TLS step entirely |
| SAN entries show unknown hostnames | Additional vhosts | Feed into Virtual Host Enumeration |