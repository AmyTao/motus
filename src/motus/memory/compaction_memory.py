"""
CompactionMemory - LLM-based context compaction with session log persistence.

Extends CompactionBase with:
- Conversation log (JSONL on disk) for session persistence and search
- Session restore via restore_from_log()
- Log-search and compaction-summary tools for the agent
"""

import dataclasses
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from motus.models import BaseChatClient, ChatMessage

from .compaction_base import CompactFn, CompactionBase
from .compaction_prompts import CONTINUATION_TEMPLATE
from .config import CompactionMemoryConfig
from .interfaces import ConversationLogStore
from .session_state import CompactionSessionState, SessionState
from .stores.local_conversation_log import LocalConversationLogStore

logger = logging.getLogger("CompactionMemory")


class CompactionMemory(CompactionBase):
    """
    Memory implementation using full-context compaction with session persistence.

    Extends CompactionBase with an append-only conversation log (JSONL) that
    allows sessions to be restored after the process exits.

    Usage::

        # Simple — agent injects client, model_name via set_model()
        agent = ReActAgent(
            client=my_client,
            model_name="gpt-4o",
            memory=CompactionMemory(
                config=CompactionMemoryConfig(safety_ratio=0.8),
            ),
        )

        # Restore a previous session
        memory = CompactionMemory.restore_from_log(
            session_id="...",
            log_base_path="./logs",
        )
    """

    def __init__(
        self,
        *,
        config: Optional[CompactionMemoryConfig] = None,
        compact_fn: Optional[CompactFn] = None,
        on_compact: Optional[Callable[[Dict[str, Any]], None]] = None,
        conversation_log_store: Optional[ConversationLogStore] = None,
        enable_memory_tools: bool = True,
        client: Optional[BaseChatClient] = None,
        model_name: Optional[str] = None,
    ) -> None:
        super().__init__(
            config=config,
            compact_fn=compact_fn,
            on_compact=on_compact,
            enable_memory_tools=enable_memory_tools,
            client=client,
            model_name=model_name,
        )
        self._session_id: str = self.config.session_id or str(uuid.uuid4())
        self._parent_session_id: Optional[str] = None

        if conversation_log_store is not None:
            self._log_store: Optional[ConversationLogStore] = conversation_log_store
        elif self.config.log_base_path is not None:
            self._log_store = LocalConversationLogStore(self.config.log_base_path)
        else:
            self._log_store = None

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def log_store(self) -> Optional[ConversationLogStore]:
        return self._log_store

    # -------------------------------------------------------------------------
    # Conversation log persistence
    # -------------------------------------------------------------------------

    async def add_message(self, message: ChatMessage) -> None:
        """Add message, logging to JSONL before auto-compact can fire.

        The log write must happen before super().add_message() because
        _auto_compact() may trigger compaction (which writes a compaction
        event via _on_compaction_recorded).  Logging the message first
        ensures restore_from_log() replays entries in the correct order.
        """
        if self._log_store is not None:
            self._write_log_entry(
                {
                    "type": "message",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "message": message.model_dump(exclude_none=True),
                }
            )
        await super().add_message(message)

    def _on_compaction_recorded(self, event: Dict[str, Any], summary: str) -> None:
        """Persist compaction record to the conversation log."""
        self._write_log_entry(
            {
                "type": "compaction",
                "ts": event["timestamp"],
                "compaction_number": event["compaction_number"],
                "messages_compacted": event["messages_compacted"],
                "summary": summary,
            }
        )

    def _write_log_entry(self, entry: dict) -> None:
        if self._log_store is None:
            return
        # Write session meta on the first entry if the session is new.
        # Uses the log store as source of truth — no internal flag needed.
        if not self._log_store.exists(self._session_id):
            self._write_session_meta()
        self._log_store.append(self._session_id, entry)

    def _write_session_meta(self) -> None:
        meta = {
            "type": "session_meta",
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": self._session_id,
            "system_prompt": self._system_prompt or "",
            "config": {
                "safety_ratio": self.config.safety_ratio,
                "token_threshold": self.config.token_threshold,
                "compact_model_name": self.config.compact_model_name,
                "max_tool_result_tokens": self.config.max_tool_result_tokens,
            },
            "parent_session_id": self._parent_session_id,
        }
        self._log_store.append(self._session_id, meta)

    # -------------------------------------------------------------------------
    # Memory tools
    # -------------------------------------------------------------------------

    def build_tools(self) -> list:
        """Provide log-search tools when a log store is configured."""
        if not self._enable_memory_tools or self._log_store is None:
            return []
        return [self._tool_search_conversation_log, self._tool_read_compaction_summary]

    async def _tool_search_conversation_log(
        self, query: str, max_results: int = 10
    ) -> str:
        """Search the conversation log for messages matching a query.

        Performs case-insensitive substring matching on message content.
        Only use this tool when the current conversation is a continuation
        of a previous session (i.e., context compaction has occurred and
        earlier messages are no longer in the active context). This lets
        you recover specific details — error messages, file paths, code
        snippets — that the compaction summary may have omitted.

        Args:
            query: The search term to look for in message content.
            max_results: Maximum number of matching messages to return.
        """
        results = self._log_store.search_messages(self._session_id, query, max_results)
        return json.dumps(
            {"status": "ok", "query": query, "count": len(results), "results": results}
        )

    async def _tool_read_compaction_summary(self, compaction_number: int = -1) -> str:
        """Read a compaction summary by number.

        Only use this tool when context compaction has occurred and you
        need to review the full summary from a previous compaction event.
        Use -1 for the most recent summary, 1 for the first, etc.

        Args:
            compaction_number: Which compaction summary to read.
                              -1 = latest, 1 = first, 2 = second, etc.
        """
        if not self._compaction_summaries:
            return json.dumps(
                {
                    "status": "no_summaries",
                    "message": "No compactions have occurred yet.",
                }
            )
        if compaction_number == -1:
            record = self._compaction_summaries[-1]
        else:
            idx = compaction_number - 1
            if idx < 0 or idx >= len(self._compaction_summaries):
                return json.dumps(
                    {
                        "status": "not_found",
                        "message": f"Compaction #{compaction_number} not found. "
                        f"Available: 1-{len(self._compaction_summaries)}.",
                    }
                )
            record = self._compaction_summaries[idx]
        return json.dumps(
            {
                "status": "ok",
                "compaction_number": record["compaction_number"],
                "messages_compacted": record["messages_compacted"],
                "summary": record["summary"],
            }
        )

    # -------------------------------------------------------------------------
    # Fork
    # -------------------------------------------------------------------------

    def fork(self) -> "CompactionMemory":
        """Create an independent copy with a new session log."""
        clone = super().fork()
        clone._parent_session_id = self._session_id
        clone._session_id = str(uuid.uuid4())
        return clone

    # -------------------------------------------------------------------------
    # Session state
    # -------------------------------------------------------------------------

    def get_session_state(self) -> CompactionSessionState:
        """Capture current session state."""
        log_base_path: Optional[str] = None
        if self._log_store is not None:
            base = getattr(self._log_store, "_path", None)
            if base is not None:
                log_base_path = str(base)
        return CompactionSessionState(
            messages=self._messages.copy(),
            system_prompt=self._system_prompt,
            session_id=self._session_id,
            log_base_path=log_base_path,
            compaction_count=self._compaction_count,
        )

    @classmethod
    def restore(
        cls,
        state: "SessionState",
        *,
        compact_fn: Optional[CompactFn] = None,
        on_compact: Optional[Callable[[Dict[str, Any]], None]] = None,
        client: Optional[BaseChatClient] = None,
        model_name: Optional[str] = None,
        config: Optional[CompactionMemoryConfig] = None,
    ) -> "CompactionMemory":
        """Restore from a CompactionSessionState snapshot.

        Loads state.messages directly — no log replay.  The restored instance
        reconnects to the same session log if log_base_path is set, so future
        messages continue the existing log.  Session meta is not re-written
        because the log store's exists() check detects the existing session.

        Args:
            state: Must be a CompactionSessionState instance.
            compact_fn: Optional custom compaction function.
            on_compact: Optional compaction callback.
            client: LLM client for future compaction calls.
            model_name: Model name for token estimation.
            config: Override config; if omitted, built from state fields.
        """
        if not isinstance(state, CompactionSessionState):
            raise TypeError(
                f"Expected CompactionSessionState, got {type(state).__name__}"
            )

        resolved_config = dataclasses.replace(
            config or CompactionMemoryConfig(),
            session_id=state.session_id,
            log_base_path=state.log_base_path,
        )

        memory = cls(
            config=resolved_config,
            compact_fn=compact_fn,
            on_compact=on_compact,
            client=client,
            model_name=model_name,
        )
        memory._system_prompt = state.system_prompt
        memory._messages = list(state.messages)
        memory._compaction_count = state.compaction_count
        return memory

    # -------------------------------------------------------------------------
    # Session restore
    # -------------------------------------------------------------------------

    @classmethod
    def restore_from_log(
        cls,
        session_id: str,
        *,
        conversation_log_store: Optional[ConversationLogStore] = None,
        log_base_path: Optional[str] = None,
        client: Optional[BaseChatClient] = None,
        model_name: Optional[str] = None,
        compact_fn: Optional[CompactFn] = None,
        on_compact: Optional[Callable[[Dict[str, Any]], None]] = None,
        system_prompt: Optional[str] = None,
        config: Optional[CompactionMemoryConfig] = None,
    ) -> "CompactionMemory":
        """Restore a CompactionMemory instance from a saved session log.

        Reads all entries from the log store and replays them to rebuild
        in-memory state (messages, compaction count, summaries).
        The restored instance continues appending to the same session log.

        Args:
            session_id: The session to restore.
            conversation_log_store: The log store backend.
                If not provided, created from log_base_path or config.log_base_path.
            log_base_path: Directory for LocalConversationLogStore.
            client: Optional client for future compaction calls.
            model_name: Optional model name for token estimation.
            compact_fn: Optional custom compaction function.
            on_compact: Optional compaction callback.
            system_prompt: Override system prompt (default: read from session_meta).
            config: Override config (default: read from session_meta).

        Returns:
            A fully reconstructed CompactionMemory ready to continue the session.

        Raises:
            ValueError: If session_id not found in the log store.
        """
        if conversation_log_store is None:
            resolved_path = log_base_path or (config.log_base_path if config else None)
            conversation_log_store = (
                LocalConversationLogStore(resolved_path)
                if resolved_path
                else LocalConversationLogStore()
            )

        entries = conversation_log_store.read_entries(session_id)
        if not entries:
            raise ValueError(f"No log entries found for session '{session_id}'")

        meta = next((e for e in entries if e.get("type") == "session_meta"), None)
        if meta is None:
            logger.warning(
                f"No session_meta for session '{session_id}', "
                "using default config and empty system prompt."
            )

        if config is None and meta and "config" in meta:
            mc = meta["config"]
            config = CompactionMemoryConfig(
                safety_ratio=mc.get("safety_ratio", 0.75),
                token_threshold=mc.get("token_threshold"),
                compact_model_name=mc.get("compact_model_name"),
                max_tool_result_tokens=mc.get("max_tool_result_tokens", 50000),
            )
        # Ensure session_id is on the config so __init__ uses it directly
        # and the log_store.exists() check finds the existing session.
        config = dataclasses.replace(
            config or CompactionMemoryConfig(), session_id=session_id
        )

        resolved_system_prompt = system_prompt or (
            meta.get("system_prompt", "") if meta else ""
        )

        memory = cls(
            config=config,
            compact_fn=compact_fn,
            on_compact=on_compact,
            conversation_log_store=conversation_log_store,
            client=client,
            model_name=model_name,
        )
        memory.set_system_prompt(resolved_system_prompt)

        for entry in entries:
            entry_type = entry.get("type")
            if entry_type == "message":
                msg = ChatMessage(**entry["message"])
                memory._messages.append(msg)
            elif entry_type == "compaction":
                summary = entry.get("summary", "")
                continuation = CONTINUATION_TEMPLATE.format(summary=summary)
                memory._messages = [ChatMessage.user_message(continuation)]
                memory._compaction_count += 1
                memory._compaction_summaries.append(
                    {
                        "compaction_number": entry.get(
                            "compaction_number", memory._compaction_count
                        ),
                        "messages_compacted": entry.get("messages_compacted", 0),
                        "summary": summary,
                    }
                )

        return memory
