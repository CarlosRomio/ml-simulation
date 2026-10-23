"""Contrato compartilhado para planejamento de rotas e próximo movimento.

O serviço centraliza a semântica de navegação sem decidir qual objetivo uma
entidade deve perseguir. As políticas de cada espécie continuam responsáveis
pela seleção e persistência dos alvos.
"""
from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass
from enum import Enum, auto

from agents.navigation.bfs import Position, find_path
from environment.world import World


Pathfinder = Callable[[World, Position, Position], list[Position] | None]


class NavigationStatus(Enum):
    """Resultado semântico de uma tentativa de planejamento."""

    PATH_FOUND = auto()
    ALREADY_AT_GOAL = auto()
    INVALID_START = auto()
    INVALID_GOAL = auto()
    TEMPORARILY_BLOCKED = auto()
    UNREACHABLE = auto()


@dataclass(frozen=True)
class NavigationResult:
    """Resultado explícito sem misturar ausência de rota com alvo inválido."""

    status: NavigationStatus
    path: list[Position] | None = None
    reason: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status in {
            NavigationStatus.PATH_FOUND,
            NavigationStatus.ALREADY_AT_GOAL,
        }


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

    def plan_route(
        self,
        world: World,
        start: Position,
        goal: Position,
        *,
        blocked_positions: Collection[Position] | None = None,
    ) -> NavigationResult:
        """Planeja uma rota e informa por que não foi possível obtê-la.

        Ocupação dinâmica é tratada como impedimento temporário; posições fora
        do mundo ou destinos não transitáveis são inválidos. A API antiga
        ``find_path`` continua disponível para os chamadores que só precisam
        da lista de posições.
        """
        for position in (start, goal):
            x, y = position
            if not (0 <= x < world.width and 0 <= y < world.height):
                status = NavigationStatus.INVALID_START if position == start else NavigationStatus.INVALID_GOAL
                return NavigationResult(status, reason="OUT_OF_BOUNDS")

        # A entidade pode estar sobre uma célula que deixou de ser transitável
        # depois que ela entrou nela (por exemplo, uma planta que mudou de
        # estado). A busca BFS permite sair da posição inicial mesmo nesse caso;
        # rejeitar o início aqui mudaria essa semântica e poderia prender o agente.
        # O destino, por outro lado, precisa continuar sendo transitável.
        if not world.is_walkable(*goal):
            return NavigationResult(NavigationStatus.INVALID_GOAL, reason="GOAL_NOT_WALKABLE")
        if start == goal:
            return NavigationResult(NavigationStatus.ALREADY_AT_GOAL, path=[start])

        blocked = set(blocked_positions or ())
        blocked.discard(start)
        if goal in blocked:
            return NavigationResult(NavigationStatus.TEMPORARILY_BLOCKED, reason="GOAL_OCCUPIED")

        path = self.find_path(world, start, goal, blocked_positions=blocked)
        if path is not None:
            return NavigationResult(NavigationStatus.PATH_FOUND, path=path)

        # Distingue bloqueios dinâmicos de impossibilidade estrutural. Esta
        # segunda busca só ocorre quando a busca com bloqueios falha.
        if blocked and self.find_path(world, start, goal) is not None:
            return NavigationResult(NavigationStatus.TEMPORARILY_BLOCKED, reason="OCCUPANCY_BLOCKS_ALL_ROUTES")
        return NavigationResult(NavigationStatus.UNREACHABLE, reason="NO_VALID_ROUTE")

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
