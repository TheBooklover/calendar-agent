from __future__ import annotations

from typing import Any, Dict, List


def test_plan_result_defaults() -> None:
    from calendar_agent.planning.plan_result import PlanResult

    r = PlanResult(baseline_blocks=[], final_blocks=[])
    assert r.ai_attempted is False
    assert r.ai_used is False
    assert r.used_fallback is True
    assert r.is_ai_assisted is False


def test_orchestrator_returns_plan_result_when_ai_disabled() -> None:
    from calendar_agent.planning.orchestrator import plan_with_optional_ai
    from calendar_agent.planning.plan_result import PlanResult

    def fake_planner(**kwargs: Any) -> List[Dict[str, Any]]:
        return [{"label": "Email", "minutes": 20}]

    result = plan_with_optional_ai(
        free=[],
        goals=[("Email", 20)],
        buffer_minutes=5,
        enable_ai=False,
        ai_reasoner=None,
        deterministic_planner=fake_planner,
    )

    assert isinstance(result, PlanResult)
    assert result.baseline_blocks == result.final_blocks
    assert result.ai_attempted is False
    assert result.ai_used is False
