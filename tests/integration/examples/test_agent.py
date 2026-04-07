"""
Integration tests for examples/agent.py — the basic ReAct agent example.

Usage:
    pytest tests/integration/examples/test_agent.py -v
"""

import importlib

import pytest


def _import_attr(dotted_path: str):
    """Import 'module.path:attribute' and return the attribute."""
    module_path, attr_name = dotted_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, attr_name)


class TestAgentConsole:
    """Call the agent directly with a mocked client."""

    @pytest.mark.integration
    async def test_console(self):
        from unittest.mock import AsyncMock, patch

        from motus.models import ChatCompletion, ChatMessage

        agent = _import_attr("examples.agent:agent")
        msg = ChatMessage.user_message(content="Say hello in one sentence.")

        mock_completion = ChatCompletion(
            id="mock-1",
            model="mock",
            content="Hello, how can I help you today?",
            tool_calls=[],
        )

        with patch.object(
            type(agent._client),
            "create",
            new_callable=AsyncMock,
            return_value=mock_completion,
        ):
            response, messages = await agent.run_turn(msg, [])

        assert isinstance(response, ChatMessage)
        assert response.role == "assistant"
        assert response.content and len(response.content) > 0
        assert isinstance(messages, list)
        assert len(messages) >= 2
