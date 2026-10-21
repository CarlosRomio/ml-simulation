"""Testes de caracterização dos mecanismos atuais de busca por água.

Estes testes registram diferenças existentes entre espécies; não definem que
as políticas devam ser iguais. A intenção é criar uma linha de base antes de
extrair serviços compartilhados.
"""
from types import SimpleNamespace
import random

from agents.agent import Agent
from agents.navigation.bfs import find_path
from animals.carnivore import Carnivore
from animals.herbivore import Herbivore
from environment.resources import Water
from environment.world import World


def empty_world(width=9, height=7):
    return World(width=width, height=height, food_count=0, obstacle_count=0,
                 water_count=0, rng=random.Random(101))


def human_water_candidates(agent, world):
    """Executa o seletor cognitivo e captura candidatos sem forçar a decisão."""
    captured = {}

    def evaluate_all(candidates, *args, **kwargs):
        captured["candidates"] = list(candidates)
        return []

    def choose(candidates, *args, **kwargs):
        candidates = list(candidates)
        captured["candidates"] = candidates
        # WAIT evita que a decisão escolhida altere o alvo durante a medição.
        selected = next((item for item in candidates if item.action_id == "WAIT"), candidates[0])
        return SimpleNamespace(candidate=selected)

    agent.decision_engine.evaluate_all = evaluate_all
    agent.decision_engine.choose = choose
    agent.decision_engine.trace = lambda chosen, evaluated: {"action_id": chosen.candidate.action_id}
    agent._select_needs_or_exploration_target(world, find_path, (agent.x, agent.y))
    return {candidate.action_id: candidate for candidate in captured["candidates"]}


def test_human_water_candidate_is_eligible_from_thirst_12():
    world = empty_world()
    world.get_cell(4, 1).resource = Water()
    agent = Agent(1, 1, vision_radius=6, rng=random.Random(1))

    agent.needs.thirst = 11.99
    assert "SEEK_WATER" not in human_water_candidates(agent, world)

    agent.needs.thirst = 12.0
    candidates = human_water_candidates(agent, world)
    assert "SEEK_WATER" in candidates
    assert candidates["SEEK_WATER"].target == (4, 1)


def test_human_water_candidate_uses_path_distance_and_records_goal_continuity():
    world = empty_world()
    world.get_cell(5, 1).resource = Water()
    agent = Agent(1, 1, vision_radius=6, rng=random.Random(2))
    agent.needs.thirst = 60
    agent.target = (5, 1)
    agent.target_intent = "SEEK_WATER"

    candidate = human_water_candidates(agent, world)["SEEK_WATER"]

    assert candidate.target == (5, 1)
    assert candidate.metadata["distance"] == len(candidate.metadata["path"]) - 1
    assert candidate.continues_current_goal is True


def test_herbivore_water_search_threshold_is_45_and_selects_nearest_source():
    world = empty_world()
    world.get_cell(2, 1).resource = Water()
    world.get_cell(6, 1).resource = Water()
    herbivore = Herbivore(1, 1, vision_radius=6, rng=random.Random(3))

    herbivore.needs.thirst = 44.99
    herbivore.choose_action(world, [])
    assert herbivore.target is None

    herbivore.needs.thirst = 45.0
    herbivore.choose_action(world, [])
    assert herbivore.target == (2, 1)
    assert herbivore.path[-1] == (2, 1)


def test_herbivore_switches_water_target_when_nearest_source_becomes_occupied():
    world = empty_world()
    near_water = (2, 1)
    far_water = (6, 1)
    world.get_cell(*near_water).resource = Water()
    world.get_cell(*far_water).resource = Water()
    herbivore = Herbivore(1, 1, vision_radius=6, rng=random.Random(4))
    herbivore.needs.thirst = 70

    herbivore.choose_action(world, [])
    assert herbivore.target == near_water

    herbivore.choose_action(
        world, [], occupied_positions={near_water},
        occupied_animal_positions={near_water},
    )
    assert herbivore.target == far_water
    assert herbivore.last_navigation_block_reason == "ANIMAL"


def test_carnivore_at_thirst_50_prioritizes_water_over_nearby_prey():
    world = empty_world()
    water = (6, 1)
    world.get_cell(*water).resource = Water()
    carnivore = Carnivore(1, 1, vision_radius=6, rng=random.Random(5))
    carnivore.needs.thirst = 50
    carnivore.needs.hunger = 70

    action = carnivore.choose_action(world, [(2, 1)])

    assert carnivore.target == water
    assert carnivore.path[-1] == water
    assert action != (0, 0)


def test_carnivore_below_thirst_50_can_prioritize_prey_before_water_fallback():
    world = empty_world()
    world.get_cell(6, 1).resource = Water()
    carnivore = Carnivore(1, 1, vision_radius=6, rng=random.Random(6))
    carnivore.needs.thirst = 49
    carnivore.needs.hunger = 70

    carnivore.choose_action(world, [(3, 1)])

    assert carnivore.target == (3, 1)


def test_carnivore_uses_water_fallback_from_thirst_35_when_no_prey_is_available():
    world = empty_world()
    water = (5, 1)
    world.get_cell(*water).resource = Water()
    carnivore = Carnivore(1, 1, vision_radius=6, rng=random.Random(7))
    carnivore.needs.thirst = 35
    carnivore.needs.hunger = 30

    carnivore.choose_action(world, [])

    assert carnivore.target == water


def test_perception_and_world_nearby_queries_use_different_geometries():
    from agents.perception import Perception

    world = empty_world(width=9, height=9)
    perception_cells = {
        (cell.x, cell.y)
        for cell in Perception().observe(world, 4, 4, radius=2)
    }
    nearby_cells = {
        (cell.x, cell.y)
        for cell in world.get_nearby_cells(4, 4, radius=2)
    }

    assert (6, 4) in perception_cells
    assert (6, 6) not in perception_cells  # fora do círculo de raio 2
    assert (6, 6) in nearby_cells           # dentro da janela quadrada 5x5


def test_human_keeps_water_target_until_periodic_reassessment():
    world = empty_world()
    water = (5, 1)
    world.get_cell(*water).resource = Water()
    agent = Agent(1, 1, vision_radius=6, rng=random.Random(8))
    agent.needs.thirst = 70
    agent.target = water
    agent.target_intent = "SEEK_WATER"
    agent.path = find_path(world, (1, 1), water) or []

    for _ in range(4):
        agent.choose_action([], world)
        assert agent.target == water
        assert agent.target_intent == "SEEK_WATER"

    # A quinta decisão invalida o alvo para reavaliar as alternativas.
    agent.choose_action([], world)
    assert agent._decision_tick == 5
    assert agent.last_decision_trace is not None
