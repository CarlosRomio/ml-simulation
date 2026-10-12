
from dataclasses import dataclass


@dataclass
class SimulationMetrics:
    # Duração e encerramento
    steps: int = 0
    agent_lifetime_steps: int = 0
    simulated_time_seconds: float = 0.0
    termination_cause: str = "RUNNING"

    # Energia e recursos
    initial_energy: float = 0.0
    final_energy: float = 0.0
    initial_health: float = 100.0
    final_health: float = 100.0
    final_hunger: float = 0.0
    final_thirst: float = 0.0
    critical_thirst_steps: int = 0
    dehydration_damage_steps: int = 0
    first_dehydration_damage_step: int | None = None
    average_health: float = 100.0
    average_hunger: float = 0.0
    average_thirst: float = 0.0
    health_sum: float = 0.0
    hunger_sum: float = 0.0
    thirst_sum: float = 0.0
    need_samples: int = 0
    water_drinks: int = 0
    water_units_consumed: float = 0.0
    food_collected: int = 0
    energy_sum: float = 0.0
    energy_samples: int = 0

    # Comportamento
    movement_steps: int = 0
    idle_steps: int = 0
    distance_travelled: float = 0.0
    unique_positions_visited: int = 0
    max_steps_without_food: int = 0

    # Interação multiagente
    movement_attempts: int = 0
    blocked_movement_attempts: int = 0
    blocked_by_agent_attempts: int = 0
    blocked_by_environment_attempts: int = 0

    @property
    def survived(self) -> bool:
        return self.termination_cause == "STEP_LIMIT"

    @property
    def average_energy(self) -> float:
        if self.energy_samples == 0:
            return 0.0
        return self.energy_sum / self.energy_samples

    def report(self) -> str:
        if self.termination_cause == "STEP_LIMIT":
            final_state = "SOBREVIVEU AO LIMITE"
        elif self.termination_cause == "RUNNING":
            final_state = "EM EXECUÇÃO"
        else:
            final_state = "MORTO"

        return (
            "\n=== Resultado da simulação ===\n"
            f"Estado final: {final_state}\n"
            f"Causa: {self.termination_cause}\n"
            f"Passos executados: {self.steps}\n"
            f"Tempo simulado: {self.simulated_time_seconds:.2f} s\n"
            f"Comida coletada: {self.food_collected}\n"
            f"Energia inicial: {self.initial_energy:.1f}\n"
            f"Energia final: {self.final_energy:.1f}\n"
            f"Vida final: {self.final_health:.1f}\n"
            f"Fome final: {self.final_hunger:.1f}\n"
            f"Sede final: {self.final_thirst:.1f}\n"
            f"Energia média: {self.average_energy:.2f}\n"
            f"Passos em movimento: {self.movement_steps}\n"
            f"Passos sem deslocamento: {self.idle_steps}\n"
            f"Distância percorrida: {self.distance_travelled:.2f}\n"
            f"Posições únicas visitadas: {self.unique_positions_visited}\n"
            f"Maior intervalo sem comida: {self.max_steps_without_food} passos\n"
            f"Tentativas de movimento: {self.movement_attempts}\n"
            f"Movimentos bloqueados: {self.blocked_movement_attempts}\n"
            f"Bloqueios por agentes: {self.blocked_by_agent_attempts}\n"
            f"Bloqueios pelo ambiente: {self.blocked_by_environment_attempts}\n"
        )
