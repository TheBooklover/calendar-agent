"""
calendar_agent/planning/plan_result.py

PlanResult is the explainability envelope returned by orchestration.

Core idea:
- The deterministic engine remains the source of truth.
- AI may influence *inputs* (bounded tweaks), but never fabricates a plan.
- We always retain:
  - baseline_blocks (deterministic)
  - final_blocks (either same as baseline or AI-assisted deterministic rerun)
  - diagnostics about whether AI was attempted/used and why/why not

This object should be cheap to construct and easy to assert in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PlanResult:
    """
    Result object for calendar planning.

    Attributes:
        baseline_blocks:
            Deterministic plan produced from the original inputs.
        final_blocks:
            The final plan returned to the caller. If AI is disabled/fails/invalid,
            this should equal baseline_blocks.
        ai_attempted:
            True if the orchestrator attempted to call the AI reasoner.
        ai_used:
            True if a valid AI proposal was applied and a deterministic rerun produced final_blocks.
        ai_error:
            Any exception message from the AI path (LLM call, apply step, etc.).
        ai_validation_errors:
            Validation errors if the AI proposal was rejected by guardrails.
        ai_proposal:
            The raw structured proposal returned by the reasoner (kept for debugging/explainability).
    """
    baseline_blocks: List[Dict[str, Any]]
    final_blocks: List[Dict[str, Any]]

    ai_attempted: bool = False
    ai_used: bool = False

    ai_error: Optional[str] = None
    ai_validation_errors: Optional[List[str]] = None
    ai_proposal: Optional[Any] = None

    @property
    def used_fallback(self) -> bool:
        """True when the deterministic baseline was returned as the final plan."""
        return not self.ai_used

    @property
    def is_ai_assisted(self) -> bool:
        """Alias for readability in callers."""
        return self.ai_used

    @classmethod
    def from_baseline_and_final(
        cls,
        *,
        baseline_blocks: List[Dict[str, Any]],
        final_blocks: List[Dict[str, Any]],
        ai_attempted: bool,
        ai_used: bool,
        ai_error: Optional[str],
        ai_validation_errors: Optional[List[str]],
        ai_proposal: Optional[Any],
    ) -> "PlanResult":
        """
        Explicit constructor to keep orchestrator stable even if __init__ evolves.
        """
        return cls(
            baseline_blocks=baseline_blocks,
            final_blocks=final_blocks,
            ai_attempted=ai_attempted,
            ai_used=ai_used,
            ai_error=ai_error,
            ai_validation_errors=ai_validation_errors,
            ai_proposal=ai_proposal,
        )
