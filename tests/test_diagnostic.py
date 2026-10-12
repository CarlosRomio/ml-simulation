from agents.agent import Agent
from configuration.simulation_config import SimulationConfig
from metrics.tracker import SimulationMetrics
from scenarios.factory import ScenarioFactory
from simulation.simulation import Simulation


def main():
    config = SimulationConfig(
        width=30,
        height=30,
        food_density=0.02,
        obstacle_density=0.01,
        vision_radius=6,
    )

    config.validate()

    scenario = ScenarioFactory.create(config, seed=123)

    agent = Agent(
        x=scenario.start_position[0],
        y=scenario.start_position[1],
        vision_radius=config.vision_radius,
        rng=__import__("random").Random(42),
    )

    world = scenario.to_world()
    simulation = Simulation(world=world, agent=agent)

    simulation.run(500)

    metrics = simulation.metrics

    print("\n=== DIAGNÓSTICO DA SIMULAÇÃO ===")
    print(f"Causa do encerramento: {metrics.termination_cause}")
    print(f"Passos executados: {metrics.steps}")
    print(f"Comida coletada: {metrics.food_collected}")
    print(f"Energia inicial: {metrics.initial_energy:.2f}")
    print(f"Energia final: {metrics.final_energy:.2f}")

    print("\n=== HISTÓRICO DE ENERGIA ===")
    history = simulation.energy_history

    if history:
        print(f"Registros: {len(history)}")
        print(f"Primeiros registros: {history[:10]}")
        print(f"Últimos registros: {history[-10:]}")
        print(f"Energia mínima: {min(history):.2f}")
        print(f"Energia máxima: {max(history):.2f}")
    else:
        print("Histórico vazio.")

    print("\n=== COLETAS DE COMIDA ===")
    collection_steps = simulation.food_collection_steps

    print(f"Quantidade de coletas registradas: {len(collection_steps)}")
    print(f"Passos das coletas: {collection_steps}")
    print(f"Tempo simulado: {metrics.simulated_time_seconds:.2f} s")
    print(f"Energia média: {metrics.average_energy:.2f}")
    print(f"Passos em movimento: {metrics.movement_steps}")
    print(f"Passos sem deslocamento: {metrics.idle_steps}")
    print(f"Distância percorrida: {metrics.distance_travelled:.2f}")
    print(f"Posições únicas visitadas: {metrics.unique_positions_visited}")
    print(f"Maior intervalo sem comida: {metrics.max_steps_without_food}")

if __name__ == "__main__":
    main()