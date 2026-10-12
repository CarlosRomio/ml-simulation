"""Loop principal da interface Pygame.

A coordenação de eventos permanece aqui nesta primeira etapa. O desenho foi
extraído para renderizadores independentes para preparar a câmera e múltiplos
agentes sem reescrever a renderização do mundo.
"""

import pygame

from simulation.simulation import Simulation
from visualization.camera import Camera
from visualization.rendering_config import (
    BACKGROUND,
    BASE_SPEED,
    GRID_PADDING,
    MAX_CELL_SIZE,
    MAX_GRID_SIZE,
    MIN_CELL_SIZE,
    SIDEBAR_WIDTH,
    SPEED_MULTIPLIERS,
    VIEW_HEIGHT,
    VIEW_WIDTH,
)
from visualization.renderers.agent_renderer import AgentRenderer
from visualization.renderers.sidebar_renderer import SidebarRenderer
from visualization.renderers.world_renderer import WorldRenderer


def run(simulation: Simulation) -> None:
    pygame.init()
    world = simulation.world

    view_width = min(VIEW_WIDTH, world.width)
    view_height = min(VIEW_HEIGHT, world.height)
    cell_size = min(
        MAX_CELL_SIZE,
        MAX_GRID_SIZE // view_width,
        MAX_GRID_SIZE // view_height,
    )
    cell_size = max(MIN_CELL_SIZE, cell_size)

    grid_width = view_width * cell_size
    grid_height = view_height * cell_size
    grid_x = SIDEBAR_WIDTH + GRID_PADDING * 2
    grid_y = GRID_PADDING
    window_width = grid_x + grid_width + GRID_PADDING
    window_height = max(grid_height + GRID_PADDING * 2, 680)

    screen = pygame.display.set_mode((window_width, window_height))
    pygame.display.set_caption("ML Simulation - Survival")
    clock = pygame.time.Clock()

    world_renderer = WorldRenderer()
    agent_renderer = AgentRenderer()
    sidebar_renderer = SidebarRenderer()
    camera = Camera(world.width, world.height, view_width, view_height)
    camera.configure_viewport(grid_width, grid_height, cell_size)
    grid_viewport = pygame.Rect(grid_x, grid_y, grid_width, grid_height)
    dragging_camera = False
    last_mouse_position: tuple[int, int] | None = None

    running = True
    paused = False
    accumulated_time = 0.0
    simulation_speed = 1

    while running:
        elapsed_ms = clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if grid_viewport.collidepoint(event.pos):
                    dragging_camera = True
                    last_mouse_position = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging_camera = False
                last_mouse_position = None
            elif event.type == pygame.MOUSEWHEEL:
                mouse_position = pygame.mouse.get_pos()
                if grid_viewport.collidepoint(mouse_position):
                    zoom_step = 3 if event.y > 0 else -3
                    new_cell_size = max(
                        MIN_CELL_SIZE,
                        min(MAX_CELL_SIZE, camera.cell_size + zoom_step),
                    )
                    if new_cell_size != camera.cell_size:
                        camera.zoom_at(
                            mouse_position[0],
                            mouse_position[1],
                            grid_x,
                            grid_y,
                            new_cell_size,
                        )
            elif event.type == pygame.MOUSEMOTION and dragging_camera:
                if last_mouse_position is not None:
                    dx = event.pos[0] - last_mouse_position[0]
                    dy = event.pos[1] - last_mouse_position[1]
                    camera.pan_pixels(dx, dy)
                last_mouse_position = event.pos
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE and simulation.agent.alive:
                    paused = not paused
                elif event.key == pygame.K_1:
                    simulation_speed = 1
                elif event.key == pygame.K_2:
                    simulation_speed = 2
                elif event.key == pygame.K_3:
                    simulation_speed = 3

        effective_speed = BASE_SPEED * SPEED_MULTIPLIERS[simulation_speed]
        if not paused and simulation.agent.alive:
            accumulated_time += elapsed_ms * effective_speed
            while accumulated_time >= 1000:
                simulation.step()
                accumulated_time -= 1000
                if not simulation.agent.alive:
                    accumulated_time = 0.0
                    break

        screen.fill(BACKGROUND)
        agent = simulation.agent

        # A câmera é independente da posição do agente e se move por arraste.
        camera_x = camera.x
        camera_y = camera.y
        cell_size = camera.cell_size
        visible_world_width = camera.visible_width
        visible_world_height = camera.visible_height

        visible_cells = simulation.perception.observe(
            world, agent.x, agent.y, radius=agent.vision_radius
        )
        visible_positions = {(cell.x, cell.y) for cell in visible_cells}
        plant_counts = world.get_plant_counts()

        sidebar_renderer.draw(
            screen,
            simulation,
            window_height=window_height,
            paused=paused,
            effective_speed=effective_speed,
            plant_counts=plant_counts,
        )
        world_renderer.draw(
            screen,
            world,
            camera_x=camera_x,
            camera_y=camera_y,
            view_width=visible_world_width,
            view_height=visible_world_height,
            cell_size=cell_size,
            grid_x=grid_x,
            grid_y=grid_y,
            viewport_width_px=grid_width,
            viewport_height_px=grid_height,
            visible_positions=visible_positions,
        )
        previous_clip = screen.get_clip()
        screen.set_clip(grid_viewport)
        try:
            agent_renderer.draw(
                screen,
                agent,
                camera_x=camera_x,
                camera_y=camera_y,
                cell_size=cell_size,
                grid_x=grid_x,
                grid_y=grid_y,
            )
        finally:
            screen.set_clip(previous_clip)
        pygame.display.flip()

    pygame.quit()
