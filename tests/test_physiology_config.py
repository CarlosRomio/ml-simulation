from configuration.simulation_config import SimulationConfig
from experiments.runner import run_single_simulation


def test_physiology_config_reaches_agents_and_metrics():
    config = SimulationConfig(
        width=10,
        height=10,
        food_density=0.0,
        obstacle_density=0.0,
        water_density=0.0,
        agent_count=1,
        thirst_per_step=2.5,
        dehydration_threshold=60.0,
        dehydration_damage_per_step=4.0,
        hunger_per_step=1.5,
        starvation_threshold=70.0,
        starvation_damage_per_step=2.0,
    )
    result = run_single_simulation(config, run_seed=4, max_steps=3, seed_spawn_count=0)
    metrics = result.all_agent_metrics[0]
# Starts at thirst 20; with no water, the configured per-step increase is visible.
    assert abs(metrics.final_thirst - 27.515) < 1e-9
    assert metrics.critical_thirst_steps == 0
    assert abs(metrics.final_hunger - 24.53) < 1e-9


def test_sleeping_recovers_fatigue_and_wakes_for_hunger():
    from agents.agent import Agent
    from agents.needs import AgentNeeds
    from environment.world import World
    from simulation.simulation import Simulation

    world = World(width=10, height=10, food_count=0, obstacle_count=0, water_count=0)
    agent = Agent(4, 4, needs=AgentNeeds(fatigue=70.0, hunger=20.0, thirst=20.0, energy=40.0))
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)
    simulation.step()
    assert agent.last_activity == "SLEEPING"
    assert agent.needs.fatigue < 70.0
    assert agent.energy > 40.0

    agent.needs.hunger = 35.0
    simulation.step()
    assert not agent.is_sleeping
    assert agent.last_sleep_interruption_reason == "HUNGER"
    assert simulation.physiology_activity_history[-1]["sleep_interruption_reason"] == "HUNGER"


def test_running_moves_two_cells_and_consumes_more_stamina_than_walking():
    from agents.agent import Agent
    from environment.world import World
    from simulation.simulation import Simulation

    world = World(width=12, height=12, food_count=0, obstacle_count=0, water_count=0)
    agent = Agent(3, 5)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)
    assert simulation.set_manual_control(agent)
    assert simulation.queue_manual_action(1, 0, run=True)
    simulation.step()
    assert (agent.x, agent.y) == (5, 5)
    assert agent.energy == 92.0
    assert simulation.physiology_activity_history[-1]["activity"] == "RUNNING"


def test_sleep_is_interrupted_by_nearby_predator():
    from agents.agent import Agent
    from agents.needs import AgentNeeds
    from animals.carnivore import Carnivore
    from environment.world import World
    from simulation.simulation import Simulation

    world = World(width=12, height=12, food_count=0, obstacle_count=0, water_count=0)
    agent = Agent(4, 4, needs=AgentNeeds(fatigue=80.0))
    carnivore = Carnivore(7, 4)
    simulation = Simulation(world, agent=agent, carnivores=[carnivore], seed_spawn_count=0)
    agent.is_sleeping = True
    simulation.step()
    assert not agent.is_sleeping
    assert simulation.physiology_activity_history[0]["sleep_interruption_reason"] == "PREDATOR_NEARBY"


def test_herbivore_can_sprint_two_cells_when_fleeing_and_has_stamina():
    from agents.agent import Agent
    from animals.herbivore import Herbivore
    from animals.carnivore import Carnivore
    from environment.world import World
    from simulation.simulation import Simulation

    world = World(width=12, height=12, food_count=0, obstacle_count=0, water_count=0)
    human = Agent(0, 0)
    herbivore = Herbivore(5, 5)
    carnivore = Carnivore(6, 5)
    simulation = Simulation(world, agents=[human], herbivores=[herbivore], carnivores=[carnivore], seed_spawn_count=0)
    before = (herbivore.x, herbivore.y)
    simulation.step()
    distance = abs(herbivore.x - before[0]) + abs(herbivore.y - before[1])
    assert herbivore.last_activity == "RUNNING"
    assert distance == 2
    assert herbivore.needs.energy == 52.0


def test_animal_sleep_reduces_fatigue_and_wakes_for_hunger():
    from agents.agent import Agent
    from agents.needs import AgentNeeds
    from animals.herbivore import Herbivore
    from environment.world import World
    from simulation.simulation import Simulation

    world = World(width=15, height=15, food_count=0, obstacle_count=0, water_count=0)
    human = Agent(0, 0)
    animal = Herbivore(10, 10, needs=AgentNeeds(max_energy=60.0, energy=40.0, hunger=20.0, thirst=20.0, fatigue=70.0))
    simulation = Simulation(world, agents=[human], herbivores=[animal], seed_spawn_count=0)
    simulation.step()
    assert animal.last_activity == "SLEEPING"
    assert animal.needs.fatigue < 70.0
    animal.needs.hunger = 50.0
    simulation.step()
    record = [r for r in simulation.physiology_activity_history if r["individual_type"] == "HERBIVORE"][-1]
    assert record["sleep_interruption_reason"] == "HUNGER"
    assert not animal.is_sleeping


def test_carnivore_can_sleep_at_baseline_hunger_when_fatigued_and_safe():
    from agents.agent import Agent
    from agents.needs import AgentNeeds
    from animals.carnivore import Carnivore
    from environment.world import World
    from simulation.simulation import Simulation

    world = World(width=12, height=12, food_count=0, obstacle_count=0, water_count=0)
    human = Agent(0, 0)
    carnivore = Carnivore(
        10, 10,
        needs=AgentNeeds(max_health=120.0, health=120.0, max_energy=80.0,
                         energy=60.0, hunger=35.0, thirst=20.0, fatigue=70.0),
    )
    simulation = Simulation(world, agents=[human], carnivores=[carnivore], seed_spawn_count=0)
    simulation.step()

    assert carnivore.last_activity == "SLEEPING"
    assert carnivore.needs.fatigue < 70.0


def test_carnivore_attack_spends_stamina_and_requires_reserve():
    from agents.agent import Agent
    from animals.carnivore import Carnivore
    from environment.world import World
    from simulation.simulation import Simulation

    world = World(width=6, height=6, food_count=0, obstacle_count=0, water_count=0)
    human = Agent(2, 2)
    human.needs.health = 100.0
    human.needs.energy = 0.0
    human.choose_action = lambda nearby_cells, world: (0, 0)
    carnivore = Carnivore(3, 2)
    simulation = Simulation(world, agents=[human], carnivores=[carnivore], seed_spawn_count=0)
    simulation.step()
    assert simulation.carnivore_attacks == 1
    assert carnivore.needs.energy == 72.0
    record = [r for r in simulation.physiology_activity_history if r["individual_type"] == "CARNIVORE"][-1]
    assert record["stamina_spent_combat"] == 8.0

    world2 = World(width=6, height=6, food_count=0, obstacle_count=0, water_count=0)
    human2 = Agent(2, 2)
    human2.choose_action = lambda nearby_cells, world: (0, 0)
    weak_carnivore = Carnivore(3, 2)
    weak_carnivore.needs.energy = 5.0
    simulation2 = Simulation(world2, agents=[human2], carnivores=[weak_carnivore], seed_spawn_count=0)
    simulation2.step()
    assert simulation2.carnivore_attacks == 0
    assert human2.alive
