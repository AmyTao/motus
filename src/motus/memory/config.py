"""Memory system configuration."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CompactionMemoryConfig:
    """Configuration for CompactionMemory and CompactionBase."""

    safety_ratio: float = 0.75  # Compact when over 75% of context limit
    token_threshold: Optional[int] = None  # Explicit threshold (overrides safety_ratio)
    compact_model_name: Optional[str] = (
        None  # Model for compaction (defaults to agent model)
    )
    max_tool_result_tokens: int = 50000  # Max tokens per tool result (0 = no limit)
    tool_result_truncation_suffix: str = "\n\n... [content truncated due to length]"

    # Session identity
    session_id: Optional[str] = None  # Auto-UUID if not provided

    # Conversation log persistence
    # Custom path for JSONL log files. None = use LocalConversationLogStore default.
    log_base_path: Optional[str] = None
