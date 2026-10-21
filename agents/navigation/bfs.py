from collections import deque


Position = tuple[int, int]

# Movimentos ortogonais: cima, baixo, esquerda e direita.
MOVEMENTS: tuple[Position, ...] = (
    (0, -1),
    (0, 1),
    (-1, 0),
    (1, 0),
)


def find_path(
    world,
    start: Position,
    goal: Position,
    *,
    blocked_positions: set[Position] | None = None,
) -> list[Position] | None:
    """
    Encontra o caminho mais curto entre duas posições usando BFS.

    Retorna:
        Lista de posições incluindo início e destino.
        None se não existir um caminho válido.

    Observação:
        Esta primeira versão considera o mapa completo conhecido.
    """
    start_x, start_y = start
    goal_x, goal_y = goal

    blocked = set(blocked_positions or ())
    # A posição inicial é válida mesmo que o chamador a inclua no conjunto.
    blocked.discard(start)

    # Verifica se as posições estão dentro do mundo.
    for x, y in (start, goal):
        if not (0 <= x < world.width and 0 <= y < world.height):
            return None

    # O destino precisa ser transitável e não pode estar ocupado por outro
    # indivíduo quando a busca é usada para navegação dinâmica.
    if not world.is_walkable(goal_x, goal_y) or goal in blocked:
        return None

    if start == goal:
        return [start]

    queue = deque([start])

    # Guarda de onde cada posição foi alcançada.
    previous: dict[Position, Position | None] = {
        start: None
    }

    while queue:
        current = queue.popleft()

        if current == goal:
            break

        x, y = current

        for dx, dy in MOVEMENTS:
            neighbor = (x + dx, y + dy)
            nx, ny = neighbor

            if not (
                0 <= nx < world.width
                and 0 <= ny < world.height
            ):
                continue

            if neighbor in previous or neighbor in blocked:
                continue

            if not world.is_walkable(nx, ny):
                continue

            previous[neighbor] = current
            queue.append(neighbor)

    # O destino não foi alcançado.
    if goal not in previous:
        return None

    # Reconstrói a rota do destino até o início.
    path = []
    current = goal

    while current is not None:
        path.append(current)
        current = previous[current]

    path.reverse()

    return path