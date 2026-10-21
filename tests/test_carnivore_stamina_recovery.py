"""Regressão: predador faminto precisa recuperar energia antes de atacar."""
from agents.agent import Agent
from animals.carnivore import Carnivore
from animals.herbivore import Herbivore
from environment.world import World
from simulation.simulation import Simulation


def test_exhausted_hungry_carnivore_recovers_then_attacks_adjacent_herbivore():
    world = World(width=7, height=7, food_count=0, obstacle_count=0, water_count=0)
    human = Agent(0, 0)
    herbivore = Herbivore(4, 3)
    herbivore.choose_action = lambda world, threats: (0, 0)
    predator = Carnivore(3, 3)
    predator.needs.hunger = 80.0
    predator.needs.energy = 0.0
    simulation = Simulation(world, agents=[human], herbivores=[herbivore],
                            carnivores=[predator], seed_spawn_count=0)
    starting_health = herbivore.health
    activities = []
    for _ in range(6):
        simulation.step()
        activities.append(predator.last_activity)
    assert activities[:4] == ["RESTING"] * 4
    assert herbivore.health < starting_health
    assert simulation.carnivore_attacks >= 1
    assert predator.alive
    assert any(r["attack_attempted"] for r in simulation.carnivore_hunt_history)


def test_thirst_priority_is_preserved_when_carnivore_is_exhausted():
    world = World(width=7, height=7, food_count=0, obstacle_count=0, water_count=0)
    predator = Carnivore(3, 3)
    predator.needs.hunger = 80.0
    predator.needs.thirst = 60.0
    predator.needs.energy = 0.0
    herbivore = Herbivore(4, 3)
    herbivore.choose_action = lambda world, threats: (0, 0)
    simulation = Simulation(world, agents=[Agent(0, 0)], herbivores=[herbivore],
                            carnivores=[predator], seed_spawn_count=0)
    simulation.step()
    assert predator.last_activity != "RESTING"
