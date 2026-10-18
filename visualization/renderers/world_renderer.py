"""Renderização do terreno, obstáculos e estágios das plantas."""

import pygame

from environment.obstacles import ObstacleType
from environment.resources import MaterialKind, MaterialResource, Plant, PlantState, Water
from environment.storage import Storage
from environment.shelter import Shelter
from visualization.rendering_config import (
    CELL_COLOR,
    FOOD_COLOR,
    GRID_COLOR,
    GROWING_LEAF_COLOR,
    GROWING_STEM_COLOR,
    ROCK_COLOR,
    SEED_COLOR,
    TREE_LEAF_COLOR,
    TREE_TRUNK_COLOR,
    UNSEEN_OVERLAY,
    WOOD_RESOURCE_COLOR,
    STONE_RESOURCE_COLOR,
    FIBER_RESOURCE_COLOR,
)


class WorldRenderer:
    """Desenha a porção do mundo atualmente visível na tela."""

    def __init__(self) -> None:
        self._unseen_overlay: pygame.Surface | None = None
        self._overlay_cell_size = 0

    def draw(
        self,
        screen: pygame.Surface,
        world,
        *,
        camera_x: int,
        camera_y: int,
        view_width: float,
        view_height: float,
        cell_size: int,
        grid_x: int,
        grid_y: int,
        viewport_width_px: int,
        viewport_height_px: int,
        visible_positions: set[tuple[int, int]] | None = None,
    ) -> None:
        """Desenha células dentro da janela de visualização.

        ``visible_positions=None`` mostra o mundo sem aplicar a camada de
        percepção. Um conjunto de posições aplica o escurecimento existente.
        """
        overlay = self._get_unseen_overlay(cell_size)
        # A origem da câmera pode ser fracionária para que o arraste seja suave.
        first_world_x = max(0, int(camera_x))
        first_world_y = max(0, int(camera_y))
        last_world_x = min(world.width, int(camera_x + view_width) + 1)
        last_world_y = min(world.height, int(camera_y + view_height) + 1)

        viewport = pygame.Rect(
            grid_x, grid_y, viewport_width_px, viewport_height_px
        )
        previous_clip = screen.get_clip()
        screen.set_clip(viewport)
        try:
            for world_y in range(first_world_y, last_world_y):
                screen_y = grid_y + round((world_y - camera_y) * cell_size)
                for world_x in range(first_world_x, last_world_x):
                    screen_x = grid_x + round((world_x - camera_x) * cell_size)
                    cell = world.get_cell(world_x, world_y)
                    rect = pygame.Rect(screen_x, screen_y, cell_size, cell_size)

                    pygame.draw.rect(screen, CELL_COLOR, rect)
                    pygame.draw.rect(screen, GRID_COLOR, rect, width=1)

                    if cell.obstacle == ObstacleType.TREE:
                        self._draw_tree(screen, rect, cell_size)
                    elif cell.obstacle == ObstacleType.ROCK:
                        self._draw_rock(screen, rect, cell_size)
                    elif isinstance(cell.resource, Plant):
                        self._draw_plant(screen, rect, cell.resource.state, cell_size)
                    elif isinstance(cell.resource, Water):
                        self._draw_water(screen, rect, cell_size)
                    elif isinstance(cell.resource, MaterialResource):
                        material_color = {
                            MaterialKind.WOOD: WOOD_RESOURCE_COLOR,
                            MaterialKind.STONE: STONE_RESOURCE_COLOR,
                            MaterialKind.FIBER: FIBER_RESOURCE_COLOR,
                        }[cell.resource.kind]
                        pygame.draw.circle(
                            screen, material_color, rect.center, max(3, cell_size // 5)
                        )
                        if cell_size >= 20:
                            label = {
                                MaterialKind.WOOD: "M",
                                MaterialKind.STONE: "P",
                                MaterialKind.FIBER: "F",
                            }[cell.resource.kind]
                            font = pygame.font.SysFont("consolas", max(10, cell_size // 3), bold=True)
                            text = font.render(label, True, (30, 32, 35))
                            screen.blit(text, text.get_rect(center=rect.center))
                    elif cell.resource is not None:
                        # Compatibilidade visual com recursos antigos, como Food.
                        pygame.draw.circle(
                            screen, FOOD_COLOR, rect.center, max(2, cell_size // 6)
                        )

                    if isinstance(cell.structure, Shelter):
                        roof = [(rect.left + cell_size // 8, rect.centery),
                                (rect.centerx, rect.top + cell_size // 8),
                                (rect.right - cell_size // 8, rect.centery)]
                        pygame.draw.rect(screen, (159, 116, 74),
                                         pygame.Rect(rect.left + cell_size // 5, rect.centery,
                                                     max(2, cell_size * 3 // 5), max(2, cell_size // 3)))
                        pygame.draw.polygon(screen, (110, 65, 43), roof)

                    if isinstance(cell.structure, Storage) and not isinstance(cell.structure, Shelter):
                        # Depósito desenhado sobre a célula, sem bloquear o recurso
                        # ou a movimentação caso futuramente coexistam camadas.
                        chest = rect.inflate(-max(4, cell_size // 5), -max(4, cell_size // 4))
                        pygame.draw.rect(screen, (130, 88, 49), chest, border_radius=max(1, cell_size // 12))
                        pygame.draw.rect(screen, (207, 166, 91), chest, width=max(1, cell_size // 16), border_radius=max(1, cell_size // 12))
                        pygame.draw.line(screen, (232, 202, 137), (chest.left, chest.centery), (chest.right, chest.centery), max(1, cell_size // 12))
                        pygame.draw.rect(screen, (62, 57, 46), pygame.Rect(chest.centerx - max(1, cell_size // 18), chest.centery - max(1, cell_size // 16), max(2, cell_size // 9), max(3, cell_size // 8)))

                    if (
                        visible_positions is not None
                        and (world_x, world_y) not in visible_positions
                    ):
                        screen.blit(overlay, rect.topleft)
        finally:
            screen.set_clip(previous_clip)

    @staticmethod
    def _draw_tree(screen: pygame.Surface, rect: pygame.Rect, cell_size: int) -> None:
        trunk_width = max(3, cell_size // 5)
        trunk_height = max(4, cell_size // 3)
        pygame.draw.rect(
            screen,
            TREE_TRUNK_COLOR,
            pygame.Rect(
                rect.centerx - trunk_width // 2,
                rect.bottom - trunk_height - 2,
                trunk_width,
                trunk_height,
            ),
        )
        pygame.draw.circle(
            screen,
            TREE_LEAF_COLOR,
            (rect.centerx, rect.centery - cell_size // 8),
            max(4, cell_size // 3),
        )

    @staticmethod
    def _draw_rock(screen: pygame.Surface, rect: pygame.Rect, cell_size: int) -> None:
        pygame.draw.ellipse(
            screen,
            ROCK_COLOR,
            rect.inflate(-max(4, cell_size // 5), -max(4, cell_size // 4)),
        )


    @staticmethod
    def _draw_water(screen: pygame.Surface, rect: pygame.Rect, cell_size: int) -> None:
        """Desenha uma fonte de água azul, distinguível das plantas maduras."""
        water_rect = rect.inflate(-max(3, cell_size // 7), -max(3, cell_size // 5))
        pygame.draw.ellipse(screen, (35, 116, 177), water_rect)
        highlight = pygame.Rect(0, 0, max(3, cell_size // 3), max(2, cell_size // 8))
        highlight.center = (rect.centerx - cell_size // 10, rect.centery - cell_size // 8)
        pygame.draw.ellipse(screen, (112, 205, 238), highlight)
        pygame.draw.arc(screen, (68, 165, 214), water_rect, 0.15, 2.8, max(1, cell_size // 18))

    @staticmethod
    def _draw_plant(
        screen: pygame.Surface,
        rect: pygame.Rect,
        state: PlantState,
        cell_size: int,
    ) -> None:
        cx, cy = rect.center

        if state == PlantState.SEED:
            # Pequena semente marrom-dourada com um ponto de destaque.
            seed_rect = pygame.Rect(0, 0, max(4, cell_size // 4), max(3, cell_size // 6))
            seed_rect.center = (cx, cy + cell_size // 8)
            pygame.draw.ellipse(screen, SEED_COLOR, seed_rect)
            pygame.draw.circle(
                screen,
                (239, 216, 158),
                (cx - max(1, cell_size // 16), cy + cell_size // 8),
                max(1, cell_size // 20),
            )
            return

        if state == PlantState.GROWING:
            stem_width = max(2, cell_size // 12)
            stem_bottom = rect.bottom - max(3, cell_size // 5)
            stem_top = rect.centery - max(2, cell_size // 8)
            pygame.draw.line(
                screen,
                GROWING_STEM_COLOR,
                (cx, stem_bottom),
                (cx, stem_top),
                stem_width,
            )
            leaf_radius = max(2, cell_size // 7)
            pygame.draw.ellipse(
                screen,
                GROWING_LEAF_COLOR,
                pygame.Rect(cx - leaf_radius * 2, stem_top, leaf_radius * 2, leaf_radius),
            )
            pygame.draw.ellipse(
                screen,
                GROWING_LEAF_COLOR,
                pygame.Rect(cx, stem_top - leaf_radius // 2, leaf_radius * 2, leaf_radius),
            )
            return

        # Planta madura: mantém o verde usado para representar o alimento.
        pygame.draw.circle(screen, FOOD_COLOR, (cx, cy), max(2, cell_size // 6))

    def _get_unseen_overlay(self, cell_size: int) -> pygame.Surface:
        if self._unseen_overlay is None or self._overlay_cell_size != cell_size:
            self._unseen_overlay = pygame.Surface(
                (cell_size, cell_size), pygame.SRCALPHA
            )
            self._unseen_overlay.fill(UNSEEN_OVERLAY)
            self._overlay_cell_size = cell_size
        return self._unseen_overlay
