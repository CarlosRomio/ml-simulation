"""Pipeline automatizado de comparação de disponibilidade de água."""
import argparse

from configuration.simulation_config import SimulationConfig
from experiments.comparison import run_water_comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara cenários com diferentes disponibilidades de água.")
    parser.add_argument("--runs", type=int, default=30, help="Execuções pareadas por condição (padrão: 30).")
    parser.add_argument("--steps", type=int, default=500, help="Passos por execução (padrão: 500).")
    parser.add_argument("--seed", type=int, default=123, help="Semente do cenário e das execuções.")
    parser.add_argument("--workers", type=int, default=4, help="Processos paralelos por condição.")
    parser.add_argument("--agents", type=int, default=10, help="Agentes por execução.")
    parser.add_argument("--output", default="results/water_comparison", help="Pasta para CSVs.")
    args = parser.parse_args()

    config = SimulationConfig(
        width=30,
        height=30,
        food_density=0.02,
        obstacle_density=0.01,
        water_density=0.02,
        vision_radius=6,
        agent_count=args.agents,
    )
    result = run_water_comparison(
        config=config,
        runs=args.runs,
        max_steps=args.steps,
        seed=args.seed,
        max_workers=args.workers,
        output_dir=args.output,
    )

    print("=== Comparação automatizada: disponibilidade de água ===")
    print(f"Condições: {len(result['summary'])}; execuções por condição: {args.runs}; passos: {args.steps}")
    print(f"Agentes por execução: {args.agents}; processos: {args.workers}; semente: {args.seed}")
    print("Cenário pareado: posições de comida e obstáculos mantidas entre condições.")
    print("\nCondição             Água  Sobreviv.  Sede média  Água/agente  Mortes desidr.  Mortes energia  Comida/pop.")
    for row in result["summary"]:
        print(
            f"{row['condition']:<20} {int(row['water_density'] * 900):>4} "
            f"{row['survival_rate_pct_mean']:>8.2f}% "
            f"{row['average_thirst_mean_mean']:>10.2f} "
            f"{row['water_units_per_agent_mean']:>11.2f} "
            f"{row['dehydration_deaths_per_run_mean']:>14.2f} "
            f"{row['starvation_deaths_per_run_mean']:>14.2f} "
            f"{row['food_per_population_mean']:>11.2f}"
        )
        print(
            f"  IC95 sobrevivência: [{row['survival_rate_pct_ci95_low']:.2f}, "
            f"{row['survival_rate_pct_ci95_high']:.2f}]%; "
            f"tempo: {row['compute_seconds']:.2f}s ({row['runs_per_second']:.2f} exec/s)"
        )
    print(f"\nCSVs salvos em: {result['output_dir']}")
    print("  runs.csv         - resultados de cada execução e condição")
    print("  summary.csv      - médias, desvios-padrão e IC95% aproximado")
    print("  paired_deltas.csv - diferenças por réplica contra a condição-base")


if __name__ == "__main__":
    main()
