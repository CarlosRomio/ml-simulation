
from agents.factory import AgentFactory
from animals.factory import HerbivoreFactory
from environment.world import World
from simulation.simulation import Simulation
from visualization.pygame_app import run
from configuration.simulation_config import SimulationConfig


def main():
    config = SimulationConfig(
        width=100,
        height=100,
        food_density=0.02,
        obstacle_density=0.01,
        vision_radius=6,
        agent_count=10,
        herbivore_count=8,
    )

    config.validate()

    start_x, start_y = config.start_position
    reserved_cells = {(start_x, start_y)}

    world = World(
        width=config.width,
        height=config.height,
        food_count=config.food_count,
        obstacle_count=config.obstacle_count,
        water_count=config.water_count,
        reserved_cells=reserved_cells,
    )

    agents = AgentFactory.create_agents(
        world=world,
        count=config.agent_count,
        vision_radius=config.vision_radius,
        preferred_position=config.start_position,
        seed=42,
        thirst_per_step=config.thirst_per_step,
        dehydration_threshold=config.dehydration_threshold,
        dehydration_damage_per_step=config.dehydration_damage_per_step,
    )

    herbivores = HerbivoreFactory.create(
        world=world,
        count=config.herbivore_count,
        vision_radius=config.vision_radius,
        seed=84,
        occupied_positions={(agent.x, agent.y) for agent in agents},
    )

    simulation = Simulation(
        world=world,
        agents=agents,
        herbivores=herbivores,
    )

    print("=== Configuração da simulação ===")
    print(f"Dimensões: {config.width} x {config.height}")
    print(f"Área: {config.area} células")
    print(f"Plantas: {config.food_count}")
    print(f"Fontes de água: {config.water_count}")
    print(f"Obstáculos: {config.obstacle_count}")
    print(f"Posição inicial: {config.start_position}")
    print(f"Agentes humanos: {config.agent_count}")
    print(f"Herbívoros: {config.herbivore_count}")
    print(f"Raio de visão: {config.vision_radius}")

    run(simulation)


if __name__ == "__main__":
    main()
