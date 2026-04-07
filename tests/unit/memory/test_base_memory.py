"""
Unit tests for BaseMemory abstract interface.

Tests cover:
- BaseMemory cannot be instantiated directly
- BasicMemory is a valid BaseMemory subclass
- CompactionMemory is a valid BaseMemory subclass
"""

import unittest

from motus.memory.base_memory import BaseMemory
from motus.memory.basic_memory import BasicMemory
from motus.memory.compaction_memory import CompactionMemory


class TestBaseMemoryAbstract(unittest.TestCase):
    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            BaseMemory()

    def test_basic_memory_is_base_memory(self):
        mem = BasicMemory()
        self.assertIsInstance(mem, BaseMemory)

    def test_compaction_memory_is_base_memory(self):
        mem = CompactionMemory(
            model_name="gpt-4",
            compact_fn=lambda msgs, sp: "summary",
        )
        self.assertIsInstance(mem, BaseMemory)

    def test_basic_memory_has_no_set_model(self):
        """BasicMemory doesn't need set_model — model_name is optional at init."""
        mem = BasicMemory()
        self.assertFalse(hasattr(mem, "set_model"))
