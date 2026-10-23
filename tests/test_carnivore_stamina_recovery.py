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
    assert activities[0] == "RESTING"
    # A reserva baixa recebe recuperação adaptativa; o predador pode atacar
    # assim que tiver estamina suficiente, sem esperar quatro passos fixos.
    assert any(activity != "RESTING" for activity in activities[1:])
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

def test_tired_carnivore_does_not_fall_asleep_again_when_prey_is_visible():
    world = World(
        width=12,
        height=12,
        food_count=0,
        obstacle_count=0,
        water_count=0,
    )

    prey = Herbivore(7, 3)
    predator = Carnivore(3, 3, vision_radius=5)

    predator.needs.hunger = 40.0
    predator.needs.fatigue = 80.0
    predator.is_sleeping = True

    simulation = Simulation(
        world,
        agents=[Agent(0, 0)],
        herbivores=[prey],
        carnivores=[predator],
        seed_spawn_count=0,
    )

    assert simulation._sleep_wake_reason(predator) == "PREY_NEARBY"

    simulation.step()

    assert not predator.is_sleeping
    assert predator.last_activity != "SLEEPING"

def test_carnivore_sleep_recovers_fatigue_at_species_specific_rate():
    from agents.needs import AgentNeeds

    world = World(width=12, height=12, food_count=0, obstacle_count=0, water_count=0)
    predator = Carnivore(
        8,
        8,
        needs=AgentNeeds(fatigue=70.0, hunger=10.0, thirst=10.0, energy=40.0),
    )
    predator.is_sleeping = True
    simulation = Simulation(
        world,
        agents=[Agent(0, 0)],
        carnivores=[predator],
        seed_spawn_count=0,
    )

    simulation.step()

    record = [
        row for row in simulation.physiology_activity_history
        if row["individual_type"] == "CARNIVORE"
    ][-1]
    assert predator.last_activity == "SLEEPING"
    assert abs(record["fatigue_delta"] - (-0.45)) < 1e-9
    assert abs(predator.needs.fatigue - 69.55) < 1e-9


def test_carnivore_attacks_persistent_prey_when_multiple_prey_are_adjacent():
    world = World(width=8, height=8, food_count=0, obstacle_count=0, water_count=0)
    human = Agent(0, 0)
    first_prey = Herbivore(4, 3)
    second_prey = Herbivore(3, 4)
    first_prey.choose_action = lambda world, threats: (0, 0)
    second_prey.choose_action = lambda world, threats: (0, 0)
    predator = Carnivore(3, 3)
    predator.needs.hunger = 80.0
    predator.hunt_target_object_id = id(second_prey)
    simulation = Simulation(
        world, agents=[human], herbivores=[first_prey, second_prey],
        carnivores=[predator], seed_spawn_count=0,
    )

    simulation.step()

    record = simulation.carnivore_hunt_history[-1]
    assert record["attack_attempted"] is True
    assert record["attack_target_id"] == simulation._herbivore_ids[id(second_prey)]
