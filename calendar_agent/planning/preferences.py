"""
Planning preferences (soft constraints).

V0.7 scope:
- Support priority ordering first (simple, explainable, testable).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class PlanningPreferences:
    """
    Soft constraints shaping scheduling behavior.

    priority_order:
    - If set, it reorders goals before scheduling.
    - Any goals not mentioned will follow in their original order.
    """
    priority_order: Optional[List[str]] = None
