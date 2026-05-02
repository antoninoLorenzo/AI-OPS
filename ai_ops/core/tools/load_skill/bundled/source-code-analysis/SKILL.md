---
name: source-code-analysis
description: Use this skill when the task requires reading, searching, or understanding source code in a repository. Covers finding files, searching for patterns, reading specific lines, tracing function references, and running AST-aware analysis. This skill teaches tool discipline — what command to run, in what order, and how to control output volume. It does not prescribe a fixed investigation process; follow the evidence.
metadata: 
  requirements:
  - tree
  - grep
  - find
  - sed
---

# Source Code Analysis

## Core discipline — read this first

**Never broaden scope before you know the output volume.**

Every read operation has a cost: tokens consumed are context permanently spent.
Before running any command repo-wide, run it scoped to a single file or directory
first. Before reading a file, check its size. Before grepping for context lines,
know how many hits you are expanding.

The failure mode is not missing a vulnerability — it is flooding context with noise
so that the signal is buried.

---

## `tree` — understand structure before touching files

### What is in this repository?
```bash
tree -L 2 .
```
Start here. Always. Gives directory shape without listing every file.
Increase depth only when a subtree warrants it.

### What is inside a specific subdirectory?
```bash
tree -L 3 src/
```
Drill into one subtree rather than increasing global depth.

### What non-code files are present?
```bash
tree -L 2 -I "__pycache__|node_modules|.git|*.pyc"
```
Filter build noise. Config files, Dockerfiles, CI definitions, and migration
directories often matter as much as source files.

---

## `find` — locate files

### Find a file by name
```bash
find . -name "filename.py"
```

### Find files matching a path pattern
```bash
find . -path "*/routes/*" -o -path "*/controllers/*"
```
Use path fragments to locate files by their role in the project layout,
without assuming specific extensions.

### Find recently modified files
```bash
find . -newer reference_file -not -path "*/.git/*"
```
Useful when you need to understand what changed recently.

### Control output volume
Always pipe to `head` when the result count is unknown:
```bash
find . -name "*.conf" | head -20
```
If the list is truncated, narrow the pattern before expanding.

---

## `wc` — check size before reading

### How long is this file?
```bash
wc -l filename
```
Run this before any file read. Decision rule:
- **< 150 lines** — reading the full file is reasonable if it is entirely relevant
- **≥ 150 lines** — use targeted reads (see `sed` and `grep` below)

### Which files in a directory are large?
```bash
find . -name "*.py" | xargs wc -l | sort -rn | head -20
```
Use to identify which files warrant targeted reads vs full reads.
Do not run this repo-wide without first scoping to a directory.

---

## `grep` — search content

The single most important tool. Always escalate output from least to most verbose.

### Escalation order — never skip steps

**Step 1 — Which files match? (minimal output)**
```bash
grep -rl "pattern" .
```
Start here. Returns only filenames. If the list is large, scope to a directory.

**Step 2 — How many matches per file?**
```bash
grep -rc "pattern" .
```
Gives counts. Tells you where the pattern is dense vs incidental.

**Step 3 — Which lines in a specific file?**
```bash
grep -n "pattern" file
```
Once you know which file matters, get line numbers.

**Step 4 — What is around a match?**
```bash
grep -n -A 5 -B 5 "pattern" file
```
Expand context only in a specific file, never repo-wide.

⚠ Running step 4 repo-wide (`grep -rn -A 5 -B 5 "pattern" .`) on any non-trivial
codebase will produce thousands of lines. Do not do it.

---

### Find where a function or symbol is defined
```bash
grep -rn "def funcname\|funcname\s*=" .
```
Language-agnostic enough to catch function definitions and top-level assignments.
If noisy, scope to the directory where the definition is expected.

### Find all references to a function or symbol
```bash
grep -rn "funcname" . | grep -v "def funcname"
```
Pipe to exclude the definition itself. If still noisy, scope to a module or package
before going repo-wide.

### Find references within a specific scope first
```bash
grep -rn "pattern" src/module/
grep -rn "pattern" .            # only broaden if needed
```
Always try the narrowest scope first.

### Search for a pattern in a specific file type
```bash
grep -rn "pattern" --include="*.ext" .
```
Use only when you already know the relevant extension from prior recon — do not use
this as a substitute for understanding the codebase structure.

### Exclude noisy paths
```bash
grep -rn "pattern" . --exclude-dir="{node_modules,vendor,.git,__pycache__}"
```
Run this by default in any project with dependency directories.

---

## `sed` — read specific line ranges

### Read a specific line range from a file
```bash
sed -n '40,80p' file
```
Use after `grep -n` gives you a line number. Read the surrounding range,
not the whole file.

### How to derive the range
If `grep -n` returns line 73 as a hit, read lines 60–100:
```bash
sed -n '60,100p' file
```
Expand the window only if the function boundary is not yet visible.

### Read the top of a file (entry point, imports, config)
```bash
head -n 40 file
```

### Read the bottom of a file (main block, exports, teardown)
```bash
tail -n 40 file
```

---

## `semgrep` — AST-aware search

Use semgrep only when grep produces too many false positives due to matching
inside strings, comments, or partial identifiers. semgrep matches against the
parsed syntax tree, not raw text.

### When grep is not enough
`grep -rn "exec("` matches the string `"exec("` anywhere — inside comments,
docstrings, variable names. semgrep matches only actual call expressions.

### Run a targeted rule
```bash
semgrep --config "rule.yaml" path/to/file
```
Prefer running against a specific file or directory rather than the full repo
until you know the rule produces useful output.

### Run a ruleset and capture output
```bash
semgrep --config "p/security-audit" . --json > /tmp/semgrep_out.json
cat /tmp/semgrep_out.json | python3 -m json.tool | grep -A 3 "path\|message"
```
Redirect to a file first. Never print raw semgrep JSON directly to the terminal.

### When not to use semgrep
- When grep already gives clean results — semgrep is slower and heavier
- When the codebase cannot be parsed (minified JS, generated code, binary)
- When you do not have a specific pattern in mind — semgrep is not a substitute
  for understanding what you are looking for

---

## Output discipline — summary rules

| Situation | Command | Why |
|---|---|---|
| First look at a repo | `tree -L 2 .` | structure without file flood |
| Before reading any file | `wc -l file` | decide read strategy |
| Does this pattern exist? | `grep -rl "pattern" .` | filenames only |
| Where is it dense? | `grep -rc "pattern" .` | counts, no content |
| Which lines? | `grep -n "pattern" file` | scoped to one file |
| What is around it? | `grep -n -A 5 -B 5 "pattern" file` | scoped, bounded |
| Read a known range | `sed -n 'N,Mp' file` | surgical, no waste |
| AST-level matching | `semgrep --config rule.yaml file` | scoped, output redirected |

The goal is to spend context budget on signal, not on noise that grep -rn -A 10
produces when run without discipline.