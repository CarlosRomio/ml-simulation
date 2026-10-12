"""Experimento não visual de interação entre humanos, herbívoros e carnívoros.

Execute com: py -3.13 run_ecosystem_experiment.py
"""
from statistics import mean
import time

from configuration.simulation_config import SimulationConfig
from experiments.runner import run_single_simulation


def main() -> None:
    runs = 20
    max_steps = 300
    base_seed = 10
    config = SimulationConfig(
        width=30,
        height=30,
        food_density=0.06,
        obstacle_density=0.01,
        water_density=0.02,
        agent_count=5,
        herbivore_count=8,
        carnivore_count=3,
        vision_radius=6,
    )
    config.validate()

    print("=== Experimento ecológico (sem visualização) ===")
    print(f"Execuções: {runs}; passos por execução: {max_steps}")
    print(
        f"População inicial: {config.agent_count} humanos, "
        f"{config.herbivore_count} herbívoros, "
        f"{config.carnivore_count} carnívoros"
    )
    print("Executando...")
    started = time.perf_counter()
    results = [
        run_single_simulation(
            config,
            run_seed=base_seed + index,
            max_steps=max_steps,
            seed_spawn_count=1,
            max_plants=100,
        )
        for index in range(runs)
    ]

    human_count = sum(result.total_agents for result in results)
    human_survivors = sum(result.surviving_agents for result in results)
    print("\n=== Resultados agregados ===")
    print(f"Sobrevivência humana: {human_survivors / human_count:.1%}")
    print(f"Humanos mortos por predação: {sum(result.humans_killed_by_carnivores for result in results)}")
    print(f"Ataques de caça humanos: {sum(result.human_hunt_attacks for result in results)}")
    print(f"Ataques de carnívoros: {sum(result.carnivore_attacks for result in results)}")
    print(f"Ataques defensivos humanos: {sum(result.human_defense_attacks for result in results)}")
    print(f"Herbívoros abatidos: {sum(result.herbivores_killed for result in results)}")
    print(f"Carnívoros abatidos: {sum(result.carnivores_killed for result in results)}")
    print(f"Herbívoros vivos ao final (média): {mean(result.living_herbivores for result in results):.2f}")
    print(f"Carnívoros vivos ao final (média): {mean(result.living_carnivores for result in results):.2f}")
    print(f"Tempo: {time.perf_counter() - started:.2f}s")


if __name__ == "__main__":
    main()
