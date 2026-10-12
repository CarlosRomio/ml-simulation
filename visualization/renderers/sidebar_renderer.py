"""Renderização do painel de estado e métricas da simulação."""

import pygame

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

        agent = simulation.agent
        if not agent.alive:
            status, status_color = "MORTO", ENERGY_LOW_COLOR
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
        self._text(screen, status, 133, self.font, status_color)

        self._text(screen, "MÉTRICAS", 185, self.small_font, MUTED_COLOR)
        self._text(screen, f"Passos: {simulation.steps}", 212)
        self._text(screen, f"Plantas: {plant_counts['total']}", 242)
        self._text(screen, f"  Sementes: {plant_counts['seeds']}", 268, self.small_font)
        self._text(screen, f"  Crescendo: {plant_counts['growing']}", 291, self.small_font)
        self._text(screen, f"  Maduras: {plant_counts['mature']}", 314, self.small_font)
        self._text(screen, f"Coletada: {simulation.metrics.food_collected}", 341)

        self._text(screen, "ENERGIA", 382, self.small_font, MUTED_COLOR)
        ratio = agent.energy / agent.max_energy if agent.max_energy > 0 else 0.0
        ratio = max(0.0, min(1.0, ratio))
        self._text(screen, f"{agent.energy:.0f} / {agent.max_energy:.0f}", 407)

        bar_rect = pygame.Rect(GRID_PADDING, 438, SIDEBAR_WIDTH - GRID_PADDING * 2, 16)
        pygame.draw.rect(screen, CELL_COLOR, bar_rect)
        fill_rect = pygame.Rect(
            bar_rect.x, bar_rect.y, int(bar_rect.width * ratio), bar_rect.height
        )
        energy_color = ENERGY_LOW_COLOR if ratio <= 0.25 else ENERGY_COLOR
        if fill_rect.width > 0:
            pygame.draw.rect(screen, energy_color, fill_rect)
        pygame.draw.rect(screen, GRID_COLOR, bar_rect, width=1)

        self._text(screen, "VELOCIDADE", 470, self.small_font, MUTED_COLOR)
        self._text(screen, f"{effective_speed:g} passos/s", 495)
        self._text(screen, "CONTROLES", 530, self.small_font, MUTED_COLOR)
        self._text(screen, "1 - Normal", 555, self.small_font)
        self._text(screen, "2 - Rápido", 578, self.small_font)
        self._text(screen, "3 - Turbo", 601, self.small_font)
        self._text(screen, "ESPAÇO - Pausar", 624, self.small_font)
        self._text(screen, "ESC - Encerrar", 647, self.small_font)

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
