# Development Setup

Set up a local development environment for contributing to Motus.

## Prerequisites

- **Python 3.12+** — check with `python3 --version`
- **uv** — install from [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/)
- **git**
- **Docker Desktop** (optional) — needed for sandbox-related tests

## Clone and install

```bash
git clone https://github.com/gpuOS-ai/motus.git
cd motus
uv sync --all-extras
```

`uv sync --all-extras` installs all dependencies including optional groups (dev, docs, test) in a local `.venv`.

## Pre-commit hooks

```bash
uv run pre-commit install
```

This registers git hooks that run **ruff** (linting + formatting) on every commit. If ruff finds issues, the commit is blocked until you fix them. You can run the checks manually:

```bash
uv run pre-commit run --all-files
```

## Verify setup

```bash
uv run pytest tests/unit/ -x -q
```

All unit tests should pass without any API keys or external services. If you see failures, check that you installed with `--all-extras` and are running Python 3.12+.

## Editor setup

The ruff configuration lives in `pyproject.toml` under `[tool.ruff]`. Point your editor at this config to get consistent linting and formatting.

**VS Code:**

1. Install the [Ruff extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff).
2. The extension auto-detects `pyproject.toml` settings.
3. Enable format-on-save for `.py` files:

```json
{
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true
  }
}
```

**PyCharm:**

1. Install the [Ruff plugin](https://plugins.jetbrains.com/plugin/20574-ruff) from the marketplace.
2. Under **Settings > Tools > Ruff**, confirm the config path points to `pyproject.toml`.
3. Enable "Run ruff on save" in the plugin settings.

## Running the docs locally

```bash
uv run mkdocs serve
```

Opens at [http://localhost:8000](http://localhost:8000). The site rebuilds on file changes. Example pages are auto-generated from `examples/`.

## Project layout

```
src/motus/
├── agent/          # Agent implementations (ReActAgent, etc.)
├── memory/         # Memory systems (CompactionMemory, etc.)
├── models/         # Model backends
├── runtime/        # Core runtime (AgentRuntime, AgentFuture, TaskInstance)
└── tools/          # Built-in tools

tests/
├── unit/           # Fast tests, no API keys
└── integration/    # VCR-based replay tests
```

## Next steps

- Read the [Code Style](code-style.md) guide for conventions beyond what ruff enforces.
- Read the [Testing](testing.md) guide before writing your first test.
- Read the [Pull Request Process](pull-requests.md) when you are ready to submit.
