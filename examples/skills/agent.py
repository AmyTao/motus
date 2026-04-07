"""Skill tool demo — agent loads on-demand instructions from skill directories.

Skills are self-contained instruction sets (SKILL.md + companion files) that
the agent can load when a user request matches. The agent sees skill
descriptions and decides when to invoke them.

Usage:
    ANTHROPIC_API_KEY=... python examples/skills/agent.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from motus.agent import ReActAgent
from motus.models import AnthropicChatClient
from motus.tools import builtin_tools

load_dotenv()

SKILLS_DIR = Path(__file__).parent / "skills"


def _separator(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


async def main():
    client = AnthropicChatClient(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = os.getenv("MODEL", "claude-haiku-4-5-20251001")

    tools = builtin_tools(skills_dir=SKILLS_DIR)

    agent = ReActAgent(
        client=client,
        model_name=model,
        system_prompt=(
            "You are a helpful coding assistant. "
            "When a user request matches an available skill, load it first "
            "to get detailed instructions before proceeding."
        ),
        tools=tools,
        max_steps=10,
    )

    print(f"Model: {model}")
    print(f"Skills: {SKILLS_DIR}")

    prompts = [
        "Review this code for bugs:\ndef divide(a, b):\n    return a/b",
        "Research the pros and cons of async/await in Python",
    ]

    _separator("Skill Demo")

    for prompt in prompts:
        print(f"\n[You]: {prompt}")
        result = await agent(prompt)
        print(f"\n[Agent]: {result}\n")

    print("\nDemo complete!")


if __name__ == "__main__":
    asyncio.run(main())
