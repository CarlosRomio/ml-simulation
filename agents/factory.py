"""Criação reproduzível de populações de agentes em um mundo existente."""

import random
from random import Random

from agents.agent import Agent
from environment.world import World


class AgentFactory:
    @staticmethod
    def create_agents(
        world: World,
        count: int,
        vision_radius: int,
        preferred_position: tuple[int, int] | None = None,
        seed: int | None = None,
    ) -> list[Agent]:
        if count < 1:
            raise ValueError("A quantidade de agentes deve ser positiva.")
        if vision_radius < 0:
            raise ValueError("O raio de visão não pode ser negativo.")

        available = [
            (cell.x, cell.y)
            for row in world.grid
            for cell in row
            if cell.resource is None and cell.obstacle is None
        ]
        available.sort(key=lambda position: (position[1], position[0]))

        positions: list[tuple[int, int]] = []
        if preferred_position in available:
            positions.append(preferred_position)
            available.remove(preferred_position)

        remaining = count - len(positions)
        if remaining > len(available):
            raise ValueError(
                f"Não há células vazias suficientes para criar {count} agentes."
            )

        position_rng = random.Random(seed)
        positions.extend(position_rng.sample(available, remaining))

        agents = []
        for index, (x, y) in enumerate(positions):
            agent_seed = None if seed is None else seed + 1_000_003 * (index + 1)
            agents.append(
                Agent(
                    x=x,
                    y=y,
                    vision_radius=vision_radius,
                    rng=Random(agent_seed) if agent_seed is not None else None,
                )
            )
        return agents
