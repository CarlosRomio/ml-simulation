
from agents.agent import Agent
from environment.world import World
from simulation.simulation import Simulation


world = World(width=10, height=10, food_count=10)
agent = Agent(x=5, y=5)

simulation = Simulation(world, agent)

simulation.run(steps=100)

remaining_food = sum(
    1
    for row in world.grid
    for cell in row
    if cell.resource is not None
)

print(f"Passos executados: {simulation.steps}")
print(f"Posição final: ({agent.x}, {agent.y})")
print(f"Comida restante: {remaining_food}")
print("Simulação concluída!")


def test_simulation_clock_uses_one_simulated_minute_per_step():
    world = World(width=3, height=3, food_count=0, obstacle_count=0)
    agent = Agent(1, 1)
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)

    assert simulation.simulated_minutes == 0
    assert simulation.simulated_time_label == "Dia 1, 00:00"
    simulation.step()
    assert simulation.simulated_minutes == 1
    assert simulation.simulated_time_label == "Dia 1, 00:01"
    simulation.run(steps=59)
    assert simulation.simulated_minutes == 60
    assert simulation.simulated_time_label == "Dia 1, 01:00"


def test_high_fatigue_enters_sleep_and_recovers_fatigue():
    from agents.needs import AgentNeeds

    world = World(width=9, height=9, food_count=0, obstacle_count=0, water_count=0)
    agent = Agent(4, 4, needs=AgentNeeds(fatigue=100.0, energy=80.0))
    simulation = Simulation(world, agent=agent, seed_spawn_count=0)

    simulation.step()

    assert agent.last_activity == "SLEEPING"
    assert agent.needs.fatigue < 100.0
    assert agent.is_sleeping
    assert agent.needs.fatigue == 99.85
