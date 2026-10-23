"""Criação reproduzível de populações de agentes em um mundo existente."""

import random
from random import Random

from agents.agent import Agent
from agents.needs import AgentNeeds
from agents.species import Species
from agents.attributes import IndividualAttributes, IndividualGenotype
from agents.cognition import Personality
from configuration.species_physiology import DEFAULT_HUNGER_PER_STEP, adjusted_hunger_rate
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
        hunger_per_step: float = DEFAULT_HUNGER_PER_STEP[Species.HUMAN],
        starvation_threshold: float = 90.0,
        starvation_damage_per_step: float | None = None,
        attribute_variation: float = 0.12,
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
            attributes_rng = random.Random(None if agent_seed is None else agent_seed + 531_771)
            genotype = IndividualGenotype.species_founder(
                Species.HUMAN, attributes_rng, variation=attribute_variation
            )
            attributes = genotype.express()
            constitution_scale = attributes.relative_multiplier(Species.HUMAN, "constitution")
            endurance_scale = attributes.relative_multiplier(Species.HUMAN, "endurance")
            needs = AgentNeeds(
                max_health=100.0 * constitution_scale,
                health=100.0 * constitution_scale,
                max_energy=100.0 * endurance_scale,
                energy=100.0 * endurance_scale,
                # A eficiência metabólica hereditária reduz ou aumenta o consumo basal.
                # O valor de configuração representa o perfil médio da espécie.
                hunger_per_step=adjusted_hunger_rate(
                    needs_template.hunger_per_step, Species.HUMAN, attributes
                ),
                thirst_per_step=needs_template.thirst_per_step,
                starvation_threshold=needs_template.starvation_threshold,
                dehydration_threshold=needs_template.dehydration_threshold,
                starvation_damage_per_step=needs_template.starvation_damage_per_step,
                dehydration_damage_per_step=needs_template.dehydration_damage_per_step,
            )
            # Traços de personalidade reproduzíveis e independentes do RNG
            # utilizado para posicionamento e decisões durante a simulação.
            sociability_rng = random.Random(None if agent_seed is None else agent_seed + 91_827)
            sociability = sociability_rng.uniform(0.15, 0.95)
            personality_rng = random.Random(None if agent_seed is None else agent_seed + 281_441)
            personality = Personality.randomized(personality_rng, sociability=sociability)
            agents.append(
                Agent(
                    x=x,
                    y=y,
                    vision_radius=vision_radius,
                    rng=Random(agent_seed) if agent_seed is not None else None,
                    needs=needs,
                    species=species,
                    personality=personality,
                    attributes=attributes,
                    genotype=genotype,
                    agent_id=f"H{index + 1:03d}",
                )
            )
        return agents
