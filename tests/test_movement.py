from environment.world import World
from agents.agent import Agent
from agents.perception import Perception

world = World(width=10, height=10, food_count=10)
agent = Agent(x=5, y=5)
perception = Perception()

print(f"Posição inicial: ({agent.x}, {agent.y})")

for step in range(10):
    nearby_cells = perception.observe(
        world,
        agent.x,
        agent.y,
        radius=agent.vision_radius,
    )

    action = agent.choose_action(nearby_cells, world)

    if action == (0, 0):
        moved = False
    else:
        moved = world.move_agent(agent, action)

    if not moved:
        agent.target = None
        agent.path.clear()

    status = "movimentou" if moved else "movimento bloqueado"

    print(
        f"Passo {step + 1}: "
        f"ação={action}, "
        f"status={status}, "
        f"posição=({agent.x}, {agent.y})"
    )

print("\nTeste concluído.")