"""Câmera independente dos agentes, com arraste e zoom ancorado no cursor.

A posição (x, y) representa o canto superior esquerdo visível em coordenadas
fracionárias do mundo. O tamanho da viewport é fixo em pixels.
"""


class Camera:
    def __init__(
        self,
        world_width: int,
        world_height: int,
        view_width: int,
        view_height: int,
    ) -> None:
        if min(world_width, world_height, view_width, view_height) < 1:
            raise ValueError("As dimensões do mundo e da câmera devem ser positivas.")

        self.world_width = world_width
        self.world_height = world_height
        self.view_width = min(view_width, world_width)
        self.view_height = min(view_height, world_height)
        self.cell_size = 30
        self.viewport_width_px = self.view_width * self.cell_size
        self.viewport_height_px = self.view_height * self.cell_size
        self.x = (world_width - self.view_width) / 2
        self.y = (world_height - self.view_height) / 2
        self._clamp()

    def configure_viewport(
        self, viewport_width_px: int, viewport_height_px: int, cell_size: int
    ) -> None:
        if min(viewport_width_px, viewport_height_px, cell_size) < 1:
            raise ValueError("As dimensões da viewport devem ser positivas.")
        center_x = self.x + self.visible_width / 2
        center_y = self.y + self.visible_height / 2
        self.viewport_width_px = viewport_width_px
        self.viewport_height_px = viewport_height_px
        self.cell_size = cell_size
        self.x = center_x - self.visible_width / 2
        self.y = center_y - self.visible_height / 2
        self._clamp()

    @property
    def visible_width(self) -> float:
        return self.viewport_width_px / self.cell_size

    @property
    def visible_height(self) -> float:
        return self.viewport_height_px / self.cell_size

    def pan_pixels(self, dx: int, dy: int, cell_size: int | None = None) -> None:
        """Move a câmera conforme o arraste do mouse em pixels da tela."""
        size = self.cell_size if cell_size is None else cell_size
        if size <= 0:
            raise ValueError("O tamanho da célula deve ser positivo.")
        self.x -= dx / size
        self.y -= dy / size
        self._clamp()

    def zoom_at(
        self,
        mouse_x: int,
        mouse_y: int,
        grid_x: int,
        grid_y: int,
        new_cell_size: int,
    ) -> None:
        """Altera o zoom mantendo fixa a coordenada do mundo sob o cursor."""
        if new_cell_size <= 0:
            raise ValueError("O tamanho da célula deve ser positivo.")

        offset_x = mouse_x - grid_x
        offset_y = mouse_y - grid_y
        world_x = self.x + offset_x / self.cell_size
        world_y = self.y + offset_y / self.cell_size

        self.cell_size = new_cell_size
        self.x = world_x - offset_x / self.cell_size
        self.y = world_y - offset_y / self.cell_size
        self._clamp()

    def _clamp(self) -> None:
        max_x = max(0.0, self.world_width - self.visible_width)
        max_y = max(0.0, self.world_height - self.visible_height)
        self.x = max(0.0, min(self.x, max_x))
        self.y = max(0.0, min(self.y, max_y))
