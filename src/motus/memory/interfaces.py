"""
Abstract base classes for memory storage backends.

Defines the interfaces that storage implementations must follow:
- ConversationLogStore: Append-only conversation log interface
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ConversationLogStore(ABC):
    """
    Abstract base class for conversation log storage backends.

    Manages append-only logs for CompactionMemory sessions.
    Each session is identified by a unique session_id string.
    Implementations can use local files, S3, DynamoDB, etc.
    """

    @abstractmethod
    def append(self, session_id: str, entry: Dict[str, Any]) -> None:
        """Append a single log entry to the session log.

        Args:
            session_id: Unique session identifier.
            entry: JSON-serializable dict to append.
        """
        ...

    @abstractmethod
    def read_entries(self, session_id: str) -> List[Dict[str, Any]]:
        """Read all log entries for a session, in chronological order.

        Args:
            session_id: Unique session identifier.

        Returns:
            List of log entry dicts. Empty list if session not found.
        """
        ...

    @abstractmethod
    def search_messages(
        self, session_id: str, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search message entries by case-insensitive substring match on content.

        Args:
            session_id: Unique session identifier.
            query: Substring to search for in message content.
            max_results: Maximum number of results to return.

        Returns:
            List of matching message dicts with keys: role, content, ts.
        """
        ...

    @abstractmethod
    def exists(self, session_id: str) -> bool:
        """Check whether a log exists for the given session_id."""
        ...

    @abstractmethod
    def list_sessions(self) -> List[str]:
        """List all known session_ids."""
        ...
