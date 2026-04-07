# Claude Agent SDK

Use the Claude Agent SDK through Motus for tracing and deployment. Import `query` from `motus.claude_agent` instead of the SDK directly.

## Installation

```bash
uv sync --extra claude-agent-sdk
```

## Basic usage

```python
from motus.claude_agent import query

async for message in query(prompt="Summarize this document."):
    print(message)
```

The `query()` function returned by `motus.claude_agent` wraps the SDK's `query()` with tracing hooks and message observation. You do not need to change your prompt format or message handling.

## With tools and options

```python
from motus.claude_agent import query, ClaudeAgentOptions

async for message in query(
    prompt="What files are in the current directory?",
    options=ClaudeAgentOptions(max_turns=5),
):
    print(message)
```

You can also pass a custom `transport` for non-default connection settings:

```python
async for message in query(prompt="Hello", options=options, transport=transport):
    print(message)
```

## Client-based usage

For multi-turn sessions or finer control, use `ClaudeSDKClient`:

```python
from motus.claude_agent import ClaudeSDKClient, ClaudeAgentOptions

client = ClaudeSDKClient(options=ClaudeAgentOptions())
await client.send_message("What is 2 + 2?")

async for message in client.receive_messages():
    print(message)
```

`ClaudeSDKClient` subclasses the SDK's original client and injects tracing hooks on construction. Messages received through `receive_messages()` and `receive_response()` are observed for span capture.

## What Motus adds

You get the following without any code changes:

### Tracing

Hook-based span capture records agent calls, tool calls, and model calls. The integration injects `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `SubagentStart`, and `SubagentStop` hooks into `ClaudeAgentOptions.hooks` at call time. Consumer messages (`AssistantMessage`, `UserMessage`, `ResultMessage`) are observed for model call content and session cost/usage.

### Subagent tracking

Stack-based nesting tracks parallel subagents. When the SDK spawns a subagent via the `Agent` tool, Motus creates an `agent_call` span and parents all child tool/model spans to it. Parallel subagents are resolved via consumer-observed tool ownership rather than stack ordering alone.

### Auto-registration

Tracing is auto-registered on import. A standalone `TraceManager` is created (no runtime needed), and traces are auto-exported on process exit.

## Deployment

```python
from motus.claude_agent import query
from motus.serve2 import AgentServer

# Wrap query() in a serve2-compatible function
async def agent(message, state):
    result = await query(prompt=message.content)
    return ChatMessage.assistant_message(content=str(result)), state + [message]

server = AgentServer(agent)
```

```bash
motus serve start myapp:server
```

## Re-exports

`motus.claude_agent` re-exports everything from the `claude_agent_sdk` package, plus these Motus-specific names:

| Export                  | Description                                                    |
|-------------------------|----------------------------------------------------------------|
| `query()`               | Drop-in replacement with tracing hooks                         |
| `ClaudeSDKClient`       | Subclass with tracing on `receive_messages`/`receive_response` |
| `ClaudeAgentOptions`    | Re-exported from `claude_agent_sdk`                            |
| `register_tracing()`    | Creates the `TraceManager` (called on import)                  |
| `get_tracer()`          | Returns the `TraceManager` instance                            |

## Streaming behavior

When tracing is active and the prompt is a plain string, `query()` converts it to an `AsyncIterable` message stream internally. This bypasses the SDK's blocking `wait_for_result_and_end_input()` path so that hooks and consumer messages arrive interleaved in real-time. The stream stays alive until a `ResultMessage` is received.

You do not need to handle this conversion. Pass a string prompt and iterate as normal:

```python
async for message in query(prompt="Hello"):
    print(type(message).__name__, message)
```

## Trace export

Traces are auto-exported on process exit when `TraceManager.config.export_enabled` is `True`. You can also export manually:

```python
from motus.claude_agent import get_tracer

tracer = get_tracer()
if tracer:
    tracer.export_trace()
```

## Traced span types

The integration produces three span types in `TraceManager`:

- **`model_call`** — Created from `AssistantMessage` observations. Contains model name, conversation snapshot, thinking/content/tool_calls.
- **`tool_call`** — Created from `PreToolUse`/`PostToolUse` hook pairs. Contains tool name, input arguments, output, and error status.
- **`agent_call`** — Created from `SubagentStart`/`SubagentStop` hook pairs. Parents child model and tool spans within the subagent session.

A root `session_summary` span is created on `inject_tracing_hooks()` and updated with cost, usage, and duration from `ResultMessage`.
