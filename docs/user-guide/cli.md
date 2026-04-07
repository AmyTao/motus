# CLI Reference

The `motus` CLI provides two command groups: `serve` for running agent
servers and `deploy` for cloud deployment.

## motus serve

### Commands

| Command | Purpose |
|---------|---------|
| `motus serve start <import-path>` | Start an agent server |
| `motus serve chat <url> [message]` | Chat with an agent (single or interactive) |
| `motus serve health <url>` | Check server health |
| `motus serve create <url>` | Create a session |
| `motus serve sessions <url>` | List sessions |
| `motus serve get <url> <id>` | Get session details |
| `motus serve delete <url> <id>` | Delete a session |
| `motus serve messages <url> <id>` | Get session messages |
| `motus serve send <url> <id> <msg>` | Send a message |

### motus serve start

```bash
motus serve start myapp:agent --port 8000 --workers 4
```

Start an HTTP server that wraps the agent at the given import path.

| Flag | Default | Purpose |
|------|---------|---------|
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8000` | Bind port |
| `--workers` | CPU count | Worker processes |
| `--ttl` | `0` (disabled) | Session idle timeout (seconds) |
| `--timeout` | `0` (disabled) | Max seconds per agent turn |
| `--max-sessions` | `0` (unlimited) | Concurrent session limit |
| `--log-level` | `info` | Log level |

### motus serve chat

```bash
# Single message — prints the response and exits
motus serve chat http://localhost:8000 "What is 2+2?"

# Interactive mode — keeps the session across turns
motus serve chat http://localhost:8000 --keep
```

In interactive mode, the client creates a session on the first turn and
reuses it until you press `Ctrl-C`. Without `--keep`, each invocation
creates a fresh session, sends the message, prints the response, and
deletes the session.

### motus serve health

```bash
motus serve health http://localhost:8000
```

Hits the `/health` endpoint and prints the server status.

### Session management commands

```bash
# Create a session and print the session ID
motus serve create http://localhost:8000

# List all active sessions
motus serve sessions http://localhost:8000

# Get details for a session
motus serve get http://localhost:8000 <session-id>

# Send a message to an existing session
motus serve send http://localhost:8000 <session-id> "Hello"

# Retrieve messages for a session
motus serve messages http://localhost:8000 <session-id>

# Delete a session
motus serve delete http://localhost:8000 <session-id>
```

These commands map directly to the REST endpoints described in
[Serving](serving.md#rest-endpoints).

## motus deploy

```bash
motus deploy myapp:agent --project-id my-project
```

Package and deploy your agent to the Motus cloud. See
[Deployment](deployment.md) for the full workflow.

### Flags

| Flag | Purpose |
|------|---------|
| `--project-id` | Project ID (reads from `motus.toml` if omitted) |
| `--git-url` | Build from git repo instead of local files |
| `--git-ref` | Git branch, tag, or SHA (used with `--git-url`) |
| `--secret KEY=VALUE` | Pass secrets to the agent container (repeatable) |

### Examples

```bash
# Deploy from local files
motus deploy myapp:agent

# Deploy with secrets
motus deploy myapp:agent --secret OPENAI_API_KEY --secret CUSTOM_KEY=value

# Deploy from a git repository
motus deploy myapp:agent \
  --git-url https://github.com/org/repo.git \
  --git-ref main
```

## motus login

```bash
motus login
```

Authenticate with the Motus cloud. Opens a browser-based OAuth flow and
stores credentials locally. Required before running `motus deploy` or
any other cloud management command.

For CI environments, set the `LITHOSAI_API_KEY` environment variable instead.

## Plugin system

CLI commands are registered dynamically through a plugin interface. Each
module that provides commands implements a `register_cli(subparsers)` function.
At startup, motus discovers registered plugins and calls `register_cli` to
add their subcommands to the argument parser.

To add a custom command group, create a module with:

```python
def register_cli(subparsers):
    parser = subparsers.add_parser("mycommand", help="My custom command")
    parser.add_argument("name")
    parser.set_defaults(func=run_mycommand)

def run_mycommand(args):
    print(f"Running with {args.name}")
```

Then register the module as a motus CLI plugin in your package metadata.
