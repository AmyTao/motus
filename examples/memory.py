"""Compaction memory demo — agent with automatic context management.

CompactionMemory provides:
  - Automatic context compaction when the context window fills up
  - Session persistence via conversation log store
  - Session restore from logs

This demo shows:
  1. Chat several turns covering different facts
  2. Trigger compaction (manual)
  3. Agent still remembers facts from before compaction via the summary
  4. Session restore from conversation log

Usage:
    ANTHROPIC_API_KEY=... python examples/memory.py
"""

import asyncio
import os
import shutil
import tempfile

from dotenv import load_dotenv

from motus.agent import ReActAgent
from motus.memory import CompactionMemory, CompactionMemoryConfig
from motus.models import AnthropicChatClient

load_dotenv()


def _separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


async def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = AnthropicChatClient(api_key=api_key)
    model = os.getenv("MODEL", "claude-haiku-4-5-20251001")

    tmp_dir = tempfile.mkdtemp(prefix="motus_compaction_demo_")
    log_path = os.path.join(tmp_dir, "conversation_logs")

    memory = CompactionMemory(
        config=CompactionMemoryConfig(
            session_id="demo-001",
            log_base_path=log_path,
            compact_model_name=model,
        ),
        on_compact=lambda stats: print(
            f"\n  [Compaction] {stats['messages_compacted']} messages compacted"
        ),
    )

    agent = ReActAgent(
        client=client,
        model_name=model,
        system_prompt="You are a helpful assistant. Keep answers concise.",
        memory=memory,
        max_steps=5,
    )

    print(f"Model: {model}")
    print(f"Log path: {log_path}")

    # --- Phase 1: Feed facts ---
    _separator("Phase 1: Teaching the agent some facts")

    facts = [
        "My name is Alice and I work at Acme Corp as a backend engineer.",
        "My favorite programming language is Rust, but I use Python daily at work.",
        "I'm working on Project Phoenix, a distributed task scheduler. Deadline is June 15th.",
        "My team lead is Bob, and our standup is at 9:30am Pacific every day.",
    ]

    for fact in facts:
        print(f"\n[You]: {fact}")
        result = await agent(fact)
        print(f"[Agent]: {result}")

    msg_count = len(memory.messages)
    print(f"\n  Messages in memory: {msg_count}")

    # --- Phase 2: Compact ---
    _separator("Phase 2: Compacting context")

    summary = await memory.compact()
    if summary:
        print(f"\n  Summary: {summary[:300]}...")
    print(f"  Messages after compaction: {len(memory.messages)}")

    # --- Phase 3: Ask about compacted facts ---
    _separator("Phase 3: Agent still remembers (via compaction summary)")

    questions = [
        "What project am I working on and when is the deadline?",
        "What's my favorite programming language?",
        "When is our team standup?",
    ]

    for question in questions:
        print(f"\n[You]: {question}")
        result = await agent(question)
        print(f"[Agent]: {result}")

    # --- Phase 4: Session restore ---
    _separator("Phase 4: Restore session from log")

    session_id = memory.session_id
    del agent, memory
    print(f"  Agent deleted. session_id={session_id}")

    restored_memory = CompactionMemory.restore_from_log(
        session_id=session_id,
        log_base_path=log_path,
        model_name=model,
    )
    agent2 = ReActAgent(
        client=client,
        model_name=model,
        system_prompt="You are a helpful assistant. Keep answers concise.",
        memory=restored_memory,
        max_steps=5,
    )

    print(f"  Restored {len(restored_memory.messages)} messages")
    print("\n[You]: What's my name and where do I work?")
    result = await agent2("What's my name and where do I work?")
    print(f"[Agent]: {result}")

    # --- Cleanup ---
    _separator("Cleanup")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"  Removed {tmp_dir}")
    print("\n  Demo complete!")


if __name__ == "__main__":
    asyncio.run(main())
