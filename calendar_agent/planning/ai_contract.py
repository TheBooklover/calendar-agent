"""
AI Planning Contract (V0.7)

This defines what the AI is allowed to suggest.

Design rules:
- AI outputs are untrusted.
- AI may suggest ONLY soft preferences (e.g., goal ordering).
- AI must provide a rationale and confidence.
- Deterministic scheduling engine remains source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class AIPlanningProposal:
    """
    Structured AI output (untrusted until validated).

    priority_order:
    - Optional ordered list of goal labels.
    - Labels must exist in the user's goal list.

    rationale:
    - Required human-readable explanation of why the AI suggested this.

    confidence:
    - Float in [0.0, 1.0]
    """
    priority_order: Optional[List[str]]
    rationale: str
    confidence: float
