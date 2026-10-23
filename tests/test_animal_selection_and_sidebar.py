"""Regression tests for observing non-human individuals in the simulation UI."""
import pytest

pygame = pytest.importorskip("pygame")

from agents.agent import Agent
from animals.carnivore import Carnivore
from animals.herbivore import Herbivore
from environment.world import World
from simulation.simulation import Simulation
from visualization.renderers.sidebar_renderer import SidebarRenderer
from visualization.rendering_config import SIDEBAR_WIDTH


@pytest.mark.parametrize("animal_type,expected_section", [
    (Herbivore, "HERBÍVORO"),
    (Carnivore, "CARNÍVORO"),
])
def test_sidebar_builds_individual_physiology_genetics_and_lifecycle_for_animals(animal_type, expected_section):
    pygame.font.init()
    try:
        world = World(width=12, height=12, food_count=0, obstacle_count=0, water_count=0)
        animal = animal_type(5, 5)
        simulation = Simulation(world, agents=[Agent(1, 1)], herbivores=[animal] if animal_type is Herbivore else [],
                               carnivores=[animal] if animal_type is Carnivore else [], seed_spawn_count=0)
        simulation.observed_individual = animal
        renderer = SidebarRenderer()
        rows = renderer._build_rows(simulation, animal, 1.0, world.get_plant_counts())
        labels = [row[1] for row in rows if row[0] in {"section", "row", "bar"}]

        assert any(expected_section in label for label in labels)
        assert "CICLO DE VIDA / REPRODUÇÃO" in labels
        assert "FENÓTIPO" in labels
        assert "GENÓTIPO" in labels
        assert "Fome" in labels
        assert "Sede" in labels
    finally:
        pygame.font.quit()
