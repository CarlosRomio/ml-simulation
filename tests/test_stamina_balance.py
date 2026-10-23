"""Regressões para o rebalanceamento de estamina e recuperação."""

from agents.agent import Agent
from agents.needs import AgentNeeds
from animals.carnivore import Carnivore
from animals.herbivore import Herbivore
from configuration.physiology_config import PhysiologyConfig
from environment.world import World
from simulation.simulation import Simulation


def test_default_stamina_profile_is_less_restrictive():
    config = PhysiologyConfig()
    config.validate()

    assert config.stamina_run_cost == 5.0
    assert config.stamina_attack_cost == 5.0
    assert config.stamina_run_minimum == 15.0
    assert config.stamina_wait_recovery == 1.5
    assert config.stamina_rest_recovery == 4.0
    assert config.stamina_sleep_recovery == 4.0
    assert config.stamina_shelter_rest_recovery == 10.0


def test_animal_species_have_larger_stamina_reserves():
    assert Herbivore(3, 3).needs.max_energy == 80.0
    assert Carnivore(4, 4).needs.max_energy == 110.0


def test_rest_recovers_more_stamina_and_never_exceeds_capacity():
    world = World(width=5, height=5, food_count=0, obstacle_count=0, water_count=0)
    needs = AgentNeeds(max_energy=100.0, energy=50.0, hunger=10.0, thirst=10.0)
    agent = Agent(2, 2, needs=needs)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)

    simulation.step()
    assert agent.energy == 54.0

    agent.needs.energy = 99.0
    simulation.step()
    assert agent.energy == 100.0


def test_sleep_recovers_more_stamina_than_before():
    world = World(width=5, height=5, food_count=0, obstacle_count=0, water_count=0)
    needs = AgentNeeds(energy=40.0, hunger=10.0, thirst=10.0, fatigue=70.0)
    agent = Agent(2, 2, needs=needs)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)

    simulation.step()

    assert agent.last_activity == "SLEEPING"
    assert agent.energy == 44.0


def test_stamina_policy_uses_hysteresis_for_running_and_resting():
    from agents.stamina_policy import should_rest_for_stamina, should_run

    config = PhysiologyConfig()
    assert should_run(
        energy=60, max_energy=100, fatigue=10, urgent=False,
        currently_running=False, config=config,
    )
    assert not should_run(
        energy=35, max_energy=100, fatigue=10, urgent=False,
        currently_running=False, config=config,
    )
    assert should_run(
        energy=35, max_energy=100, fatigue=10, urgent=False,
        currently_running=True, config=config,
    )
    assert not should_run(
        energy=10, max_energy=100, fatigue=10, urgent=True,
        currently_running=False, config=config,
    )
    assert should_rest_for_stamina(
        energy=20, max_energy=100, urgent=False,
        currently_resting=False, config=config,
    )
    assert should_rest_for_stamina(
        energy=40, max_energy=100, urgent=False,
        currently_resting=True, config=config,
    )
    assert not should_rest_for_stamina(
        energy=60, max_energy=100, urgent=False,
        currently_resting=True, config=config,
    )
    assert not should_rest_for_stamina(
        energy=10, max_energy=100, urgent=True,
        currently_resting=False, config=config,
    )


def test_low_stamina_recovery_scales_up_and_is_capped_by_max_energy():
    from agents.stamina_policy import recovery_amount

    config = PhysiologyConfig()
    assert recovery_amount(4.0, 50.0, 100.0, config) == 4.0
    assert recovery_amount(4.0, 0.0, 100.0, config) == 7.0

    needs = AgentNeeds(max_energy=100.0, energy=98.0)
    needs.restore_energy(recovery_amount(4.0, needs.energy, needs.max_energy, config))
    assert needs.energy == 100.0


def test_low_stamina_agent_recovers_adaptively_without_dying():
    world = World(width=5, height=5, food_count=0, obstacle_count=0, water_count=0)
    needs = AgentNeeds(energy=0.0, hunger=20.0, thirst=20.0)
    agent = Agent(2, 2, needs=needs)
    agent.choose_action = lambda nearby_cells, world: (0, 0)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)

    simulation.step()

    assert agent.alive
    assert agent.energy == 7.0
    assert agent.last_activity == "RESTING"


def test_anticipatory_rest_preserves_reserve_for_expected_effort():
    from agents.stamina_policy import should_rest_for_stamina

    config = PhysiologyConfig()
    # 30 de energia bastariam para o limiar absoluto de 22%, mas não para
    # pagar uma arrancada prevista e preservar a reserva de segurança.
    assert should_rest_for_stamina(
        energy=30.0, max_energy=100.0, urgent=False,
        currently_resting=False, expected_effort=15.0, config=config,
    )
    # Sem esforço previsto, o mesmo nível de energia não exige descanso.
    assert not should_rest_for_stamina(
        energy=30.0, max_energy=100.0, urgent=False,
        currently_resting=False, expected_effort=0.0, config=config,
    )
    # Uma urgência real pode sobrepor a reserva, mas nunca muda a energia em si.
    assert not should_rest_for_stamina(
        energy=10.0, max_energy=100.0, urgent=True,
        currently_resting=False, expected_effort=10.0, config=config,
    )


def test_carnivore_keeps_preferred_prey_when_alternative_is_only_slightly_closer():
    world = World(width=12, height=12, food_count=0, obstacle_count=0, water_count=0)
    carnivore = Carnivore(2, 2)
    carnivore.needs.hunger = 50.0
    preferred_prey = (5, 2)
    slightly_closer_prey = (3, 2)
    carnivore.preferred_hunt_target = preferred_prey

    carnivore.choose_action(world, [slightly_closer_prey, preferred_prey])

    assert carnivore.target == preferred_prey


def test_carnivore_switches_to_materially_closer_prey():
    world = World(width=12, height=12, food_count=0, obstacle_count=0, water_count=0)
    carnivore = Carnivore(2, 2)
    carnivore.needs.hunger = 50.0
    carnivore.preferred_hunt_target = (8, 8)
    closer_prey = (4, 2)

    carnivore.choose_action(world, [carnivore.preferred_hunt_target, closer_prey])

    assert carnivore.target == closer_prey
