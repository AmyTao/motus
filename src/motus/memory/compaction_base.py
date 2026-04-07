"""
CompactionBase — abstract base for memory implementations that use LLM compaction.

Provides the shared core that both CompactionMemory and BackgroundMemory build on:
- set_model() for agent injection
- add_message() with _pending_tool_calls tracking for accurate boundary detection
- _is_at_boundary() — clean turn-unit boundary detection
- _auto_compact() → compact() pipeline
- compact() / _default_compact() — LLM summarization + context replacement
- _get_token_threshold() — model-aware threshold resolution

Turn boundary rules
-------------------
Compaction is deferred until the current reasoning unit completes:

  Unit A — [user msg]
  Unit B — [assistant + tool_calls] followed by ALL tool results
  Unit C — [assistant, no tool_calls]  (final response in a ReAct step)

This prevents orphaned tool results and ensures the continuation summary
always starts at a semantically clean point.
"""

import copy
import logging
from abc import abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from .session_state import SessionState

from motus.models import BaseChatClient, ChatMessage

from .base_memory import BaseMemory
from .compaction_prompts import (
    COMPACTION_USER_PROMPT,
    CONTINUATION_TEMPLATE,
    CONTINUATION_WITH_PENDING_TEMPLATE,
)
from .config import CompactionMemoryConfig
from .model_limits import estimate_compaction_threshold

logger = logging.getLogger(__name__)

CompactFn = Callable[[List[ChatMessage], str], str]
"""Signature: (messages, system_prompt) -> summary_text"""


