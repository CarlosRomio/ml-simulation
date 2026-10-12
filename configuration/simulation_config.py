from dataclasses import dataclass


@dataclass
class SimulationConfig:
    # Dimensões do mundo
    width: int = 30
    height: int = 30

    # Densidades relativas à área do mundo
    food_density: float = 0.02
    obstacle_density: float = 0.01

    # Configuração da população
    agent_count: int = 1
    vision_radius: int = 6

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def food_count(self) -> int:
        return int(self.area * self.food_density)

    @property
    def obstacle_count(self) -> int:
        return int(self.area * self.obstacle_density)

    @property
    def start_position(self) -> tuple[int, int]:
        return self.width // 2, self.height // 2

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("As dimensões do mundo devem ser positivas.")
        if not 0 <= self.food_density <= 1:
            raise ValueError("A densidade de comida deve estar entre 0 e 1.")
        if not 0 <= self.obstacle_density <= 1:
            raise ValueError("A densidade de obstáculos deve estar entre 0 e 1.")
        if self.food_density + self.obstacle_density >= 1:
            raise ValueError("A soma das densidades deve ser menor que 1.")
        if self.agent_count < 1:
            raise ValueError("A quantidade de agentes deve ser positiva.")
        if self.agent_count + self.food_count + self.obstacle_count > self.area:
            raise ValueError(
                "Não há células suficientes para agentes, recursos e obstáculos."
            )
        if self.vision_radius < 0:
            raise ValueError("O raio de visão não pode ser negativo.")
