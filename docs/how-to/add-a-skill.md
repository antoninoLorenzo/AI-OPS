# Add a Skill to AI-OPS

You can give the agent task-specific instructions and knowledge through [Agent Skills](https://agentskills.io/home), markdown documents (`SKILL.md`) that the agent loads on demand via the `LoadSkill` tool when it decides a task needs them.

AI-OPS uses two kinds of skills:

| Kind | Location | Purpose |
|---|---|---|
| **Bundled** | `ai_ops/core/tools/load_skill/bundled/<skill-name>/` | Ship with AI-OPS (`network-enumeration`, `web-sql-injection`, etc.) |
| **User** | `~/.local/share/ai_ops/user_skills/<skill-name>/` | Yours, added without touching AI-OPS's source |

Both are loaded the same way and merged into one registry at startup. If a user skill has the same `name` as a bundled one, the user skill overrides the bundled one.

## Skill format & location

A user skill is a directory containing a single `SKILL.md`:

```
~/.local/share/ai_ops/
└── user_skills/
    └── my-skill/
        └── SKILL.md
```

`SKILL.md` is YAML frontmatter followed by the instructions body:

```markdown
---
name: my-skill
description: One-line description shown in the skill index.
metadata:
  requirements:
    - nmap
---

## Instructions

Your prompt...
```

- `name` and `description` are required, a skill missing either is skipped (logged as a warning).
- `description` is what the agent sees in the skill index before deciding whether to load the full skill.
- The instructions body can't be empty; a skill with no content after the frontmatter is skipped.
- `metadata.requirements` is optional. A skill with no `metadata` block at all is valid.

## Requirement Verification

`requirements` lists binaries the skill's instructions assume are on `PATH` (e.g. `nmap`, `ffuf`). AI-OPS never installs anything on your behalf, this list only lets it check whether a binary is available. Verification is controlled by the environment variable `SKILL_VERIFY_INSTALLED` (`true`/`false`, defaults to false). When verification is enabled, each requirement is checked with `shutil.which` at startup. If any listed binary isn't found on `PATH`, AI-OPS prints the missing binaries and exits.

This is intentional: catching a missing dependency at startup is cheaper than letting the agent discover it mid-task, burning iterations and tokens on a command that was never going to work. If you're developing a skill and want to skip the check temporarily, set `SKILL_VERIFY_INSTALLED=false`.

> **Note:** the API runs inside a container built from `docker.io/kalilinux/kali-rolling:latest`. If `SKILL_VERIFY_INSTALLED=true` and a requirement isn't present in that image, startup fails. To avoid this, either:
> - only list requirements already available in `kali-rolling` (check with `docker run --rm kalilinux/kali-rolling:latest which <binary>`), or
> - extend the `Dockerfile` to install the missing package and rebuild the image.