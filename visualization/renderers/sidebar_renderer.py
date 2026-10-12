"""Renderização do painel de estado e métricas da simulação."""

import pygame

from agents.species import Species
from environment.resources import Water

from visualization.rendering_config import (
    CELL_COLOR,
    ENERGY_COLOR,
    ENERGY_LOW_COLOR,
    GRID_PADDING,
    GRID_COLOR,
    MUTED_COLOR,
    PANEL_COLOR,
    SIDEBAR_WIDTH,
    TEXT_COLOR,
)


class SidebarRenderer:
    def __init__(self) -> None:
        self.title_font = pygame.font.SysFont("consolas", 23, bold=True)
        self.font = pygame.font.SysFont("consolas", 18)
        self.small_font = pygame.font.SysFont("consolas", 15)

    def draw(
        self,
        screen: pygame.Surface,
        simulation,
        *,
        window_height: int,
        paused: bool,
        effective_speed: float,
        plant_counts: dict[str, int],
    ) -> None:
        sidebar = pygame.Rect(0, 0, SIDEBAR_WIDTH, window_height)
        pygame.draw.rect(screen, PANEL_COLOR, sidebar)

        agent = next(iter(simulation.alive_agents), simulation.agent)
        alive_count = len(simulation.alive_agents)
        animal_count = len(simulation.alive_herbivores)
        if alive_count == 0 and animal_count == 0:
            status, status_color = "POPULAÇÃO MORTA", ENERGY_LOW_COLOR
        elif paused:
            status, status_color = "PAUSADO", MUTED_COLOR
        else:
            status, status_color = "EXECUTANDO", ENERGY_COLOR

        self._text(screen, "ML SIMULATION", 24, self.title_font)
        self._text(screen, "SURVIVAL", 54, self.small_font, MUTED_COLOR)
        pygame.draw.line(
            screen, GRID_COLOR, (GRID_PADDING, 85),
            (SIDEBAR_WIDTH - GRID_PADDING, 85), 1,
        )

        self._text(screen, "ESTADO", 108, self.small_font, MUTED_COLOR)
        self._text(screen, status, 133, self.small_font, status_color)

        self._text(screen, "MÉTRICAS", 185, self.small_font, MUTED_COLOR)
        self._text(screen, f"Passos: {simulation.steps}", 212)
        self._text(screen, f"Humanos: {alive_count}/{len(simulation.agents)}", 238, self.small_font)
        self._text(screen, f"Plantas: {plant_counts['total']}", 265)
        water_count = len(simulation.world.get_water_positions())
        herbivores = animal_count
        self._text(screen, f"Água: {water_count} fontes", 286, self.small_font, (90, 190, 235))
        self._text(screen, f"Herbívoros: {herbivores}/{len(simulation.herbivores)}", 308, self.small_font, (126, 210, 112))
        self._text(screen, f"Ataques: {simulation.attacks} | Caças: {simulation.animals_killed}", 423, self.small_font)
        self._text(screen, f"  Sementes: {plant_counts['seeds']}", 333, self.small_font)
        self._text(screen, f"  Crescendo: {plant_counts['growing']}", 355, self.small_font)
        self._text(screen, f"  Maduras: {plant_counts['mature']}", 377, self.small_font)
        total_food = sum(m.food_collected for m in simulation.metrics_by_agent.values())
        self._text(screen, f"Coletada: {total_food}", 400)

        self._text(screen, "ESTAMINA (AGENTE)", 448, self.small_font, MUTED_COLOR)
        ratio = agent.energy / agent.max_energy if agent.max_energy > 0 else 0.0
        ratio = max(0.0, min(1.0, ratio))
        self._text(screen, f"{agent.energy:.0f} / {agent.max_energy:.0f}", 473)

        bar_rect = pygame.Rect(GRID_PADDING, 504, SIDEBAR_WIDTH - GRID_PADDING * 2, 16)
        pygame.draw.rect(screen, CELL_COLOR, bar_rect)
        fill_rect = pygame.Rect(
            bar_rect.x, bar_rect.y, int(bar_rect.width * ratio), bar_rect.height
        )
        energy_color = ENERGY_LOW_COLOR if ratio <= 0.25 else ENERGY_COLOR
        if fill_rect.width > 0:
            pygame.draw.rect(screen, energy_color, fill_rect)
        pygame.draw.rect(screen, GRID_COLOR, bar_rect, width=1)


        self._text(screen, "FOME", 532, self.small_font, MUTED_COLOR)
        self._text(screen, f"{agent.hunger:.1f} / {agent.needs.max_hunger:.0f}", 553, self.small_font)
        hunger_ratio = max(0.0, min(1.0, agent.hunger / agent.needs.max_hunger))
        hunger_rect = pygame.Rect(GRID_PADDING, 575, SIDEBAR_WIDTH - GRID_PADDING * 2, 10)
        pygame.draw.rect(screen, CELL_COLOR, hunger_rect)
        if hunger_ratio > 0:
            hunger_color = (225, 100, 85) if agent.hunger >= agent.needs.starvation_threshold else (220, 170, 80)
            pygame.draw.rect(screen, hunger_color, pygame.Rect(hunger_rect.x, hunger_rect.y, int(hunger_rect.width * hunger_ratio), hunger_rect.height))
        pygame.draw.rect(screen, GRID_COLOR, hunger_rect, width=1)

        self._text(screen, "SEDE", 593, self.small_font, MUTED_COLOR)
        self._text(screen, f"{agent.thirst:.1f} / {agent.needs.max_thirst:.0f}", 614, self.small_font)
        thirst_ratio = max(0.0, min(1.0, agent.thirst / agent.needs.max_thirst))
        thirst_rect = pygame.Rect(GRID_PADDING, 636, SIDEBAR_WIDTH - GRID_PADDING * 2, 10)
        pygame.draw.rect(screen, CELL_COLOR, thirst_rect)
        if thirst_ratio > 0:
            thirst_color = (225, 100, 85) if agent.thirst >= agent.needs.dehydration_threshold else (90, 190, 235)
            pygame.draw.rect(screen, thirst_color, pygame.Rect(thirst_rect.x, thirst_rect.y, int(thirst_rect.width * thirst_ratio), thirst_rect.height))
        pygame.draw.rect(screen, GRID_COLOR, thirst_rect, width=1)

        self._text(screen, "VELOCIDADE", 596, self.small_font, MUTED_COLOR)
        self._text(screen, f"{effective_speed:g} passos/s", 687)
        self._text(screen, "CONTROLES", 644, self.small_font, MUTED_COLOR)
        self._text(screen, "1 - Normal", 667, self.small_font)
        self._text(screen, "2 - Rápido", 690, self.small_font)
        self._text(screen, "3 - Turbo", 713, self.small_font)
        self._text(screen, "ESPAÇO - Pausar", 736, self.small_font)
        self._text(screen, "ESC - Encerrar", 759, self.small_font)

    @staticmethod
    def _text(
        screen: pygame.Surface,
        text: str,
        y: int,
        selected_font: pygame.font.Font | None = None,
        color: tuple[int, int, int] = TEXT_COLOR,
    ) -> None:
        # x fixo por enquanto; o painel mantém a mesma margem visual.
        if selected_font is None:
            selected_font = pygame.font.SysFont("consolas", 18)
        surface = selected_font.render(text, True, color)
        screen.blit(surface, (GRID_PADDING, y))
