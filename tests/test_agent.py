from agents.agent import Agent
from agents.perception import Perception
from environment.world import World

world = World(width=10, height=10, food_count=10)
agent = Agent(x=5, y=5)
perception = Perception()

print(f"Posição inicial: ({agent.x}, {agent.y})")

for step in range(5):
    nearby_cells = perception.observe(
        world,
        agent.x,
        agent.y,
        radius=agent.vision_radius,
    )

    action = agent.choose_action(nearby_cells, world)

    print(f"Passo {step + 1}: ação escolhida = {action}")

    if action == (0, 0):
        print("Nenhum movimento disponível.")
        break

    moved = world.move_agent(agent, action)

    if not moved:
        agent.target = None
        agent.path.clear()

print(f"Posição final: ({agent.x}, {agent.y})")