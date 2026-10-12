
from agents.agent import Agent
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
    )

    config.validate()

    start_x, start_y = config.start_position
    reserved_cells = {(start_x, start_y)}

    world = World(
        width=config.width,
        height=config.height,
        food_count=config.food_count,
        obstacle_count=config.obstacle_count,
        reserved_cells=reserved_cells,
    )

    agent = Agent(
        x=start_x,
        y=start_y,
        vision_radius=config.vision_radius,
    )

    simulation = Simulation(
        world=world,
        agent=agent,
    )

    print("=== Configuração da simulação ===")
    print(f"Dimensões: {config.width} x {config.height}")
    print(f"Área: {config.area} células")
    print(f"Comida: {config.food_count}")
    print(f"Obstáculos: {config.obstacle_count}")
    print(f"Posição inicial: {config.start_position}")
    print(f"Raio de visão: {config.vision_radius}")

    run(simulation)


if __name__ == "__main__":
    main()
