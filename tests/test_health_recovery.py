"""Contratos da recuperação de saúde usados pelas três espécies."""
import pytest

from agents.needs import AgentNeeds
from simulation.health_recovery import recover_health_during_rest


@pytest.mark.parametrize("activity", ["RESTING", "SLEEPING"])
def test_resting_healthy_needs_recover_health_and_report_effective_amount(activity):
    needs = AgentNeeds(max_health=100.0, health=60.0, hunger=20.0, thirst=20.0)
    healed, reason = recover_health_during_rest(needs, activity, 2.5)
    assert healed == pytest.approx(2.5)
    assert needs.health == pytest.approx(62.5)
    assert reason == "RECOVERED"


def test_recovery_is_capped_at_max_health():
    needs = AgentNeeds(max_health=100.0, health=99.0, hunger=20.0, thirst=20.0)
    healed, reason = recover_health_during_rest(needs, "RESTING", 5.0)
    assert healed == pytest.approx(1.0)
    assert needs.health == 100.0
    assert reason == "RECOVERED"


@pytest.mark.parametrize(
    ("activity", "hunger", "thirst", "damage_causes", "expected_reason"),
    [
        ("WALKING", 20.0, 20.0, (), "NOT_RESTING"),
        ("RESTING", 20.0, 20.0, ("DEFENSE",), "DAMAGE_THIS_STEP"),
        ("RESTING", 70.0, 20.0, (), "CRITICAL_NEED"),
        ("RESTING", 20.0, 70.0, (), "CRITICAL_NEED"),
        ("SLEEPING", 20.0, 20.0, (), "HEALTH_FULL"),
    ],
)
def test_recovery_block_reason_is_explicit(activity, hunger, thirst, damage_causes, expected_reason):
    needs = AgentNeeds(max_health=100.0, health=100.0 if expected_reason == "HEALTH_FULL" else 50.0,
                       hunger=hunger, thirst=thirst)
    needs.last_damage_causes = damage_causes
    healed, reason = recover_health_during_rest(needs, activity, 1.0)
    assert healed == 0.0
    assert reason == expected_reason


def test_damage_is_reported_even_when_agent_is_not_resting():
    needs = AgentNeeds(max_health=100.0, health=50.0, hunger=20.0, thirst=20.0)
    needs.last_damage_causes = ("DEFENSE",)
    healed, reason = recover_health_during_rest(needs, "WALKING", 1.0)
    assert healed == 0.0
    assert reason == "DAMAGE_THIS_STEP"


def test_critical_need_has_priority_over_non_resting_activity():
    needs = AgentNeeds(max_health=100.0, health=50.0, hunger=75.0, thirst=20.0)
    healed, reason = recover_health_during_rest(needs, "WALKING", 1.0)
    assert healed == 0.0
    assert reason == "CRITICAL_NEED"
