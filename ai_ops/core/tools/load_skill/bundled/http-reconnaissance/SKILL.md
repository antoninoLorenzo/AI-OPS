---
name: http-reconnaissance
description: Perform initial HTTP/HTTPS reconnaissance on a target host to identify the web stack, exposed endpoints, security headers, and surface-level misconfigurations. Use this skill at the start of any web-facing engagement before running deeper enumeration or exploitation tools.
metadata:
  requirements:
  - curl
  - grep
  - ffuf
---

## Inputs
| Variable      | Description                              | Example                  |
|---------------|------------------------------------------|--------------------------|
| `TARGET_URL`  | Base URL including scheme and port       | `http://10.10.11.42:80`  |
| `OUTPUT_DIR`  | Directory to write output files into     | `/tmp/recon/http`        |
 

### 1. Baseline request
Capture the raw HTTP response (headers + body excerpt) for the root path.
 
```bash
mkdir -p $OUTPUT_DIR
curl -sk -D $OUTPUT_DIR/headers.txt -o $OUTPUT_DIR/body.html --max-time 10 "$TARGET_URL/"
```

**What to look for in headers.txt:**
- `Server` / `X-Powered-By` → technology fingerprint
- `Set-Cookie` → session cookie flags (`HttpOnly`, `Secure`, `SameSite`)
- Missing security headers: `Content-Security-Policy`, `X-Frame-Options`,
  `Strict-Transport-Security`, `X-Content-Type-Options`
- Redirect chains (`Location`) that reveal internal structure

### 2. Technology fingerprint

```bash
grep -i "generator\|framework\|powered" $OUTPUT_DIR/body.html | head -20
```

### 3. Robots and sitemap
```bash
for path in robots.txt sitemap.xml sitemap_index.xml; do
    curl -sk -o $OUTPUT_DIR/$path --max-time 5 "$TARGET_URL/$path"
    [ -s $OUTPUT_DIR/$path ] && echo "[+] Found: $path"
done
```
 
### 4. Common path discovery (light)
```bash
# Use a small wordlist for the prototype — swap for larger list in real engagements
ffuf -u "$TARGET_URL/FUZZ" \
     -w /usr/share/seclists/Discovery/Web-Content/common.txt \
     -mc 200,201,204,301,302,307,401,403 \
     -t 40 -o $OUTPUT_DIR/ffuf.json -of json -s
```
 
Parse hits:
```bash
cat $OUTPUT_DIR/ffuf.json | python3 -c "
import json,sys
data=json.load(sys.stdin)
for r in data.get('results',[]):
    print(f\"{r['status']}  {r['length']:>8}  {r['url']}\")
" | sort
```
 
### 5. TLS / certificate check (HTTPS targets only)
```bash
echo | openssl s_client -connect ${TARGET_HOST}:${TARGET_PORT} 2>/dev/null \
    | openssl x509 -noout -subject -issuer -dates -ext subjectAltName \
    > $OUTPUT_DIR/cert.txt
cat $OUTPUT_DIR/cert.txt
```
 
> Replace `TARGET_HOST` and `TARGET_PORT` by splitting `TARGET_URL`.
 
### 6. Summarise findings
After the steps above, write a short findings block to the whiteboard:
 
```
## HTTP Recon — <TARGET_URL>
 
**Stack:** <identified technologies>
**Interesting paths:** <comma-separated list from ffuf>
**Missing headers:** <list>
**Cookie flags issues:** <list or "none">
**TLS notes:** <expiry, SANs, self-signed?>
**Next steps:** <suggested follow-up — e.g. SQLi probe on /login, LFI on ?page=>
```

## Success Criteria
- `headers.txt` is non-empty (the host responded)
- At least one technology identified (step 2 or grep fallback)
- ffuf run completed without fatal errors
- Findings block written to whiteboard
 
## Common Failure Modes
| Symptom                          | Likely cause                        | Fix                                      |
|----------------------------------|-------------------------------------|------------------------------------------|
| `curl` times out                 | Host down or port filtered          | Verify with `nmap -sV -p <port> <host>` |
| `ffuf` exits immediately         | Wordlist path wrong                 | Confirm path; fallback to `/usr/share/wordlists/dirb/common.txt` |
| All ffuf responses same size     | Catch-all / wildcard response       | Add `-fs <size>` to filter that size     |