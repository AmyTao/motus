# Tracing

Every `@agent_task` — LLM calls, tool invocations, task dependencies — is recorded as a span automatically. No manual instrumentation required.

## Quick start

```bash
MOTUS_TRACING=1 python my_agent.py
```

Sets collection to `detailed`, exports traces to `traces/trace_<timestamp>/`, and opens an HTML viewer on exit.

## Collection levels

| Level | Captures | Overhead |
|-------|----------|----------|
| `disabled` | Nothing | None |
| `basic` (default) | Task names, timing, parent relationships | Minimal |
| `detailed` | + full messages, tool arguments, model outputs | Higher |

## Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `MOTUS_TRACING` | `1` enables `detailed` collection + file export | off |
| `MOTUS_COLLECTION_LEVEL` | Explicit level (`disabled`, `basic`, `detailed`). Overrides `MOTUS_TRACING` level but not its export behavior | `basic` |
| `MOTUS_TRACING_EXPORT` | `1` enables file export only | off |
| `MOTUS_TRACING_ONLINE` | `1` enables detailed collection + file export + live SSE viewer | off |
| `MOTUS_TRACING_DIR` | Custom output directory | `traces/trace_<timestamp>/` |

## Export formats

`TraceManager.export_trace()` writes to the output directory:

- **`tracer_state.json`** — raw span metadata (timing, parents, extracted fields)
- **`trace_viewer.html`** — interactive span tree with timing bars and search. Opens automatically on exit.
- **`jaeger_traces.json`** — OpenTelemetry-format spans for Jaeger/Zipkin/OTLP backends

## Hooks

Tracing is built on `HookManager`. Register callbacks at three levels of specificity:

```python
from motus.runtime.hooks import (
    register_hook,          # global — fires for every task
    register_task_hook,     # per-name — fires for a specific function/tool
    register_tool_hook,     # per-type — fires for all tool calls
    register_model_hook,    # per-type — fires for all model calls
)

register_hook("task_end", my_callback)
register_task_hook("web_search", "task_end", my_callback)
register_tool_hook("task_end", my_callback)
```

Decorator equivalents:

```python
from motus.runtime.hooks import global_hook, task_hook, tool_task_hook

@global_hook("task_error")
def on_error(event):
    logging.error(f"{event.name} failed: {event.error}")

@task_hook("fetch_data", "task_end")
def on_fetch(event):
    logging.info(f"Fetched: {event.result}")

@tool_task_hook("task_end")
def on_tool(event):
    logging.info(f"Tool {event.name}: {event.result}")
```

Execution order: global, then name, then type hooks. Pass `prepend=True` to run first within a group. Callbacks may be sync or async. Exceptions are logged, never propagated.

### `HookEvent`

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | `str` | `"task_start"`, `"task_end"`, `"task_error"`, `"task_cancelled"` |
| `name` | `str` | Function or tool name |
| `task_type` | `str` | `"normal_task"`, `"tool_call"`, `"model_call"`, `"agent_call"`, `"magic_task"` |
| `args` / `kwargs` | `tuple` / `dict` | Task arguments |
| `result` | `Any` | Return value (`task_end` only) |
| `error` | `Exception` | Exception (`task_error` / `task_cancelled` only) |
| `task_id` | `AgentTaskId` | Unique identifier |
| `metadata` | `dict` | Additional context (e.g. `parent_stack`) |

## Programmatic access

```python
from motus.runtime import get_runtime

tracer = get_runtime().scheduler.tracer  # auto-inits runtime if needed

tracer.export_trace()
tracer.get_trace_id()           # UUID for this session

for task_id, meta in tracer.task_meta.items():
    print(f"{meta['func']}: {meta.get('ended_at', 'running')}")
```

## `TraceConfig`

Tracing reads from environment variables by default. For advanced use, construct directly:

```python
from pathlib import Path
from motus.runtime.tracing import TraceConfig, CollectionLevel

config = TraceConfig(
    collection_level=CollectionLevel.DETAILED,
    export_enabled=True,
    log_dir=Path("my_traces/run_001"),
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `collection_level` | `CollectionLevel` | from env | What data to collect |
| `export_enabled` | `bool` | from env | Write trace files on export |
| `online_tracing` | `bool` | from env | Start local SSE viewer |
| `log_dir` | `Path` | `traces/trace_<ts>/` | Output directory |
| `json_path` | `str` | `"tracer_state.json"` | JSON state filename |
| `cloud_api_url` | `str \| None` | from credentials | Cloud API endpoint |
| `cloud_api_key` | `str \| None` | from credentials | Cloud API key |
| `project` | `str \| None` | `MOTUS_PROJECT` / `motus.toml` | Project tag for cloud traces |
| `build` | `str \| None` | `MOTUS_BUILD` / `motus.toml` | Build tag for cloud traces |

## Cloud tracing

With cloud credentials, spans stream to the Motus dashboard in real time.

Authenticate via `motus login` or environment variables:

```bash
motus login --api-url https://api.<tenant>.dev.lithosai.cloud
# or
export LITHOSAI_API_URL=https://api.<tenant>.dev.lithosai.cloud
export LITHOSAI_API_KEY=<your-key>
```

Then run with tracing:

```bash
MOTUS_TRACING=1 python my_agent.py
```

The `CloudLiveExporter` runs a background thread: `POST /traces` to create a record, `POST /traces/{id}/spans` every second, `POST /traces/{id}/complete` on exit. Non-blocking; network errors are logged, never raised.

Tag traces with project/build:

```bash
MOTUS_PROJECT=my-project MOTUS_BUILD=v1.2.3 python my_agent.py
```

## Next steps

- [Runtime Engine](runtime.md) — `@agent_task`, `AgentFuture`, and the task graph
- [Agents](agents.md) — agents whose calls appear as traced spans
- [Overview](overview.md) — how tracing fits into the architecture
