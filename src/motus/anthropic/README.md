# motus.anthropic

Compatibility layer for the [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) (v0.49.0+).

## What it does

- **Serve adapter** — `ToolRunner` wraps the Anthropic SDK's Beta Tool Runner
  with a `run_turn(message, state)` method that satisfies the motus serve agent
  contract. Each turn creates a fresh `BetaAsyncToolRunner` (tool runners are
  single-use generators), replays conversation state as Anthropic messages, and
  returns the text response.

- **Tracing** — Instrumented subclasses (`MotusBetaToolRunner`,
  `MotusBetaAsyncToolRunner`, and their streaming variants) override
  `_handle_request()` and `_generate_tool_call_response()` to emit
  `model_call` and `tool_call` spans into the motus `TraceManager`. A root
  `agent_call` span parents all child spans for the turn. Traces are
  auto-exported on process exit.

- **LLM proxying** — On the cloud platform, the standard `AsyncAnthropic()`
  client picks up platform-injected environment variables that route requests
  through the model proxy, so no `ANTHROPIC_API_KEY` is needed at deploy time.

## Usage

```python
from motus.anthropic import ToolRunner, beta_async_tool

@beta_async_tool
async def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"Sunny in {city}"

runner = ToolRunner(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=[get_weather],
)

# Local: motus serve start my_module:runner
# Cloud: motus deploy my_module:runner
```

## Module layout

| File | Purpose |
|------|---------|
| `__init__.py` | Re-exports Anthropic SDK symbols, defines `ToolRunner` serve adapter, manages tracing lifecycle |
| `_motus_runner.py` | Instrumented subclasses of all four Beta Tool Runner variants (sync/async x streaming/non-streaming) |
| `_motus_tracing.py` | Pure functions that build `model_call`, `tool_call`, and `agent_call` span dicts from Anthropic SDK objects |

## Requirements

```
anthropic>=0.49.0
```
