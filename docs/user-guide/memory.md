# Memory

Long conversations break most agent frameworks — the context window fills up and the agent crashes or forgets. Motus manages this automatically. `CompactionMemory` monitors token count after every message and summarizes older turns when the budget runs thin. The agent never notices. Choose a strategy based on conversation length and persistence needs.

## Quick Start

```python
# Short conversations — keep all messages (default)
agent = ReActAgent(client=client, model_name="gpt-4o", memory_type="basic")

# Long conversations — auto-compact when token budget is reached
agent = ReActAgent(client=client, model_name="gpt-4o", memory_type="compact")
```

## Strategies

| Strategy | Token Management | Persistence | Use Case |
|----------|-----------------|-------------|----------|
| `basic` | None — grows unbounded | In-memory only | Short conversations, testing |
| `compact` | Auto-compacts at threshold | Optional log-based restore | Production agents, long sessions |
| `background` | Auto-compacts + agent-managed memory | Cross-session persistence | Coming soon |

Both extend `BaseMemory` and share an async interface: `add_message()`, `compact()`, `get_context()`, `get_memory_trace()`.

## Architecture

```
BaseMemory (abstract)
├── BasicMemory              — append-only, no compaction
└── CompactionBase (abstract) — boundary detection, compact(), set_model()
    └── CompactionMemory     — + conversation log store, session restore
```

`CompactionBase` provides the core compaction logic shared by all compacting memory types: turn boundary detection, token threshold management, and LLM-based summarization. `CompactionMemory` adds conversation log persistence and session restore on top.

## BasicMemory

Append-only message list with no compaction. Messages accumulate until the conversation ends. If the context window overflows, the model provider returns an API error.

```python
agent = ReActAgent(client=client, model_name="gpt-4o", memory_type="basic")
```

This is the default. You get it when you pass no `memory_type` or `memory` argument.

## CompactionMemory

The most commonly used strategy for production agents. CompactionMemory monitors token count after every message. When the estimated token count exceeds a threshold **and** the conversation is at a turn boundary, it summarizes older turns into a continuation message. The agent loop continues without interruption.

### Turn boundary detection

Compaction only triggers at clean turn boundaries to avoid corrupting in-progress tool call sequences. A ReAct agent loop produces three types of turn units:

- **Unit A** — `[user message]`
- **Unit B** — `[assistant + tool_calls]` followed by `[tool_result × N]`
- **Unit C** — `[assistant, no tool calls]` (final response)

Compaction defers until all tool results from a parallel tool call batch have arrived. This is tracked via `_pending_tool_calls` — a counter incremented when the assistant issues tool calls and decremented as each result arrives. Compaction fires only when the counter reaches zero.

### Configuration

```python
from motus.memory import CompactionMemory, CompactionMemoryConfig

memory = CompactionMemory(
    config=CompactionMemoryConfig(
        compact_model_name="claude-haiku-4-5-20251001",
        token_threshold=8000,
        safety_ratio=0.75,
        session_id="user-123",
        log_base_path="./conversation_logs",
    ),
    on_compact=lambda stats: print(f"Compacted {stats['messages_compacted']} messages"),
)

agent = ReActAgent(client=client, model_name="gpt-4o", memory=memory)
```

**Configuration fields:**

| Field | Default | Description |
|-------|---------|-------------|
| `compact_model_name` | Agent's model | Model used for the compaction LLM call |
| `token_threshold` | `None` | Explicit token threshold. When `None`, derived from the model's context window times `safety_ratio` |
| `safety_ratio` | `0.75` | Fraction of the context window that triggers compaction |
| `session_id` | Auto UUID | Identifier for the conversation session |
| `log_base_path` | `None` | Directory for JSONL conversation logs. `None` disables logging |
| `max_tool_result_tokens` | `50000` | Maximum tokens per tool result before truncation |

When you set `log_base_path`, CompactionMemory writes every message and compaction event to a JSONL file. This enables session restore and provides memory tools (conversation log search, compaction summary retrieval) that the agent can call during execution.

### Session Restore

```python
restored = CompactionMemory.restore_from_log(
    session_id="user-123",
    log_base_path="./conversation_logs",
)
agent = ReActAgent(client=client, model_name="gpt-4o", memory=restored)
# Agent continues with the previous conversation's context
```

`restore_from_log` replays all log entries — messages and compaction events — to rebuild the in-memory state. The restored instance appends to the same session log.

### Session State

For programmatic session persistence, use `SessionState`:

```python
from motus.memory import CompactionSessionState

# Snapshot current state
state = memory.get_session_state()
data = state.to_dict()  # serialize to JSON-compatible dict

# Restore later
restored_state = CompactionSessionState.from_dict(data)
```

`SessionState` captures the current context window (messages + system prompt). `CompactionSessionState` adds session identity and log store location for cross-session continuity.

### Custom Compaction Function

```python
def my_compaction(messages, system_prompt):
    """Return a summary string from the conversation."""
    return f"Summary: {len(messages)} messages processed"

memory = CompactionMemory(compact_fn=my_compaction)
```

Pass a `compact_fn` to replace the default LLM-based compaction with your own logic. The function receives the message list and system prompt, and returns a summary string.

## Custom Memory

```python
from motus.memory import BaseMemory

class MyMemory(BaseMemory):
    async def compact(self, **kwargs):
        """Implement your compaction strategy."""
        ...

    def reset(self):
        """Clear all state and return counts."""
        count = len(self._messages)
        self._messages.clear()
        return {"messages": count}

agent = ReActAgent(client=client, model_name="gpt-4o", memory=MyMemory())
```

Subclass `BaseMemory` and implement `compact()` and `reset()`. The base class provides working memory management, token estimation, tool result truncation, and trace logging. Override `_auto_compact()` to control when compaction triggers automatically, and `build_tools()` to expose memory-specific tools to the agent.

For compacting memory types, extend `CompactionBase` instead — it provides boundary-aware auto-compaction, `set_model()`, and the default LLM summarization logic.

## BackgroundMemory (coming soon)

A long-term memory solution that works both locally and on the cloud is under active development. `BackgroundMemory` will extend `CompactionBase` with agent-managed cross-session memory, allowing the main agent to remember facts, preferences, and context across conversations without distraction.

## Next Steps

- [Tools](tools.md) — define tools that interact with memory
- [Guardrails](guardrails.md) — validate agent inputs and outputs
- [Tracing](tracing.md) — inspect memory operations via trace logs
