# Cloud Deployment

Pack and deploy a project to the cloud.

## Quick Start

```bash
# Authenticate (one-time)
motus login

# First deploy — creates a new project
motus deploy --name my-project server:app

# Subsequent deploys — reads from motus.toml
motus deploy
```

To deploy from a Git repository instead of local files:

```bash
motus deploy --name my-project --git-url https://github.com/org/repo --git-ref main server:app
```

---

## Contents

- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
  - [Ignore Rules](#ignore-rules)
- [CLI](#cli)
- [Configuration](#configuration)
- [Authentication](#authentication)
- [File Structure](#file-structure)

---

## How It Works

A deployment proceeds through these steps:

1. **Validate** the import path (`module:variable` format) by importing it locally.
2. **Resolve the project** — look up an existing project by `--project-id`, or create one with `--name`.
3. **Create a build** via the cloud API with the project ID, import path, optional Git source, and optional secrets.
4. **Persist** `project_id`, `build_id`, and `import_path` to `motus.toml` so subsequent deploys can reuse them. (`git_url` and `git_ref` are also saved when provided.)
5. **Upload source code** (local deploys only): collect project files, pack them into a `.tar.zst` archive, and upload via a presigned URL. Git deploys skip this step — the build service pulls the repository directly.
6. **Stream build status** via SSE. The build progresses through: `queued` → `building` → `built` → `deploying` → `deployed` (or `failed`). After deployment, health checks continue in the background until the build transitions to `healthy`.

### Ignore Rules

When packing local files, a three-layer ignore strategy determines which files are included:

1. **Dotfiles** are always skipped (`.env`, `.git/`, `.vscode/`, etc.).
2. **Default patterns** exclude common artifacts:
   ```
   __pycache__/
   *.pyc
   *venv*/
   *.egg-info/
   dist/
   build/
   htmlcov/
   ```
3. **`.gitignore` files** in the project tree are respected. Nested `.gitignore` files are scoped to their own directory.

Git-based deploys bypass archiving entirely — the build service clones the repository at the specified ref.

---

## CLI

```
motus deploy [OPTIONS] [import-path]
```

| Flag | Default | Description |
|---|---|---|
| `import-path` | `motus.toml` | Python import path (`module:variable`) |
| `--name` | — | Project name (creates a new project if needed) |
| `--project-id` | `motus.toml` | Existing project ID |
| `--git-url` | — | Git repository URL (builds from Git instead of uploading local files) |
| `--git-ref` | — | Branch, tag, or commit SHA to check out (requires `--git-url`) |
| `--secret` | — | `KEY=VALUE` or just `KEY` to read from environment (repeatable) |

`--name` and `--project-id` are mutually exclusive. On the first deploy you must provide one of them; on subsequent deploys, the project ID is read from `motus.toml`.

```bash
# Deploy with secrets
motus deploy --secret API_KEY=sk-123 --secret DATABASE_URL

# Deploy a specific import path to an existing project
motus deploy --project-id proj_abc123 myapp.agents:assistant
```

---

## Configuration

Deploy reads and writes a `motus.toml` file in your project directory. The file is created on the first deploy and found by walking up the directory tree on subsequent runs.

After each deploy, these keys are persisted so that future runs need fewer flags:

```toml
project_id = "proj_abc123"
build_id = "build_def456"
import_path = "server:app"
```

When `--git-url` and `--git-ref` are provided, those are persisted as well:

```toml
git_url = "https://github.com/org/repo"
git_ref = "main"
```

---

## Authentication

Deploy requires an API key. Run `motus login` to authenticate via the browser — this stores credentials in `~/.motus/credentials.json`.

The `LITHOSAI_API_KEY` environment variable overrides the credential file.

Other auth commands: `motus whoami` (check current identity), `motus logout` (revoke key and clear credentials).

---

## File Structure

```
deploy/
├── __init__.py    # (empty)
├── deploy.py      # Core: validate, pack, upload, stream build status
├── walk.py        # Project file collection with three-layer ignore strategy
├── cli.py         # CLI registration and argument handling
└── README.md
```
