# motus.google_adk

Compatibility layer for the [Google Agent Development Kit](https://github.com/google/adk-python) (v1.27.2+).

## What it does

- **Serve adapter** — `motus.google_adk.agents.Agent` subclasses Google ADK's
  `Agent` and adds a `run_turn(message, state)` method that satisfies the motus
  serve agent contract. Each turn creates an `InMemoryRunner`, replays
  conversation history into the session, executes the agent, and collects the
  final response text.

- **Tracing** — `MotusSpanProcessor` implements the OpenTelemetry
  `SpanProcessor` interface. Google ADK emits OTEL spans for agent invocations
  (`invoke_agent`), LLM calls (`generate_content`), and tool executions
  (`execute_tool`). The processor converts each completed span into motus
  `task_meta` format — extracting model name, token usage, tool arguments and
  responses, and error types from ADK's semantic convention attributes — and
  ingests them into `TraceManager`. Traces are auto-exported on process exit.

- **LLM proxying** — On the cloud platform, the Google ADK client picks up
  platform-injected environment variables that route requests through the model
  proxy, so no `GOOGLE_API_KEY` is needed at deploy time.

## Usage

```python
from google.adk.tools import FunctionTool
from motus.google_adk.agents import Agent

def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"Sunny in {city}"

root_agent = Agent(
    name="weather",
    model="gemini-2.0-flash",
    instruction="You are a helpful weather assistant.",
    tools=[get_weather],
)

# Local: motus serve start my_module:root_agent
# Cloud: motus deploy my_module:root_agent
```

## Module layout

| File | Purpose |
|------|---------|
| `__init__.py` | Package init |
| `agents/llm_agent.py` | `Agent` subclass with `run_turn()` serve adapter and tracing lifecycle management |
| `_motus_tracing.py` | `MotusSpanProcessor` — converts Google ADK OTEL spans into motus TraceManager spans |

## Requirements

```
google-adk>=1.27.2
```
