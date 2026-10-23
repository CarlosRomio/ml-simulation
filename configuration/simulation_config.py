from dataclasses import dataclass
from math import isfinite


@dataclass
class SimulationConfig:
    # Dimensões do mundo
    width: int = 30
    height: int = 30

    # Densidades relativas à área do mundo
    food_density: float = 0.02
    obstacle_density: float = 0.01
    water_density: float = 0.005
    wood_density: float = 0.01
    stone_density: float = 0.01

    # Capacidade de regeneração vegetal, escalada pela área do mundo.
    # A referência preserva a calibração experimental de 60x60 -> 300 plantas.
    plant_cap_reference_width: int = 60
    plant_cap_reference_height: int = 60
    plant_cap_reference_max: int = 300

    # Configuração da população
    agent_count: int = 1
    herbivore_count: int = 0
    carnivore_count: int = 0
    vision_radius: int = 6
    # Desvio-padrão da variação individual ao redor do perfil da espécie (escala 0..1).
    attribute_variation: float = 0.12

    # Parâmetros fisiológicos (mantêm os valores atuais por padrão)
    hunger_per_step: float = 0.25
    thirst_per_step: float = 0.2
    starvation_threshold: float = 90.0
    dehydration_threshold: float = 90.0
    starvation_damage_per_step: float | None = None
    dehydration_damage_per_step: float | None = None

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def food_count(self) -> int:
        return int(self.area * self.food_density)

    @property
    def water_count(self) -> int:
        return int(self.area * self.water_density)

    @property
    def obstacle_count(self) -> int:
        return int(self.area * self.obstacle_density)

    @property
    def wood_count(self) -> int:
        return int(self.area * self.wood_density)

    @property
    def stone_count(self) -> int:
        return int(self.area * self.stone_density)

    @property
    def plant_cap_density(self) -> float:
        """Capacidade de plantas por célula, definida pela referência calibrada."""
        reference_area = self.plant_cap_reference_width * self.plant_cap_reference_height
        if reference_area <= 0:
            raise ValueError("A área de referência do limite de plantas deve ser positiva.")
        return self.plant_cap_reference_max / reference_area

    @property
    def max_plants_capacity(self) -> int:
        """Limite de plantas proporcional à área do mundo."""
        if self.width <= 0 or self.height <= 0:
            raise ValueError("As dimensões do mundo devem ser positivas.")
        return max(1, round(self.plant_cap_density * self.area))

    @property
    def start_position(self) -> tuple[int, int]:
        return self.width // 2, self.height // 2

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("As dimensões do mundo devem ser positivas.")
        if self.plant_cap_reference_width <= 0 or self.plant_cap_reference_height <= 0:
            raise ValueError("As dimensões de referência do limite de plantas devem ser positivas.")
        if self.plant_cap_reference_max <= 0:
            raise ValueError("O limite de plantas de referência deve ser positivo.")
        if not 0 <= self.food_density <= 1:
            raise ValueError("A densidade de comida deve estar entre 0 e 1.")
        if not 0 <= self.water_density <= 1:
            raise ValueError("A densidade de água deve estar entre 0 e 1.")
        if not 0 <= self.obstacle_density <= 1:
            raise ValueError("A densidade de obstáculos deve estar entre 0 e 1.")
        if not 0 <= self.wood_density <= 1 or not 0 <= self.stone_density <= 1:
            raise ValueError("As densidades de madeira e pedra devem estar entre 0 e 1.")
        if self.food_density + self.obstacle_density + self.water_density + self.wood_density + self.stone_density >= 1:
            raise ValueError("A soma das densidades deve ser menor que 1.")
        if self.agent_count < 1:
            raise ValueError("A quantidade de agentes humanos deve ser positiva.")
        if self.herbivore_count < 0:
            raise ValueError("A quantidade de herbívoros não pode ser negativa.")
        if self.carnivore_count < 0:
            raise ValueError("A quantidade de carnívoros não pode ser negativa.")
        if self.agent_count + self.herbivore_count + self.carnivore_count + self.food_count + self.obstacle_count + self.water_count + self.wood_count + self.stone_count > self.area:
            raise ValueError(
                "Não há células suficientes para agentes, recursos e obstáculos."
            )
        if self.vision_radius < 0:
            raise ValueError("O raio de visão não pode ser negativo.")
        if not isfinite(self.attribute_variation) or self.attribute_variation < 0:
            raise ValueError("attribute_variation deve ser finito e não negativo.")
        for name in ("hunger_per_step", "thirst_per_step"):
            value = getattr(self, name)
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} deve ser finito e não negativo.")
        for name in ("starvation_threshold", "dehydration_threshold"):
            value = getattr(self, name)
            if not 0 <= value <= 100:
                raise ValueError(f"{name} deve estar entre 0 e 100.")
        for name in ("starvation_damage_per_step", "dehydration_damage_per_step"):
            value = getattr(self, name)
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError(f"{name} deve ser finito e não negativo.")
