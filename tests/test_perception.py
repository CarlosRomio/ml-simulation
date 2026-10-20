from environment.world import World
from agents.agent import Agent
from agents.perception import Perception


world = World(width=10, height=10, food_count=10)
agent = Agent(x=5, y=5)
perception = Perception()

nearby = perception.observe(
    world,
    agent.x,
    agent.y,
    radius=agent.vision_radius,
)

print(f"Posição do agente: ({agent.x}, {agent.y})")
print(f"Células percebidas: {len(nearby)}")
print("\nPercepção local:")

for y in range(agent.y - 1, agent.y + 2):
    for x in range(agent.x - 1, agent.x + 2):
        cell = world.get_cell(x, y)

        if (x, y) == (agent.x, agent.y):
            symbol = "A"
        elif cell.obstacle is not None:
            symbol = "#"
        elif cell.resource is not None:
            symbol = "F"
        else:
            symbol = "."

        print(symbol, end=" ")
    print()