from environment.world import World
from agents.agent import Agent
from agents.perception import Perception

world = World(width=10, height=10, food_count=10)
agent = Agent(x=5, y=5)
perception = Perception()

for step in range(30):
    cell = world.get_cell(agent.x, agent.y)

    if cell.resource is not None:
        world.collect_resource(agent.x, agent.y)
        print(
            f"Passo {step + 1}: "
            f"comida coletada em ({agent.x}, {agent.y})"
        )

        if agent.target == (agent.x, agent.y):
            agent.target = None
            agent.path.clear()

    nearby_cells = perception.observe(
        world,
        agent.x,
        agent.y,
        radius=agent.vision_radius,
    )

    action = agent.choose_action(nearby_cells, world)
    target = agent.target
    old_position = (agent.x, agent.y)

    if action == (0, 0):
        moved = False
    else:
        moved = world.move_agent(agent, action)

    if not moved:
        agent.target = None
        agent.path.clear()

    print(
        f"Passo {step + 1}: "
        f"posição={old_position} -> "
        f"({agent.x}, {agent.y}), "
        f"ação={action}, "
        f"alvo={target}, "
        f"movimentou={moved}"
    )

print("\nTeste concluído.")