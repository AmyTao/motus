# Agents

`ReActAgent` is the default way to build an LLM-powered agent that operates in a ReAct loop. The agent can use either Motus's default or customized tool sets to navigate the problem space in a step-by-step manner. Memory, reasoning, caching, chat messages, and many more functionalities are naturally provided under the hood.

## Minimal example

```python
import asyncio
from motus.agent import ReActAgent
from motus.models import OpenAIChatClient
from motus.tools import tool

@tool
async def weather(city: str) -> str:
    """Get the weather for a city."""
    return f"22°C and sunny in {city}."

client = OpenAIChatClient(api_key="sk-...")
agent = ReActAgent(
    client=client,
    model_name="gpt-4o",
    system_prompt="You are a helpful assistant.",
    tools=[weather],
)

async def main():
    response = await agent("What's the weather in Tokyo?")
    print(response)

asyncio.run(main())
```

The agent sends your prompt to the LLM along with the tool definitions. When the LLM returns a tool call, the agent executes it, feeds the result back, and loops. When the LLM returns a text response with no tool calls, the loop ends.

## Constructor parameters

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `client` | `BaseChatClient` | required | LLM provider client |
| `model_name` | `str` | required | Model identifier (e.g. `"gpt-4o"`, `"claude-sonnet-4-20250514"`) |
| `name` | `str \| None` | auto-inferred | Agent name for tracing and tool registration |
| `system_prompt` | `str \| None` | `None` | System prompt prepended to every LLM call |
| `tools` | list, dict, or single | `None` | Tools available to the agent |
| `max_steps` | `int` | `20` | Max reasoning-action cycles before the agent stops |
| `timeout` | `float \| None` | `None` | Timeout in seconds for the entire run |
| `memory_type` | `"basic" \| "compact"` | `"basic"` | Memory strategy |
| `memory` | `BaseMemory \| None` | `None` | Custom memory instance (overrides `memory_type`) |
| `response_format` | `type[BaseModel] \| None` | `None` | Structured output via Pydantic model |
| `input_guardrails` | `list[Callable]` | `[]` | Pre-run validation hooks |
| `output_guardrails` | `list[Callable]` | `[]` | Post-run validation hooks |
| `reasoning` | `ReasoningConfig` | `ReasoningConfig.auto()` | Controls LLM extended thinking (see below) |
| `cache_policy` | `CachePolicy \| str` | `"auto"` | Prompt caching strategy (Anthropic only) |
| `step_callback` | `Callable \| None` | `None` | Async callback invoked after each LLM step |

See [Models](models.md) for client setup, [Tools](tools.md) for tool definitions, and [Memory](memory.md) for memory strategies.

## Multi-turn conversations

Calling the agent multiple times preserves conversation history in memory.

```python
import asyncio
from motus.agent import ReActAgent
from motus.models import OpenAIChatClient

client = OpenAIChatClient(api_key="sk-...")
agent = ReActAgent(client=client, model_name="gpt-4o")

async def main():
    await agent("My name is Alice.")
    response = await agent("What's my name?")
    # response contains "Alice"
    print(response)

asyncio.run(main())
```

Each call appends the user message and the assistant reply to the agent's memory. The full history is sent to the LLM on the next call. For long conversations, switch to `memory_type="compact"` to keep token usage under control. See [Memory](memory.md) for details.

## Structured output

Pass a Pydantic model as `response_format` to get typed responses instead of raw strings.

```python
import asyncio
from pydantic import BaseModel
from motus.agent import ReActAgent
from motus.models import OpenAIChatClient

class Sentiment(BaseModel):
    label: str
    score: float

client = OpenAIChatClient(api_key="sk-...")
agent = ReActAgent(
    client=client,
    model_name="gpt-4o",
    response_format=Sentiment,
)

async def main():
    result = await agent("Analyze: 'I love this product'")
    # result is a Sentiment instance
    print(result.label, result.score)

asyncio.run(main())
```

The agent uses the LLM's structured output mode to guarantee valid JSON conforming to your schema. The return value is a parsed Pydantic model instance.

## Agent as tool

You can expose an agent as a tool for another agent using `as_tool()`. This enables multi-agent composition where a supervisor delegates subtasks to specialist agents.

