# Runtime Engine

The motus runtime turns ordinary Python into a task graph. No DAG definitions, no edge declarations, no YAML — decorate a function with `@agent_task`, call it, and get back an `AgentFuture` instead of a concrete value. Pass futures as arguments to express dependencies — motus infers the graph and schedules everything automatically.

## Basic example

```python
from motus.runtime import resolve, shutdown
from motus.runtime.agent_task import agent_task

@agent_task
def add(a, b):
    return a + b

@agent_task
def multiply(x, y):
    return x * y

a = add(3, 4)        # returns AgentFuture, not 7
b = multiply(a, 10)  # depends on a — runs after a completes
print(resolve(b))    # 70

shutdown()
```

When you call `add(3, 4)`, the runtime registers a task and returns an `AgentFuture`. When you pass that future into `multiply(a, 10)`, the runtime detects the dependency and waits for `a` to resolve before executing `multiply`. The `GraphScheduler` manages this DAG and dispatches tasks as their dependencies become ready.

## Getting results

```python
from motus.runtime import resolve

# Block until a single future resolves (sync code)
value = resolve(future)

# Block until multiple futures resolve
a, b, c = resolve([future_a, future_b, future_c])

# Block with a timeout (raises TimeoutError if exceeded)
value = future.af_result(timeout=5)
```

Inside an `@agent_task` or any async context, use `await` instead of blocking:

```python
@agent_task
async def pipeline():
    data = await fetch_data("https://api.example.com")
    return await process(data)
```

The public API for blocking resolution is `af_result()` or `resolve()`. There is no `.result()` method on `AgentFuture`.

## Non-blocking operators

Arithmetic, `__getitem__`, and `__getattr__` on futures create new futures that extend the task graph without blocking:

```python
x = add(10, 5)
total = x + 100       # AgentFuture, not blocking
doubled = x * 2       # AgentFuture, extends the DAG

data = make_data()
first = data["scores"][0]  # chained getitem — two new futures
```

This is the key design insight: arithmetic on futures extends the dependency graph lazily. `total = x + 100` does not wait for `x` to resolve — it creates a new node in the DAG that will execute when `x` is ready. You write normal Python; motus builds the execution plan.

Ordering comparisons (`>`, `<`, `>=`, `<=`) also return futures. Equality (`==`) and hashing (`hash()`) are sync barriers — they block to resolve the value. See [Critical constraint](#critical-constraint) below.

## Retries and timeouts

```python
@agent_task(retries=3, timeout=10.0, retry_delay=1.0)
async def fetch(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()
```

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `retries` | `int` | `0` | Number of retry attempts after failure |
| `timeout` | `float \| None` | `None` | Per-execution timeout in seconds |
| `retry_delay` | `float` | `0.0` | Seconds to wait between retries |

When a task fails and has retries remaining, the runtime re-queues it with the same arguments after waiting `retry_delay` seconds. If the task exceeds `timeout` seconds, it raises `TimeoutError` (which counts as a failure and triggers retries if available).

## Policy overrides at call site

You can override the default policy for a specific invocation without changing the decorator:

```python
result = fetch.policy(retries=5, timeout=30)("https://api.example.com")
```

`.policy()` returns a new `AgentTaskDefinition` with the updated settings. The original definition remains unchanged.

## Multi-return

```python
@agent_task(num_returns=2)
def split(data):
    mid = len(data) // 2
    return data[:mid], data[mid:]

left, right = split([1, 2, 3, 4])
# left and right are separate AgentFutures
combined = add(resolve(left)[-1], resolve(right)[0])
```

When `num_returns` is set, the call returns a tuple of `AgentFuture` objects — one per return value. Each future resolves independently, so downstream tasks can depend on individual outputs.

## Async and sync tasks

Both sync and async functions work with `@agent_task`:

```python
@agent_task
def cpu_bound(data):
    """Runs in a thread pool executor."""
    return heavy_computation(data)

@agent_task
async def io_bound(url):
    """Runs as a coroutine on the runtime event loop."""
    return await fetch(url)
```

Sync tasks run in the runtime's `ThreadPoolExecutor`. Async tasks run directly on the runtime's event loop. Prefer async for I/O-bound work and sync for CPU-bound work.

## Class methods

`@agent_task` implements the descriptor protocol, so it works on class methods:

```python
class DataProcessor:
    def __init__(self, multiplier):
        self.multiplier = multiplier

    @agent_task
    def process(self, value):
        return value * self.multiplier

proc = DataProcessor(3)
result = proc.process(10)  # AgentFuture — resolves to 30
```

When accessed through an instance, `@agent_task` binds `self` automatically, matching the behavior of regular Python methods.

## Per-task hooks

You can attach hooks directly in the decorator:

```python
def log_start(event):
    print(f"Starting {event.name}")

def log_end(event):
    print(f"Finished {event.name}: {event.result}")

@agent_task(on_start=log_start, on_end=log_end)
def important_task(data):
    return transform(data)
```

These hooks fire only for this specific task. For broader hook patterns, see [Tracing](tracing.md).

## Lifecycle

```python
from motus.runtime import init, shutdown, is_initialized

# Explicit initialization
init()

# ... run tasks ...

# Clean shutdown — waits for in-flight tasks, stops the event loop
shutdown()
```

`init()` starts the runtime thread and event loop. If you skip it, the runtime auto-initializes on the first `@agent_task` call. `shutdown()` stops the event loop, drains the thread pool executor, and releases resources. Call it when your program exits.

`is_initialized()` returns `True` if the runtime is running.

## Critical constraint

Never put an `AgentFuture` in a `set()` or use it as a dictionary key. The `__eq__` and `__hash__` methods on `AgentFuture` are **sync barriers** — they block the calling thread to resolve the underlying value. Inside an `@agent_task`, this deadlocks the runtime.

```python
# WRONG — will deadlock
futures = {add(1, 2), add(3, 4)}

# CORRECT — key by object identity
futures = {}
f = add(1, 2)
futures[id(f)] = f
```

Use `dict[int, AgentFuture]` keyed by `id(future)` when you need to collect futures.

## Next steps

- [Tracing](tracing.md) — observe task execution, measure timing, export traces
- [Agents](agents.md) — build LLM-powered agents that run on the runtime
- [Tools](tools.md) — define tools that agents can invoke as tasks
