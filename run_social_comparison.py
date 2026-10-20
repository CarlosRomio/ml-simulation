"""Executa comparação pareada das políticas de comportamento social.

Exemplo rápido: py -3.13 run_social_comparison.py --runs 2 --steps 30 --workers 1
Experimento padrão: py -3.13 run_social_comparison.py
"""
import argparse

from configuration.simulation_config import SimulationConfig
from experiments.social_comparison import run_social_comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara condições de comportamento social com sementes pareadas.")
    parser.add_argument("--runs", type=int, default=30, help="Réplicas pareadas por condição (padrão: 30).")
    parser.add_argument("--steps", type=int, default=1000, help="Passos por execução (padrão: 1000).")
    parser.add_argument("--seed", type=int, default=123, help="Semente-base para cenários e réplicas.")
    parser.add_argument("--workers", type=int, default=0, help="Processos paralelos; 0 = automático (até 8, preservando um núcleo quando possível); 1 = sequencial.")
    parser.add_argument("--affinity-threshold", type=float, default=0.5, help="Limiar de afinidade para grupos sociais.")
    parser.add_argument("--interval-steps", type=int, default=100, help="Tamanho em passos das janelas de resumo de atividade.")
    parser.add_argument("--output", default="results/social_comparison", help="Diretório de saída dos CSVs.")
    args = parser.parse_args()

    config = SimulationConfig(
        width=30, height=30, food_density=0.02, obstacle_density=0.01,
        water_density=0.005, wood_density=0.01, stone_density=0.01,
        agent_count=5, herbivore_count=8, carnivore_count=3, vision_radius=6,
    )
    result = run_social_comparison(
        config=config, runs=args.runs, max_steps=args.steps, seed=args.seed,
        max_workers=args.workers, output_dir=args.output,
        affinity_threshold=args.affinity_threshold,
        activity_interval_steps=args.interval_steps,
    )
    print("=== Comparação pareada: comportamento social ===")
    print(f"Condições: {len(result['summary'])}; réplicas/condição: {args.runs}; passos: {args.steps}")
    print(f"Humanos/herbívoros/carnívoros: {config.agent_count}/{config.herbivore_count}/{config.carnivore_count}")
    print(f"Sementes pareadas: {args.seed}–{args.seed + args.runs - 1}; limiar de grupo: {args.affinity_threshold:.2f}")
    print(f"Processos de simulação: {result['workers']}")
    print("\nCondição                     Sobreviv.  Afinidade  Grupos finais  Reencontros sucesso  Tempo")
    for row in result["summary"]:
        print(f"{row['condition']:<28} {row['human_survival_pct_mean']:>8.2f}% "
              f"{row['final_mean_pair_affinity_mean']:>10.3f} "
              f"{row['final_group_count_mean']:>14.2f} "
              f"{row['reunion_success_rate_pct_mean']:>18.2f}% "
              f"{row['compute_seconds']:>7.1f}s")
    print(f"\nResultados: {result['output_dir']}")
    print("  runs.csv          - uma linha por réplica e condição")
    print("  summary.csv       - médias, desvios-padrão e IC95% aproximados")
    print("  paired_deltas.csv - diferenças por réplica contra A_CONTROLE")
    print("  paired_summary.csv - média e IC95% das diferenças pareadas")
    print("  group_history.csv - grupos detectados por passo")
    print("  group_events.csv  - formação, dissolução e mudança de composição")
    print("  agent_activity_history.csv - decisões, deslocamento, coleta e fisiologia por humano/passo")
    print("  activity_interval_summary.csv - resumo temporal em janelas de passos")


if __name__ == "__main__":
    main()
