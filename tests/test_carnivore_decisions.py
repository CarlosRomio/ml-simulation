"""Testes unitários das regras puras de retirada de carnívoros."""
from simulation.carnivore_decisions import evaluate_human_threat


def _evaluate(**overrides):
    values = {
        "health": 100.0,
        "max_health": 120.0,
        "hunger": 50.0,
        "risk_aversion": 0.5,
        "aggressiveness": 0.5,
        "persistence": 0.5,
        "nearby_human_count": 2,
        "adjacent_human_count": 1,
        "adjacent_herbivore_count": 0,
    }
    values.update(overrides)
    return evaluate_human_threat(**values)


def test_wounded_carnivore_retreats_from_adjacent_human_even_when_hungry():
    decision = _evaluate(health=20.0, hunger=99.0)
    assert decision.should_retreat
    assert decision.reason == "WOUNDED_NEAR_HUMANS"


def test_outnumbered_carnivore_retreats_when_hunger_is_not_critical():
    decision = _evaluate(health=100.0, hunger=50.0)
    assert decision.should_retreat
    assert decision.reason == "OUTNUMBERED_NEAR_HUMANS"


def test_critical_hunger_and_high_persistence_can_override_group_retreat():
    decision = _evaluate(health=100.0, hunger=99.0, persistence=0.95)
    assert not decision.should_retreat
    assert decision.reason == "NO_RETREAT_CONDITION"


def test_adjacent_herbivore_changes_outnumbered_decision_but_not_wounded_decision():
    healthy = _evaluate(health=100.0, adjacent_herbivore_count=1)
    wounded = _evaluate(health=20.0, adjacent_herbivore_count=1)
    assert not healthy.should_retreat
    assert wounded.should_retreat


def test_retreat_threshold_responds_to_personality_traits():
    cautious = _evaluate(health=45.0, risk_aversion=0.9, aggressiveness=0.1)
    bold = _evaluate(health=45.0, risk_aversion=0.1, aggressiveness=0.9)
    assert cautious.retreat_health_fraction > bold.retreat_health_fraction
