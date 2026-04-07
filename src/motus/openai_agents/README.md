# motus.openai_agents

Compatibility layer for the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) (v0.0.10+).

## What it does

- **Serve adapter** — `Runner` wraps the upstream `Runner` class. Its `run()`,
  `run_sync()`, and `run_streamed()` methods inject a `MotusOpenAIProvider` as
  the default model provider and wrap agent tool invocations, then delegate to
  the original SDK runner. Agent code that already defines a module-level
  `Agent` instance can be served directly via `motus serve start` or deployed
  with `motus deploy`.

- **Tracing** — `MotusTracingProcessor` implements the SDK's `TracingProcessor`
  interface. It replaces the SDK's default `BackendSpanExporter` (which would
  POST traces to `api.openai.com` and fail with non-OpenAI keys) and converts
  each completed span — agent, generation, response, function, handoff,
  guardrail — into motus `task_meta` format for `TraceManager`. Parent-child
  relationships are preserved via a `span_id` mapping. Traces are auto-exported
  on process exit.

- **LLM proxying** — `MotusOpenAIProvider`, `MotusMultiProvider`, and
  `MotusLitellmProvider` subclass the SDK's model providers and return
  Motus-wrapped model instances (`MotusChatCompletionsModel`,
  `MotusResponsesModel`, `MotusLitellmModel`). On the cloud platform, the
  underlying `OpenAI` client picks up platform-injected environment variables
  that route requests through the model proxy, so no `OPENAI_API_KEY` or
  `OPENROUTER_API_KEY` is needed at deploy time.

- **Tool wrapping** — `_wrap_tools_for_motus()` recursively wraps
  `on_invoke_tool` on all tools across the agent graph (including handoff
  targets). Currently a transparent pass-through; provides a stable extension
  point for future tool-level caching, rate limiting, and sandboxing.

## Usage

```python
from motus.openai_agents import Agent, Runner, function_tool

@function_tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"Sunny in {city}"

agent = Agent(
    name="weather",
    instructions="You are a helpful weather assistant.",
    tools=[get_weather],
    model="gpt-4o",
)

# Local: motus serve start my_module:agent
# Cloud: motus deploy my_module:agent
```

## Module layout

| File | Purpose |
|------|---------|
| `__init__.py` | Re-exports all OAI SDK symbols, overrides `Runner`/providers/models with Motus variants, manages tracing lifecycle |
| `_motus_model.py` | `MotusChatCompletionsModel`, `MotusResponsesModel`, `MotusLitellmModel` — transparent model subclasses |
| `_motus_provider.py` | `MotusOpenAIProvider`, `MotusMultiProvider`, `MotusLitellmProvider` — provider subclasses that return Motus-wrapped models |
| `_motus_tools.py` | Recursive tool wrapping across agent graphs |
| `_motus_tracing.py` | `MotusTracingProcessor` — bridges OAI SDK span events into motus TraceManager |

## Requirements

```
openai-agents>=0.0.10
```
