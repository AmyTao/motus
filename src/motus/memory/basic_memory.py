"""
BasicMemory - Simple append-only memory with no compaction.

Messages are appended to a list. No compaction, no memory tools,
no conversation logging. When the context window overflows, the
agent will receive an API error from the model provider.

This is the default memory for lithos agents — suitable for short
conversations or when the caller manages context externally.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from .base_memory import BaseMemory

if TYPE_CHECKING:
    from .session_state import SessionState


class BasicMemory(BaseMemory):
    """Append-only memory with no compaction or tools.

    The simplest memory implementation. Messages accumulate until the
    conversation ends or the context window is exceeded.
    """

    def __init__(
        self,
        *,
        model_name: Optional[str] = None,
        system_prompt: str = "",
        max_tool_result_tokens: int = 50000,
        tool_result_truncation_suffix: str = "\n\n... [content truncated due to length]",
        enable_memory_tools: bool = True,
    ):
        super().__init__(
            model_name=model_name,
            system_prompt=system_prompt,
            max_tool_result_tokens=max_tool_result_tokens,
            tool_result_truncation_suffix=tool_result_truncation_suffix,
            enable_memory_tools=enable_memory_tools,
        )

    async def compact(self, **kwargs) -> None:
        """No-op — BasicMemory does not support compaction."""
        return None

    def reset(self) -> Dict[str, int]:
        """Clear all messages."""
        count = len(self._messages)
        self.clear_messages()
        return {"messages": count}

    @classmethod
    def restore(cls, state: "SessionState", **kwargs: Any) -> "BasicMemory":
        """Restore from a SessionState snapshot.

        Args:
            state: SessionState with messages and system_prompt.
            **kwargs: Passed to BasicMemory.__init__ (model_name, etc).
        """
        memory = cls(**kwargs)
        memory._system_prompt = state.system_prompt
        memory._messages = list(state.messages)
        return memory
