# Model Clients

Motus provides a unified `BaseChatClient` interface across four LLM providers. Switch providers by changing one line -- your agent code stays the same.

```python
import asyncio
from motus.agent import ReActAgent
from motus.models import OpenAIChatClient

client = OpenAIChatClient(api_key="sk-...")
agent = ReActAgent(client=client, model_name="gpt-4o")

async def main():
    print(await agent("Hello!"))

asyncio.run(main())
```

Replace `OpenAIChatClient` with any other client below. Everything else stays identical.

## Supported providers

| Class | Provider | Package |
|-------|----------|---------|
| `OpenAIChatClient` | OpenAI, local models (Ollama, vLLM) | `openai` |
| `AnthropicChatClient` | Anthropic Claude | `anthropic` |
| `GeminiChatClient` | Google Gemini | `google-genai` |
| `OpenRouterChatClient` | OpenRouter (multi-provider) | `openai` (OpenAI-compatible) |

## Creating a client

=== "OpenAI"

    ```python
    from motus.models import OpenAIChatClient

    client = OpenAIChatClient(api_key="sk-...")
    ```

=== "Anthropic"

    ```python
    from motus.models import AnthropicChatClient

    client = AnthropicChatClient(api_key="sk-ant-...")
    ```

=== "Gemini"

    ```python
    from motus.models import GeminiChatClient

    client = GeminiChatClient(api_key="...")
    ```

=== "OpenRouter"

    ```python
    from motus.models import OpenRouterChatClient

    client = OpenRouterChatClient(api_key="sk-or-...")
    ```

All clients accept `**kwargs` forwarded to the underlying SDK constructor. For example, you can pass `timeout`, `max_retries`, or `default_headers`.

## Local models

`OpenAIChatClient` works with any OpenAI-compatible API. Point `base_url` at your local server.

```python
from motus.models import OpenAIChatClient

# Ollama
client = OpenAIChatClient(base_url="http://localhost:11434/v1")

# vLLM
client = OpenAIChatClient(base_url="http://localhost:8000/v1")
```

No API key is required when the server does not enforce authentication. Pass the model name to the agent as usual:

```python
from motus.agent import ReActAgent

agent = ReActAgent(client=client, model_name="llama3.1")
```

## Gemini on Vertex AI

`GeminiChatClient` supports both the Gemini Developer API and Vertex AI.

```python
from motus.models import GeminiChatClient

# Vertex AI
client = GeminiChatClient(vertexai=True, project="my-project", location="us-central1")
```

## BaseChatClient interface

Every client implements two async methods:

| Method | Purpose |
|--------|---------|
| `create(model, messages, tools, ...)` | Standard chat completion. Returns `ChatCompletion`. |
| `parse(model, messages, response_format, ...)` | Structured output. Parses the response into a Pydantic model. |

You do not call these directly when using `ReActAgent` -- the agent manages the call loop. They are relevant if you build a custom agent or need raw completions.

```python
import asyncio
from motus.models import OpenAIChatClient
from motus.models.base import ChatMessage

client = OpenAIChatClient(api_key="sk-...")

async def main():
    completion = await client.create(
        model="gpt-4o",
        messages=[ChatMessage.user_message("What is 2 + 2?")],
    )
    print(completion.content)

asyncio.run(main())
```

## ChatMessage

`ChatMessage` is the unified message format used across all providers. Factory methods create messages for each role:

```python
from motus.models.base import ChatMessage

system  = ChatMessage.system_message("You are a helpful assistant.")
user    = ChatMessage.user_message("Hello!")
assist  = ChatMessage.assistant_message("Hi there!")
tool    = ChatMessage.tool_message(content="result", tool_call_id="call_123", name="my_tool")
```

| Method | Role | Required args |
|--------|------|---------------|
| `system_message(content)` | `system` | `content` |
| `user_message(content, base64_image=None)` | `user` | `content` |
| `assistant_message(content, tool_calls=None)` | `assistant` | `content` |
| `tool_message(content, tool_call_id, name)` | `tool` | `content`, `tool_call_id`, `name` |

`user_message` and `assistant_message` accept an optional `base64_image` parameter for vision inputs.

## Prompt caching

Anthropic supports prompt caching to reduce latency and cost on repeated calls. Motus exposes this through `CachePolicy`.

| Policy | Behavior |
|--------|----------|
| `NONE` | No caching. Every request is a full prompt send. |
| `STATIC` | Cache the system prompt and tool definitions. After the first call, these are read from cache. |
| `AUTO` | `STATIC` + cache the conversation turn prefix. Prior turns are read from cache each step. |

Set the policy on the agent:

```python
from motus.agent import ReActAgent
from motus.models import AnthropicChatClient

client = AnthropicChatClient(api_key="sk-ant-...")
agent = ReActAgent(
    client=client,
    model_name="claude-sonnet-4-20250514",
    cache_policy="auto",
)
```

`AUTO` is the default. For agents with large system prompts or many tools, caching significantly reduces per-step token costs. The policy has no effect on providers that do not support caching (OpenAI, Gemini, OpenRouter).

## ChatCompletion

`client.create()` returns a `ChatCompletion` with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str \| None` | Text response |
| `tool_calls` | `list[ToolCall] \| None` | Tool calls requested by the model |
| `reasoning` | `str \| None` | Chain-of-thought reasoning (if supported) |
| `finish_reason` | `str` | `"stop"`, `"tool_calls"`, or `"length"` |
| `usage` | `dict` | Token usage (`prompt_tokens`, `completion_tokens`) |
| `parsed` | `Any \| None` | Parsed Pydantic object (from `parse()`) |

Call `completion.to_message()` to convert a completion into a `ChatMessage` for appending to conversation history.
