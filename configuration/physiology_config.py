"""Parâmetros temporais e fisiológicos dos humanos.

Um passo equivale a um minuto simulado. Os valores são parâmetros abstratos
calibráveis do modelo, não estimativas médicas de um humano real.
"""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class PhysiologyConfig:
    minutes_per_step: int = 1
    # Variação de fadiga por minuto. Fadiga cresce durante vigília e esforço.
    fatigue_wait_per_step: float = 0.10
    fatigue_walk_per_step: float = 0.15
    fatigue_run_per_step: float = 0.45
    fatigue_rest_per_step: float = 0.02
    # Sono: redução de fadiga por minuto dormindo; o abrigo melhora a recuperação.
    fatigue_sleep_recovery: float = 0.15
    fatigue_shelter_sleep_recovery: float = 0.18
    # Perfil específico de carnívoros: deslocamento e perseguição são frequentes,
    # portanto a fadiga precisa recuperar também durante pausas curtas.
    carnivore_fatigue_wait_per_step: float = 0.05
    carnivore_fatigue_walk_per_step: float = 0.10
    carnivore_fatigue_run_per_step: float = 0.30
    carnivore_fatigue_rest_recovery: float = 0.12
    carnivore_fatigue_sleep_recovery: float = 0.45
    carnivore_fatigue_shelter_sleep_recovery: float = 0.55
    sleep_start_threshold: float = 65.0
    sleep_end_threshold: float = 15.0
    sleep_wake_hunger_threshold: float = 50.0
    sleep_wake_thirst_threshold: float = 50.0
    sleep_wake_predator_radius: int = 4
    # Custos metabólicos adicionais de fome por minuto, além da taxa basal.
    hunger_wait_cost: float = 0.0
    hunger_walk_cost: float = 0.005
    hunger_run_cost: float = 0.025
    hunger_rest_cost: float = 0.0
    thirst_wait_cost: float = 0.0
    thirst_walk_cost: float = 0.005
    thirst_run_cost: float = 0.025
    thirst_rest_cost: float = 0.0
    # Recuperação de estamina por minuto.
    stamina_wait_recovery: float = 1.5
    stamina_rest_recovery: float = 4.0
    stamina_shelter_rest_recovery: float = 10.0
    stamina_sleep_recovery: float = 4.0
    stamina_run_cost: float = 5.0
    stamina_run_minimum: float = 15.0
    stamina_attack_cost: float = 5.0
    # Política adaptativa de estamina: correr preserva reserva para emergências;
    # o limiar de retomada é maior que o de início para evitar oscilações.
    stamina_run_start_ratio: float = 0.50
    stamina_run_continue_ratio: float = 0.30
    stamina_urgent_run_ratio: float = 0.18
    stamina_rest_start_ratio: float = 0.22
    stamina_rest_resume_ratio: float = 0.55
    # Reserva que deve permanecer disponível depois de um esforço planejado.
    stamina_reserve_ratio: float = 0.30
    stamina_low_recovery_ratio: float = 0.30
    stamina_low_recovery_bonus: float = 0.75

    def validate(self) -> None:
        if self.minutes_per_step != 1:
            raise ValueError("Nesta etapa, cada passo deve equivaler a exatamente um minuto.")
        for name in (
            "fatigue_wait_per_step", "fatigue_walk_per_step", "fatigue_run_per_step",
            "fatigue_rest_per_step", "fatigue_sleep_recovery", "fatigue_shelter_sleep_recovery",
            "carnivore_fatigue_wait_per_step", "carnivore_fatigue_walk_per_step",
            "carnivore_fatigue_run_per_step", "carnivore_fatigue_rest_recovery",
            "carnivore_fatigue_sleep_recovery", "carnivore_fatigue_shelter_sleep_recovery",
            "sleep_start_threshold", "sleep_end_threshold", "sleep_wake_hunger_threshold",
            "sleep_wake_thirst_threshold", "stamina_sleep_recovery", "stamina_run_cost",
            "stamina_run_minimum", "stamina_attack_cost", "hunger_wait_cost", "hunger_walk_cost",
            "hunger_run_cost", "hunger_rest_cost", "thirst_wait_cost",
            "thirst_walk_cost", "thirst_run_cost", "thirst_rest_cost", "stamina_wait_recovery",
            "stamina_rest_recovery", "stamina_shelter_rest_recovery",
            "stamina_run_start_ratio", "stamina_run_continue_ratio",
            "stamina_urgent_run_ratio", "stamina_rest_start_ratio",
            "stamina_rest_resume_ratio", "stamina_reserve_ratio", "stamina_low_recovery_ratio",
            "stamina_low_recovery_bonus",
        ):
            value = getattr(self, name)
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} deve ser finito e não negativo.")
        for name in (
            "stamina_run_start_ratio", "stamina_run_continue_ratio",
            "stamina_urgent_run_ratio", "stamina_rest_start_ratio",
            "stamina_rest_resume_ratio", "stamina_reserve_ratio", "stamina_low_recovery_ratio",
        ):
            if getattr(self, name) > 1.0:
                raise ValueError(f"{name} deve estar na escala 0..1.")
        if self.stamina_run_continue_ratio >= self.stamina_run_start_ratio:
            raise ValueError("stamina_run_continue_ratio deve ser menor que stamina_run_start_ratio.")
        if self.stamina_urgent_run_ratio > self.stamina_run_start_ratio:
            raise ValueError("stamina_urgent_run_ratio não pode exceder o limiar normal de corrida.")
        if self.stamina_rest_start_ratio >= self.stamina_rest_resume_ratio:
            raise ValueError("stamina_rest_start_ratio deve ser menor que stamina_rest_resume_ratio.")
        if self.sleep_end_threshold >= self.sleep_start_threshold:
            raise ValueError("sleep_end_threshold deve ser menor que sleep_start_threshold.")
        if self.sleep_start_threshold > 100.0 or self.sleep_end_threshold > 100.0:
            raise ValueError("Os limiares de fadiga devem estar na escala 0..100.")
        if self.sleep_wake_predator_radius < 0:
            raise ValueError("sleep_wake_predator_radius deve ser não negativo.")


DEFAULT_PHYSIOLOGY_CONFIG = PhysiologyConfig()
