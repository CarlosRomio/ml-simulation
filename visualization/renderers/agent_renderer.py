"""Renderização de agentes independente da câmera."""

import pygame

from visualization.rendering_config import AGENT_COLOR
from agents.species import Species


class AgentRenderer:
    def __init__(self) -> None:
        self.label_font = pygame.font.SysFont("consolas", 11, bold=True)

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
        selected: bool = False,
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
        if selected:
            pygame.draw.circle(screen, (245, 220, 90), center, radius + max(2, cell_size // 10), width=max(2, cell_size // 12))
        pygame.draw.circle(screen, color, center, radius)
        pygame.draw.circle(screen, (24, 34, 28), center, radius, width=max(1, cell_size // 18))
        # Em zoom alto rotula todos os humanos; em zoom distante mantém apenas
        # o ID do indivíduo selecionado para evitar poluição visual.
        if selected or cell_size >= 16:
            label = self.label_font.render(agent.agent_id or "H?", True, (250, 245, 225))
            label_rect = label.get_rect(midbottom=(center[0], center[1] - radius - 2))
            background = label_rect.inflate(4, 2)
            pygame.draw.rect(screen, (28, 34, 30), background, border_radius=2)
            screen.blit(label, label_rect)
