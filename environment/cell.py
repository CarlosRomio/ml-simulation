
from dataclasses import dataclass

from environment.obstacles import ObstacleType


@dataclass
class Cell:
    x: int
    y: int
    resource: object | None = None
    obstacle: ObstacleType | None = None

    @property
    def is_walkable(self) -> bool:
        if self.obstacle is not None:
            return False

        if self.resource is not None:
            return self.resource.is_walkable

        return True
