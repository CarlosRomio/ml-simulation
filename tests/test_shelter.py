from agents.agent import Agent
from environment.world import World
from environment.resources import MaterialKind
from environment.shelter import Shelter
from simulation.simulation import Simulation


def test_shelter_requires_materials_and_preserves_inventory_on_failure():
    world = World(width=5, height=5, food_count=0)
    agent = Agent(2, 2)
    sim = Simulation(world, agent=agent)
    assert not sim.build_shelter(agent)
    assert world.get_cell(2, 2).structure is None
    agent.inventory.add(MaterialKind.WOOD, 5)
    agent.inventory.add(MaterialKind.STONE, 2)
    assert sim.build_shelter(agent)
    assert isinstance(world.get_cell(2, 2).structure, Shelter)
    assert agent.inventory.quantity_of(MaterialKind.WOOD) == 0
    assert agent.inventory.quantity_of(MaterialKind.STONE) == 0
    assert not sim.build_shelter(agent)


def test_tired_human_stays_in_shelter_and_recovers_extra_energy():
    from agents.needs import AgentNeeds

    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    needs = AgentNeeds(energy=50.0, hunger=10.0, thirst=10.0)
    agent = Agent(2, 2, needs=needs)
    world.get_cell(2, 2).structure = Shelter()
    sim = Simulation(world, agent=agent, seed_spawn_count=0)

    sim.step()

    assert (agent.x, agent.y) == (2, 2)
    assert agent.energy == 60.0
    assert sim.diagnostic_history[-1]["rest_energy_recovered"] == 10.0


def test_shelter_does_not_override_urgent_thirst_or_hunger():
    from agents.needs import AgentNeeds

    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    needs = AgentNeeds(energy=50.0, hunger=40.0, thirst=50.0)
    agent = Agent(2, 2, needs=needs)
    world.get_cell(2, 2).structure = Shelter()

    action = agent.choose_action([], world)

    assert action != (0, 0)


def test_shelter_reduces_carnivore_damage_without_making_human_invulnerable():
    from animals.carnivore import Carnivore
    from agents.needs import AgentNeeds

    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    human = Agent(2, 2, needs=AgentNeeds(health=100.0, energy=100.0, hunger=10.0, thirst=10.0))
    world.get_cell(2, 2).structure = Shelter()
    carnivore = Carnivore(3, 2, needs=AgentNeeds(
        max_health=120.0, health=120.0, max_energy=80.0, energy=80.0,
        hunger=60.0, thirst=10.0, hunger_per_step=0.0, thirst_per_step=0.0,
    ))
    sim = Simulation(world, agent=human, carnivores=[carnivore], seed_spawn_count=0)
    sim.set_manual_control(human, True)

    sim.step()

    # O dano padrão é 35; no abrigo, 25% dele é aplicado (8,75).
    assert human.health == 91.25
    assert human.alive
    assert sim.carnivore_attacks == 1
    assert sim.damage_events[-1]["target_id"] == id(human)
    assert sim.damage_events[-1]["damage"] == 8.75
    assert sim.damage_events[-1]["sheltered"] is True


def test_human_outside_shelter_takes_full_carnivore_damage():
    from animals.carnivore import Carnivore
    from agents.needs import AgentNeeds

    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    human = Agent(2, 2, needs=AgentNeeds(health=100.0, energy=100.0, hunger=10.0, thirst=10.0))
    carnivore = Carnivore(3, 2, needs=AgentNeeds(
        max_health=120.0, health=120.0, max_energy=80.0, energy=80.0,
        hunger=60.0, thirst=10.0, hunger_per_step=0.0, thirst_per_step=0.0,
    ))
    sim = Simulation(world, agent=human, carnivores=[carnivore], seed_spawn_count=0)
    sim.set_manual_control(human, True)

    sim.step()

    assert human.health == 65.0
    assert sim.carnivore_attacks == 1
    assert sim.damage_events[-1]["damage"] == 35.0
    assert sim.damage_events[-1]["sheltered"] is False


def test_test_carnivore_spawns_adjacent_with_stable_test_needs():
    from animals.carnivore import Carnivore

    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    human = Agent(2, 2)
    world.get_cell(2, 2).structure = Shelter()
    sim = Simulation(world, agent=human, seed_spawn_count=0)

    carnivore = sim.spawn_test_carnivore_near(human)

    assert isinstance(carnivore, Carnivore)
    assert abs(carnivore.x - human.x) + abs(carnivore.y - human.y) == 1
    assert carnivore.health == 300.0
    assert carnivore.hunger >= 30.0
    assert carnivore.test_target_agent is human
    assert carnivore in sim.carnivores


def test_test_carnivore_spawn_fails_when_all_adjacent_cells_are_blocked():
    from environment.obstacles import ObstacleType

    world = World(width=3, height=3, food_count=0, obstacle_count=0)
    human = Agent(1, 1)
    for x, y in ((1, 0), (2, 1), (1, 2), (0, 1)):
        world.get_cell(x, y).obstacle = ObstacleType.TREE
    sim = Simulation(world, agent=human, seed_spawn_count=0)

    assert sim.spawn_test_carnivore_near(human) is None
    assert sim.carnivores == []


def test_default_shared_storage_is_a_shelter_with_storage_capacity():
    from environment.storage import Storage
    from environment.shelter import Shelter

    world = World(width=5, height=5, food_count=0, obstacle_count=0)
    structure = world.place_storage(2, 2)

    assert isinstance(structure, Shelter)
    assert isinstance(structure, Storage)
    assert structure.capacity_weight == 500.0
    assert world.get_storage_positions() == [(2, 2)]


def test_autonomous_human_gathers_materials_and_builds_shelter():
    from agents.needs import AgentNeeds
    from environment.resources import MaterialKind, MaterialResource
    from environment.shelter import Shelter

    world = World(width=12, height=8, food_count=0, obstacle_count=0)
    world.get_cell(3, 2).resource = MaterialResource(MaterialKind.WOOD, quantity=5)
    world.get_cell(5, 2).resource = MaterialResource(MaterialKind.STONE, quantity=2)
    human = Agent(2, 2, needs=AgentNeeds(energy=100, hunger=0, thirst=0,
                                        hunger_per_step=0.01, thirst_per_step=0.01))
    sim = Simulation(world, agent=human, seed_spawn_count=0)

    for _ in range(60):
        sim.step()
        if any(isinstance(cell.structure, Shelter) for row in world.grid for cell in row):
            break

    shelters = [cell for row in world.grid for cell in row if isinstance(cell.structure, Shelter)]
    assert len(shelters) == 1
    assert human.inventory.quantity_of(MaterialKind.WOOD) <= 0.0 + 1e-9
    assert human.inventory.quantity_of(MaterialKind.STONE) <= 0.0 + 1e-9
    assert sim.shelters_built == 1
