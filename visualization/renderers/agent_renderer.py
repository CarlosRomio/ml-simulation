"""Renderização do agente independente da câmera."""

import pygame

from visualization.rendering_config import AGENT_COLOR


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
        pygame.draw.circle(screen, AGENT_COLOR, center, max(3, cell_size // 3))
