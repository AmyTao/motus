# Quickstart

This guide walks you through creating and running your first Motus agent. By the end, you will have a working agent that can use tools to answer questions.

## 1. Create a tool

A tool is any async Python function decorated with `@tool`. The docstring becomes the tool description that the LLM sees.

```python
from motus.tools import tool

@tool
async def weather(city: str) -> str:
    """Get the current weather for a city."""
    # In a real app, call a weather API here
    return f"It is 22°C and sunny in {city}."
```

## 2. Create a model client

Motus supports multiple LLM providers through a unified client interface. Pick the one you have an API key for:

=== "OpenAI"

    ```python
    from motus.models import OpenAIChatClient

    client = OpenAIChatClient(api_key="sk-...")
    model = "gpt-4o"
    ```

=== "Anthropic"

    ```python
    from motus.models import AnthropicChatClient

    client = AnthropicChatClient(api_key="sk-ant-...")
    model = "claude-sonnet-4-20250514"
    ```

=== "OpenRouter"

    ```python
    from motus.models import OpenRouterChatClient

    client = OpenRouterChatClient(api_key="sk-or-...")
    model = "openai/gpt-4o"
    ```

## 3. Create an agent

`ReActAgent` ties a model client, a model name, and tools into a reasoning loop. Each call sends a user message and returns the agent's final text response.

```python
from motus.agent import ReActAgent

agent = ReActAgent(
    client,
    model,
    system_prompt="You are a helpful weather assistant.",
    tools=[weather],
)
```

## 4. Run the agent

Agents are async callables. Pass a user prompt and `await` the response:

```python
import asyncio

async def main():
    response = await agent("What's the weather like in Tokyo?")
    print(response)

asyncio.run(main())
```

Expected output:

```
It is 22°C and sunny in Tokyo.
```

The agent received your question, decided to call the `weather` tool with `city="Tokyo"`, incorporated the tool result, and returned a natural-language answer.

## 5. Full example

Here is the complete script in one block:

```python
import asyncio
from motus.agent import ReActAgent
from motus.models import OpenAIChatClient
from motus.tools import tool

@tool
async def weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"It is 22°C and sunny in {city}."

client = OpenAIChatClient(api_key="sk-...")
agent = ReActAgent(
    client,
    "gpt-4o",
    system_prompt="You are a helpful weather assistant.",
    tools=[weather],
)

async def main():
    print(await agent("What's the weather like in Tokyo?"))

asyncio.run(main())
```

## Next steps

- [Configuration](configuration.md) — set up environment variables and provider defaults
- [Architecture Overview](../user-guide/overview.md) — understand how runtime, agents, tools, and memory fit together
- [Tools](../user-guide/tools.md) — learn about FunctionTool, MCP integration, and Docker sandboxes
