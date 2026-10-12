"""Regression test for the Pygame sidebar renderer."""

import pytest

pygame = pytest.importorskip("pygame")

from agents.agent import Agent
from environment.world import World
from simulation.simulation import Simulation
from visualization.renderers.sidebar_renderer import SidebarRenderer
from visualization.rendering_config import SIDEBAR_WIDTH


def test_sidebar_draw_renders_all_physiology_bars_without_argument_errors():
    """The full draw path must pass both bar color and y position."""
    pygame.font.init()
    try:
        world = World(width=10, height=10, food_count=8, water_count=2)
        agent = Agent(x=5, y=5)
        simulation = Simulation(world, agent)
        screen = pygame.Surface((SIDEBAR_WIDTH, 900))
        renderer = SidebarRenderer()

        renderer.draw(
            screen,
            simulation,
            window_height=900,
            paused=False,
            effective_speed=1.0,
            plant_counts=world.get_plant_counts(),
        )

        assert renderer.max_scroll >= 0
    finally:
        pygame.font.quit()
