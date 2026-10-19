"""Criação reproduzível de populações de agentes em um mundo existente."""

import random
from random import Random

from agents.agent import Agent
from agents.needs import AgentNeeds
from agents.species import Species
from environment.world import World


class AgentFactory:
    @staticmethod
    def create_agents(
        world: World,
        count: int,
        vision_radius: int,
        preferred_position: tuple[int, int] | None = None,
        seed: int | None = None,
        species: Species = Species.HUMAN,
        thirst_per_step: float = 0.2,
        dehydration_threshold: float = 90.0,
        dehydration_damage_per_step: float | None = None,
        hunger_per_step: float = 0.25,
        starvation_threshold: float = 90.0,
        starvation_damage_per_step: float | None = None,
    ) -> list[Agent]:
        """Cria agentes com espécie e parâmetros fisiológicos configuráveis.

        Os parâmetros novos têm defaults equivalentes ao comportamento anterior,
        preservando chamadas existentes a create_agents.
        """
        if count < 1:
            raise ValueError("A quantidade de agentes deve ser positiva.")
        if vision_radius < 0:
            raise ValueError("O raio de visão não pode ser negativo.")

        if Species(species) is not Species.HUMAN:
            raise ValueError("AgentFactory cria agentes humanos; use HerbivoreFactory para animais.")

        # AgentNeeds valida os parâmetros fisiológicos, inclusive valores negativos.
        needs_template = AgentNeeds(
            hunger_per_step=hunger_per_step,
            thirst_per_step=thirst_per_step,
            starvation_threshold=starvation_threshold,
            dehydration_threshold=dehydration_threshold,
            starvation_damage_per_step=starvation_damage_per_step,
            dehydration_damage_per_step=dehydration_damage_per_step,
        )

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
            needs = AgentNeeds(
                hunger_per_step=needs_template.hunger_per_step,
                thirst_per_step=needs_template.thirst_per_step,
                starvation_threshold=needs_template.starvation_threshold,
                dehydration_threshold=needs_template.dehydration_threshold,
                starvation_damage_per_step=needs_template.starvation_damage_per_step,
                dehydration_damage_per_step=needs_template.dehydration_damage_per_step,
            )
            # Personalidades reproduzíveis, geradas independentemente do RNG
            # usado para posicionamento e decisões de movimento.
            sociability_rng = random.Random(None if agent_seed is None else agent_seed + 91_827)
            sociability = sociability_rng.uniform(0.15, 0.95)
            agents.append(
                Agent(
                    x=x,
                    y=y,
                    vision_radius=vision_radius,
                    rng=Random(agent_seed) if agent_seed is not None else None,
                    needs=needs,
                    species=species,
                    sociability=sociability,
                    agent_id=f"H{index + 1:03d}",
                )
            )
        return agents
