
# Contributing

You're welcome to contribute to AI-OPS, whether you want to simply provide feedback or help in the development process.

## General

<details>
<summary> On AI Coding </summary>
Kinda sus putting that in the repo of an AI Agent, however as AI-OPS shouldn't be blindly used for ethical hacking (if we ever get to that), if you're looking to contribute you shouldn't be the "middleman" between the repo and an ai agent, I could do that myself if I wanted to.

You *can* use AI, but here's a couple of nice guidelines if you do so:
* Coding agents are "objective-oriented", so they quickly try to find workarounds to fix problems, those workarounds *may* be a solution but more often than not they hard-code an edge-case without really solving anything. If you use an agent to find a bug, take a piece of paper or whatever and think about the problem on your own before thinking about asking ai (I can't believe I'm prompting people).
* This is not the linux kernel, it's an agent, it's not supposed to be ~512k loc (if you know you know). Coding agents tend to write code that *looks* professional, the reason it never scales is that it's often over-engineered boilerplate. Basically what I'm saying here is KISS, often a function does the job.

</details>

<details>
<summary> Tips on LLM APIs </summary>
LLMs ain't cheap, so even developing an AI Agent requires you to manage token consumption. The obvious trick here is avoiding as much as possible LLM calls in development, however at some point you'll have to make api calls. AI-OPS is trying to target medium sized LLMs (ex. Gemma4 31B) and there's effort in context compaction so even 16k could do the job. 

That said, if you are blessed with enough hardware to get medium-sized at >30tok/s (under that you'll suffer the wrath of linear algebra) you may still be interested in knowing what low-hanging fruits are around. I personally still have to spend a cent on llm inference, this is thanks to the two following platforms:
* [Modal](https://modal.com/docs): you register and *once you connect a payment method* you get 30$ worth of credits, note that by default the budget is set to 42.5$ (let's call that a tax on not paying attention) but you can lower it to 30$. It offers serverless GPUs and if you're familiar with Docker containers you'll understand their Images api.

</details>

---

### Development Workflow

> As of 2026-06-09 (v0.1.0) the `development` and `main` branch are completely different, so you may want to see what's into the dev branch before doing any work. For this reason and also common-sense *I do not accept pull-requests directly to the main branch*.

Contributing is as-easy as:
1. Opening an issue or looking at open ones, also take a look at [ROADMAP.md](ROADMAP.md#help-wanted).
2. Create a new branch (from dev) like `fix/something` or `feat/whatever`.
3. Once you're done, make a pull request.

---

### Technical Guidelines

**Submodules**
```
git submodule init
git submodule update --recursive
```

**Use Logging**: print statements are ok for debugging (I understand that `pdb` may be a bit of a pain in the ass), though don't commit them, instead use the log utilities.

```python
from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)

var = 1
log_event(_logger, logging.INFO, "Message", var=var)
```

**Test your changes**: when implementing code changes (ex. fixing a tool implementation or whatever) use `pytest` to verify the behaviour is the expected one. Personally, I like decoupling the test cases definition and the execution logic, however that's just my personal style: 
```python
import pytest

def foo(bar: int) -> int:
    return 2 * bar

_TEST_PARAMS = [
    {
        "input": {"bar": 2},
        "expected": 4
    }
]

@pytest.mark.parametrize("test_case", _TEST_PARAMS)
def test_foo(test_case):
    assert foo(**test_case["input"]) == test_case["expected"]
```

---

### Documentation

The docs live in `docs/` (plain markdown) and are built with [MkDocs](https://www.mkdocs.org/) + [Material](https://squidfunk.github.io/mkdocs-material/). The build tools are in the `docs` dependency group, install them with:

```bash
uv sync --group docs
```

**Preview** (live-reloads as you edit) at http://127.0.0.1:8000:

```bash
uv run --group docs mkdocs serve
```

**Build**, the same strict build CI runs (fails on any broken link or nav entry):

```bash
uv run --group docs mkdocs build --strict
```

A few notes:

* Run through `uv run --group docs` (or a venv with the group synced). A bare `mkdocs` may resolve to a system install without the Material theme and fail with `Unrecognised theme name: 'material'`.
* Page order and the sidebar come from the `nav:` block in `mkdocs.yml`. When you add a page under `docs/`, add it to `nav:` too.
* `site/` is generated output and is gitignored, don't commit it. `mkdocs.yml` and everything under `docs/` are tracked.
* The `Docs` GitHub Action validates the build on every docs change. Publishing to GitHub Pages via `mkdocs gh-deploy` is available but left commented out in `.github/workflows/docs.yml`.

