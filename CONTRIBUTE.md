# Contributing

You're welcome to contribute to AI-OPS, whether you want to simply provide feedback or help in the development process.

> I am the only maintainer of this project and the codebase is not yet mature, for this reason the `dev` and `main` branch are often off-sync. 
> **All work happens on `dev`: branch from it and open your PR against it**. 


## Development Workflow

AI-OPS runs only on Linux (isn't meant to be cross-platform), on Windows you can use WSL.

It's recommended to use `uv` to create and manage Python environments; you can follow their [documentation](https://docs.astral.sh/uv/) to install it. Before setting up Python, checkout to `dev` first:
```bash
git clone https://github.com/antoninoLorenzo/AI-OPS.git -b dev && cd AI-OPS
uv sync --python 3.12
source .venv/bin/activate
```

Once you've done the initial setup create branch to implement your changes (ex. `fix/something` or `feat/whatever`):
```bash
git switch -c fix/something
```

AI-OPS uses `pytest` to test the codebase, when you implement your changes add any relevant test case and run any existing tests to ensure everything behaves as expected. 
```bash
# run your new tests
python -m pytest test/core/test_[your_test].py<::test_foo>

# run this depending on the impact of your changes
python -m pytest test/core
python -m pytest test/api
python -m pytest test/ 
```
> CI will run the full suite anyway, it's a way to get faster feedback.


When implementing a test, leverage `@pytest.mark.parametrize` where you can to make tests more readable and extendible:
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

Before submitting a PR, run the linters (CI will too, catch locally anyway):
```bash
# python
ruff check ai_ops/

# typescript (cli)
cd cli/
npx oxlint src
```

When you open the pull request set the base branch to `dev` (GH defaults to `main`).


### AI Assisted Contributions

You can use coding agents freely, after all that's an AI agent project, the rules are simple: review the code, test it yourself, when opening a PRs describe it yourself.
You **must** disclose usage of AI assistance both in the PR as a note and in commit message(s) as follows:
```
[your message]

Co-authored-by: [gipiti or claudio or whatever]
```

---

## Other

### Documentation

The docs live in `docs/` (plain markdown) and are built with [MkDocs](https://www.mkdocs.org/) + [Material](https://squidfunk.github.io/mkdocs-material/). The build tools are in the `docs` dependency group, install them with:

```bash
# already included with dev dependencies
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


### Submodules

The repository includes submodules, specifically a fork of [AutoPenBench](https://github.com/antoninoLorenzo/auto-pen-bench/tree/dfef9fe56e1948a86e26262787c786f6b17084b7) under `benchmark/auto_pen_bench/auto-pen-bench`; to initialize it run the following commands:
```bash
git submodule init
git submodule update --recursive
```

