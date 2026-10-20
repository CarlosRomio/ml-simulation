
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
