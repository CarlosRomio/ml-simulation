
from agents.agent import Agent
from environment.world import World
from simulation.simulation import Simulation


def test_energy_decreases():
    agent = Agent(x=0, y=0)

    agent.consume_energy()

    assert agent.energy == 99.0
    assert agent.alive


def test_eating_restores_energy():
    agent = Agent(x=0, y=0)

    agent.consume_energy(50)
    agent.eat(25)

    assert agent.energy == 75.0
    assert agent.alive


def test_energy_does_not_exceed_maximum():
    agent = Agent(x=0, y=0)

    agent.eat(25)

    assert agent.energy == 100.0


def test_agent_dies_at_zero_energy():
    agent = Agent(x=0, y=0)

    agent.consume_energy(100)

    assert agent.energy == 0.0
    assert not agent.alive


def test_dead_agent_cannot_recover_energy():
    agent = Agent(x=0, y=0)

    agent.consume_energy(100)
    agent.eat(25)

    assert agent.energy == 0.0
    assert not agent.alive

def test_environment_continues_when_agent_dies():
    world = World(
        width=10,
        height=10,
        food_count=0,
    )

    agent = Agent(x=5, y=5)
    agent.consume_energy(100)

    simulation = Simulation(
        world,
        agent,
        seed_spawn_count=0,
    )

    simulation.run(steps=10)

    assert not agent.alive
    assert simulation.steps == 10
    assert len(simulation.resource_history) == 11
    assert simulation.metrics.termination_cause == "STARVATION"


def run_all_tests():
    tests = [
        test_energy_decreases,
        test_eating_restores_energy,
        test_energy_does_not_exceed_maximum,
        test_agent_dies_at_zero_energy,
        test_dead_agent_cannot_recover_energy,
        test_environment_continues_when_agent_dies,
    ]

    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")

    print(f"\nTodos os {len(tests)} testes de sobrevivência passaram!")


if __name__ == "__main__":
    run_all_tests()