```python
from motus.agent import ReActAgent
from motus.models import OpenAIChatClient

client = OpenAIChatClient(api_key="sk-...")

researcher = ReActAgent(
    client=client,
    model_name="gpt-4o",
    name="researcher",
    system_prompt="You research topics thoroughly.",
)

supervisor = ReActAgent(
    client=client,
    model_name="gpt-4o",
    system_prompt="You coordinate research tasks.",
    tools=[researcher.as_tool(description="Research a topic in depth")],
)
```

`as_tool()` accepts optional `name`, `description`, `output_extractor`, and `stateful` parameters. When `stateful=True`, the sub-agent preserves its memory across calls within the same parent run. See [Tools](tools.md) for the full tool API.

## Forking

`agent.fork()` creates an independent copy of the agent with the same configuration and a forked copy of the conversation history.

```python
import asyncio
from motus.agent import ReActAgent
from motus.models import OpenAIChatClient

client = OpenAIChatClient(api_key="sk-...")
agent = ReActAgent(client=client, model_name="gpt-4o")

async def main():
    await agent("My name is Alice.")

    forked = agent.fork()
    # forked agent remembers "Alice" but diverges from here
    await forked("Call me Bob instead.")

    original_response = await agent("What's my name?")   # "Alice"
    forked_response = await forked("What's my name?")     # "Bob"

asyncio.run(main())
```

Changes to the forked agent's memory do not affect the original. This is useful for running parallel exploratory conversations or A/B comparisons.

## Timeouts and step limits

The `max_steps` parameter caps the number of reasoning-action cycles. If the agent reaches the limit without producing a final response, it raises a `RuntimeError`.

The `timeout` parameter sets a wall-clock deadline in seconds. When exceeded, the agent raises a `TimeoutError` before starting the next step.

```python
agent = ReActAgent(
    client=client,
    model_name="gpt-4o",
    max_steps=5,
    timeout=30.0,
)
```

Both mechanisms ensure the agent does not run indefinitely. Callers should catch these errors if graceful degradation is needed.

## Guardrails

Input guardrails run before the agent's `_run()` method. Output guardrails run after the final response. Declare the parameters you care about — return `None` to pass through, return a value to replace, or raise to block.

```python
from motus.agent import ReActAgent
from motus.guardrails import InputGuardrailTripped
from motus.models import OpenAIChatClient

def block_profanity(value: str):
    if "badword" in value.lower():
        raise InputGuardrailTripped("Input rejected by guardrail.")

client = OpenAIChatClient()
agent = ReActAgent(
    client=client,
    model_name="gpt-4o",
    input_guardrails=[block_profanity],
)
```

See [Guardrails](guardrails.md) for the full guardrail API.

## Reasoning

The `reasoning` parameter controls extended thinking for models that support it. By default, reasoning is set to `auto`, which enables adaptive thinking on supported models (Opus 4.6, Sonnet 4.6).

```python
from motus.agent import ReActAgent
from motus.models import AnthropicChatClient
from motus.models.base import ReasoningConfig

client = AnthropicChatClient()

# Adaptive (default) — model decides how much to think
agent = ReActAgent(client=client, model_name="claude-opus-4-6")

# Lower effort for faster, cheaper responses
agent = ReActAgent(
    client=client,
    model_name="claude-opus-4-6",
    reasoning=ReasoningConfig(effort="low"),
)

# Explicit token budget (older models like Sonnet 4.5)
agent = ReActAgent(
    client=client,
    model_name="claude-sonnet-4-5-20250929",
    reasoning=ReasoningConfig(budget_tokens=5000),
)

# Disable thinking entirely
agent = ReActAgent(
    client=client,
    model_name="claude-opus-4-6",
    reasoning=ReasoningConfig.disabled(),
)
```

## Usage tracking

After an agent run, you can inspect token usage and estimated cost:

```python
response = await agent("Explain quantum computing.")

print(agent.usage)
# {"input_tokens": 1234, "output_tokens": 567, "cache_read_input_tokens": 200, ...}

print(agent.cost)
# 0.0042  (USD, or None if pricing unavailable for the model)

print(agent.context_window_usage)
# {"estimated_tokens": 1801, "threshold": 150000, "ratio": 0.012, "percent": "1%"}
```

- `usage` — accumulated token counts across all LLM calls in the run
- `cost` — total cost in USD based on model pricing, or `None` if the model has no pricing entry
- `context_window_usage` — current memory utilization relative to the compaction threshold
