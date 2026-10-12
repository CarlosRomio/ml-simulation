
import time

from configuration.simulation_config import SimulationConfig
from experiments.runner import ExperimentRunner
from scenarios.factory import ScenarioFactory


def main():
    config = SimulationConfig(
        width=30,
        height=30,
        food_density=0.02,
        obstacle_density=0.01,
        vision_radius=6,
    )

    scenario = ScenarioFactory.create(config, seed=123)

    runner = ExperimentRunner(
        config=config,
        runs=100,
        max_steps=500,
        seed=42,
        max_workers=4,
        scenario=scenario,
    )

    print("=== Experimento em cenário fixo ===")
    print(f"Execuções: {runner.runs}")
    print(f"Limite de passos: {runner.max_steps}")
    print(f"Semente do cenário: {scenario.seed}")
    print(f"Processos: {runner.max_workers}")
    print("Executando...")

    start_time = time.perf_counter()
    results = runner.run()
    elapsed = time.perf_counter() - start_time

    summary = runner.summarize()

    
    print("\n=== Resultados do experimento ===")
    print(f"Execuções concluídas: {summary.total_runs}")
    print(
        f"Sobrevivência: {summary.survival_rate:.1%} "
        f"({summary.survived_runs}/{summary.total_runs})"
    )
    print(f"Mortes por inanição: {summary.starvation_runs}")

    print("\n--- Desempenho e recursos ---")
    print(f"Média de passos: {summary.average_steps:.1f}")
    print(
        f"Tempo simulado médio: "
        f"{summary.average_simulated_time:.2f} s"
    )
    print(
        f"Comida coletada por execução: "
        f"{summary.average_food_collected:.2f}"
    )
    print(f"Energia média: {summary.average_energy:.2f}")

    print("\n--- Comportamento ---")
    print(
        f"Distância percorrida: "
        f"{summary.average_distance_travelled:.2f}"
    )
    print(
        f"Posições únicas visitadas: "
        f"{summary.average_unique_positions_visited:.2f}"
    )
    print(
        f"Passos em movimento: "
        f"{summary.average_movement_steps:.2f}"
    )
    print(
        f"Passos sem deslocamento: "
        f"{summary.average_idle_steps:.2f}"
    )
    print(
        f"Maior intervalo sem comida: "
        f"{summary.average_max_steps_without_food:.2f} passos"
    )

    print(f"\nTempo computacional total: {elapsed:.3f} s")


if __name__ == "__main__":
    main()
