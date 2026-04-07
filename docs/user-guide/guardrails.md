# Guardrails

A guardrail is a plain Python function — no base class, no registration DSL. Declare the parameters you care about, return a dict to modify them, raise to block. Guardrails work at two levels: on the agent (before/after the entire run) and on individual tools (before/after each tool call).

## How guardrails work

A guardrail is a plain Python function. No base class, no decorator required.
Three conventions govern every guardrail:

- **Return `None`** (or return nothing) -- pass through unchanged.
- **Return a value** (`str`, `dict`, or the appropriate type) -- replace or update the input/output.
- **Raise an exception** -- block execution entirely.

Guardrails declare only the parameters they care about. The system inspects the
function signature and extracts matching values automatically -- you never need
to accept the full set of arguments.

Both sync and async guardrail functions are supported. Sync functions run on a
background thread via `asyncio.to_thread`.

## Tool input guardrails

Tool input guardrails run before the tool function executes. They receive
keyword arguments that match their declared parameter names.

```python
from motus.guardrails import ToolInputGuardrailTripped
from motus.tools import FunctionTool

def block_drop(query: str):
    if "DROP" in query.upper():
        raise ToolInputGuardrailTripped("DROP statements are forbidden")

sql_tool = FunctionTool(execute_sql, input_guardrails=[block_drop])
```

The guardrail declares `query` -- the system extracts it from the tool's kwargs.
Other tool parameters are ignored.

To **modify** an argument, return a `dict`. The returned dict merges into the
tool's kwargs -- keys you omit stay unchanged:

```python
def redact_api_key(token: str) -> dict:
    return {"token": re.sub(r"sk-\w+", "[REDACTED]", token)}
```

## Tool output guardrails

Tool output guardrails run after the tool returns, before the result is encoded
back to the model. They receive the typed return value directly.

```python
import re

def redact_passwords(result: str) -> str:
    return re.sub(r"password=\S+", "password=***", result)

tool = FunctionTool(get_user, output_guardrails=[redact_passwords])
```

When a tool guardrail raises, the exception message is returned to the model as
a tool error -- the agent sees it and can adjust without crashing the run.

## Agent input guardrails

Agent input guardrails run before the agent's `_run()` method. They receive the
user's prompt as a string. If the guardrail also declares an `agent` parameter,
the agent instance is passed in.

```python
from motus.guardrails import InputGuardrailTripped

def no_homework(value: str, agent):
    if "homework" in value.lower():
        raise InputGuardrailTripped("No homework help!")

agent = ReActAgent(..., input_guardrails=[no_homework])
```

Return a string to rewrite the prompt before the agent sees it. Return `None` to
pass through. Raise `InputGuardrailTripped` to block the run -- the exception
propagates to the caller.

## Agent output guardrails

When the agent returns a plain string (no `response_format`), output guardrails
receive `(value: str)` or `(value: str, agent)`. Return a string to replace the
output, `None` to pass through, or raise to block.

```python
import re

def redact_ssn(value: str) -> str:
    return re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", value)

agent = ReActAgent(..., output_guardrails=[redact_ssn])
```

### Structured output

When the agent uses `response_format` with a Pydantic `BaseModel`, output
guardrails use field matching -- the same mechanism as tool input guardrails.
Declare only the fields you need to inspect:

```python
from pydantic import BaseModel
from motus.guardrails import OutputGuardrailTripped

class AnalysisResult(BaseModel):
    score: float
    summary: str

def validate_score(score: float):
    if score < 0 or score > 1:
        raise OutputGuardrailTripped("Score must be between 0 and 1")

agent = ReActAgent(
    ...,
    response_format=AnalysisResult,
    output_guardrails=[validate_score],
)
```

`validate_score` declares `score` -- other fields are untouched. Return a
`dict` for partial updates (e.g. `{"raw_data": "[REDACTED]"}`). If the
guardrail also declares an `agent` parameter, the agent instance is passed in.

## Guardrail chaining

When you pass multiple guardrails, they form a sequential pipeline. Each
guardrail sees the output of the previous one:

```python
from motus.guardrails import ToolInputGuardrailTripped
from motus.tools import tool

def normalize_whitespace(text: str) -> dict:
    return {"text": " ".join(text.split())}

def lowercase(text: str) -> dict:
    return {"text": text.lower()}

def reject_profanity(text: str):
    bad_words = {"damn", "crap"}
    if set(text.split()) & bad_words:
        raise ToolInputGuardrailTripped("Profanity detected")

@tool(input_guardrails=[normalize_whitespace, lowercase, reject_profanity])
async def post_comment(text: str) -> str:
    """Post a comment."""
    return f"posted: {text}"
```

Input `"  Hello   WORLD  "` flows through: normalize -> lowercase ->
profanity check. The tool receives `"hello world"`.

Agent-level guardrails also support `parallel=True` mode, where all guardrails
run concurrently on the *original* value. Modifications are discarded -- only
tripwire exceptions take effect.

## Where to attach guardrails

| Level | How | Parameters |
|---|---|---|
| Single tool | `@tool(...)` or `FunctionTool(...)` | `input_guardrails`, `output_guardrails` |
| Tool collection | `@tools(...)` on the class | `input_guardrails`, `output_guardrails` |
| Agent | `ReActAgent(...)` | `input_guardrails`, `output_guardrails` |

For tool collections, method-level `@tool` guardrails override class-level
defaults -- they do not merge. See the
[Tools page](tools.md) for examples.

## Exception hierarchy

All guardrail exceptions inherit from `GuardrailTripped`:

| Exception | Where it applies |
|---|---|
| `InputGuardrailTripped` | Agent input guardrails |
| `OutputGuardrailTripped` | Agent output guardrails |
| `ToolInputGuardrailTripped` | Tool input guardrails |
| `ToolOutputGuardrailTripped` | Tool output guardrails |

```python
from motus.guardrails import (
    InputGuardrailTripped,
    OutputGuardrailTripped,
    ToolInputGuardrailTripped,
    ToolOutputGuardrailTripped,
)
```

Agent guardrail exceptions propagate to the caller. Tool guardrail exceptions
are caught internally and returned to the model as error messages -- the agent
sees the guardrail feedback and can adjust its next action.

## Next steps

See `examples/runtime/guardrails/guardrails_demo.py` for a runnable demo covering
all guardrail types, chaining, parallel mode, and structured output validation.

For tool-specific guardrail patterns (decorators, class-level defaults, schema
overrides), see the [Guardrails section in Tools](tools.md#guardrails).
