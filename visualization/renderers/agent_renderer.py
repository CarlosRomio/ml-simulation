"""Renderização de agentes independente da câmera."""

import pygame

from visualization.rendering_config import AGENT_COLOR
from agents.species import Species


class AgentRenderer:
    def draw(
        self,
        screen: pygame.Surface,
        agent,
        *,
        camera_x: float,
        camera_y: float,
        cell_size: int,
        grid_x: int,
        grid_y: int,
    ) -> None:
        center = (
            grid_x + round((agent.x - camera_x) * cell_size) + cell_size // 2,
            grid_y + round((agent.y - camera_y) * cell_size) + cell_size // 2,
        )
        if not agent.alive:
            color = (115, 115, 115)
        elif agent.species == Species.HERBIVORE:
            color = (126, 210, 112)
        else:
            color = AGENT_COLOR
        radius = max(3, cell_size // 3)
        pygame.draw.circle(screen, color, center, radius)
        pygame.draw.circle(screen, (24, 34, 28), center, radius, width=max(1, cell_size // 18))