class CompactionBase(BaseMemory):
    """
    Abstract base providing LLM-based compaction for memory implementations.

    Subclasses must implement:
      - reset()     (from BaseMemory)

    Subclasses may override:
      - _auto_compact()          — for custom compaction trigger logic
      - _on_compaction_recorded()— hook called after compact() updates state,
                                   before the on_compact callback fires
      - build_tools()            — to expose memory tools to the agent
    """

    def __init__(
        self,
        *,
        config: Optional[CompactionMemoryConfig] = None,
        compact_fn: Optional[CompactFn] = None,
        on_compact: Optional[Callable[[Dict[str, Any]], None]] = None,
        enable_memory_tools: bool = True,
        # Main agent model — injected by AgentBase.set_model() if not provided
        client: Optional[BaseChatClient] = None,
        model_name: Optional[str] = None,
    ) -> None:
        self.config = config or CompactionMemoryConfig()
        super().__init__(
            model_name=model_name,
            max_tool_result_tokens=self.config.max_tool_result_tokens,
            tool_result_truncation_suffix=self.config.tool_result_truncation_suffix,
            enable_memory_tools=enable_memory_tools,
        )
        self._client = client
        self._compact_model_name = self.config.compact_model_name
        self._compact_fn = compact_fn
        self._token_threshold = self.config.token_threshold
        self._safety_ratio = self.config.safety_ratio
        self._on_compact = on_compact
        self._compaction_count: int = 0
        self._compaction_summaries: List[Dict[str, Any]] = []
        self._pending_tool_calls: int = 0

    # -------------------------------------------------------------------------
    # Model / client injection (called by AgentBase during init)
    # -------------------------------------------------------------------------

    def set_model(self, *, client: BaseChatClient, model_name: str) -> None:
        """Fill model-related params not provided at init."""
        if self._model_name is None:
            self._model_name = model_name
        if self._client is None:
            self._client = client
        if self._compact_model_name is None:
            self._compact_model_name = self._model_name

    # -------------------------------------------------------------------------
    # Turn boundary detection
    # -------------------------------------------------------------------------

    async def add_message(self, message: ChatMessage) -> None:
        """Add message, update pending tool call counter, then auto-compact."""
        # Track pending tool calls BEFORE appending so _is_at_boundary() is
        # correct when _auto_compact() runs after the message is appended.
        if message.role == "assistant":
            self._pending_tool_calls = (
                len(message.tool_calls) if message.tool_calls else 0
            )
        elif message.role == "tool":
            self._pending_tool_calls = max(0, self._pending_tool_calls - 1)

        await super().add_message(message)  # _append_message + _auto_compact

    def _is_at_boundary(self) -> bool:
        """True when the last message completes a reasoning unit.

        Unit A: user message
        Unit B: all tool results received for the preceding assistant step
        Unit C: assistant message with no tool calls (final response)
        """
        if not self._messages:
            return False
        last = self._messages[-1]
        if last.role == "user":
            return True
        if last.role == "assistant" and not last.tool_calls:
            return True
        if last.role == "tool" and self._pending_tool_calls == 0:
            return True
        return False

    # -------------------------------------------------------------------------
    # Token threshold
    # -------------------------------------------------------------------------

    def _get_token_threshold(self) -> int:
        """Resolve the compaction token threshold for the current model."""
        if self._token_threshold is not None:
            return self._token_threshold
        threshold = estimate_compaction_threshold(
            model_id=self._model_name or "",
            safety_ratio=self._safety_ratio,
        )
        if threshold is None:
            fallback = int(128_000 * self._safety_ratio)
            logger.warning(
                f"Model '{self._model_name}' not in limits table, "
                f"using fallback threshold: {fallback}"
            )
            return fallback
        return threshold

    # -------------------------------------------------------------------------
    # Auto-compaction
    # -------------------------------------------------------------------------

    async def _auto_compact(self) -> None:
        """Trigger compaction at a clean boundary when threshold is exceeded."""
        if not self._is_at_boundary():
            return
        if self.estimate_working_memory_tokens() <= self._get_token_threshold():
            return
        await self._do_compact()

    async def _do_compact(self) -> None:
        """Execute compaction. Override in subclasses to add side effects."""
        await self.compact()

    # -------------------------------------------------------------------------
    # Compaction
    # -------------------------------------------------------------------------

    def _find_last_turn_start(self) -> int:
        """Return the index where the split between to_summarize and to_replay falls.

        Split-compaction only replays for units with pending work:
          Unit A (user msg)  — pending request, must be preserved
          Unit B (tool results) — agent needs to process results
          Unit C (assistant, no tools) — conversation at rest, summarize everything

        Returns len(messages) for Unit C (no replay), or the start index
        of the last unit for Unit A / Unit B.
        """
        if not self._messages:
            return 0
        last = self._messages[-1]
        # Unit C: no pending work — summarize everything
        if last.role == "assistant":
            return len(self._messages)
        # Unit A: pending user message
        if last.role == "user":
            return len(self._messages) - 1
        # Unit B: scan backward past tool results to the owning assistant
        i = len(self._messages) - 1
        while i >= 0 and self._messages[i].role == "tool":
            i -= 1
        return max(0, i)

    async def compact(self, **kwargs) -> Optional[str]:
        """
        Compact the current context using split-compaction.

        Split behavior depends on the boundary type:
          Unit A — pending user message embedded into the continuation template
          Unit B — assistant + tool results replayed verbatim (prevents
                   summarization overflow from large tool results)
          Unit C — full compaction, no replay (conversation at rest)

        Falls back to full compaction if the last turn is the entire history.

        Returns:
            The summary text, or None if there was nothing to compact.
        """
        if not self._messages:
            return None

        split_idx = self._find_last_turn_start()
        to_summarize = self._messages[:split_idx]
        to_replay = self._messages[split_idx:]

        if not to_summarize:
            # Last turn is entire history — fall back to summarizing everything
            to_summarize = self._messages
            to_replay = []

        logger.info(
            f"Compacting {len(to_summarize)} messages "
            f"(replaying {len(to_replay)} verbatim, "
            f"~{self.estimate_working_memory_tokens()} estimated tokens)"
        )

        if self._compact_fn is not None:
            summary = self._compact_fn(to_summarize, self._system_prompt)
        else:
            summary = await self._default_compact(to_summarize, self._system_prompt)

        # Unit A: embed pending user message in continuation to avoid
        # two consecutive user messages in the replayed context.
        replayed_count = len(to_replay)
        if to_replay and to_replay[0].role == "user":
            continuation_content = CONTINUATION_WITH_PENDING_TEMPLATE.format(
                summary=summary,
                pending_request=to_replay[0].content or "",
            )
            to_replay = []
        else:
            continuation_content = CONTINUATION_TEMPLATE.format(summary=summary)

        summarized_count = len(to_summarize)
        self._messages = [ChatMessage.user_message(continuation_content)] + to_replay
        self._compaction_count += 1
        summary_tokens = self.estimate_message_tokens(self._messages[0])

        compaction_event = {
            "type": "compaction",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "messages_compacted": summarized_count,
            "messages_replayed": replayed_count,
            "summary_tokens": summary_tokens,
            "compaction_number": self._compaction_count,
        }
        self._trace_log.append(compaction_event)

        summary_record = {
            "compaction_number": self._compaction_count,
            "messages_compacted": summarized_count,
            "summary": summary,
        }
        self._compaction_summaries.append(summary_record)

        # Hook for subclasses (e.g., CompactionMemory writes to disk log)
        self._on_compaction_recorded(compaction_event, summary)

        if self._on_compact is not None:
            self._on_compact(
                {
                    "messages_compacted": summarized_count,
                    "messages_replayed": replayed_count,
                    "summary_tokens": summary_tokens,
                    "compaction_number": self._compaction_count,
                    "summary": summary,
                }
            )

        logger.info(
            f"Compaction complete: {summarized_count} messages summarized, "
            f"{replayed_count} replayed ({summary_tokens} tokens in continuation)"
        )
        return summary

    def _on_compaction_recorded(self, event: Dict[str, Any], summary: str) -> None:
        """Hook called after compaction state is updated.

        Override in subclasses to persist the compaction record
        (e.g., write to a conversation log on disk).
        """
        pass

    async def _default_compact(
        self, messages: List[ChatMessage], system_prompt: str
    ) -> str:
        """Default compaction via the agent's LLM client."""
        if self._client is None:
            raise ValueError(
                "CompactionBase requires either a 'client' or a 'compact_fn'. "
                "Neither was provided."
            )
        compaction_messages = [
            ChatMessage.system_message(system_prompt),
            *messages,
            ChatMessage.user_message(COMPACTION_USER_PROMPT),
        ]
        completion = await self._client.create(
            model=self._compact_model_name,
            messages=compaction_messages,
        )
        return completion.content or "Unable to generate summary."

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def reset(self) -> Dict[str, int]:
        """Reset to initial state. Clears messages, compaction state, and trace."""
        count = len(self._messages)
        self._messages.clear()
        self._trace_log.clear()
        self._compaction_count = 0
        self._compaction_summaries.clear()
        self._pending_tool_calls = 0
        return {"messages": count}

    # -------------------------------------------------------------------------
    # Session state (REQUIRED in subclasses)
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_session_state(self) -> "SessionState":
        """Capture current session state for persistence and restoration.

        Returns a SessionState subclass appropriate for this memory type,
        containing the current message window plus backing-store metadata
        (session_id/log_path for CompactionMemory, tree_root for BackgroundMemory).
        """
        ...

    @classmethod
    @abstractmethod
    def restore(cls, state: "SessionState", **kwargs: Any) -> "CompactionBase":
        """Restore a memory instance from a session state snapshot.

        Trusts state.messages directly without replaying any log.
        Use CompactionMemory.restore_from_log() for full log-replay restore.

        Args:
            state: A SessionState subclass instance produced by get_session_state().
            **kwargs: Runtime parameters that cannot be serialized (client, compact_fn, etc.)
        """
        ...

    # -------------------------------------------------------------------------
    # Fork
    # -------------------------------------------------------------------------

    def fork(self) -> "CompactionBase":
        """Create an independent copy, deep-copying mutable collections."""
        clone = copy.copy(self)
        clone._messages = copy.deepcopy(self._messages)
        clone._trace_log = copy.deepcopy(self._trace_log)
        clone._compaction_summaries = copy.deepcopy(self._compaction_summaries)
        return clone
