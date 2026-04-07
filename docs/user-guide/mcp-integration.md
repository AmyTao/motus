# MCP Integration

The [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) is an open standard for connecting AI agents to external tools and data sources. Connect to any MCP-compatible server and expose its tools to your agent with `get_mcp()`.

## Basic Usage

This example uses an MCP server that runs via `npx` (requires [Node.js](https://nodejs.org/)). You can also connect to remote HTTP servers without Node.js — see [Remote HTTP](#remote-http) below.

```python
from motus.agent import ReActAgent
from motus.models import OpenAIChatClient
from motus.tools import get_mcp

session = get_mcp(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"])
agent = ReActAgent(
    client=OpenAIChatClient(),
    model_name="gpt-4o",
    tools=[session],
)
response = await agent("List files in /workspace")
```

`get_mcp()` returns an `MCPSession` — a live connection to an MCP server. Pass
it directly to the agent's `tools` list. The agent discovers every tool the
server exposes and can call them during execution.

## Connection Modes

`MCPSession` supports two connection modes:

| Mode | How | When |
|------|-----|------|
| Lazy | Pass `get_mcp()` to agent — connects on first use | Default, no lifecycle management needed |
| Explicit | `async with get_mcp() as session:` | When you need to inspect tools before running |

### Lazy (default)

```python
session = get_mcp(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"])
agent = ReActAgent(client=client, model_name="gpt-4o", tools=[session])
# Connection opens automatically on the first agent call
response = await agent("Read /workspace/README.md")
```

No `async with` block, no manual cleanup. The runtime manages the session
lifecycle.

### Explicit

```python
async with get_mcp(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]) as session:
    # Inspect available tools before building the agent
    print(session.tool_names)
    agent = ReActAgent(client=client, model_name="gpt-4o", tools=[session])
    response = await agent("Read /workspace/README.md")
# Session closes when the block exits
```

Use explicit mode when you need to inspect available tools, validate the
connection, or control the exact teardown point.

## Transports

### Stdio (local process)

The server runs as a child process. Communication happens over stdin/stdout.

```python
session = get_mcp(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"])
```

### Remote HTTP

Point to a running MCP endpoint. Pass authentication headers as needed.

```python
session = get_mcp(url="https://mcp.jina.ai/v1", headers={"Authorization": "Bearer ..."})
```

## Docker Sandbox

Run an MCP server inside a container to isolate file system access, network
calls, and dependencies from the host:

```python
session = get_mcp(
    image="node:20",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-everything"],
    port=3000,
)
```

The `image` parameter pulls and starts the container automatically. Use `port`
to expose the server's listening port. You can also pass a pre-configured
`sandbox=` object for finer control over volumes, environment variables, and
network policies.

## Filtering and Guardrails

An MCP server can expose dozens of tools. Use `tools()` to filter, rename,
and attach guardrails before handing them to the agent:

```python
from motus.tools import get_mcp, tools

async with get_mcp(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]) as session:
    wrapped = tools(session, prefix="fs_", blocklist={"write_file", "create_directory"})
    agent = ReActAgent(client=client, model_name="gpt-4o", tools=wrapped)
    response = await agent("List files in /workspace")
```

`tools()` works identically to how it works with plain class instances (see
[Custom Tools](tools.md#the-tools-decorator)):

| Parameter | Purpose |
|-----------|---------|
| `prefix` | Prepend to all tool names (e.g. `"fs_"`) |
| `allowlist` | Only expose these tools |
| `blocklist` | Exclude these tools |
| `input_guardrails` | Default input guardrails for all tools |
| `output_guardrails` | Default output guardrails for all tools |

## Selecting Individual Tools

`MCPSession` is a mapping — access individual tools as attributes. Combine
with `tool()` to add per-tool configuration:

```python
from motus.tools import get_mcp, tool

async with get_mcp(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]) as session:
    agent = ReActAgent(
        client=client,
        model_name="gpt-4o",
        tools=[tool(session.read_file, input_guardrails=[validate_path])],
    )
    response = await agent("Read /workspace/config.yaml")
```

This gives you full control: pick one tool from a large server, rename it,
and attach guardrails — all with the same `tool()` API used for plain
functions.

## Mixing MCP with Other Tools

MCP sessions mix freely with every other tool type in the `tools` list:

```python
from motus.tools import get_mcp, tool

async def summarize(text: str) -> str:
    """Summarize a block of text."""
    ...

fs_session = get_mcp(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/workspace"])
search_session = get_mcp(url="https://mcp.jina.ai/v1", headers={...})

agent = ReActAgent(
    client=client,
    model_name="gpt-4o",
    tools=[
        fs_session,       # all tools from the filesystem server
        search_session,   # all tools from the remote search server
        summarize,        # plain Python function
    ],
)
```

## Summary

| What you have | How to connect |
|---------------|---------------|
| Local MCP server (stdio) | `get_mcp(command=..., args=...)` |
| Remote MCP server (HTTP) | `get_mcp(url=..., headers=...)` |
| MCP server in Docker | `get_mcp(image=..., command=..., port=...)` |
| Filtered subset of tools | `tools(session, allowlist=..., blocklist=...)` |
| Single tool with guardrails | `tool(session.tool_name, input_guardrails=...)` |

For a runnable reference covering all patterns, see `examples/mcp_tools.py`.
