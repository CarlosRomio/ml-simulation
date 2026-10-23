"""Estado fisiológico e regras de evolução das necessidades de um indivíduo.

Convenções:
- saúde: condição física; chegar a zero significa morte;
- energia: estamina para ações exigentes; chegar a zero não mata;
- fome/sede: escalas de necessidade entre zero (satisfeita) e o máximo
  (necessidade extrema).

Os valores são unidades abstratas do simulador, não unidades fisiológicas reais.
"""
from dataclasses import dataclass, field
from math import isfinite


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
    max_fatigue: float = 100.0
    fatigue: float = 0.0
    starvation_threshold: float = 90.0
    dehydration_threshold: float = 90.0
    damage_per_step: float = 1.0
    last_damage_cause: str | None = None
    dehydration_damage_per_step: float | None = None
    starvation_damage_per_step: float | None = None
    last_damage_causes: tuple[str, ...] = field(default_factory=tuple, init=False)
    damage_by_cause: dict[str, float] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        positive_names = ("max_health", "max_energy", "max_hunger", "max_thirst", "max_fatigue")
        for name in positive_names:
            value = getattr(self, name)
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{name} deve ser finito e positivo.")

        nonnegative_names = (
            "hunger_per_step", "thirst_per_step", "damage_per_step",
            "starvation_threshold", "dehydration_threshold",
        )
        for name in nonnegative_names:
            value = getattr(self, name)
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} deve ser finito e não negativo.")
        for name in ("dehydration_damage_per_step", "starvation_damage_per_step"):
            value = getattr(self, name)
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError(f"{name} deve ser finito e não negativo.")

        for value_name, max_name in (
            ("health", "max_health"), ("energy", "max_energy"),
            ("hunger", "max_hunger"), ("thirst", "max_thirst"),
            ("fatigue", "max_fatigue"),
        ):
            value = getattr(self, value_name)
            if not isfinite(value) or not 0 <= value <= getattr(self, max_name):
                raise ValueError(f"{value_name} deve estar entre zero e {max_name}.")
        if self.starvation_threshold > self.max_hunger:
            raise ValueError("starvation_threshold não pode exceder max_hunger.")
        if self.dehydration_threshold > self.max_thirst:
            raise ValueError("dehydration_threshold não pode exceder max_thirst.")

    @property
    def alive(self) -> bool:
        return self.health > 0

    def advance_step(
        self, *, hunger_extra: float = 0.0, thirst_extra: float = 0.0, fatigue_delta: float = 0.0
    ) -> None:
        """Avança necessidades um minuto e aplica dano crítico uma vez por passo."""
        if not isfinite(hunger_extra) or hunger_extra < 0:
            raise ValueError("O custo metabólico adicional deve ser finito e não negativo.")
        if not isfinite(thirst_extra) or thirst_extra < 0:
            raise ValueError("O custo adicional de sede deve ser finito e não negativo.")
        if not isfinite(fatigue_delta):
            raise ValueError("A variação de fadiga deve ser finita.")
        self.last_damage_cause = None
        causes: list[str] = []
        self.hunger = min(self.max_hunger, self.hunger + self.hunger_per_step + hunger_extra)
        self.fatigue = max(0.0, min(self.max_fatigue, self.fatigue + fatigue_delta))
        self.thirst = min(self.max_thirst, self.thirst + self.thirst_per_step + thirst_extra)

        if self.hunger >= self.starvation_threshold:
            amount = self.damage_per_step if self.starvation_damage_per_step is None else self.starvation_damage_per_step
            if self.damage(amount, cause="STARVATION") > 0:
                causes.append("STARVATION")
        if self.thirst >= self.dehydration_threshold:
            amount = self.damage_per_step if self.dehydration_damage_per_step is None else self.dehydration_damage_per_step
            if self.damage(amount, cause="DEHYDRATION") > 0:
                causes.append("DEHYDRATION")
        self.last_damage_causes = tuple(causes)

    def damage(self, amount: float, cause: str | None = None) -> float:
        """Aplica dano e retorna a quantidade efetivamente removida da saúde."""
        if not isfinite(amount) or amount < 0:
            raise ValueError("O dano deve ser finito e não negativo.")
        previous_health = self.health
        self.health = max(0.0, self.health - amount)
        actual_damage = previous_health - self.health
        if actual_damage > 0 and cause is not None:
            self.last_damage_cause = cause
            self.damage_by_cause[cause] = self.damage_by_cause.get(cause, 0.0) + actual_damage
            self.last_damage_causes = tuple(dict.fromkeys((*self.last_damage_causes, cause)))
        return actual_damage

    def eat(self, amount: float) -> None:
        if not isfinite(amount) or amount < 0:
            raise ValueError("A quantidade de alimento deve ser finita e não negativa.")
        self.hunger = max(0.0, self.hunger - amount)

    def drink(self, amount: float) -> None:
        if not isfinite(amount) or amount < 0:
            raise ValueError("A quantidade de água deve ser finita e não negativa.")
        self.thirst = max(0.0, self.thirst - amount)

    def restore_health(self, amount: float) -> float:
        """Recupera saúde sem ultrapassar o máximo; retorna a cura efetiva."""
        if not isfinite(amount) or amount < 0:
            raise ValueError("A recuperação de saúde deve ser finita e não negativa.")
        previous_health = self.health
        self.health = min(self.max_health, self.health + amount)
        return self.health - previous_health

    def restore_energy(self, amount: float) -> None:
        if not isfinite(amount) or amount < 0:
            raise ValueError("A recuperação de energia deve ser finita e não negativa.")
        self.energy = min(self.max_energy, self.energy + amount)
