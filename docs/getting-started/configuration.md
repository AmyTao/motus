# Configuration

Configure Motus through environment variables and an optional `motus.toml` project file.

## API keys

Set provider API keys as environment variables before running your agent.

| Variable | Provider | Example |
|----------|----------|---------|
| `OPENAI_API_KEY` | OpenAI | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic | `sk-ant-...` |
| `OPENROUTER_API_KEY` | OpenRouter | `sk-or-...` |
| `BRAVE_API_KEY` | Brave Search | |
| `JINA_API_KEY` | Jina AI (MCP) | |

`OpenRouterChatClient` also accepts `OPENROUTER_BASE_URL` to override the default endpoint (`https://openrouter.ai/api/v1`).

`OpenAIChatClient` accepts `OPENAI_BASE_URL` for custom endpoints. This is useful when you run a local model server such as Ollama:

```bash
export OPENAI_BASE_URL="http://localhost:11434/v1"
```

## Runtime environment variables

These variables control Motus runtime behavior.

| Variable | Purpose | Default |
|----------|---------|---------|
| `MOTUS_LOG_LEVEL` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `DEBUG` |
| `MOTUS_QUIET_SYNC` | Suppress sync barrier warnings (`1` to enable) | off |
| `MOTUS_TRACING` | Enable detailed tracing with export (`1`) | off |
| `MOTUS_COLLECTION_LEVEL` | Tracing level: `disabled`, `basic`, `detailed` | `basic` |
| `MOTUS_TRACING_ONLINE` | Enable detailed tracing + live viewer (`1`) | off |
| `MOTUS_TRACING_EXPORT` | Enable trace file export (`1`) | off |
| `MOTUS_TRACING_DIR` | Custom trace output directory | `traces/trace_<timestamp>/` |

### Tracing

When you enable tracing, Motus records task execution, tool calls, and model interactions. Set `MOTUS_TRACING=1` to turn it on, then choose a collection level:

- **`disabled`** — no trace data collected.
- **`basic`** — task-level events only (start, end, errors).
- **`detailed`** — includes model request/response payloads and tool arguments.

To view traces in real time, set `MOTUS_TRACING_ONLINE=1` — this also enables detailed collection and file export. To enable file export without the live viewer, set `MOTUS_TRACING_EXPORT=1`. By default, trace files are written to `traces/trace_<timestamp>/`; override this with `MOTUS_TRACING_DIR`.

## `motus.toml`

Create a `motus.toml` file in your project root to store project-level configuration. Motus searches upward from the current working directory until it finds this file.

```toml
project_id = "my-project"
import_path = "myapp:agent"
```

| Field | Description |
|-------|-------------|
| `project_id` | Unique identifier for your project, used in deployment and tracing. |
| `import_path` | Python import path to your agent instance, in `module:attribute` format. |

The `motus deploy` and `motus serve` commands read these values so you do not need to pass them as CLI flags every time:

```bash
# Without motus.toml
motus serve --import-path myapp:agent

# With motus.toml (reads import_path automatically)
motus serve
```

## `.env` file

Motus core does not auto-load `.env` files. If you prefer to keep secrets in a `.env` file, load them yourself at the top of your entry point using `python-dotenv`:

```bash
pip install python-dotenv
```

```
# .env
OPENAI_API_KEY=sk-...
MOTUS_LOG_LEVEL=INFO
```

```python
from dotenv import load_dotenv

load_dotenv()  # loads .env into os.environ

from motus.agent import ReActAgent
```

Call `load_dotenv()` before any Motus imports so that environment variables are available when modules initialize.

## Verifying your configuration

Run a quick check to confirm your API key is set and Motus can reach the provider:

```python
import os

from motus.models import OpenAIChatClient

assert os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY is not set"

client = OpenAIChatClient()
```

If the key is missing or invalid, the client raises an error at request time with a descriptive message.

## Next steps

- [Quickstart](quickstart.md) — build and run your first agent.
- [Architecture Overview](../user-guide/overview.md) — how runtime, agents, tools, and memory fit together.
