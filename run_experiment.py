
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
        agent_count=10,
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
    print(f"Agentes por execução: {config.agent_count}")
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
    print(f"Execuções com todos os agentes mortos: {summary.starvation_runs}")
    print(f"Sobrevivência por agente: {summary.agent_survival_rate:.1%}")
    print(f"Agentes vivos em média ao final: {summary.average_surviving_agents:.2f}")
    print(f"Comida coletada pela população: {summary.average_population_food_collected:.2f} por execução")
    print(f"Agentes mortos em média ao final: {summary.average_starved_agents:.2f}")
    print(f"Comida por agente (mín./média/máx.): {summary.minimum_food_per_agent:.2f} / {summary.average_food_collected:.2f} / {summary.maximum_food_per_agent:.2f}")
    print(f"Desvio-padrão da comida por agente: {summary.food_collection_stddev:.2f}")

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
    print(f"Saúde final média: {summary.average_final_health:.2f}")
    print(f"Fome final média: {summary.average_final_hunger:.2f}")
    print(f"Sede final média: {summary.average_final_thirst:.2f}")
    print(f"Bebidas por agente: {summary.average_water_drinks:.2f}")
    print(f"Água consumida por agente: {summary.average_water_units_consumed:.2f}")
    print(f"Mortes por desidratação (média por execução): {summary.average_deaths_by_dehydration:.2f}")
    print(f"Mortes por inanição/energia (média por execução): {summary.average_deaths_by_starvation:.2f}")

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

    print("\n--- Interação entre agentes ---")
    print(f"Movimentos bloqueados por execução: {summary.average_blocked_movement_attempts:.2f}")
    print(f"  Por ocupação de outro agente: {summary.average_blocked_by_agent_attempts:.2f}")
    print(f"  Por obstáculo/limite do mundo: {summary.average_blocked_by_environment_attempts:.2f}")
    if summary.average_population_alive_by_step:
        checkpoints = [0, len(summary.average_population_alive_by_step) // 4, len(summary.average_population_alive_by_step) // 2, (3 * len(summary.average_population_alive_by_step)) // 4, len(summary.average_population_alive_by_step) - 1]
        checkpoints = sorted(set(checkpoints))
        print("Evolução média de agentes vivos:")
        for index in checkpoints:
            print(f"  Passo {index}: {summary.average_population_alive_by_step[index]:.2f}")

    print(f"\nTempo computacional total: {elapsed:.3f} s")


if __name__ == "__main__":
    main()
