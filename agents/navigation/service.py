"""Contrato compartilhado para planejamento de rotas e próximo movimento.

O serviço centraliza a semântica de navegação sem decidir qual objetivo uma
entidade deve perseguir. As políticas de cada espécie continuam responsáveis
pela seleção e persistência dos alvos.
"""
from __future__ import annotations

from collections.abc import Callable, Collection

from agents.navigation.bfs import Position, find_path
from environment.world import World


Pathfinder = Callable[[World, Position, Position], list[Position] | None]


class NavigationService:
    """Planeja caminhos transitáveis e converte caminhos em movimentos.

    ``pathfinder`` mantém compatibilidade com os seletores existentes que
    recebem uma função de busca injetável. Restrições de ocupação dinâmica são
    aplicadas pelo BFS compartilhado; políticas que injetam um pathfinder
    customizado continuam podendo usá-lo quando não há bloqueios extras.
    """

    def __init__(self, pathfinder: Pathfinder = find_path) -> None:
        self._pathfinder = pathfinder

    def find_path(
        self,
        world: World,
        start: Position,
        goal: Position,
        *,
        blocked_positions: Collection[Position] | None = None,
    ) -> list[Position] | None:
        blocked = set(blocked_positions or ())
        if not blocked:
            return self._pathfinder(world, start, goal)

        if self._pathfinder is find_path:
            return find_path(world, start, goal, blocked_positions=blocked)

        # Um pathfinder customizado não precisa conhecer o argumento de
        # ocupação dinâmica. Para não retornar uma rota sabidamente inválida,
        # rejeitamos seu caminho se ele atravessar uma célula bloqueada.
        path = self._pathfinder(world, start, goal)
        if path is None or any(position in blocked for position in path[1:]):
            return None
        return path

    @staticmethod
    def next_step(path: list[Position] | None, current: Position) -> Position | None:
        """Retorna o deslocamento para o próximo passo, ou None se não aplicável."""
        if not path:
            return None
        try:
            index = path.index(current)
        except ValueError:
            return None
        if index + 1 >= len(path):
            return None
        next_position = path[index + 1]
        dx = next_position[0] - current[0]
        dy = next_position[1] - current[1]
        if abs(dx) + abs(dy) != 1:
            return None
        return dx, dy
