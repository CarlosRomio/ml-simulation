from environment.world import World
from environment.cell import Cell


class Perception:

    def observe(
        self,
        world: World,
        x: int,
        y: int,
        radius: int,
    ) -> list[Cell]:
        if radius < 0:
            raise ValueError("radius não pode ser negativo")

        nearby_cells = []

        # Amplia levemente o alcance real da percepção.
        effective_radius = radius + 0.5
        search_radius = int(effective_radius + 0.5)

        min_x = max(0, x - search_radius)
        max_x = min(world.width - 1, x + search_radius)
        min_y = max(0, y - search_radius)
        max_y = min(world.height - 1, y + search_radius)

        for cell_y in range(min_y, max_y + 1):
            for cell_x in range(min_x, max_x + 1):
                distance_squared = (
                    (cell_x - x) ** 2
                    + (cell_y - y) ** 2
                )

                if distance_squared > effective_radius ** 2:
                    continue

                if not self._has_line_of_sight(
                    world, x, y, cell_x, cell_y
                ):
                    continue

                nearby_cells.append(
                    world.get_cell(cell_x, cell_y)
                )

        return nearby_cells

    def _has_line_of_sight(
        self,
        world: World,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
    ) -> bool:
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)

        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1

        error = dx - dy
        x, y = x0, y0

        while (x, y) != (x1, y1):
            double_error = 2 * error

            if double_error > -dy:
                error -= dy
                x += sx

            if double_error < dx:
                error += dx
                y += sy

            # O próprio obstáculo continua visível.
            if (x, y) == (x1, y1):
                break

            if world.get_cell(x, y).obstacle is not None:
                return False

        return True