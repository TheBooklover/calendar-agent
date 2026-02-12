"""
calendar_agent/planning/orchestrator.py

Orchestration layer for planning:
- ALWAYS produces a deterministic baseline plan first.
- Optionally asks an AI reasoner for a *proposal* (never a final plan).
- Validates AI proposal with guardrails.
- Applies proposal in a bounded, explainable way.
- Falls back to deterministic baseline on *any* failure.

Design goals:
- Deterministic source-of-truth
- Testable (pure functions where possible)
- Explainable (keep baseline vs final, store proposal + errors)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# -----------------------------
# Light types (duck-typed)
# -----------------------------

Intervals = Sequence[Any]
Goals = Sequence[Tuple[str, int]]  # (label, minutes), matches propose_blocks signature
Blocks = List[Dict[str, Any]]      # propose_blocks returns List[Dict[str, Any]]


# -----------------------------
# Diagnostics for explainability
# -----------------------------

@dataclass(frozen=True)
class _OrchestratorDiagnostics:
    """Debug payload to keep orchestration explainable and test-friendly."""
    ai_attempted: bool
    ai_used: bool
    ai_error: Optional[str]
    ai_validation_errors: Optional[List[str]]
    ai_proposal: Optional[Any]


# -----------------------------
# Public API
# -----------------------------

def plan_with_optional_ai(
    *,
    free: Intervals,
    goals: Goals,
    buffer_minutes: int,
    min_block_minutes_by_label: Optional[Dict[str, int]] = None,
    preferences: Optional[Any] = None,
    enable_ai: bool = True,
    ai_reasoner: Optional[Any] = None,
    # Dependency injection for testability
    deterministic_planner: Optional[Callable[..., Blocks]] = None,
) -> Any:
    """
    Main entry point.

    Behavior:
    1) Compute deterministic baseline plan.
    2) If AI disabled or no reasoner, return baseline PlanResult.
    3) Otherwise, attempt AI-assisted plan (guardrailed).
       - Any exception => return baseline PlanResult.

    Returns:
        Your project's PlanResult object (constructed via adapter).
    """
    # Late import / default wiring to reduce coupling
    if deterministic_planner is None:
        deterministic_planner = _default_deterministic_planner()

    baseline_blocks = deterministic_planner(
        free=list(free),
        goals=list(goals),
        buffer_minutes=buffer_minutes,
        min_block_minutes_by_label=min_block_minutes_by_label,
    )

    if (not enable_ai) or (ai_reasoner is None):
        diagnostics = _OrchestratorDiagnostics(
            ai_attempted=False,
            ai_used=False,
            ai_error=None,
            ai_validation_errors=None,
            ai_proposal=None,
        )
        return _build_plan_result(
            baseline_blocks=baseline_blocks,
            final_blocks=baseline_blocks,
            diagnostics=diagnostics,
        )

    return plan_with_ai_reasoner(
        free=free,
        goals=goals,
        buffer_minutes=buffer_minutes,
        min_block_minutes_by_label=min_block_minutes_by_label,
        preferences=preferences,
        ai_reasoner=ai_reasoner,
        deterministic_planner=deterministic_planner,
        baseline_blocks=baseline_blocks,
    )


def plan_with_ai_reasoner(
    *,
    free: Intervals,
    goals: Goals,
    buffer_minutes: int,
    min_block_minutes_by_label: Optional[Dict[str, int]] = None,
    preferences: Optional[Any],
    ai_reasoner: Any,
    deterministic_planner: Callable[..., Blocks],
    baseline_blocks: Optional[Blocks] = None,
) -> Any:
    """
    AI-assisted planning.

    Rules:
    - Baseline exists and is always the fallback.
    - AI only proposes bounded input tweaks; we re-run deterministic engine.
    - Proposal must pass validation guardrails.
    - Any error => baseline result.
    """
    if baseline_blocks is None:
        baseline_blocks = deterministic_planner(
            free=list(free),
            goals=list(goals),
            buffer_minutes=buffer_minutes,
            min_block_minutes_by_label=min_block_minutes_by_label,
        )

    try:
        proposal = _call_ai_reasoner(
            ai_reasoner=ai_reasoner,
            free=free,
            goals=goals,
            buffer_minutes=buffer_minutes,
            min_block_minutes_by_label=min_block_minutes_by_label,
            preferences=preferences,
            baseline_blocks=baseline_blocks,
        )

        validation_errors = _validate_proposal(proposal, goal_labels=[label for (label, _mins) in goals])
        if validation_errors:
            diagnostics = _OrchestratorDiagnostics(
                ai_attempted=True,
                ai_used=False,
                ai_error=None,
                ai_validation_errors=validation_errors,
                ai_proposal=proposal,
            )
            return _build_plan_result(
                baseline_blocks=baseline_blocks,
                final_blocks=baseline_blocks,
                diagnostics=diagnostics,
            )

        tweaked_inputs = _apply_proposal_bounded(
            proposal=proposal,
            free=free,
            goals=goals,
            buffer_minutes=buffer_minutes,
            min_block_minutes_by_label=min_block_minutes_by_label,
            preferences=preferences,
        )

        final_blocks = deterministic_planner(
            free=list(tweaked_inputs.free),
            goals=list(tweaked_inputs.goals),
            buffer_minutes=tweaked_inputs.buffer_minutes,
            min_block_minutes_by_label=tweaked_inputs.min_block_minutes_by_label,
        )

        diagnostics = _OrchestratorDiagnostics(
            ai_attempted=True,
            ai_used=True,
            ai_error=None,
            ai_validation_errors=None,
            ai_proposal=proposal,
        )
        return _build_plan_result(
            baseline_blocks=baseline_blocks,
            final_blocks=final_blocks,
            diagnostics=diagnostics,
        )

    except Exception as e:
        diagnostics = _OrchestratorDiagnostics(
            ai_attempted=True,
            ai_used=False,
            ai_error=f"{type(e).__name__}: {e}",
            ai_validation_errors=None,
            ai_proposal=None,
        )
        return _build_plan_result(
            baseline_blocks=baseline_blocks,
            final_blocks=baseline_blocks,
            diagnostics=diagnostics,
        )


# -----------------------------
# Proposal application (bounded)
# -----------------------------

@dataclass(frozen=True)
class _TweakedInputs:
    """What we allow the AI to influence (bounded, deterministic)."""
    free: Intervals
    goals: Goals
    buffer_minutes: int
    min_block_minutes_by_label: Optional[Dict[str, int]]


def _apply_proposal_bounded(
    *,
    proposal: Any,
    free: Intervals,
    goals: Goals,
    buffer_minutes: int,
    min_block_minutes_by_label: Optional[Dict[str, int]],
    preferences: Optional[Any],
) -> _TweakedInputs:
    """
    Apply an AIPlanningProposal in a bounded way.

    Allowed (safe surface area):
    - Re-order goal priority by label: proposal.goal_order = [label1, label2, ...]
    - Adjust buffer: proposal.buffer_minutes or proposal.buffer_minutes_delta
    - Adjust per-label minimums: proposal.min_block_minutes_by_label (clamped)

    Everything else is ignored by design.
    """
    new_goals = list(goals)
    new_buffer = int(buffer_minutes)
    new_min_by_label = dict(min_block_minutes_by_label or {})

    # Goal ordering
    goal_order = getattr(proposal, "goal_order", None)
    if goal_order:
        minutes_by_label = {label: mins for (label, mins) in new_goals}
        ordered = [(label, minutes_by_label[label]) for label in goal_order if label in minutes_by_label]
        remaining = [(label, mins) for (label, mins) in new_goals if label not in set(goal_order)]
        new_goals = ordered + remaining

    # Buffer adjust
    proposed_buffer = getattr(proposal, "buffer_minutes", None)
    proposed_delta = getattr(proposal, "buffer_minutes_delta", None)

    if proposed_buffer is not None:
        new_buffer = int(proposed_buffer)
    elif proposed_delta is not None:
        new_buffer = int(new_buffer + int(proposed_delta))

    # Clamp buffer
    new_buffer = max(0, min(new_buffer, 60))

    # Per-label min block minutes adjust
    proposed_min_map = getattr(proposal, "min_block_minutes_by_label", None)
    if isinstance(proposed_min_map, dict):
        for label, mins in proposed_min_map.items():
            try:
                mins_int = int(mins)
            except Exception:
                continue
            mins_int = max(5, min(mins_int, 240))
            new_min_by_label[str(label)] = mins_int

    return _TweakedInputs(
        free=free,
        goals=new_goals,
        buffer_minutes=new_buffer,
        min_block_minutes_by_label=new_min_by_label if new_min_by_label else None,
    )


# -----------------------------
# Reasoner + validation wiring
# -----------------------------

def _call_ai_reasoner(
    *,
    ai_reasoner: Any,
    free: Intervals,
    goals: Goals,
    buffer_minutes: int,
    min_block_minutes_by_label: Optional[Dict[str, int]],
    preferences: Optional[Any],
    baseline_blocks: Blocks,
) -> Any:
    """
    Calls the AI reasoner using duck-typing:
    - Prefer ai_reasoner.propose(...)
    - Else call ai_reasoner(...)
    """
    if hasattr(ai_reasoner, "propose") and callable(getattr(ai_reasoner, "propose")):
        return ai_reasoner.propose(
            free=list(free),
            goals=list(goals),
            buffer_minutes=buffer_minutes,
            min_block_minutes_by_label=min_block_minutes_by_label,
            preferences=preferences,
            baseline_blocks=baseline_blocks,
        )

    if callable(ai_reasoner):
        return ai_reasoner(
            free=list(free),
            goals=list(goals),
            buffer_minutes=buffer_minutes,
            min_block_minutes_by_label=min_block_minutes_by_label,
            preferences=preferences,
            baseline_blocks=baseline_blocks,
        )

    raise TypeError("ai_reasoner must be callable or expose .propose(...)")


def _normalize_validation_result(raw):
    """Normalize validator outputs into List[str] errors."""
    if raw is None:
        return []
    # Common: already a list of strings
    if isinstance(raw, list):
        # If it's a list of strings, keep non-empty strings
        if all(isinstance(x, str) for x in raw):
            return [x for x in raw if x.strip()]
        # Some validators return [ok_bool, message]
        if len(raw) == 2 and isinstance(raw[0], bool) and isinstance(raw[1], str):
            return [] if raw[0] else ([raw[1]] if raw[1].strip() else ["Invalid AI proposal"])
        # Unknown list shape: treat as invalid
        return ["Invalid AI proposal (unrecognized validator output)"]
    # Tuple: (ok, msg)
    if isinstance(raw, tuple) and len(raw) == 2 and isinstance(raw[0], bool) and isinstance(raw[1], str):
        return [] if raw[0] else ([raw[1]] if raw[1].strip() else ["Invalid AI proposal"])
    # String: single error
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    return ["Invalid AI proposal (unrecognized validator output)"]


def _validate_proposal(proposal: Any, *, goal_labels: List[str]) -> List[str]:
    """
    Validate using your existing guardrails.

    Supported patterns:
    - validate_ai_planning_proposal(proposal) -> List[str]
    - proposal.validate() -> List[str]
    """
    try:
        from calendar_agent.planning.ai_validate import validate_ai_planning_proposal  # type: ignore
        errors = validate_ai_planning_proposal(proposal, goal_labels=list(goal_labels))
        return _normalize_validation_result(errors)
    except Exception:
        pass

    if hasattr(proposal, "validate") and callable(getattr(proposal, "validate")):
        errors = proposal.validate()
        return list(errors or [])

    # Strict posture: no validator means invalid
    return ["No validator available for AI proposal"]


def _default_deterministic_planner() -> Callable[..., Blocks]:
    """Late import to avoid circular imports."""
    from calendar_agent.planner import propose_blocks  # type: ignore
    return propose_blocks


# -----------------------------
# PlanResult adapter
# -----------------------------

def _build_plan_result(
    *,
    baseline_blocks: Blocks,
    final_blocks: Blocks,
    diagnostics: _OrchestratorDiagnostics,
) -> Any:
    """
    Build your project's PlanResult without hard-coding its exact constructor.

    Supported:
    1) PlanResult.from_baseline_and_final(**payload)
    2) PlanResult(**payload)
    """
    from calendar_agent.planning.plan_result import PlanResult  # type: ignore

    payload = {
        "baseline_blocks": baseline_blocks,
        "final_blocks": final_blocks,
        "ai_attempted": diagnostics.ai_attempted,
        "ai_used": diagnostics.ai_used,
        "ai_error": diagnostics.ai_error,
        "ai_validation_errors": diagnostics.ai_validation_errors,
        "ai_proposal": diagnostics.ai_proposal,
    }

    if hasattr(PlanResult, "from_baseline_and_final") and callable(getattr(PlanResult, "from_baseline_and_final")):
        return PlanResult.from_baseline_and_final(**payload)

    return PlanResult(**payload)
