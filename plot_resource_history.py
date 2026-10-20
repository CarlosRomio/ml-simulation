
import csv
from pathlib import Path

import matplotlib.pyplot as plt


CSV_PATH = Path("results/resource_history.csv")
OUTPUT_DIR = Path("results/plots")


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Histórico não encontrado: {CSV_PATH}. "
            "Execute primeiro run_ecology_experiment.py."
        )

    with CSV_PATH.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    if not rows:
        raise ValueError("O histórico ecológico está vazio.")

    steps = [int(row["step"]) for row in rows]
    seeds = [int(row["seeds"]) for row in rows]
    growing = [int(row["growing"]) for row in rows]
    mature = [int(row["mature"]) for row in rows]
    total = [int(row["total"]) for row in rows]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Gráfico 1: população total de plantas.
    plt.figure(figsize=(10, 5))
    plt.plot(steps, total, label="Total de plantas")
    plt.axhline(
        y=100,
        linestyle="--",
        label="Limite configurado: 100",
    )
    plt.xlabel("Passo da simulação")
    plt.ylabel("Quantidade de plantas")
    plt.title("Evolução da população vegetal")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "plant_population.png", dpi=150)
    plt.close()

    # Gráfico 2: distribuição por estágio.
    plt.figure(figsize=(10, 5))
    plt.plot(steps, seeds, label="Sementes")
    plt.plot(steps, growing, label="Em crescimento")
    plt.plot(steps, mature, label="Maduras")
    plt.xlabel("Passo da simulação")
    plt.ylabel("Quantidade de plantas")
    plt.title("Ciclo de vida das plantas")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "plant_stages.png", dpi=150)
    plt.close()

    print(f"Registros analisados: {len(rows)}")
    print(f"Passo inicial: {steps[0]}")
    print(f"Último passo registrado: {steps[-1]}")
    print(f"População inicial: {total[0]}")
    print(f"População final: {total[-1]}")
    print(f"Maior população observada: {max(total)}")
    print(f"Gráficos salvos em: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
