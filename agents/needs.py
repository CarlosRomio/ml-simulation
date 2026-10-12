"""Estado fisiológico e regras de evolução das necessidades de um agente."""
from dataclasses import dataclass


@dataclass
class AgentNeeds:
    max_health: float = 100.0
    health: float = 100.0
    max_energy: float = 100.0
    energy: float = 100.0
    max_hunger: float = 100.0
    hunger: float = 20.0
    max_thirst: float = 100.0
    thirst: float = 20.0
    hunger_per_step: float = 0.25
    thirst_per_step: float = 0.2
    starvation_threshold: float = 90.0
    dehydration_threshold: float = 90.0
    damage_per_step: float = 1.0
    last_damage_cause: str | None = None
    dehydration_damage_per_step: float | None = None
    starvation_damage_per_step: float | None = None

    def __post_init__(self) -> None:
        for name in ("max_health", "max_energy", "max_hunger", "max_thirst"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} deve ser positivo.")
        for name in ("hunger_per_step", "thirst_per_step", "damage_per_step"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} não pode ser negativo.")
        for name in ("dehydration_damage_per_step", "starvation_damage_per_step"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} não pode ser negativo.")
        for value_name, max_name in (("health", "max_health"), ("energy", "max_energy"), ("hunger", "max_hunger"), ("thirst", "max_thirst")):
            value = getattr(self, value_name)
            if not 0 <= value <= getattr(self, max_name):
                raise ValueError(f"{value_name} deve estar entre zero e {max_name}.")

    @property
    def alive(self) -> bool:
        return self.health > 0

    def advance_step(self) -> None:
        """Aumenta fome/sede e aplica dano quando atingem níveis críticos."""
        self.last_damage_cause = None
        self.hunger = min(self.max_hunger, self.hunger + self.hunger_per_step)
        self.thirst = min(self.max_thirst, self.thirst + self.thirst_per_step)
        if self.hunger >= self.starvation_threshold:
            amount = self.damage_per_step if self.starvation_damage_per_step is None else self.starvation_damage_per_step
            self.damage(amount, cause="STARVATION")
        if self.thirst >= self.dehydration_threshold:
            amount = self.damage_per_step if self.dehydration_damage_per_step is None else self.dehydration_damage_per_step
            self.damage(amount, cause="DEHYDRATION")

    def damage(self, amount: float, cause: str | None = None) -> None:
        if amount < 0:
            raise ValueError("O dano não pode ser negativo.")
        previous_health = self.health
        self.health = max(0.0, self.health - amount)
        if self.health < previous_health and cause is not None:
            self.last_damage_cause = cause

    def eat(self, amount: float) -> None:
        if amount < 0:
            raise ValueError("A quantidade de alimento não pode ser negativa.")
        self.hunger = max(0.0, self.hunger - amount)

    def drink(self, amount: float) -> None:
        if amount < 0:
            raise ValueError("A quantidade de água não pode ser negativa.")
        self.thirst = max(0.0, self.thirst - amount)

    def restore_energy(self, amount: float) -> None:
        if amount < 0:
            raise ValueError("A recuperação de energia não pode ser negativa.")
        self.energy = min(self.max_energy, self.energy + amount)
