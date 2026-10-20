from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class SocialBehaviorConfig:
    """Parâmetros ajustáveis da memória e da formação de vínculos sociais."""

    affinity_gain_per_close_step: float = 0.025
    affinity_decay_per_far_step: float = 0.0005
    reunion_affinity_threshold: float = 0.2
    memory_ttl_steps: int = 30
    reunion_max_distance: int = 12

    def validate(self) -> None:
        for name in ("affinity_gain_per_close_step", "affinity_decay_per_far_step"):
            value = getattr(self, name)
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} deve ser finito e não negativo.")
        if not 0.0 <= self.reunion_affinity_threshold <= 1.0:
            raise ValueError("reunion_affinity_threshold deve estar entre 0 e 1.")
        if self.memory_ttl_steps < 1:
            raise ValueError("memory_ttl_steps deve ser pelo menos 1.")
        if self.reunion_max_distance < 1:
            raise ValueError("reunion_max_distance deve ser pelo menos 1.")
