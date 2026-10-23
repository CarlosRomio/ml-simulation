"""Seleção e validação de objetivos antes do planejamento de rotas.

O seletor ordena candidatos e coordena tentativas de navegação. A política de
cada espécie continua decidindo quando procurar cada tipo de recurso e quais
prioridades aplicar.
"""
from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass

from agents.navigation.service import NavigationResult, NavigationService
from environment.world import World

Position = tuple[int, int]
Pathfinder = Callable[[World, Position, Position], list[Position] | None]


@dataclass(frozen=True)
class TargetSelectionAttempt:
    """Resultado de planejar uma rota para um candidato específico."""

    target: Position
    navigation: NavigationResult
    static_path: list[Position] | None
    blocked_steps: tuple[Position, ...] = ()


@dataclass(frozen=True)
class TargetSelectionResult:
    """Resultado da seleção, incluindo tentativas para observabilidade."""

    target: Position | None
    navigation: NavigationResult | None
    attempts: tuple[TargetSelectionAttempt, ...]

    @property
    def succeeded(self) -> bool:
        return (
            self.target is not None
            and self.navigation is not None
            and self.navigation.succeeded
        )


class TargetSelector:
    """Ordena candidatos e seleciona um objetivo com rota válida."""

    @staticmethod
    def is_valid_goal(world: World, goal: Position) -> bool:
        """Valida limites do mundo e transitabilidade do destino atual."""
        x, y = goal
        return (
            0 <= x < world.width
            and 0 <= y < world.height
            and world.is_walkable(x, y)
        )

    @staticmethod
    def _ordered_positions(
        current_position: Position, positions: Iterable[Position]
    ) -> list[Position]:
        current_x, current_y = current_position
        return sorted(
            set(positions),
            key=lambda position: (
                abs(position[0] - current_x) + abs(position[1] - current_y),
                position[1],
                position[0],
            ),
        )

    def nearest_reachable_target(
        self,
        world: World,
        current_position: Position,
        positions: Iterable[Position],
        pathfinder: Pathfinder,
    ) -> tuple[Position, list[Position]] | None:
        """API legada: retorna o alvo alcançável mais próximo para deslocamento.

        Empates preservam a ordenação por distância Manhattan, coordenada y e
        coordenada x. A posição atual e rotas de comprimento zero são ignoradas.
        """
        for position in self._ordered_positions(current_position, positions):
            if position == current_position:
                continue
            if not self.is_valid_goal(world, position):
                continue
            path = pathfinder(world, current_position, position)
            if path is not None and len(path) > 1:
                return position, path
        return None

    def select_reachable_target(
        self,
        world: World,
        current_position: Position,
        positions: Iterable[Position],
        navigation: NavigationService,
        *,
        blocked_positions: Collection[Position] | None = None,
        capture_static_path: bool = True,
    ) -> TargetSelectionResult:
        """Seleciona o primeiro candidato alcançável pelo contrato de navegação.

        Ao contrário da API legada, aceita ``ALREADY_AT_GOAL``: em uma busca por
        água, estar sobre a fonte é um alvo válido. Cada tentativa mantém seu
        status e motivo, diferenciando destino inválido, bloqueio temporário e
        ausência de rota. O caminho estático de diagnóstico só é calculado
        quando há posições dinamicamente bloqueadas e a captura está habilitada.
        """
        blocked = set(blocked_positions or ())
        blocked.discard(current_position)
        attempts: list[TargetSelectionAttempt] = []

        for target in self._ordered_positions(current_position, positions):
            # O caminho sem bloqueios só é necessário para diagnosticar quais
            # ocupantes interceptariam a rota estática. Sem bloqueios dinâmicos,
            # essa busca seria redundante: plan_route já calcula a rota efetiva.
            static_path = (
                navigation.find_path(world, current_position, target)
                if capture_static_path and blocked
                else None
            )
            blocked_steps = tuple(
                step for step in (static_path or [])[1:] if step in blocked
            )
            result = navigation.plan_route(
                world, current_position, target, blocked_positions=blocked
            )
            attempts.append(
                TargetSelectionAttempt(
                    target=target,
                    navigation=result,
                    static_path=static_path,
                    blocked_steps=blocked_steps,
                )
            )
            if result.succeeded:
                return TargetSelectionResult(target, result, tuple(attempts))

        return TargetSelectionResult(None, None, tuple(attempts))
