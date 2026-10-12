"""Câmera independente dos agentes, com movimento por arraste do mouse.

As coordenadas da câmera são expressas em células do mundo e podem ser
fracionárias, permitindo deslocamento suave sem alterar o tamanho das células.
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

        # Começa centralizada no mundo, nunca em função da posição do agente.
        self.x = (world_width - self.view_width) / 2
        self.y = (world_height - self.view_height) / 2
        self._clamp()

    def pan_pixels(self, dx: int, dy: int, cell_size: int) -> None:
        """Move a câmera conforme o arraste do mouse em pixels da tela."""
        if cell_size <= 0:
            raise ValueError("O tamanho da célula deve ser positivo.")

        self.x -= dx / cell_size
        self.y -= dy / cell_size
        self._clamp()

    def _clamp(self) -> None:
        max_x = max(0.0, self.world_width - self.view_width)
        max_y = max(0.0, self.world_height - self.view_height)
        self.x = max(0.0, min(self.x, max_x))
        self.y = max(0.0, min(self.y, max_y))
