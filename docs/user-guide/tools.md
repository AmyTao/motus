# Tools

Tools are Python functions. Type hints become the JSON schema, docstrings become the description.

```python
async def search(query: str) -> str:
    """Search the web for a query."""
    return await web_search(query)

agent = ReActAgent(model_name="gpt-4o", tools=[search], client=client)
```

Both sync and async functions work. Motus extracts the name, description, and parameter schema automatically.

## `@tool` decorator

Customize the name, schema, or attach guardrails:

```python
from motus.tools import tool

@tool(name="web_search")
async def search(query: str) -> str:
    """Search the web."""
    return await web_search(query)

# Also works as a function call for functions you don't own
configured = tool(third_party_fn, name="fetch", input_guardrails=[validate_url])
```

| Parameter | Purpose |
|-----------|---------|
| `name` | Override tool name (default: function name) |
| `description` | Override description (default: docstring) |
| `schema` | Override input schema (Pydantic model, dict, or JSON Schema) |
| `input_guardrails` | Guardrails run before execution |
| `output_guardrails` | Guardrails run after execution |
| `on_start` / `on_end` / `on_error` | Lifecycle hook callbacks |

## `FunctionTool`

For full control:

```python
from motus.tools import FunctionTool

ft = FunctionTool(
    search,
    name="web_search",
    schema=SearchInput,
    input_guardrails=[validate_query],
    output_guardrails=[redact_pii],
)
```

Explicit arguments take priority over `@tool` metadata, which takes priority over introspection.

## Parameter descriptions

**`Annotated`** — lightweight inline descriptions:

```python
from typing import Annotated

async def search(
    query: Annotated[str, "The search query"],
    max_results: Annotated[int, "Max results to return"] = 10,
) -> str: ...
```

**`InputSchema`** — Pydantic model for validation constraints and nested objects:

```python
from motus.tools import InputSchema
from pydantic import Field

class SearchInput(InputSchema):
    query: str = Field(description="The search query")
    max_results: int = Field(ge=1, le=50, description="Max results")

@tool(schema=SearchInput)
async def search(query: str, max_results: int) -> str: ...
```

**Raw dict** — exact JSON Schema control:

```python
@tool(schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})
async def search(query: str) -> str: ...
```

### Supported types

| Python | JSON Schema |
|--------|-------------|
| `str`, `int`, `float`, `bool` | `string`, `integer`, `number`, `boolean` |
| `list[T]` | `array` with `items` |
| `dict[str, T]` | `object` with `additionalProperties` |
| `T \| None` | `anyOf [T, null]` |
| `BaseModel`, `TypedDict` | `object` with `properties` |
| `Annotated[T, "desc"]` | schema of `T` + `description` |

## Tool collections

Group related tools as a class. Public methods become tools, `self` is excluded from the schema:

```python
from motus.tools import tools

@tools(prefix="db_", blocklist={"_connect"})
class DatabaseTools:
    def __init__(self, conn_string: str):
        self.conn = connect(conn_string)

    async def query(self, sql: str) -> str:
        """Execute a SQL query."""
        return str(self.conn.execute(sql))

    async def insert(self, table: str, data: dict) -> str:
        """Insert a row."""
        ...

# Tools: "db_query", "db_insert"
```

`@tools` also works as a function call: `tools(instance, allowlist={"get"}, prefix="api_")`.

| Parameter | Purpose |
|-----------|---------|
| `prefix` | Prepend to all tool names |
| `include_private` | Expose `_private` methods (default: `False`) |
| `method_schemas` | Per-method schema overrides |
| `method_aliases` | Rename methods |
| `allowlist` / `blocklist` | Filter exposed methods |
| `input_guardrails` / `output_guardrails` | Default guardrails for all methods |

Per-method `@tool` overrides class-level `@tools` settings:

```python
@tools(prefix="db_", input_guardrails=[log_all])
class DatabaseTools:
    @tool(name="raw_query", input_guardrails=[validate_sql])
    async def query(self, sql: str) -> str: ...   # "db_raw_query", uses [validate_sql]

    async def insert(self, table: str, data: dict) -> str: ...   # "db_insert", uses [log_all]
```

## Guardrails

Guardrails validate or transform inputs/outputs. They are plain functions that declare only the parameters they inspect:

```python
from motus.guardrails import ToolInputGuardrailTripped, ToolOutputGuardrailTripped

# Input: return None (pass-through), dict (partial update), or raise (block)
def block_drop(query: str):
    if "DROP" in query.upper():
        raise ToolInputGuardrailTripped("DROP not allowed")

# Output: return None (pass-through), value (replace), or raise (block)
def redact_secrets(result: str) -> str:
    return re.sub(r'password=\S+', 'password=***', result)

@tool(input_guardrails=[block_drop], output_guardrails=[redact_secrets])
async def query(query: str) -> str:
    """Execute SQL."""
    ...
```

Guardrails run sequentially (each sees the previous one's output). Both sync and async supported. Class-level guardrails apply to all methods unless overridden per-method.

For agent output guardrails with `response_format`, the same convention applies — declare only the fields you care about:

```python
from motus.guardrails import OutputGuardrailTripped

def validate_score(score: float):
    if not 0 <= score <= 1:
        raise OutputGuardrailTripped("Score must be 0-1")

agent = ReActAgent(..., response_format=MyModel, output_guardrails=[validate_score])
```

## Builtin tools

Code-agent tools for filesystem access and shell execution:

```python
from motus.tools.builtins import builtin_tools

agent = ReActAgent(model_name="gpt-4o", tools=[builtin_tools()], client=client)
```

| Tool | Description |
|------|-------------|
| `bash` | Shell command execution (default 120s timeout, max 600s, output truncated to 30k chars) |
| `read_file` | Read file with line numbers (`offset`/`limit`, default: first 2000 lines) |
| `write_file` | Write file, creates parent directories |
| `edit_file` | Exact string replacement. Fails on ambiguous match unless `replace_all=True` |
| `glob_search` | Find files by glob pattern |
| `grep_search` | Regex search with context lines, type filters, output modes |
| `to_do` | Task checklist for agent self-tracking |

Pass a `Sandbox` for isolated execution:

```python
from motus.tools.providers.docker import DockerSandbox
bt = builtin_tools(sandbox=DockerSandbox("python:3.12"))
```

## MCP tools

Consume tools from any [MCP](https://modelcontextprotocol.io/) server:

```python
from motus.tools import MCPSession

mcp = MCPSession(url="http://localhost:3000/mcp")
# or stdio: MCPSession(command="npx", args=["-y", "@anthropic/mcp-server-filesystem", "/workspace"])

agent = ReActAgent(model_name="gpt-4o", tools=[mcp], client=client)
```

Connects lazily on first run, cleans up on finish.

## Agents as tools

Pass an agent as a tool to another agent:

```python
researcher = ReActAgent(name="researcher", model_name="gpt-4o", system_prompt="...", client=client)
orchestrator = ReActAgent(model_name="gpt-4o", tools=[researcher], client=client)
```

## Summary

| Source | Registration |
|--------|-------------|
| Function | `[my_func]` |
| Function you don't own | `tool(func, name=...)` |
| Class instance | `[MyClass()]` |
| Class with config | `@tools(prefix=...)` |
| Instance you don't own | `tools(instance, allowlist=...)` |
| Full control | `FunctionTool(func, ...)` |
| MCP server | `MCPSession(url=...)` or `MCPSession(command=...)` |
| Agent | `[my_agent]` |
