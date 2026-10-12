
import random
import statistics
from dataclasses import dataclass

from agents.agent import Agent
from environment.world import World
from simulation.simulation import Simulation


@dataclass
class ExperimentResults:
    runs: int
    max_steps: int
    seed: int
    survival_steps: list[int]
    food_collected: list[int]
    survived: int

    @property
    def survival_rate(self) -> float:
        return self.survived / self.runs * 100

    def report(self) -> str:
        average_steps = statistics.mean(self.survival_steps)
        median_steps = statistics.median(self.survival_steps)
        std_steps = (
            statistics.pstdev(self.survival_steps)
            if self.runs > 1
            else 0.0
        )

        return (
            "\n=== Experimento de sobrevivência ===\n"
            f"Execuções: {self.runs}\n"
            f"Limite por execução: {self.max_steps} passos\n"
            f"Semente inicial: {self.seed}\n"
            f"Sobrevivência média: {average_steps:.1f} passos\n"
            f"Sobrevivência mediana: {median_steps:.1f} passos\n"
            f"Melhor resultado: {max(self.survival_steps)} passos\n"
            f"Pior resultado: {min(self.survival_steps)} passos\n"
            f"Comida média coletada: "
            f"{statistics.mean(self.food_collected):.2f}\n"
            f"Taxa de sobrevivência: {self.survival_rate:.1f}%\n"
            f"Desvio-padrão dos passos: {std_steps:.2f}\n"
        )


def run_experiment(
    runs: int = 100,
    max_steps: int = 500,
    seed: int = 42,
    width: int = 10,
    height: int = 10,
    food_count: int = 10,
) -> ExperimentResults:
    if runs < 1:
        raise ValueError("runs deve ser pelo menos 1")

    if max_steps < 1:
        raise ValueError("max_steps deve ser pelo menos 1")

    survival_steps = []
    food_collected = []
    survived = 0

    for run_index in range(runs):
        random.seed(seed + run_index)

        world = World(
            width=width,
            height=height,
            food_count=food_count,
        )

        agent = Agent(
            x=width // 2,
            y=height // 2,
        )

        simulation = Simulation(world, agent)
        simulation.run(max_steps)

        if agent.alive:
            simulation.metrics.termination_cause = "STEP_LIMIT"

        survival_steps.append(simulation.steps)
        food_collected.append(simulation.metrics.food_collected)

        if simulation.metrics.survived:
            survived += 1

    return ExperimentResults(
        runs=runs,
        max_steps=max_steps,
        seed=seed,
        survival_steps=survival_steps,
        food_collected=food_collected,
        survived=survived,
    )


if __name__ == "__main__":
    results = run_experiment()
    print(results.report())
